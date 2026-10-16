"""The storyboard, checked against the code it describes.

A presentation outline is the part of a delivery most likely to go stale and
least likely to be noticed doing it. A scenario can change route, a case can
stop owing real evidence, a panel can quietly describe a scenario that no longer
exists, and nothing fails: the document just becomes wrong while still reading
as authoritative.

So the outline is parsed and checked. Every panel must name a scenario that
exists and the route that scenario really runs, all six must appear exactly
once, and every case in a panel's "still owed" column must be a real case that
genuinely still owes real evidence. A panel claiming something is owed that is
not, or owed by a case that does not exist, is a finding.

The checks are deliberately one-directional about wording. They verify the
identifiers, the routes and the obligations, and say nothing about the prose:
the prose is for a person to write, and a test that policed it would be a test
nobody could change the document past.
"""
import pathlib
import re

from . import matrix
from .demos import MAIN_PATHS

STORYBOARD = "scenarios/STORYBOARD.md"

#: The sections this module reads, by their heading.
PANEL_SECTION = "## Per-scenario storyboard"
DECK_SECTION = "## Deck outline"
VIDEO_SECTION = "## Video outline"

#: A panel's scenario cell: the scenario id and the route it is shown on.
PANEL_SCENARIO = re.compile(r"\A(DEMO-\d\d), route ([A-Z_]+)\Z")

#: A case identifier anywhere in a cell.
CASE = re.compile(r"\bT-\d\d\b")

#: Claims the outline must carry, because leaving one out is how a factual
#: outline becomes a misleading one. Each is matched as a phrase, not as an
#: exact sentence, so the prose around it stays the author's.
REQUIRED_CLAIMS = (
    {"claim": "the local run is labelled as a local model run",
     "phrase": "local model run"},
    {"claim": "a local run is not presented as a public test network result",
     "phrase": "may not present a local run as a public test network"},
    {"claim": "a rendered page is not presented as interface acceptance",
     "phrase": "may not present a rendered status page as operable interface"},
    {"claim": "no cooperation with a real counterparty is implied",
     "phrase": "may not imply cooperation"},
    {"claim": "the registration routes are named as simulated roles",
     "phrase": "simulated business roles"},
)


def _rows(lines):
    """The data rows of one markdown table, without its header or separator."""
    rows = []
    for line in lines:
        text = line.strip()
        if not text.startswith("|"):
            continue
        cells = [cell.strip() for cell in text.strip("|").split("|")]
        if all(set(cell) <= set("- :") and cell for cell in cells):
            continue
        rows.append(cells)
    return rows[1:] if rows else []


def _section(text, heading):
    """One section's lines, from its heading to the next one at the same level."""
    lines = text.splitlines()
    try:
        start = lines.index(heading)
    except ValueError:
        return None
    for position in range(start + 1, len(lines)):
        if lines[position].startswith("## "):
            return lines[start + 1:position]
    return lines[start + 1:]


def parse(root="."):
    """The outline's panels, deck slides and video segments, as written."""
    path = pathlib.Path(root) / STORYBOARD
    if not path.is_file():
        return {"readable": False, "error": "EX_STORYBOARD_UNREADABLE",
                "panels": [], "deckSlides": [], "videoSegments": [], "claims": []}
    text = path.read_text(encoding="utf-8")
    panels = []
    for cells in _rows(_section(text, PANEL_SECTION) or []):
        if len(cells) < 5:
            continue
        match = PANEL_SCENARIO.match(cells[1])
        panels.append({
            "panel": cells[0],
            "scenarioCell": cells[1],
            "scenarioId": match.group(1) if match else None,
            "route": match.group(2) if match else None,
            "shown": cells[2],
            "figureSource": cells[3],
            "stillOwed": cells[4],
            "owedCases": sorted(set(CASE.findall(cells[4]))),
        })
    segments = []
    for cells in _rows(_section(text, VIDEO_SECTION) or []):
        if len(cells) < 4:
            continue
        segments.append({"segment": cells[0], "length": cells[1],
                         "content": cells[2], "labelling": cells[3],
                         "scenarioIds": sorted(set(re.findall(r"DEMO-\d\d", cells[2])))})
    slides = [line.strip() for line in (_section(text, DECK_SECTION) or [])
              if re.match(r"\A\d+\. ", line.strip())]
    return {
        "readable": True, "error": None, "panels": panels,
        "deckSlides": slides, "videoSegments": segments,
        "claims": [dict(entry, present=entry["phrase"] in text)
                   for entry in REQUIRED_CLAIMS],
    }


def check(root="."):
    """Whether the outline still describes the code, with every finding named."""
    parsed = parse(root)
    findings = []
    if not parsed["readable"]:
        findings.append({"finding": "the outline could not be read",
                         "detail": parsed["error"]})
        return {"schema": "8415ex-storyboard-check/1", "parsed": parsed,
                "findings": findings, "consistent": False,
                "panelCount": 0, "scenariosShown": [], "isNot": []}

    owing = {row["case"] for case, row in
             ((row["case"], row) for row in _matrix_rows())
             if row["remainingRealEvidence"]}
    shown = [panel["scenarioId"] for panel in parsed["panels"]]
    for panel in parsed["panels"]:
        where = "panel %s" % panel["panel"]
        if panel["scenarioId"] is None:
            findings.append({"finding": "a panel does not name a scenario and a route",
                             "detail": "%s: %s" % (where, panel["scenarioCell"])})
            continue
        if panel["scenarioId"] not in MAIN_PATHS:
            findings.append({"finding": "a panel names a scenario that does not exist",
                             "detail": "%s: %s" % (where, panel["scenarioId"])})
            continue
        expected = MAIN_PATHS[panel["scenarioId"]]
        if panel["route"] != expected:
            findings.append({
                "finding": "a panel shows a scenario on the wrong route",
                "detail": "%s: %s runs on %s, the outline says %s"
                          % (where, panel["scenarioId"], expected, panel["route"])})
        if not panel["owedCases"]:
            findings.append({"finding": "a panel names nothing still owed",
                             "detail": where})
        for case in panel["owedCases"]:
            if case not in matrix.CASE_REQUIREMENTS:
                findings.append({"finding": "a panel owes a case that does not exist",
                                 "detail": "%s: %s" % (where, case)})
            elif case not in owing:
                findings.append({
                    "finding": "a panel says a case is still owed when it is not",
                    "detail": "%s: %s owes no remaining real evidence" % (where, case)})
    missing = sorted(set(MAIN_PATHS) - set(shown))
    if missing:
        findings.append({"finding": "a scenario has no panel",
                         "detail": ", ".join(missing)})
    repeated = sorted({scenario for scenario in shown
                       if scenario and shown.count(scenario) > 1})
    if repeated:
        findings.append({"finding": "a scenario has more than one panel",
                         "detail": ", ".join(repeated)})
    for segment in parsed["videoSegments"]:
        unknown = sorted(set(segment["scenarioIds"]) - set(MAIN_PATHS))
        if unknown:
            findings.append({"finding": "a video segment names a scenario that does not exist",
                             "detail": "%s: %s" % (segment["segment"], ", ".join(unknown))})
        if not segment["labelling"]:
            findings.append({"finding": "a video segment requires no on-screen labelling",
                             "detail": segment["segment"]})
    for claim in parsed["claims"]:
        if not claim["present"]:
            findings.append({"finding": "the outline no longer carries a required claim",
                             "detail": claim["claim"]})
    return {
        "schema": "8415ex-storyboard-check/1",
        "parsed": parsed,
        "panelCount": len(parsed["panels"]),
        "scenariosShown": sorted(entry for entry in shown if entry),
        "deckSlideCount": len(parsed["deckSlides"]),
        "videoSegmentCount": len(parsed["videoSegments"]),
        "findings": findings,
        "findingCount": len(findings),
        "consistent": not findings,
        "isNot": [
            "not acceptance of the outline: this checks that it still describes "
            "the code, never that a demonstration, deck or video was produced",
            "not a review of the prose: the identifiers, routes and obligations "
            "are checked, and the wording stays the author's",
        ],
    }


def _matrix_rows():
    """The acceptance rows, for the remaining-evidence column only.

    Built without a run: the obligations are a property of the declared matrix,
    not of a particular execution, so nothing is executed to read them.
    """
    return matrix.build({"commit": None, "tree": None, "branch": None,
                         "worktreeClean": None}, {})["rows"]
