"""The evidence index: one place a reviewer can start from and verify.

This extends the existing delivery rather than recomputing it. Every row is
assembled from the artefacts the run already produced - the acceptance matrix,
the two harness reports, the manifest and the handoff - so the index cannot
disagree with them. It adds no scenario, runs nothing of its own, and multiplies
nothing: the six scenarios and the three route contracts appear as the nine
runners that exist, each with the cases it actually recorded.

For every case the index answers, in one row:

    approved requirement
      -> the assertion that was actually recorded
      -> where it is implemented and which test covers it
      -> the exact source and run it was observed under
      -> what was observed, with the raw expected and observed values
      -> which artifact carries the row, and where inside it
      -> what real evidence is still owed, and who owns it

The artifact leg is the one that was missing. Without it a reviewer holding a
delivered file cannot tell which rows it is supposed to carry, and a row cannot
say whether it reached a file at all. It is also the leg that must not be
overstated: the index is built before the outputs are written, so at index time
every artifact is declared, not delivered, and says so.
"""
from copy import deepcopy

#: Where this index sits inside the delivered bundle. Row pointers are given
#: relative to the artifact root as well as to this index, because a reviewer
#: opening a delivered file navigates from the file's root.
BUNDLE_POINTER = "/evidenceIndex"

#: What an artifact's delivery status can be at index time. The index runs
#: before the outputs are written, so the only truthful answer here is that
#: publication was not observed in this process; the delivery report written
#: after the fact carries the actual per-path result.
ARTIFACT_NOT_OBSERVED = "NOT_CAPTURED_IN_PROCESS"

from . import handoff, manifest, matrix
from .demos import MAIN_PATHS
from .paths import PATH_CONTRACTS


def _assertions_by_case(reports):
    """Every recorded assertion, grouped by the case it serves."""
    grouped = {}
    for report in reports:
        for scenario in (report or {}).get("scenarios", []):
            for position, expectation in enumerate(scenario["expectations"]):
                for case in expectation["cases"]:
                    grouped.setdefault(case, []).append({
                        "scenarioId": scenario["scenarioId"],
                        "mainPath": scenario["mainPath"],
                        "index": position,
                        "assertion": expectation["name"],
                        "outcome": expectation["outcome"],
                        "expected": expectation["expected"],
                        "observed": expectation["observed"],
                        "detail": expectation["detail"],
                    })
    return grouped


def _command_references(case, commands):
    """Pointers to supplied records, never guessed log filenames or results.

    Suite coverage is aggregate evidence, not an individual test verdict.
    Inline stream tails/digests are explicitly distinguished from full raw logs.
    """
    refs = []
    coverage = matrix.CASE_IMPLEMENTATION[case][1]
    for position, command in enumerate(commands):
        text = command.get("command", "")
        explicit = case in command.get("cases", [])
        suite = (("scenarios/tests" in text and "scenarios/tests/" in coverage)
                 or ("exchange/tests" in text and "exchange/tests/" in coverage))
        if not (explicit or suite):
            continue
        pointer = f"#/commands/{position}"
        refs.append({
            "commandRef": pointer,
            "coverageScope": ("whole-invocation" if command.get("scope") == "final-outer-process"
                              else "declared-case" if explicit else "suite-aggregate"),
            "command": text,
            "outcome": command.get("outcome"),
            "executed": command.get("executed"),
            "runRef": "#/runIdentity",
            "streamRefs": {name: pointer + "/" + name
                           for name in ("stdout", "stderr") if name in command},
            "rawLogRefs": {name: pointer + "/" + name
                           for name in ("rawLog", "rawLogPath", "rawLogRef")
                           if command.get(name)},
            "note": "stream references contain captured tails and digests, not full raw logs",
        })
    return refs


def _artifact_slots(artifacts):
    """The declared output artifacts, with no claim that any of them was written.

    ``artifacts`` is the delivery plan: the paths this run intends to publish.
    An empty plan is reported as an empty plan, not as a delivery failure and
    not as a missing feature - a run asked for no output file is a legitimate
    run whose rows are carried by stdout only.
    """
    slots = []
    for position, entry in enumerate(artifacts or []):
        path = entry.get("path") if isinstance(entry, dict) else entry
        kind = entry.get("format", "unknown") if isinstance(entry, dict) else (
            "json" if str(path).endswith(".json") else "text" if str(path).endswith(".txt") else "unknown")
        slots.append({
            "artifactRef": "#/artifacts/%d" % position,
            "path": path,
            "format": kind,
            "formatBasis": "declared-output-role" if isinstance(entry, dict) else "caller-path-suffix-inference",
            "carries": ("the sealed calculation record, this index included" if kind == "json"
                        else "text summary only" if kind == "text" else "unspecified content"),
            "deliveryStatus": ARTIFACT_NOT_OBSERVED,
            "deliveryReportedBy": ("outputDelivery in externally captured final stdout JSON from run-all --json; "
                                   "not a pointer inside this saved artifact; final process exit must also be captured"),
        })
    return slots


def _artifact_references(position, slots):
    """Where one row lands: which artifact, and the pointer inside it."""
    within_index = "#/rows/%d" % position
    within_bundle = "%s/rows/%d" % (BUNDLE_POINTER, position)
    if not slots:
        return [{
            "artifactRef": None,
            "path": None,
            "pointerInIndex": within_index,
            "pointerInArtifact": None,
            "deliveryStatus": "NO_ARTIFACT_DECLARED",
            "note": "no output file declared; full rows require JSON stdout capture, not the default text summary",
        }]
    return [{
        "artifactRef": slot["artifactRef"],
        "path": slot["path"],
        "pointerInIndex": within_index,
        "pointerInArtifact": (within_bundle if slot["format"] == "json" else None),
        "deliveryStatus": slot["deliveryStatus"],
        "note": ("a JSON pointer resolves this row inside the delivered record"
                 if slot["format"] == "json"
                 else "the text output is a summary; it does not carry the row verbatim"),
    } for slot in slots]


def build(scenario_report=None, path_report=None, root=".", run_identity=None,
          commands=None, observations=None, source=None, artifacts=None,
          guarantee_report=None):
    """One index over supplied evidence, including missing execution records.

    JSON pointers are relative to this index. Optional command and observation
    records are copied verbatim; absent evidence produces no invented pointer.
    Observation references locate measurements, not per-case acceptance passes.
    Supply the observed bundle source when indexing an earlier execution; a
    later observer must not relabel earlier results with its own source reading.
    """
    source = deepcopy(source) if source is not None else manifest.source_identity(root)
    run_identity = dict(run_identity or {})
    commands = deepcopy(commands or [])
    observations = deepcopy(observations or {})
    acceptance = matrix.build(source, run_identity, scenario_report, path_report,
                              guarantee_report)
    assertions = _assertions_by_case([scenario_report, path_report, guarantee_report])
    checklist = handoff.build(acceptance)
    slots = _artifact_slots(artifacts)

    rows = []
    for position, row in enumerate(acceptance["rows"]):
        case = row["case"]
        recorded = assertions.get(case, [])
        rows.append({
            "case": case,
            "requirements": row["requirements"],
            "stage": row["stage"],
            "assertions": recorded,
            "assertionCount": len(recorded),
            "commandReferences": _command_references(case, commands),
            "observationReferences": [
                {"observationRef": "#/observations/" + name,
                 "runRef": "#/runIdentity", "scope": "run-level observation"}
                for name in ({"T-39": ("secretScan", "resourceObservation"),
                              "T-40": ("workload",)}.get(case, ()))
                if name in observations],
            "implementation": row["implementation"],
            "unitCoverage": row["unitCoverage"],
            "scenarios": row["scenarios"],
            "sourceIdentity": {"commit": source["commit"], "tree": source["tree"],
                               "branch": source["branch"],
                               "worktreeClean": source["worktreeClean"]},
            "runIdentity": run_identity,
            "localOutcome": row["localOutcome"],
            "assertionOutcomes": row["scenarioAssertionCounts"],
            "scenarioProblems": row["scenarioProblems"],
            "partiallyLocal": row["partiallyLocal"],
            "remainingRealEvidence": row["remainingRealEvidence"],
            "remainingOwner": ("integration acceptance" if row["remainingRealEvidence"]
                               else None),
            "artifactReferences": _artifact_references(position, slots),
        })

    runners = []
    for report, kind in ((scenario_report, "scenario"), (path_report, "route contract"),
                         (guarantee_report, "guarantee contract")):
        for scenario in (report or {}).get("scenarios", []):
            runners.append({
                "runner": scenario["scenarioId"],
                "kind": kind,
                "mainPath": scenario["mainPath"],
                "cases": list(scenario["cases"]),
                "counts": scenario["counts"],
                "passed": scenario["passed"],
                "error": scenario["error"],
                "steps": len(scenario["steps"]),
                "scope": scenario["scope"],
            })

    by_outcome = {}
    for row in rows:
        by_outcome.setdefault(row["localOutcome"], []).append(row["case"])
    return {
        "schema": "8415ex-evidence-index/3",
        "sourceIdentity": source,
        "runIdentity": run_identity,
        "commands": commands,
        "observations": observations,
        "artifacts": slots,
        "artifactCount": len(slots),
        "artifactDeliveryStatus": ARTIFACT_NOT_OBSERVED,
        "bundlePointer": BUNDLE_POINTER,
        "runners": runners,
        "runnerCount": len(runners),
        "scenarioRunners": sorted(MAIN_PATHS),
        "routeRunners": [contract.scenario_id for contract in PATH_CONTRACTS],
        "rows": rows,
        "caseCount": len(rows),
        "casesByOutcome": {name: sorted(cases)
                           for name, cases in sorted(by_outcome.items())},
        "unsoundCases": acceptance["unsoundCases"],
        "allCasesSound": acceptance["allCasesSound"],
        "evidenceSlots": checklist["evidenceSlots"],
        "existingOwnerDependencies": checklist["existingOwnerDependencies"],
        "reproduce": [
            "PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover "
            "-s scenarios/tests -t .",
            "PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover "
            "-s exchange/tests -t .",
            "PYTHONDONTWRITEBYTECODE=1 python3 -B -m scenarios.cli run-all "
            "--execute-suites --json-out /tmp/ex-run.json --text-out /tmp/ex-run.txt",
        ],
        "note": ("assembled from the artefacts this run already produced, so it "
                 "cannot disagree with them; it records what failed, what was "
                 "blocked and what is still owed on the same terms as what passed, "
                 "names the artifact each row lands in without claiming the "
                 "artifact was written, and every local result is model evidence "
                 "about this source only"),
    }
