"""Requirement-section coverage and technical evidence categories.

PRD.md is the product requirements document. Each section identifies its
requirement families, implementation paths and additional evidence category.
Paths and family membership are checked; these are coverage checks, not
acceptance claims. The legacy owner field carries an evidence category."""
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
     "owner": 'product specification',
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
     "owner": 'browser acceptance evidence',
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
     "owner": 'artifact provenance',
     "thisSurfaceDoes": "PRD.md records the product requirements; this ledger records "
                        "coverage and evidence dependencies"},
    {"section": 21, "label": "the definition of done",
     "families": (), "delivers": ("scenarios/completion.py",),
     "owner": None, "thisSurfaceDoes": None},
)


def _members(family):
    """The declared requirements belonging to one identifier family."""
    return sorted(name for name in matrix.DECLARED_REQUIREMENTS
                  if name.rsplit("-", 1)[0] == family)


def build(root="."):
    """Every section, with what addresses it and what is missing."""
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
                "finding": 'a section has no implementation or evidence category',
                "detail": "section %d: %s" % (entry["section"], entry["label"])})
        if entry["owner"] is not None and not entry["thisSurfaceDoes"]:
            findings.append({
                "finding": 'a section names an evidence category without describing this surface',
                "detail": "section %d" % entry["section"]})
        sections.append({
            "section": entry["section"],
            "label": entry["label"],
            "requirementFamilies": families,
            "requirements": sorted({name for family in families
                                    for name in family["requirements"]}),
            "delivers": delivers,
            "deliverableCount": len(delivers),
            "owner": entry["owner"],
            "thisSurfaceDoes": entry["thisSurfaceDoes"],
            "addressedHere": bool(delivers) or bool(families),
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
            "the section, never that the section is satisfied",
            "not an acceptance decision for any section",
        ],
    }
