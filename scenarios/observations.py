"""Secret and private-content checks, and measured resource observations.

The secret check scans the repository's own text for credential-shaped content
and for private requirement material that must never reach public Git. It
reports what it found; it does not redact or rewrite anything.

The resource observations are **measured**, not promised. This package states no
throughput or latency target: it records what one local run cost on the machine
that ran it, so a later comparison has a baseline.
"""
import re
import resource
import subprocess
import time
from pathlib import Path

#: Credential-shaped content that must never appear in the repository.
SECRET_PATTERNS = (
    ("private key block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("mnemonic marker", re.compile(r"(?i)\b(mnemonic|seed phrase)\b\s*[:=]")),
    ("api or access token", re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|secret[_-]?key)\b"
                                       r"\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{8,}")),
    ("bearer credential", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}")),
    ("password assignment", re.compile(r"(?i)\bpassword\b\s*[:=]\s*['\"]?\S{3,}")),
    ("hex private key", re.compile(r"(?i)\bprivate[_-]?key\b\s*[:=]\s*['\"]?0x[0-9a-f]{64}")),
    ("aws key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("ssh private marker", re.compile(r"\bssh-rsa\s+AAAA")),
)

#: Private material that belongs only in the authorized private locations.
PRIVATE_CONTENT_PATTERNS = (
    ("private requirements link", re.compile(r"drive\.google\.com/file/d/")),
    ("private requirements digest",
     re.compile(r"78081da95b9f698a9bdfa8fb5dbca38f687bd87331adb9ace7a0a24d9db87f70")),
    ("internal coordinator name", re.compile(r"熊安")),
    ("non-english prose in source", None),  # handled separately, per file
)

#: Scripts that carry actual prose in another language. Typography such as an
#: arrow or a dash is not non-English prose, so only these ranges are flagged.
NON_ENGLISH_PROSE = re.compile(
    r"[\u2e80-\u9fff\uac00-\ud7af\u0400-\u04ff\u0590-\u05ff\u0600-\u06ff\u3040-\u30ff]")

#: Files whose own job is to describe these patterns, so a literal match inside
#: them is the check itself rather than a leak.
SELF_DESCRIBING = ("scenarios/observations.py", "scenarios/tests/test_observations.py")

TEXT_SUFFIXES = (".py", ".md", ".yml", ".yaml", ".json", ".txt", ".cfg", ".toml", ".sh")


def _tracked(root):
    listed = subprocess.run(("git", "ls-files"), capture_output=True, text=True, cwd=root,
                            check=False)
    return [name for name in listed.stdout.split() if name.endswith(TEXT_SUFFIXES)]


def secret_scan(root="."):
    """T-39: credential-shaped content and private material in the repository."""
    base = Path(root)
    findings, scanned = [], 0
    for name in _tracked(root):
        target = base / name
        try:
            text = target.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as problem:
            findings.append({"path": name, "kind": "unreadable", "detail": str(problem)})
            continue
        scanned += 1
        self_describing = name in SELF_DESCRIBING
        for label, pattern in SECRET_PATTERNS:
            if self_describing:
                continue
            for match in pattern.finditer(text):
                findings.append({"path": name, "kind": "secret", "pattern": label,
                                 "line": text[:match.start()].count("\n") + 1})
        for label, pattern in PRIVATE_CONTENT_PATTERNS:
            if pattern is None or self_describing:
                continue
            for match in pattern.finditer(text):
                findings.append({"path": name, "kind": "private-content", "pattern": label,
                                 "line": text[:match.start()].count("\n") + 1})
        if not self_describing and name.endswith((".py", ".md", ".yml")):
            for number, line in enumerate(text.splitlines(), start=1):
                if NON_ENGLISH_PROSE.search(line):
                    findings.append({"path": name, "kind": "non-english",
                                     "pattern": "non-english prose in public source",
                                     "line": number})
    return {
        "schema": "8415ex-secret-scan/1",
        "cases": ["T-39"],
        "filesScanned": scanned,
        "findings": findings,
        "clean": findings == [],
        "scope": ("a pattern scan of this repository's tracked text; it is not a substitute "
                  "for an independent security review"),
    }


def measure(run):
    """T-40: what one local run actually cost. No target is implied.

    ``run`` is called once. The elapsed wall time, CPU time and peak resident
    size are recorded around it.
    """
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
