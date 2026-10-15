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
      -> what real evidence is still owed, and who owns it
"""
from copy import deepcopy

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


def build(scenario_report=None, path_report=None, root=".", run_identity=None,
          commands=None, observations=None, source=None):
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
    acceptance = matrix.build(source, run_identity, scenario_report, path_report)
    assertions = _assertions_by_case([scenario_report, path_report])
    checklist = handoff.build(acceptance)

    rows = []
    for row in acceptance["rows"]:
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
            "remainingOwner": (checklist["owner"] if row["remainingRealEvidence"]
                               else None),
        })

    runners = []
    for report, kind in ((scenario_report, "scenario"), (path_report, "route contract")):
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
        "schema": "8415ex-evidence-index/2",
        "sourceIdentity": source,
        "runIdentity": run_identity,
        "commands": commands,
        "observations": observations,
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
                 "and every local result is model evidence about this source only"),
    }
