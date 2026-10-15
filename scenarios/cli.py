"""One reproducible entry point for the local Stage 5 preparation.

    python3 -B -m scenarios.cli run-all [--execute-suites]
                                        [--json] [--json-out FILE] [--text-out FILE]
    python3 -B -m scenarios.cli scenarios | paths | matrix | manifest | handoff
    python3 -B -m scenarios.cli validate-config | observations

``run-all`` is the whole local delivery in one command: the six scenarios, the
three path contracts, the acceptance matrix, the manifest, the handoff, the
secret scan and the measured observations.

Three rules govern what it records.

*Execution.* A command record is written only for a command that actually ran,
and only after its exit code is known. The run's own record is sealed at the
very end from the real exit status. The two unit suites are recorded as NOT_RUN
unless ``--execute-suites`` is given, in which case they are really executed as
subprocesses and their true status, timing and output digests are kept.

*Source.* The reported root must be the tree this code was imported from, the
worktree must be clean, and the file inventory must be complete. A failure in
any of those is a failure of the run, not a footnote.

*One run, one identity.* ``--json-out`` and ``--text-out`` write both forms of
the same single execution, under one run id. Two invocations are two runs and
are never presented as one.
"""
import argparse
import hashlib
import os
import sys
import time
import uuid

from exchange.ids import canonical_json

from . import execution, handoff, manifest, matrix, observations, validation
from .demos import DEMOS
from .harness import report_text, run_all
from .paths import PATH_CONTRACTS, coverage_map

#: The suites whose real status this bundle can carry, and the case they serve.
UNIT_SUITES = (
    ("scenario preparation suite",
     ("python3", "-B", "-m", "unittest", "discover", "-s", "scenarios/tests", "-t", ".")),
    ("domain suite",
     ("python3", "-B", "-m", "unittest", "discover", "-s", "exchange/tests", "-t", ".")),
)

#: Why a suite is NOT_RUN when it was not executed in this invocation.
NOT_EXECUTED_HERE = ("not executed in this invocation; pass --execute-suites to run it and "
                     "record its real status")

#: Set in a suite subprocess this run started. The scenario suite exercises this
#: very bundle, so executing the suites from inside a suite would re-enter the
#: run without end. The nested level records the suites as NOT_RUN rather than
#: recursing, which keeps the outer record real and the inner one empty.
NESTING_GUARD_ENV = "EX_SUITE_EXECUTION_IN_PROGRESS"
NESTED_NOT_EXECUTED = ("not executed: this bundle is already running inside a suite this run "
                       "started, and nesting would re-enter the run")


def _run_id():
    """A run identity no second run can repeat."""
    return (f"local-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
            f"-{uuid.uuid4().hex[:12]}")


def _suite_records(root, execute):
    nested = os.environ.get(NESTING_GUARD_ENV) == "1"
    records = []
    for title, argv in UNIT_SUITES:
        if execute and not nested:
            record = execution.run_command(argv, root=root, env={NESTING_GUARD_ENV: "1"})
        else:
            record = execution.not_run(" ".join(argv),
                                       NESTED_NOT_EXECUTED if nested else NOT_EXECUTED_HERE)
        record["title"] = title
        records.append(record)
    return records


def _bundle(root, execute_suites=False, run_id=None, started_at=None):
    """Everything this run observed, with no record of its own exit status yet.

    The self record cannot exist here: the exit status is not known until the
    bundle is complete. ``seal`` adds it afterwards.
    """
    run_id = run_id or _run_id()
    started_at = started_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # The source is pinned before anything runs and checked again after
    # packaging, so an earlier clean reading cannot be combined with a later,
    # different one.
    before = manifest.snapshot(root)
    (scenario_report, path_report), measured = observations.measure(
        lambda: (run_all(list(DEMOS)), run_all(list(PATH_CONTRACTS))))
    source = manifest.source_identity(root)
    acceptance = matrix.build(source, {"runId": run_id, "startedAt": started_at},
                              scenario_report, path_report)
    commands = _suite_records(root, execute_suites)
    scan = observations.secret_scan(root)
    package = manifest.build(root, commands=commands, run_id=run_id)
    bundle = {
        "schema": "8415ex-local-delivery/2",
        "runId": run_id,
        "startedAt": started_at,
        "source": source,
        "runtime": manifest.runtime_identity(),
        "scenarioReport": scenario_report,
        "pathReport": path_report,
        "coverage": coverage_map(),
        "matrix": acceptance,
        "manifest": package,
        "commands": commands,
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
                   for row in acceptance["rows"] if row.get("remainingRealEvidence")]
        + [{"obligation": record["title"], "status": "NOT_RUN",
            "requires": record["reason"]}
           for record in commands if record["outcome"] == "not-run"],
    }
    after = manifest.snapshot(root)
    reconciliation = manifest.reconcile(before, after)
    bundle["sourceReconciliation"] = reconciliation
    executed = [record for record in commands if record["executed"]]
    # The evidence record is the shape the validator refuses a guess in. It is
    # built from this run and checked here, so a record that could not stand on
    # its own identity blocks the run instead of being reported beside it.
    evidence = {
        "schema": "8415ex-local-delivery-evidence/1",
        "runId": run_id,
        "commit": source["commit"],
        "tree": source["tree"],
        "worktreeClean": source["worktreeClean"],
        "commands": commands,
        "startedAt": started_at,
        "finishedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "scenarioDigest": scenario_report["deterministicDigest"],
        # Filled in below, once the outstanding obligations are collected.
        "notRun": [],
        "transactionHashes": "NOT_RUN",
    }
    blocking = []
    if not scenario_report["allPassed"]:
        blocking.append("a scenario did not pass")
    if not path_report["allPassed"]:
        blocking.append("a path contract did not pass")
    if not scan["clean"]:
        blocking.append(f"the secret scan is not clean ({scan['enumerationState']})")
    if not acceptance["allCasesSound"]:
        blocking.append(f"unsound acceptance cases: {', '.join(acceptance['unsoundCases'])}")
    if not source["ok"]:
        blocking.append("the source identity could not be established: "
                        + "; ".join(source["errors"] or ["incomplete"]))
    elif source["worktreeClean"] is not True:
        blocking.append(f"the worktree is not clean ({source['dirtyFileCount']} files)")
    if not source["executedSourceConfirmed"]:
        blocking.append("the reported root is not the tree this code executed from")
    if not package["inventoryOk"]:
        blocking.append(f"the file inventory is incomplete ({package['enumerationState']})")
    if not reconciliation["consistent"]:
        blocking.append("the source did not hold still during the run: "
                        + "; ".join(reconciliation["reasons"]))
    for record in executed:
        if record["outcome"] != "passed":
            blocking.append(f"{record['command']} ended {record['outcome']}")
    evidence["notRun"] = [{"obligation": entry["obligation"], "status": "NOT_RUN"}
                          for entry in bundle["notRun"]]
    checked = validation.validate_result(evidence)
    bundle["evidence"] = evidence
    bundle["evidenceValidation"] = checked
    if not checked["accepted"]:
        blocking.append("the evidence record was refused: " + ", ".join(checked["reasons"]))
    # Valid evidence of a real failure is still evidence that this run did not
    # pass. Structural validity never stands in for the result.
    for reason in checked["notPassing"]:
        if reason not in blocking:
            blocking.append(reason)
    bundle["blocking"] = blocking
    bundle["allLocalPassed"] = blocking == []
    bundle["meaning"] = ("every local expectation passed over a confirmed source tree; it is "
                         "not deployment, chain or UI evidence" if blocking == []
                         else "this run is not a local pass")
    return bundle


def seal(bundle, exit_code, finished_at=None):
    """Attach this run's own record, once the calculation's status is known.

    The record covers the calculation and the delivery this process performed.
    It deliberately does not claim the final outer process status: that is not
    knowable from inside the process that is still running, so it is marked as
    needing external capture and `execution.capture_cli` is what captures it.
    """
    finished_at = finished_at or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    record = execution.self_record("python3 -B -m scenarios.cli run-all", exit_code,
                                   bundle["startedAt"], finished_at)
    record["scope"] = "calculation-and-delivery-performed-in-process"
    record["finalProcessStatus"] = "NOT_CAPTURED_IN_PROCESS"
    record["detail"] = ("this record covers the calculation and the output delivery "
                        "this process performed, written once both were decided; the "
                        "final outer process exit status is not observable from inside "
                        "the running process and must be captured externally, with "
                        "execution.capture_cli")
    bundle["finishedAt"] = finished_at
    bundle["commands"] = [record] + list(bundle["commands"])
    bundle["manifest"]["commands"] = list(bundle["commands"])
    bundle["calculationExitCode"] = exit_code
    bundle["exitCode"] = exit_code
    # The sealed evidence carries the run's own record and its real end time.
    # It is validated again, so the record that leaves this run is the one that
    # was checked, not an earlier draft of it.
    bundle["evidence"] = dict(bundle["evidence"], commands=list(bundle["commands"]),
                              finishedAt=finished_at)
    bundle["evidenceValidation"] = validation.validate_result(bundle["evidence"])
    return bundle


def _destination_error(path):
    """Why this path could not receive an output, or None if it can."""
    if os.path.isdir(path):
        # Staging would succeed and the publish would fail, so this has to be
        # caught before anything is written.
        return f"[Errno 21] Is a directory: {path!r}"
    parent = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(parent):
        return f"[Errno 2] No such directory: {parent!r}"
    return None


def deliver_outputs(targets, run_id):
    """Write every requested output, or publish none of them.

    Each destination is checked, then each file is staged beside it, and only
    once every stage has succeeded is anything moved into place. A failure
    anywhere leaves no partial output, no orphaned half of the pair and no
    staging file behind, so the two outputs can never disagree about which run
    produced them. The returned records say what actually happened to each path.
    """
    wanted = [(path, content) for path, content in targets if path]
    records = {path: None for path, _ in wanted}
    staged = []

    def refuse(path, error, stage):
        records[path] = {"path": path, "ok": False, "bytes": None, "sha256": None,
                         "error": error, "stage": stage}

    try:
        for path, content in wanted:
            error = _destination_error(path)
            if error is not None:
                refuse(path, error, "destination")
                continue
            staging = f"{path}.staging-{run_id}"
            try:
                with open(staging, "w", encoding="utf-8") as handle:
                    handle.write(content)
            except OSError as problem:
                refuse(path, str(problem), "staging")
                continue
            staged.append((staging, path, content))

        if any(record is not None for record in records.values()):
            # Something could not be prepared, so nothing is published.
            for path in records:
                if records[path] is None:
                    refuse(path, "withheld: another output in the same delivery "
                                 "could not be prepared", "withheld")
            return [records[path] for path, _ in wanted]

        for staging, path, content in staged:
            try:
                os.replace(staging, path)
            except OSError as problem:
                refuse(path, str(problem), "publish")
                continue
            data = content.encode("utf-8")
            records[path] = {"path": path, "ok": True, "bytes": len(data),
                             "sha256": hashlib.sha256(data).hexdigest(),
                             "error": None, "stage": "published"}
        return [records[path] for path, _ in wanted]
    finally:
        # No staging file survives this call, whatever happened above.
        for staging, _, _ in staged:
            if os.path.exists(staging):
                try:
                    os.unlink(staging)
                except OSError:
                    pass


def summary_text(bundle):
    """The human summary, derived from the same bundle as the JSON."""
    scan = bundle["secretScan"]
    lines = [report_text(bundle["scenarioReport"]), "",
             report_text(bundle["pathReport"]), "",
             f"run id: {bundle['runId']}",
             f"acceptance matrix: {bundle['matrix']['localOutcomeCounts']}",
             f"secret scan: {'clean' if scan['clean'] else 'FINDINGS'} over "
             f"{scan['coverage']['scanned']} of {scan['coverage']['enumerated']} files "
             f"({scan['enumerationState']})",
             f"measured: {bundle['resourceObservation']['elapsedMs']} ms wall, "
             f"{bundle['resourceObservation']['peakResidentKib']} KiB peak resident "
             f"(measured, no target implied)"]
    for record in bundle["commands"]:
        if record["executed"]:
            lines.append(f"command: {record['command']} -> {record['outcome']} "
                         f"exit {record['exitCode']}")
        else:
            lines.append(f"command: {record['command']} -> {record['outcome'].upper()} "
                         f"(no exit code recorded)")
    lines.append("real evidence still owed: "
                 + ", ".join(entry["obligation"] for entry in bundle["notRun"]) + " = NOT_RUN")
    lines.append(f"source: {bundle['source']['commit']} tree {bundle['source']['tree']} "
                 f"clean={bundle['source']['worktreeClean']} "
                 f"executedFrom={bundle['source']['executedFrom']}")
    for reason in bundle["blocking"]:
        lines.append(f"BLOCKING {reason}")
    lines.append(f"local delivery passed: {bundle['allLocalPassed']}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local Stage 5 preparation for 8415ex.")
    parser.add_argument("command", choices=("run-all", "scenarios", "paths", "matrix",
                                            "manifest", "handoff", "validate-config",
                                            "observations"))
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true", help="print the canonical record only")
    parser.add_argument("--json-out", help="write the canonical record of this same run here")
    parser.add_argument("--text-out", help="write the summary of this same run here")
    parser.add_argument("--execute-suites", action="store_true",
                        help="really execute the two unit suites and record their true status")
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
        built = matrix.build(manifest.source_identity(arguments.root), {"runId": _run_id()})
        print(canonical_json(built))
        return 0 if built["allCasesSound"] else 1
    if arguments.command == "manifest":
        built = manifest.build(arguments.root, run_id=_run_id())
        print(canonical_json(built))
        return 0 if built["consistent"] else 1
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

    bundle = _bundle(arguments.root, execute_suites=arguments.execute_suites)
    # The calculation's status is decided from the observations. It is not the
    # command's status: the outputs still have to be delivered, and a process
    # cannot observe its own final exit.
    calculation_passed = bundle["allLocalPassed"]
    calculation_exit = 0 if calculation_passed else 1
    bundle["calculationPassed"] = calculation_passed
    bundle["outputDeliveryPlan"] = [path for path in (arguments.json_out,
                                                      arguments.text_out) if path]
    bundle["outputDeliveryStatus"] = "NOT_CAPTURED_IN_PROCESS"
    seal(bundle, calculation_exit)

    # The published files carry this sealed calculation record. Both come from
    # this one execution under this one run id, and they are published together
    # or not at all, so one can never describe a run whose other half is
    # missing.
    text, record = summary_text(bundle), canonical_json(bundle)
    delivery = deliver_outputs(
        [(arguments.json_out, record + "\n"), (arguments.text_out, text + "\n")],
        bundle["runId"])
    delivered = all(entry["ok"] for entry in delivery)
    for entry in delivery:
        if not entry["ok"]:
            print(f"output delivery failed: {entry['path']}: {entry['error']}",
                  file=sys.stderr)

    # What actually happened to the outputs is known only now, after the files
    # were written, so it belongs to the record this process still emits rather
    # than to the files it has already closed. Those files say so themselves,
    # through outputDeliveryStatus.
    bundle["outputDelivery"] = delivery
    bundle["outputDeliveryStatus"] = "delivered" if delivered else "withheld"
    bundle["allLocalPassed"] = calculation_passed and delivered
    if not delivered:
        for entry in delivery:
            if not entry["ok"]:
                bundle["blocking"].append(
                    f"output delivery to {entry['path']} failed: {entry['error']}")
    exit_code = 0 if bundle["allLocalPassed"] else 1
    bundle["exitCode"] = exit_code
    print(canonical_json(bundle) if arguments.json else summary_text(bundle))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
