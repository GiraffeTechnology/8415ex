"""Section by section: what in this repository addresses each requirement area.

The acceptance matrix answers one axis and the stage map another. Neither
answers the question that matters when a whole requirements document has been
assigned at once: is any section of it addressed by nothing at all?

That gap is easy to miss precisely because the other two reports look complete.
Every declared requirement can have a case, and every stage can have
deliverables, while a whole section of the document has quietly been skipped -
because a section that produced no requirement identifier and no stage entry
appears in neither report.

So each section is listed with what addresses it: the requirement families whose
identifiers it carries, the modules and reports built for it, and, where it is
not this surface's to carry, the owner it belongs to. A section with no
requirement family, no deliverable and no owner is a finding. Every path is
checked against the disk and every requirement family against the declared
requirements, so a label cannot stand in for something that is not there.

Sections are identified by number and by a short engineering label describing
what this repository does about them. The requirements document itself is
private and none of its text is reproduced here.

A section was called addressed when its deliverable paths existed, which is a
different question from whether anything establishes it. Two sections read as
addressed while the evidence behind them was not a local result at all: one
whose three requirements are all awaiting real network execution, and one
carrying a not-run obligation beside two requirements evidenced only by test
suites. The paths existed, so the ledger said addressed, and the page a reviewer
reads to ask "is the document covered?" answered with file existence.

So the evidence axis is read from the acceptance matrix and reported beside the
deliverables: which cases back each section, their recorded outcomes, the
weakest of them, and - where that is not a pass - what is still owed and by
whom. A section whose weakness is accounted for is reported as awaiting that
evidence, which is not a defect. A section whose weakness is accounted for by
nothing is a finding. Without a matrix the evidence is reported as not supplied,
never as a pass.
"""
import pathlib

from . import matrix

#: The sections of the requirements document, with what addresses each.
#:
#: ``families`` are requirement-identifier prefixes whose members belong to that
#: section. ``delivers`` are paths in this repository built for it. ``owner`` is
#: set only where the section is genuinely not this surface's to carry, and then
#: it says what this surface does instead.
SECTIONS = (
    {"section": 1, "label": "the executive conclusion",
     "families": (), "delivers": (),
     "owner": "the product owner",
     "thisSurfaceDoes": "nothing: a conclusion about the round is not an "
                        "engineering artifact and is not restated here"},
    {"section": 2, "label": "requirement status and change rules",
     "families": (), "delivers": ("scenarios/matrix.py", "scenarios/decisions.py"),
     "owner": None, "thisSurfaceDoes": None},
    {"section": 3, "label": "product goals and boundary",
     "families": ("EX-SCOPE",), "delivers": ("scenarios/matrix.py",),
     "owner": None, "thisSurfaceDoes": None},
    {"section": 4, "label": "the current baseline and its factual edges",
     "families": (), "delivers": ("scenarios/manifest.py", "scenarios/reuse.py"),
     "owner": None, "thisSurfaceDoes": None},
    {"section": 5, "label": "participants and the trust boundary",
     "families": ("EX-AUTH",), "delivers": ("scenarios/reuse.py",),
     "owner": None, "thisSurfaceDoes": None},
    {"section": 6, "label": "the domain model and its state split",
     "families": ("EX-INV",), "delivers": ("scenarios/demos.py",),
     "owner": None, "thisSurfaceDoes": None},
    {"section": 7, "label": "continuous trading, registration order, the deadline "
                             "and collection path, and the invariants",
     "families": ("EX-INV", "EX-TIME", "EX-EXIT"),
     "delivers": ("scenarios/demos.py", "scenarios/paths.py"),
     "owner": None, "thisSurfaceDoes": None},
    {"section": 8, "label": "conditional funds, suffix rollback and failure recovery",
     "families": ("EX-SETTLE", "EX-ROLLBACK", "EX-GAS"),
     "delivers": ("scenarios/demos.py",),
     "owner": None, "thisSurfaceDoes": None},
    {"section": 9, "label": "the wallet, agent and matching boundary",
     "families": ("EX-AUTH", "EX-MATCH"), "delivers": ("scenarios/demos.py",),
     "owner": None, "thisSurfaceDoes": None},
    {"section": 10, "label": "the operation and event contracts",
     "families": (),
     "delivers": ("scenarios/operations.py", "scenarios/events.py"),
     "owner": None, "thisSurfaceDoes": None},
    {"section": 11, "label": "the minimal interface and operator console",
     "families": (), "delivers": (),
     "owner": "the party that owns UI acceptance",
     "thisSurfaceDoes": "reads the rendered pages as development output and "
                        "keeps the page state NOT_RUN; the pages themselves and "
                        "their own tests belong to the domain surface"},
    {"section": 12, "label": "the non-functional and security requirements",
     "families": ("EX-NFR",),
     "delivers": ("scenarios/observations.py", "scenarios/validation.py"),
     "owner": None, "thisSurfaceDoes": None},
    {"section": 13, "label": "reuse of existing components and external dependencies",
     "families": (), "delivers": ("scenarios/reuse.py",),
     "owner": None, "thisSurfaceDoes": None},
    {"section": 14, "label": "the three simulated registration routes",
     "families": (), "delivers": ("scenarios/paths.py",),
     "owner": None, "thisSurfaceDoes": None},
    {"section": 15, "label": "the six core demonstrations",
     "families": ("EX-DEMO",),
     "delivers": ("scenarios/demos.py", "scenarios/dossier.py",
                  "scenarios/STORYBOARD.md", "scenarios/storyboard.py"),
     "owner": None, "thisSurfaceDoes": None},
    {"section": 16, "label": "staged implementation and acceptance",
     "families": (), "delivers": ("scenarios/stages.py",),
     "owner": None, "thisSurfaceDoes": None},
    {"section": 17, "label": "the requirement and test matrix",
     "families": (),
     "delivers": ("scenarios/matrix.py", "scenarios/evidence_index.py"),
     "owner": None, "thisSurfaceDoes": None},
    {"section": 18, "label": "the engineering delivery contract",
     "families": (),
     "delivers": ("scenarios/receipt.py", "scenarios/execution.py",
                  "scenarios/handoff.py", "scenarios/cli.py"),
     "owner": None, "thisSurfaceDoes": None},
    {"section": 19, "label": "open decisions and local gates",
     "families": (), "delivers": ("scenarios/decisions.py",),
     "owner": None, "thisSurfaceDoes": None},
    {"section": 20, "label": "source and decision tracking",
     "families": (), "delivers": (),
     "owner": "the party that owns the private handover",
     "thisSurfaceDoes": "nothing publishable: the sources are private documents, "
                        "and their content, identity, digest and location are "
                        "never written into this repository"},
    {"section": 21, "label": "the definition of done",
     "families": (), "delivers": ("scenarios/completion.py",),
     "owner": None, "thisSurfaceDoes": None},
)


def _members(family):
    """The declared requirements belonging to one identifier family."""
    return sorted(name for name in matrix.DECLARED_REQUIREMENTS
                  if name.rsplit("-", 1)[0] == family)


#: Outcomes from weakest to strongest. The weakest outcome behind a section is
#: what the section really rests on.
OUTCOME_ORDER = ("error", "failed", "blocked", "incomplete", "not-run",
                 "unit-suite-only", "passed")

#: Outcomes that are a local result for the section. ``unit-suite-only`` is one:
#: the case is evidenced by a declared test suite rather than by a scenario, and
#: the matrix names that suite.
ESTABLISHED_OUTCOMES = ("passed", "unit-suite-only")


def _section_evidence(requirements, rows, claimed):
    """What the acceptance matrix records about one section's requirements."""
    if rows is None:
        return {"evidence": "NOT_SUPPLIED", "cases": [], "caseOutcomes": {},
                "weakestOutcome": None, "locallyEstablished": False,
                "awaitingRealEvidence": [], "weakWithoutReason": []}
    cases = sorted({case for name in requirements
                    for case in claimed.get(name, [])},
                   key=lambda name: int(name.split("-")[1]))
    outcomes = {case: rows[case]["localOutcome"] for case in cases
                if case in rows}
    present = [outcome for outcome in OUTCOME_ORDER
               if outcome in set(outcomes.values())]
    weakest = present[0] if present else None
    awaiting, unaccounted = [], []
    for case, outcome in sorted(outcomes.items()):
        if outcome in ESTABLISHED_OUTCOMES:
            continue
        owed = matrix.REMAINING_EVIDENCE.get(case)
        if owed:
            awaiting.append({"case": case, "outcome": outcome, "requires": owed})
        else:
            unaccounted.append({"case": case, "outcome": outcome})
    return {
        "evidence": "supplied",
        "cases": cases,
        "caseOutcomes": outcomes,
        "weakestOutcome": weakest,
        "locallyEstablished": bool(outcomes) and weakest in ESTABLISHED_OUTCOMES,
        "awaitingRealEvidence": awaiting,
        "weakWithoutReason": unaccounted,
    }


def build(root=".", acceptance=None):
    """Every section, with what addresses it, what establishes it, what is missing.

    ``acceptance`` is an acceptance matrix from a run. Without it the evidence
    axis reports ``NOT_SUPPLIED``: the deliverables can be checked against the
    disk from any working copy, but what a section rests on is a result, and a
    result cannot be inferred from a file being present.
    """
    rows = None
    if acceptance is not None:
        rows = {row["case"]: row for row in acceptance.get("rows", [])}
    claimed = matrix.requirement_coverage()["claimedByCases"]
    covered_families = set()
    sections, findings = [], []
    for entry in SECTIONS:
        families = []
        for family in entry["families"]:
            members = _members(family)
            families.append({"family": family, "requirements": members,
                             "requirementCount": len(members),
                             "declared": bool(members)})
            if not members:
                findings.append({
                    "finding": "a section names a requirement family that does "
                               "not exist",
                    "detail": "section %d: %s" % (entry["section"], family)})
            covered_families.add(family)
        delivers = []
        for where in entry["delivers"]:
            exists = (pathlib.Path(root) / where).is_file()
            delivers.append({"where": where, "exists": exists})
            if not exists:
                findings.append({
                    "finding": "a section names a deliverable that is not there",
                    "detail": "section %d: %s" % (entry["section"], where)})
        if not families and not delivers and entry["owner"] is None:
            findings.append({
                "finding": "a section is addressed by nothing and owed by nobody",
                "detail": "section %d: %s" % (entry["section"], entry["label"])})
        if entry["owner"] is not None and not entry["thisSurfaceDoes"]:
            findings.append({
                "finding": "a section is handed to an owner without saying what "
                           "this surface does instead",
                "detail": "section %d" % entry["section"]})
        requirements = sorted({name for family in families
                               for name in family["requirements"]})
        evidence = _section_evidence(requirements, rows, claimed)
        for entry_without_reason in evidence["weakWithoutReason"]:
            findings.append({
                "finding": "a section rests on a case that neither passed nor "
                           "says what it is still owed",
                "detail": "section %d: %s is %s" % (entry["section"],
                                                    entry_without_reason["case"],
                                                    entry_without_reason["outcome"])})
        sections.append({
            "section": entry["section"],
            "label": entry["label"],
            "requirementFamilies": families,
            "requirements": requirements,
            "delivers": delivers,
            "deliverableCount": len(delivers),
            "owner": entry["owner"],
            "thisSurfaceDoes": entry["thisSurfaceDoes"],
            # Two different questions, kept apart: whether anything in this
            # repository is built for the section, and whether a result
            # establishes it.
            "addressedHere": bool(delivers) or bool(families),
            **evidence,
        })
    declared_families = {name.rsplit("-", 1)[0]
                         for name in matrix.DECLARED_REQUIREMENTS}
    unplaced = sorted(declared_families - covered_families)
    for family in unplaced:
        findings.append({
            "finding": "a declared requirement family belongs to no section",
            "detail": family})
    numbers = [entry["section"] for entry in sections]
    gaps = [number for number in range(1, max(numbers) + 1)
            if number not in numbers]
    for number in gaps:
        findings.append({"finding": "a section number is missing from this ledger",
                         "detail": str(number)})
    return {
        "schema": "8415ex-section-ledger/1",
        "sections": sections,
        "sectionCount": len(sections),
        "sectionsAddressedHere": [entry["section"] for entry in sections
                                  if entry["addressedHere"]],
        "sectionsOwedElsewhere": [entry["section"] for entry in sections
                                  if entry["owner"] is not None],
        "evidenceSupplied": rows is not None,
        "sectionsLocallyEstablished": [entry["section"] for entry in sections
                                       if entry["locallyEstablished"]],
        "sectionsAwaitingRealEvidence": [
            {"section": entry["section"], "weakestOutcome": entry["weakestOutcome"],
             "awaiting": entry["awaitingRealEvidence"]}
            for entry in sections if entry["awaitingRealEvidence"]],
        "sectionsWeakWithoutReason": [entry["section"] for entry in sections
                                      if entry["weakWithoutReason"]],
        "sectionsWithNoCases": [entry["section"] for entry in sections
                                if entry["addressedHere"] and not entry["cases"]
                                and rows is not None],
        "requirementFamiliesPlaced": sorted(covered_families),
        "requirementFamiliesUnplaced": unplaced,
        "missingSectionNumbers": gaps,
        "findings": findings,
        "findingCount": len(findings),
        "consistent": not findings,
        "isNot": [
            "not the requirements document: sections are identified by number "
            "and by what this repository does about them, and none of the "
            "document's own text is reproduced here",
            "not a completeness claim about a section: it says what addresses "
            "the section and what the recorded evidence behind it is, never "
            "that the section is satisfied",
            "not a local pass for a section awaiting real evidence: that is "
            "reported as awaiting, with what is owed and by whom, and it is "
            "not a defect of this surface",
            "not an acceptance decision for any section",
        ],
    }
