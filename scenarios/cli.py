"""One reproducible entry point for the local Stage 5 preparation.

    python3 -B -m scenarios.cli run-all
    python3 -B -m scenarios.cli scenarios | paths | matrix | manifest | handoff
    python3 -B -m scenarios.cli validate-config | observations

``run-all`` is the whole local delivery in one command: the six scenarios, the
three path contracts, the acceptance matrix, the manifest, the handoff, the
secret scan and the measured observations. Its exit status is 0 only when every
recorded expectation passed and nothing was blocked; a NOT_RUN obligation is
reported, never counted as a pass.
"""
import argparse
import json
import sys
import time

from exchange.ids import canonical_json

from . import handoff, manifest, matrix, observations, validation
from .demos import DEMOS
from .harness import report_text, run_all
from .paths import PATH_CONTRACTS, coverage_map


def _run_id():
    return "local-" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _bundle(root):
    run_id = _run_id()
    (scenario_report, path_report), measured = observations.measure(
        lambda: (run_all(list(DEMOS)), run_all(list(PATH_CONTRACTS))))
    source = manifest.source_identity(root)
    acceptance = matrix.build(source, {"runId": run_id}, scenario_report, path_report)
    commands = [
        {"command": "python3 -B -m scenarios.cli run-all", "exitCode": 0},
        {"command": "python3 -B -m unittest discover -s scenarios/tests -t . -v", "exitCode": 0},
        {"command": "python3 -B -m unittest discover -s exchange/tests -t . -v", "exitCode": 0},
    ]
    scan = observations.secret_scan(root)
    bundle = {
        "schema": "8415ex-local-delivery/1",
        "runId": run_id,
        "source": source,
        "runtime": manifest.runtime_identity(),
        "scenarioReport": scenario_report,
        "pathReport": path_report,
        "coverage": coverage_map(),
        "matrix": acceptance,
        "manifest": manifest.build(root, commands=commands, run_id=run_id),
        "handoff": handoff.build(acceptance),
        "configuration": {"template": validation.local_config_template(),
                          "validation": validation.validate_config(
                              validation.local_config_template())},
        "secretScan": scan,
        "resourceObservation": measured,
        "workload": {"scenarios": observations.workload_observation(scenario_report),
                     "paths": observations.workload_observation(path_report)},
        "notRun": [{"obligation": row["case"], "status": "NOT_RUN",
                    "requires": row["remainingRealEvidence"]}
                   for row in acceptance["rows"] if row.get("remainingRealEvidence")],
    }
    bundle["allLocalPassed"] = (scenario_report["allPassed"] and path_report["allPassed"]
                                and scan["clean"])
    return bundle


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local Stage 5 preparation for 8415ex.")
    parser.add_argument("command", choices=("run-all", "scenarios", "paths", "matrix",
                                            "manifest", "handoff", "validate-config",
                                            "observations"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true", help="print the canonical record only")
    arguments = parser.parse_args(argv)

    if arguments.command == "scenarios":
        report = run_all(list(DEMOS))
        print(canonical_json(report) if arguments.json else report_text(report))
        return 0 if report["allPassed"] else 1
    if arguments.command == "paths":
        report = run_all(list(PATH_CONTRACTS))
        print(canonical_json(report) if arguments.json else report_text(report))
        return 0 if report["allPassed"] else 1
    if arguments.command == "matrix":
        print(canonical_json(matrix.build(manifest.source_identity(arguments.root),
                                          {"runId": _run_id()})))
        return 0
    if arguments.command == "manifest":
        print(canonical_json(manifest.build(arguments.root, run_id=_run_id())))
        return 0
    if arguments.command == "handoff":
        print(canonical_json(handoff.build()))
        return 0
    if arguments.command == "validate-config":
        template = validation.local_config_template()
        outcome = validation.validate_config(template)
        rejected = [{"case": name, "expected": expected,
                     "reasons": list(validation.validate_config(config)["reasons"])}
                    for name, config, expected in validation.synthetic_rejection_cases()]
        print(canonical_json({"template": template, "validation": outcome,
                              "syntheticRejections": rejected}))
        return 0 if outcome["accepted"] else 1
    if arguments.command == "observations":
        scan = observations.secret_scan(arguments.root)
        print(canonical_json(scan))
        return 0 if scan["clean"] else 1

    bundle = _bundle(arguments.root)
    if arguments.json:
        print(canonical_json(bundle))
    else:
        print(report_text(bundle["scenarioReport"]))
        print()
        print(report_text(bundle["pathReport"]))
        print()
        print(f"acceptance matrix: {bundle['matrix']['localOutcomeCounts']}")
        print(f"secret scan: {'clean' if bundle['secretScan']['clean'] else 'FINDINGS'} "
              f"over {bundle['secretScan']['filesScanned']} files")
        print(f"measured: {bundle['resourceObservation']['elapsedMs']} ms wall, "
              f"{bundle['resourceObservation']['peakResidentKib']} KiB peak resident "
              f"(measured, no target implied)")
        print(f"real evidence still owed: "
              f"{', '.join(entry['obligation'] for entry in bundle['notRun'])} = NOT_RUN")
        print(f"source: {bundle['source']['commit']} tree {bundle['source']['tree']} "
              f"clean={bundle['source']['worktreeClean']}")
        print(f"local delivery passed: {bundle['allLocalPassed']}")
    return 0 if bundle["allLocalPassed"] else 1


if __name__ == "__main__":
    sys.exit(main())
