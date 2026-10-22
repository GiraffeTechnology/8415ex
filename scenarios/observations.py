"""Secret and private-content checks, and measured resource observations.

Both are fail-closed. A scan that could not enumerate its input, could not read
a file, or saw nothing at all is reported as a failure, never as a clean result:
"zero files, no findings" is the shape a silent breakage takes, so it is
refused.

The scan carries no private value of its own. Credential-shaped detection is
generic, and any private fingerprint to look for is supplied through the
input argument or environment variable at call time, never embedded in this public
source. There is no exemption for this file: the scanner's own source is
scanned on the same terms as everything else.

The resource observations are measured, not promised. No throughput or latency
target is set or implied.
"""
import ast
import json
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

#: Generic patterns for potentially sensitive content.
#: These are pattern shapes rather than actual values.
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

#: What this scan reads is decided by the bytes, not by the file name. A suffix
#: allow-list exempted exactly the names a credential is most likely to carry -
#: ``.env``, a Dockerfile, an extensionless key file - and reported the exemption
#: as an ordinary skip, so the scan stayed clean over a file nobody had read.
#: Anything that decodes as UTF-8 and carries no NUL byte is read; anything else
#: is binary, where a text pattern certifies nothing, and is reported as skipped
#: with that reason.
SCAN_BYTE_LIMIT = 8 * 1024 * 1024

#: The environment variable through which callers may
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


def _read_text(target):
    """The file's text, or the reason it was not read.

    Exactly one of the two is returned. A file that does not decode as UTF-8,
    or that carries a NUL byte, is binary: reading a text pattern over it
    certifies nothing, so it is skipped with that reason. A file too large to
    read in full is kept apart from that, because it is a gap in coverage
    rather than a file with no text in it.
    """
    try:
        size = target.stat().st_size
    except OSError as problem:
        return None, {"kind": "unreadable", "reason": "unreadable: %s" % problem}
    if size > SCAN_BYTE_LIMIT:
        return None, {"kind": "notReadInFull",
                      "reason": "%d bytes exceeds the %d byte scan limit, so the "
                                "file was not read" % (size, SCAN_BYTE_LIMIT)}
    try:
        data = target.read_bytes()
    except OSError as problem:
        return None, {"kind": "unreadable", "reason": "unreadable: %s" % problem}
    if b"\x00" in data:
        return None, {"kind": "skipped",
                      "reason": "binary: the file carries a NUL byte"}
    try:
        return data.decode("utf-8"), None
    except UnicodeDecodeError as problem:
        return None, {"kind": "skipped",
                      "reason": "binary: not valid utf-8 (%s)" % problem.reason}


def _private_markers(supplied=None):
    'Fingerprints supplied as input or through the environment variable.'
    if supplied is not None:
        return tuple(str(marker) for marker in supplied if str(marker).strip())
    raw = os.environ.get(PRIVATE_MARKER_ENV, "")
    return tuple(marker.strip() for marker in raw.split(",") if marker.strip())


#: What this scan is, said plainly, and what it is not. A pattern scan over the
#: tracked text of one checkout is bounded evidence, and saying so is part of
#: the result rather than a footnote somewhere else.
def coverage_statement(coverage, marker_count, enumeration_state):
    """A statement of exactly how far this scan reached."""
    enumerated = coverage["enumerated"]
    scanned = coverage["scanned"]
    skipped = len(coverage["skipped"])
    unreadable = len(coverage["unreadable"])
    partial = len(coverage["notReadInFull"])
    return {
        "inventoryTotal": enumerated,
        "scannedCount": scanned,
        "skippedCount": skipped,
        "unreadableCount": unreadable,
        "notReadInFullCount": partial,
        "accountedFor": scanned + skipped + unreadable + partial == enumerated,
        "enumerationState": enumeration_state,
        "suppliedPrivateMarkers": marker_count,
        "boundedCoverage": (
            f"{scanned} of {enumerated} tracked files were read; {skipped} were "
            f"skipped as binary with a recorded reason, {unreadable} were "
            f"unreadable and {partial} were too large to read in full"),
        "isNot": [
            "not a private-fingerprint certification: "
            + ("no private markers were supplied, so detection was generic only"
               if marker_count == 0 else
               f"{marker_count} supplied markers were checked, which certifies "
               "nothing beyond those exact values"),
            "not a historical-repository certification: only this checkout's "
            "tracked text was read, not any earlier commit",
            "not an independent security review",
        ],
    }



# Translation values are product data. The file is still fully read and all
# credential/private-content checks use its original bytes. This language view
# changes only proven data literals in the two display-resource entry points.
DISPLAY_LOCALES = frozenset(("en", "zh-Hans", "zh-Hant", "fr", "es", "ja"))
_LOCALE_TOKEN = re.compile(
    r"(?P<space>\s+)|(?P<string>'(?:\\.|[^'\\\r\n])*'|\"(?:\\.|[^\"\\\r\n])*\")"
    r"|(?P<word>[A-Za-z_$][A-Za-z0-9_$]*)|(?P<symbol>[{}\[\]:,])")


# Only literal product display resources are language data. Credential and
# private-content scanning still uses every original byte, including literals.
PYTHON_DISPLAY_TABLES = {
    "exchange/collateral_scenario.py": ("WORDS",),
    "exchange/authorization_page.py": ("TEXT",),
    "exchange/evidence_page.py": ("_TEXT", "LANGUAGES", "UNVERIFIED"),
    "exchange/gap_projection.py": ("GAP_LABELS",),
    "exchange/gas_disclosure_locales.py": ("WORDS", "TRANSPORT", "AVAILABILITY", "BUDGET_OBSERVATION"),
    "exchange/market_page.py": ("BASE_UNITS", "WORDS", "STATES", "EMPTY_MODE"),
    "exchange/nft_detail_page.py": ("LOCALES", "QUOTE_LABELS"),
    "exchange/queue_status_page.py": ("TEXT", "CONTROL_TEXT", "WINDOW_TEXT"),
    "exchange/reference_provenance_page.py": ("LABELS", "VALUES", "EVIDENCE_LABELS"),
    "exchange/register_projection_page.py": ("BLOCK_TIME", "LABELS"),
    "exchange/registration_source_locales.py": ("WORDS",),
    "exchange/remint_draft_workbench.py": ("WORDS",),
    "exchange/remint_review.py": ("WORDS",),
    "exchange/remint_history_workbench.py": ("WORDS",),
    "exchange/remint_receipt_workbench.py": ("WORDS",),
    "exchange/rollback_page.py": ("TEXT", "HISTORY"),
    "exchange/settlement_record_page.py": ("TEXT",),
    "exchange/timeline_page.py": ("TEXT", "SIMULATION"),
}


def _python_display_spans(name, text):
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []
    lines = text.splitlines(keepends=True)
    starts, total = [], 0
    for line in lines:
        starts.append(total)
        total += len(line)

    def offset(line, column):
        prefix = lines[line - 1].encode("utf-8")[:column].decode("utf-8")
        return starts[line - 1] + len(prefix)

    def display_values(value):
        if isinstance(value, str):
            return True
        if isinstance(value, (tuple, list)):
            return bool(value) and all(display_values(item) for item in value)
        if isinstance(value, dict):
            return bool(value) and all(isinstance(key, str) and key.isascii()
                                       and display_values(item) for key, item in value.items())
        return False

    spans = []
    for statement in tree.body:
        if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
            continue
        target = statement.targets[0]
        if not isinstance(target, ast.Name) or target.id not in PYTHON_DISPLAY_TABLES[name]:
            continue
        try:
            value = ast.literal_eval(statement.value)
            if target.id == "LANGUAGES":
                valid = (isinstance(value, (tuple, list)) and len(value) == len(DISPLAY_LOCALES)
                         and all(isinstance(pair, tuple) and len(pair) == 2
                                 and isinstance(pair[0], str) and isinstance(pair[1], str) for pair in value)
                         and {pair[0] for pair in value} == DISPLAY_LOCALES)
            else:
                valid = (isinstance(value, dict) and set(value) == DISPLAY_LOCALES
                         and all(display_values(item) for item in value.values()))
            if not valid:
                continue
            for node in ast.walk(statement.value):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    spans.append((offset(node.lineno, node.col_offset),
                                  offset(node.end_lineno, node.end_col_offset)))
        except (ValueError, TypeError, UnicodeError):
            continue
    return spans


def _localized_language_view(name, text):
    spans = []
    if name == "ui/commodity-market/locales.js":
        wrapper = re.fullmatch(
            r"\s*'use strict';\s*window\.EX_LOCALES\s*=\s*(\{[\s\S]*\});\s*",
            text)
        if wrapper is None:
            return text
        body, offset = wrapper.group(1), wrapper.start(1)
        tokens, cursor = [], 0
        while cursor < len(body):
            token = _LOCALE_TOKEN.match(body, cursor)
            if token is None:
                return text
            if token.lastgroup != "space":
                tokens.append(token)
            cursor = token.end()
        encoded = []
        try:
            for index, token in enumerate(tokens):
                following = tokens[index + 1].group() if index + 1 < len(tokens) else ""
                if token.lastgroup == "word":
                    if following != ":":
                        return text
                    encoded.append(json.dumps(token.group()))
                elif token.lastgroup == "string":
                    value = ast.literal_eval(token.group())
                    encoded.append(json.dumps(value))
                    if following != ":":
                        spans.append((offset + token.start() + 1,
                                      offset + token.end() - 1))
                else:
                    encoded.append(token.group())
            def unique_object(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("duplicate translation key")
                    result[key] = value
                return result
            locales = json.loads("".join(encoded), object_pairs_hook=unique_object)
        except (SyntaxError, ValueError, TypeError):
            return text
        if not isinstance(locales, dict) or set(locales) != DISPLAY_LOCALES:
            return text
        for values in locales.values():
            if not isinstance(values, dict) or not values:
                return text
            for key, value in values.items():
                if not key.isascii() or not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", key):
                    return text
                if not (isinstance(value, str) or
                        isinstance(value, list) and all(isinstance(item, str) for item in value)):
                    return text
    elif name == "ui/commodity-market/index.html":
        for select in re.finditer(
                r"<select\b(?=[^>]*\bid=(['\"])language\1)[^>]*>([\s\S]*?)</select>",
                text):
            for option in re.finditer(
                    r"<option\s+value=(['\"])([^'\"]+)\1\s*>([^<>]*)</option>",
                    select.group(2)):
                if option.group(2) in DISPLAY_LOCALES:
                    spans.append((select.start(2) + option.start(3),
                                  select.start(2) + option.end(3)))
    elif name in PYTHON_DISPLAY_TABLES:
        spans = _python_display_spans(name, text)
    else:
        return text
    view = list(text)
    for start, end in spans:
        view[start:end] = ["\n" if character == "\n" else " "
                           for character in view[start:end]]
    return "".join(view)


def secret_scan(root=".", private_markers=None):
    """T-39: credential-shaped content and private material in the source.

    Fails closed. ``clean`` is true only when enumeration succeeded, at least
    one file was read, nothing was unreadable, and no pattern matched.
    """
    enumeration = tracked_files(root)
    markers = _private_markers(private_markers)
    if not enumeration["ok"]:
        return {
            "schema": "8415ex-secret-scan/4", "cases": ["T-39"], "ok": False,
            "enumerationState": enumeration["state"], "error": enumeration["error"],
            "coverage": {"enumerated": 0, "scanned": 0, "skipped": [],
                         "unreadable": [], "notReadInFull": []},
            "coverageStatement": coverage_statement(
                {"enumerated": 0, "scanned": 0, "skipped": [], "unreadable": [],
                 "notReadInFull": []},
                len(markers), enumeration["state"]),
            "findings": [], "clean": False,
            "privateMarkerCount": len(markers),
            "scope": "the source file list could not be established, so nothing is certified",
        }
    base = Path(root)
    findings, skipped, unreadable, partial, scanned = [], [], [], [], 0
    buckets = {"skipped": skipped, "unreadable": unreadable, "notReadInFull": partial}
    for name in enumeration["files"]:
        target = base / name
        if not target.is_file():
            unreadable.append({"path": name, "reason": "tracked but missing from the worktree"})
            continue
        text, refusal = _read_text(target)
        if refusal is not None:
            buckets[refusal["kind"]].append({"path": name, "reason": refusal["reason"]})
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
        # Technical prose is checked in every file read. Only recognized
        # display-translation values and native language-selector labels are
        # classified as localized UI data; secret checks above keep the full text.
        language_view = _localized_language_view(name, text)
        for number, line in enumerate(language_view.splitlines(), start=1):
            if NON_ENGLISH_PROSE.search(line):
                findings.append({"path": name, "kind": "non-english",
                                 "pattern": "non-english prose in public source",
                                 "line": number})
    # A file that was not read in full is a hole in the coverage, so it refuses
    # a clean result in the same way an unreadable file does. A binary file is
    # not: there is no text in it for a text pattern to certify.
    clean = (findings == [] and scanned > 0 and unreadable == [] and partial == [])
    coverage = {"enumerated": len(enumeration["files"]), "scanned": scanned,
                "skipped": skipped, "unreadable": unreadable,
                "notReadInFull": partial,
                "textDecidedBy": ("content: read when it decodes as utf-8 and "
                                  "carries no NUL byte, never by file name"),
                "byteLimit": SCAN_BYTE_LIMIT}
    return {
        "schema": "8415ex-secret-scan/4", "cases": ["T-39"], "ok": True,
        "enumerationState": enumeration["state"], "error": None,
        "coverage": coverage,
        "coverageStatement": coverage_statement(coverage, len(markers),
                                                enumeration["state"]),
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


#: Step facts that measure a backlog. ``outstandingLegs`` is how many legs are
#: still unresolved; ``deferredLegs`` is how many registration results are
#: buffered waiting for a gap. Both are read from the facts the scenarios
#: already record, so nothing is instrumented specially for this.
BACKLOG_FACTS = ("outstandingLegs", "deferredLegs")


def _rate(part, whole):
    """A rate in parts per thousand, as an integer. No floating point appears
    anywhere in these records, and a rate over nothing is reported as None
    rather than as zero: zero would read as a measurement."""
    if not whole:
        return None
    return (part * 1000 + whole // 2) // whole


def _backlog(report):
    """The highest backlog each scenario reached, from the facts it recorded.

    A backlog is read as a count, never as a failure: a deferred result waiting
    for a gap is the normal serial-registration state, and an outstanding leg is
    work in flight.

    The second figure is the *last recorded* value, not the end state. A
    scenario stops recording a fact once it is no longer what a step is about,
    so a non-zero last value means the scenario stopped mentioning the backlog,
    not necessarily that it ended with one. Calling it final would be the kind
    of small overstatement that a reader then builds on.
    """
    observed = {}
    for scenario in report["scenarios"]:
        for fact in BACKLOG_FACTS:
            seen = [step["facts"][fact] for step in scenario["steps"]
                    if isinstance(step["facts"].get(fact), (int, list))
                    and not isinstance(step["facts"].get(fact), bool)]
            counts = [value if isinstance(value, int) else len(value) for value in seen]
            if not counts:
                continue
            entry = observed.setdefault(fact, {"observedIn": [], "peak": 0,
                                               "lastRecordedByScenario": {},
                                               "lastRecordedStepByScenario": {}})
            entry["observedIn"].append(scenario["scenarioId"])
            entry["peak"] = max(entry["peak"], max(counts))
            entry["lastRecordedByScenario"][scenario["scenarioId"]] = counts[-1]
            entry["lastRecordedStepByScenario"][scenario["scenarioId"]] = max(
                step["index"] for step in scenario["steps"]
                if fact in step["facts"])
    for fact, entry in observed.items():
        entry["observedIn"] = sorted(set(entry["observedIn"]))
        entry["clearedWhereLastRecorded"] = sorted(
            scenario for scenario, value
            in entry["lastRecordedByScenario"].items() if value == 0)
        entry["stillCountedWhenLastRecorded"] = sorted(
            scenario for scenario, value
            in entry["lastRecordedByScenario"].items() if value != 0)
        entry["lastRecordedIsNotTheEndState"] = True
    return {fact: observed.get(fact) for fact in BACKLOG_FACTS}


def workload_observation(report):
    """T-40: the load that produced a report, its backlog and its rates.

    EX-NFR-08 asks for a recorded test load, execution time, queue backlog and
    failure rate before any throughput or latency figure is spoken about, and
    these are those four. Two things are kept strictly apart. A ``not-run``
    obligation is not a failure, so it has its own rate and is excluded from the
    failure rate; counting it as a failure would make an honest outstanding duty
    look like a defect. And none of this is a target: one observation on one
    machine is a load record, not a baseline distribution and not an SLA.
    """
    expectations = sum(len(scenario["expectations"]) for scenario in report["scenarios"])
    steps = sum(len(scenario["steps"]) for scenario in report["scenarios"])
    totals = report["totals"]
    recorded = sum(totals.get(outcome, 0) for outcome in
                   ("passed", "failed", "blocked", "not-run"))
    elapsed = [scenario["elapsedMs"] for scenario in report["scenarios"]]
    return {
        "scenarios": report["scenariosTotal"],
        "recordedExpectations": expectations,
        "recordedSteps": steps,
        "outcomeTotals": totals,
        "slowestScenarioMs": max(elapsed, default=0),
        "totalScenarioMs": sum(elapsed),
        "ratesPerThousand": {
            "passed": _rate(totals.get("passed", 0), recorded),
            "failed": _rate(totals.get("failed", 0), recorded),
            "blocked": _rate(totals.get("blocked", 0), recorded),
            "notRun": _rate(totals.get("not-run", 0), recorded),
        },
        "rateDenominator": recorded,
        "failureRateExcludesNotRun": True,
        "backlog": _backlog(report),
        "isNot": [
            "not a service level: one observation on one machine is a load "
            "record, never a throughput or latency target",
            "not a defect count: a not-run obligation has its own rate and is "
            "excluded from the failure rate",
            "not a backlog problem: a deferred result waiting for a gap is the "
            "normal serial-registration state",
        ],
    }
