"""Published guarantee evidence and every exercised adapter stay accounted for."""
import ast
import contextlib
import copy
import io
import json
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

from scenarios import cli, completion, evidence_index, guarantees

ROOT = str(Path(__file__).resolve().parents[2])
REPORTS = ("scenarioReport", "pathReport", "guaranteeReport")


class PublishedGuarantees(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.bundle = cli._bundle(ROOT)

    def assert_guarantees_retained(self, bundle):
        index = bundle["evidenceIndex"]
        rows = {row["case"]: row for row in index["rows"]}
        matrix = {row["case"]: row for row in bundle["matrix"]["rows"]}
        for case in guarantees.COVERED_CASES:
            with self.subTest(case=case):
                self.assertEqual(rows[case]["localOutcome"], "passed")
                self.assertGreater(rows[case]["assertionCount"], 0)
                self.assertEqual(rows[case]["assertionOutcomes"],
                                 matrix[case]["scenarioAssertionCounts"])
                self.assertEqual(rows[case]["scenarios"], matrix[case]["scenarios"])
        self.assertEqual({runner["runner"] for runner in index["runners"]},
                         {scenario["scenarioId"] for key in REPORTS
                          for scenario in bundle[key]["scenarios"]})

    def test_sealing_preserves_guarantee_assertions_and_runner_inventory(self):
        self.assert_guarantees_retained(cli.seal(copy.deepcopy(self.bundle), 1))

    def test_published_run_file_retains_guarantees(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run.json"
            with contextlib.redirect_stdout(io.StringIO()):
                cli.main(["run-all", "--root", ROOT, "--json-out", str(output)])
            self.assert_guarantees_retained(json.loads(output.read_text()))

    def test_ci_rebuild_preserves_the_same_guarantee_evidence(self):
        # Evaluate only the existing index-build expression, not the workflow
        # or its commands. This exercises the real call site's arguments and
        # catches an exporter that silently omits one execution group.
        workflow = Path(ROOT, ".github/workflows/bootstrap.yml").read_text()
        script = workflow.split("python3 -B - <<'PYCODE'\n", 1)[1]
        script = textwrap.dedent(script.split("          PYCODE", 1)[0])
        calls = [node for node in ast.walk(ast.parse(script))
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                 and isinstance(node.func.value, ast.Name)
                 and node.func.value.id == "evidence_index" and node.func.attr == "build"]
        self.assertEqual(len(calls), 1)
        expression = ast.Expression(calls[0])
        built = eval(compile(expression, "bootstrap-index-call", "eval"),
                     {"evidence_index": evidence_index, "bundle": self.bundle,
                      "observed": {"cases": ["T-39", "T-40"]}})
        self.assert_guarantees_retained(dict(self.bundle, evidenceIndex=built))

    def test_sealing_keeps_failed_guarantee_assertions_failed(self):
        bundle = copy.deepcopy(self.bundle)
        scenario = bundle["guaranteeReport"]["scenarios"][0]
        assertion = next(entry for entry in scenario["expectations"]
                         if entry["outcome"] == "passed")
        assertion["outcome"] = "failed"
        assertion["observed"] = "regression control"
        scenario["passed"] = False
        bundle["guaranteeReport"]["allPassed"] = False
        sealed = cli.seal(bundle, 1)
        rows = {row["case"]: row for row in sealed["evidenceIndex"]["rows"]}
        for case in assertion["cases"]:
            self.assertEqual(rows[case]["localOutcome"], "failed")
            self.assertTrue(any(entry["outcome"] == "failed"
                                for entry in rows[case]["assertions"]))
        self.assertFalse(sealed["evidenceIndex"]["allCasesSound"])


class StdoutOnlyCommands(unittest.TestCase):

    def test_every_stdout_command_refuses_both_file_flags_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "must-not-be-written"
            for command in cli.STDOUT_ONLY:
                for flag in ("--json-out", "--text-out"):
                    with self.subTest(command=command, flag=flag):
                        stdout, stderr = io.StringIO(), io.StringIO()
                        with contextlib.redirect_stdout(stdout), \
                                contextlib.redirect_stderr(stderr), \
                                self.assertRaises(SystemExit) as raised:
                            cli.main([command, "--root", ROOT, flag, str(output)])
                        self.assertEqual(raised.exception.code, 2)
                        self.assertIn("stdout only", stderr.getvalue())
                        self.assertEqual(stdout.getvalue(), "")
                        self.assertFalse(output.exists())


class AdapterProvenance(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.bundle = cli._bundle(ROOT)

    def test_bundle_reuse_accounts_for_labels_from_all_three_reports(self):
        expected = {}
        for key in REPORTS:
            for scenario in self.bundle[key]["scenarios"]:
                for role, label in scenario.get("setup", {}).get("simulatedAdapters", {}).items():
                    if label is not None:
                        expected.setdefault(role, set()).add(label)
        self.assertEqual(self.bundle["reuse"]["adaptersRecordedInThisRun"],
                         {role: sorted(labels) for role, labels in expected.items()})
        checked = self.bundle["completion"]["notMeantChecked"]
        self.assertEqual(checked["scenariosRead"],
                         sum(len(self.bundle[key]["scenarios"]) for key in REPORTS))
        self.assertTrue(checked["everyAdapterSimulated"])

    def test_standalone_reuse_includes_guarantee_matching_fixture(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            result = cli.main(["reuse", "--root", ROOT])
        self.assertEqual(result, 0)
        self.assertIn("matching", json.loads(stdout.getvalue())["adaptersRecordedInThisRun"])

    def test_unsafe_guarantee_setup_breaks_the_non_claim_gate(self):
        for field, value, verdict in (
                ("simulatedAdapters", {"registrar": "LiveRegistrarGateway"},
                 "everyAdapterSimulated"),
                ("receipt", {"chainId": completion.MAINNET_CHAIN_ID}, "noMainnet"),
                ("quoteAsset", "live-quote", "quoteAssetIsATestLabel")):
            with self.subTest(field=field):
                bundle = copy.deepcopy(self.bundle)
                bundle["guaranteeReport"]["scenarios"][0]["setup"][field] = value
                built = completion.build(bundle)
                self.assertFalse(built["notMeantChecked"][verdict])
                self.assertFalse(built["notMeantHolds"])

    def test_undeclared_or_live_guarantee_adapters_block_the_actual_bundle(self):
        original = cli.run_all
        for role, label in (("unlisted-role", "simulated undeclared adapter"),
                            ("registrar", "LiveRegistrarGateway")):
            with self.subTest(role=role):
                def changed(contracts):
                    report = original(contracts)
                    if contracts and contracts[0].scenario_id.startswith("GUARANTEE-"):
                        report["scenarios"][0]["setup"]["simulatedAdapters"] = {role: label}
                    return report

                with mock.patch.object(cli, "run_all", side_effect=changed):
                    bundle = cli._bundle(ROOT)
                self.assertFalse(bundle["reuse"]["complete"])
                self.assertFalse(bundle["reuse"]["allAdaptersSimulated"])
                self.assertFalse(bundle["completion"]["notMeantHolds"])
                self.assertFalse(bundle["allLocalPassed"])
                self.assertTrue(any(check["key"] == "completion"
                                    and check["verdict"] is False
                                    for check in bundle["consistencyChecks"]))


if __name__ == "__main__":
    unittest.main()
