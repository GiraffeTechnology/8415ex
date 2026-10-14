"""Secret and private-content checks, and measured resource observations.

Both are fail-closed. A scan that could not enumerate its input, could not read
a file, or saw nothing at all is reported as a failure, never as a clean result:
"zero files, no findings" is the shape a silent breakage takes, so it is
refused.

The scan carries no private value of its own. Credential-shaped detection is
generic, and any private fingerprint to look for is supplied through the
already-approved private mechanism at call time, never embedded in this public
source. There is no exemption for this file: the scanner's own source is
scanned on the same terms as everything else.

The resource observations are measured, not promised. No throughput or latency
target is set or implied.
"""
import os
import re
import resource
import subprocess
import time
from pathlib import Path

#: Credential-shaped content. Each pattern names the shape it looks for and
#: carries no real credential, fingerprint or identifier.
SECRET_PATTERNS = (
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("mnemonic marker", re.compile(r"(?i)\b(mnemonic|seed phrase)\b\s*[:=]\s*\S")),
    ("api or access token", re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|secret[_-]?key)\b"
                                      r"\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{8,}")),
    ("bearer credential", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}")),
    ("password assignment", re.compile(r"(?i)\bpassword\b\s*[:=]\s*['\"]?[^\s'\"]{3,}")),
    ("hex private key", re.compile(r"(?i)\bprivate[_-]?key\b\s*[:=]\s*['\"]?0x[0-9a-f]{64}")),
    ("cloud access key id", re.compile(r"\b[A-Z]{4}[A-Z0-9]{16}\b")),
    ("ssh private marker", re.compile(r"\bssh-rsa\s+AAAA")),
)

#: Private material that belongs only in the authorized private locations. These
#: are shapes, not values: no private link, digest or name appears here.
PRIVATE_CONTENT_PATTERNS = (
    ("document sharing link", re.compile(r"(?i)\b(?:drive|docs)\.google\.com/\S+")),
    # A leading slash is not a word character, so ``\b`` would never match at
    # the start of a line; an explicit left-hand guard is required instead.
    ("internal operational path",
     re.compile(r"(?i)(?<![\w./-])(?:/srv|/opt/private|/mnt/private)/\S+")),
)

#: Scripts that carry prose in another language, as code-point ranges so this
#: public source stays ASCII. Typography such as an arrow or a dash is not
#: non-English prose, so only these ranges are flagged.
NON_ENGLISH_RANGES = (
    (0x2E80, 0x9FFF),   # CJK radicals through unified ideographs
    (0xAC00, 0xD7AF),   # Hangul syllables
    (0x0400, 0x04FF),   # Cyrillic
    (0x0590, 0x05FF),   # Hebrew
    (0x0600, 0x06FF),   # Arabic
    (0x3040, 0x30FF),   # Hiragana and Katakana
)
NON_ENGLISH_PROSE = re.compile(
    "[" + "".join(f"{chr(low)}-{chr(high)}" for low, high in NON_ENGLISH_RANGES) + "]")

#: Text this scan reads. Anything else is skipped and reported as skipped, with
#: its reason, rather than silently ignored.
TEXT_SUFFIXES = (".py", ".md", ".yml", ".yaml", ".json", ".txt", ".cfg", ".toml", ".sh")

#: The environment variable through which the approved private mechanism may
#: supply fingerprints to look for. Its contents are never written to this
#: source, to a report, or to any public artifact.
PRIVATE_MARKER_ENV = "EX_PRIVATE_CONTENT_MARKERS"


class EnumerationError(Exception):
    """Raised when the source file list could not be established."""


def tracked_files(root="."):
    """Every tracked path, enumerated NUL-delimited so spaces survive.

    Returns the paths and an explicit status. A non-repository, a failed Git
    invocation and a failed enumeration are distinguished from a genuinely empty
    repository; none of them is reported as a clean, empty source.
    """
    try:
        inside = subprocess.run(("git", "rev-parse", "--git-dir"), cwd=root,
                                capture_output=True, text=True, check=False)
    except OSError as problem:
        return {"ok": False, "state": "git-unavailable", "error": str(problem), "files": ()}
    if inside.returncode != 0:
        return {"ok": False, "state": "not-a-repository",
                "error": inside.stderr.strip() or "git rev-parse failed", "files": ()}
    try:
        listed = subprocess.run(("git", "ls-files", "-z"), cwd=root,
                                capture_output=True, check=False)
    except OSError as problem:
        return {"ok": False, "state": "git-unavailable", "error": str(problem), "files": ()}
    if listed.returncode != 0:
        return {"ok": False, "state": "enumeration-failed",
                "error": listed.stderr.decode("utf-8", "replace").strip()
                or "git ls-files failed", "files": ()}
    names = tuple(name for name in listed.stdout.decode("utf-8", "surrogateescape").split("\0")
                  if name)
    if not names:
        # A tracked-file list is never legitimately empty for this repository.
        # An empty result here means the lookup did not see the source.
        return {"ok": False, "state": "empty-enumeration",
                "error": "git reported no tracked files", "files": ()}
    return {"ok": True, "state": "enumerated", "error": None, "files": names}


def _private_markers(supplied=None):
    """Fingerprints to look for, from the approved private mechanism only."""
    if supplied is not None:
        return tuple(str(marker) for marker in supplied if str(marker).strip())
    raw = os.environ.get(PRIVATE_MARKER_ENV, "")
    return tuple(marker.strip() for marker in raw.split(",") if marker.strip())


def secret_scan(root=".", private_markers=None):
    """T-39: credential-shaped content and private material in the source.

    Fails closed. ``clean`` is true only when enumeration succeeded, at least
    one file was read, nothing was unreadable, and no pattern matched.
    """
    enumeration = tracked_files(root)
    markers = _private_markers(private_markers)
    if not enumeration["ok"]:
        return {
            "schema": "8415ex-secret-scan/2", "cases": ["T-39"], "ok": False,
            "enumerationState": enumeration["state"], "error": enumeration["error"],
            "coverage": {"enumerated": 0, "scanned": 0, "skipped": [], "unreadable": []},
            "findings": [], "clean": False,
            "privateMarkerCount": len(markers),
            "scope": "the source file list could not be established, so nothing is certified",
        }
    base = Path(root)
    findings, skipped, unreadable, scanned = [], [], [], 0
    for name in enumeration["files"]:
        target = base / name
        if not name.endswith(TEXT_SUFFIXES):
            skipped.append({"path": name, "reason": "not a scanned text suffix"})
            continue
        if not target.is_file():
            unreadable.append({"path": name, "reason": "tracked but missing from the worktree"})
            continue
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as problem:
            unreadable.append({"path": name, "reason": f"unreadable: {problem}"})
            continue
        scanned += 1
        for label, pattern in SECRET_PATTERNS + PRIVATE_CONTENT_PATTERNS:
            for match in pattern.finditer(text):
                findings.append({"path": name,
                                 "kind": "secret" if (label, pattern) in SECRET_PATTERNS
                                 else "private-content",
                                 "pattern": label,
                                 "line": text[:match.start()].count("\n") + 1})
        for marker in markers:
            index = text.find(marker)
            if index >= 0:
                # The marker itself is never echoed into the report.
                findings.append({"path": name, "kind": "private-content",
                                 "pattern": "configured private fingerprint",
                                 "line": text[:index].count("\n") + 1})
        if name.endswith((".py", ".md", ".yml")):
            for number, line in enumerate(text.splitlines(), start=1):
                if NON_ENGLISH_PROSE.search(line):
                    findings.append({"path": name, "kind": "non-english",
                                     "pattern": "non-english prose in public source",
                                     "line": number})
    clean = findings == [] and scanned > 0 and unreadable == []
    return {
        "schema": "8415ex-secret-scan/2", "cases": ["T-39"], "ok": True,
        "enumerationState": enumeration["state"], "error": None,
        "coverage": {"enumerated": len(enumeration["files"]), "scanned": scanned,
                     "skipped": skipped, "unreadable": unreadable,
                     "scannedSuffixes": list(TEXT_SUFFIXES)},
        "findings": findings, "clean": clean,
        "privateMarkerCount": len(markers),
        "scope": ("a pattern scan of this repository's tracked text, including this scanner's "
                  "own source; it is not a substitute for an independent security review"),
    }


def measure(run):
    """T-40: what one local run actually cost. No target is implied."""
    before = resource.getrusage(resource.RUSAGE_SELF)
    started = time.time()
    result = run()
    elapsed = time.time() - started
    after = resource.getrusage(resource.RUSAGE_SELF)
    return result, {
        "schema": "8415ex-resource-observation/1",
        "cases": ["T-40"],
        "elapsedMs": int(elapsed * 1000),
        "userCpuMs": int((after.ru_utime - before.ru_utime) * 1000),
        "systemCpuMs": int((after.ru_stime - before.ru_stime) * 1000),
        "peakResidentKib": after.ru_maxrss,
        "note": ("measured on the machine that ran it; no throughput or latency target is "
                 "set or implied, and a single observation is not a baseline distribution"),
    }


def workload_observation(report):
    """The size of the workload that produced a report, for later comparison."""
    expectations = sum(len(scenario["expectations"]) for scenario in report["scenarios"])
    steps = sum(len(scenario["steps"]) for scenario in report["scenarios"])
    return {
        "scenarios": report["scenariosTotal"],
        "recordedExpectations": expectations,
        "recordedSteps": steps,
        "outcomeTotals": report["totals"],
        "slowestScenarioMs": max((scenario["elapsedMs"] for scenario in report["scenarios"]),
                                 default=0),
    }
