"""Regression tests for evidence truthfulness; all fixtures are synthetic."""
import unittest
from pathlib import Path

from scenarios import evidence_index, execution, matrix, validation

ROOT = str(Path(__file__).resolve().parents[2])


class AcceptanceRecords(unittest.TestCase):
    def test_present_null_executed_is_not_optional(self):
        for outcome in validation.COMMAND_OUTCOMES:
            record = execution.not_run("python3", "fixture")
            record.update(outcome=outcome, executed=None)
            self.assertIn("EX_EVIDENCE_COMMAND_REFUSED:executed",
                          validation.validate_command_record(record))

    def test_unexecuted_records_refuse_execution_signals(self):
        signals = {"signal": 15, "durationMs": 0,
                   "stdout": {"bytes": 1, "tail": "x"},
                   "stderr": "error", "rawLog": "capture.log",
                   "rawLogPath": "capture.log", "rawLogRef": "#/logs/1",
                   "observedInRun": "other-run", "selfReported": True}
        for outcome in validation.UNEXECUTED_OUTCOMES:
            for key, value in signals.items():
                with self.subTest(outcome=outcome, field=key):
                    record = execution.not_run("python3", "fixture")
                    record.update(outcome=outcome, **{key: value})
                    self.assertIn("EX_EVIDENCE_UNEXECUTED_SIGNAL:" + key,
                                  validation.validate_command_record(record))

    def test_historical_run_label_is_refused_even_inside_current_window(self):
        command = {"command": "python3", "outcome": "passed", "exitCode": 0,
                   "executed": True, "startedAt": "2026-10-14T00:00:00Z",
                   "finishedAt": "2026-10-14T00:00:01Z", "observedInRun": "old"}
        result = validation.validate_result({
            "schema": "synthetic-fixture", "runId": "current", "commit": "a" * 40,
            "tree": "b" * 40, "worktreeClean": True, "commands": [command],
            "startedAt": command["startedAt"], "finishedAt": command["finishedAt"],
            "scenarioDigest": "0x" + "c" * 64, "notRun": []})
        self.assertIn("EX_EVIDENCE_HISTORICAL_COMMAND_UNSUPPORTED", result["reasons"])

    def test_historical_citations_require_full_identity_and_explicit_limits(self):
        citation = {"scope": "historical-citation", "verification": "unverified",
                    "observedInRun": "prior-run", "evidenceLocator": "prior-run.json",
                    "sourceIdentity": {"commit": "a" * 40, "tree": "b" * 40}}
        self.assertEqual(validation.validate_historical_citation(citation), ())
        for key in citation:
            missing = dict(citation)
            del missing[key]
            self.assertTrue(validation.validate_historical_citation(missing))
        for changes in ({"verification": "verified"},
                        {"sourceIdentity": {"commit": "a" * 7, "tree": "b" * 40}},
                        {"evidenceLocator": " "}, {"observedInRun": None}):
            self.assertTrue(validation.validate_historical_citation({**citation, **changes}))

    def test_index_refs_resolve_to_supplied_evidence_including_t39_t40(self):
        command = execution.not_run(
            "python3 -m unittest discover -s scenarios/tests -t .", "fixture")
        command.update(outcome="passed", executed=True, exitCode=0,
                       stdout={"tail": "synthetic output"})
        index = evidence_index.build(root=ROOT, run_identity={"runId": "fixture"},
                                     commands=[command], observations={
                                         "secretScan": {"clean": False},
                                         "resourceObservation": {"durationMs": 1},
                                         "workload": {"fixture": True}})
        def resolve(pointer):
            value = index
            for key in pointer[2:].split("/"):
                value = value[int(key)] if isinstance(value, list) else value[key]
            return value
        for row in index["rows"]:
            if row["case"] not in ("T-39", "T-40"):
                continue
            self.assertTrue(row["commandReferences"])
            self.assertTrue(row["observationReferences"])
            for ref in row["commandReferences"]:
                self.assertEqual(resolve(ref["commandRef"]), command)
                self.assertEqual(resolve(ref["runRef"]), {"runId": "fixture"})
                self.assertEqual(ref["rawLogRefs"], {})
                self.assertEqual(resolve(ref["streamRefs"]["stdout"]), command["stdout"])
                self.assertEqual(ref["coverageScope"], "suite-aggregate")
            for ref in row["observationReferences"]:
                self.assertIsInstance(resolve(ref["observationRef"]), dict)
            self.assertEqual(row["localOutcome"], "unit-suite-only")
        command["stdout"]["tail"] = "changed"
        self.assertEqual(index["commands"][0]["stdout"]["tail"], "synthetic output")

    def test_absent_commands_and_observations_are_not_fabricated(self):
        index = evidence_index.build(root=ROOT)
        self.assertEqual(index["commands"], [])
        self.assertEqual(index["observations"], {})
        for row in index["rows"]:
            self.assertEqual(row["commandReferences"], [])
            self.assertEqual(row["observationReferences"], [])


class ConservativeMatrixSemantics(unittest.TestCase):
    def test_mixed_failed_blocked_preserves_counts_and_conservative_outcome(self):
        scenario = {"scenarioId": "MIXED", "cases": ["T-11", "T-12"],
                    "passed": False, "error": None,
                    "counts": {"passed": 0, "failed": 1, "blocked": 1, "not-run": 0},
                    "expectations": [
                        {"name": "wrong answer", "cases": ["T-11"], "outcome": "failed"},
                        {"name": "cannot run", "cases": ["T-12"], "outcome": "blocked"}]}
        built = matrix.build({}, {}, {"scenarios": [scenario]}, None)
        rows = {r["case"]: r for r in built["rows"]}
        self.assertEqual(rows["T-11"]["localOutcome"], "failed")
        self.assertEqual(rows["T-12"]["localOutcome"], "failed")
        self.assertEqual(rows["T-12"]["scenarioAssertionCounts"]["failed"], 0)
        self.assertEqual(rows["T-12"]["scenarioAssertionCounts"]["blocked"], 1)
        self.assertEqual(rows["T-12"]["scenarioProblems"][0]["status"], "failed")
        self.assertFalse(built["allCasesSound"])
        scenario["error"] = "synthetic exception after partial recording"
        built = matrix.build({}, {}, {"scenarios": [scenario]}, None)
        rows = {r["case"]: r for r in built["rows"]}
        for case in ("T-11", "T-12"):
            self.assertEqual(rows[case]["localOutcome"], "error")
            self.assertIn(case, built["unsoundCases"])
