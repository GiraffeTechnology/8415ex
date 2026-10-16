"""Acceptance checks for local-only deterministic scenario orchestration."""
import contextlib
import io
import json
import unittest
from exchange import fixtures as F
from exchange import stage5 as S

class ScenarioContracts(unittest.TestCase):
    def scenario(self, name):
        result = S.run_scenario(name)
        self.assertEqual(result["status"], "passed", result.get("failure"))
        self.assertTrue(result["simulated"])
        self.assertTrue(all(v == "NOT_RUN" for v in result["realEvidence"].values()))
        self.assertTrue(result["observed"]["receipt"]["simulatedRegistration"])
        return result

    def test_single_sale_and_separate_exit_records(self):
        result = self.scenario("DEMO-01")
        observed = result["observed"]
        self.assertEqual(observed["receipt"]["owner"]["account"], F.B)
        self.assertEqual(observed["receipt"]["holder"]["account"], F.B)
        self.assertEqual(len(observed["exit"]["distinctCompletionInstants"]), 4)
        self.assertEqual(observed["funds"]["segments"][0]["netToPayee"], str(F.PRICE_AB))
        self.assertTrue(observed["exit"]["historyPreserved"])

    def test_serial_registration_and_prefix_release_before_d(self):
        result = self.scenario("DEMO-02")
        prefix = result["checkpoints"][0]
        self.assertEqual(prefix["receipt"]["owner"]["account"], F.D)
        self.assertEqual(prefix["receipt"]["holder"]["account"], F.B)
        self.assertEqual([s["released"] for s in prefix["funds"]["segments"]], [True, False, False])
        self.assertEqual([s["principal"] for s in result["observed"]["funds"]["segments"]],
                         ["1000000", "1250000", "900000"])

    def test_b_refusal_refunds_original_buyers(self):
        result = self.scenario("DEMO-03")
        self.assertEqual(result["observed"]["receipt"]["owner"]["account"], F.A)
        self.assertEqual([s["buyer"] for s in result["observed"]["funds"]["segments"]], [F.B, F.C, F.D])
        self.assertTrue(all(s["refunded"] and not s["released"] for s in result["observed"]["funds"]["segments"]))

    def test_c_refusal_preserves_ab_payment(self):
        result = self.scenario("DEMO-04")
        segments = result["observed"]["funds"]["segments"]
        self.assertEqual(result["observed"]["receipt"]["owner"]["account"], F.B)
        self.assertEqual(segments[0]["netToPayee"], str(F.PRICE_AB))
        self.assertEqual([s["refunded"] for s in segments], [False, True, True])

    def test_shortfall_blocks_and_recovers_without_custody(self):
        result = self.scenario("DEMO-05")
        blocked = result["checkpoints"][0]["rollback"]
        self.assertEqual(blocked["state"], "blocked")
        self.assertFalse(blocked["complete"])
        self.assertTrue(result["observed"]["rollback"]["complete"])
        self.assertIn("not queried", result["fixtureConditions"]["ordinaryWalletETH"])

    def test_cutoff_inflight_and_eligible_exit_are_distinct(self):
        result = self.scenario("DEMO-06")
        before = result["checkpoints"][0]["beforeCutoffRefusal"]["receipt"]
        self.assertEqual(before["recordedLegs"], 1)
        self.assertFalse(before["tradingOpen"])
        self.assertTrue(result["observed"]["exit"]["burned"])

    def test_repeated_run_is_canonical_and_deterministic(self):
        for scenario in S.SCENARIOS:
            with self.subTest(scenario=scenario):
                first = json.dumps(S.run_scenario(scenario), sort_keys=True)
                second = json.dumps(S.run_scenario(scenario), sort_keys=True)
                self.assertEqual(first, second)

    def test_unrecognized_scenario_or_path_is_refused(self):
        for scenario, path in (("unrecognized", None), ("DEMO-01", "other")):
            with self.assertRaises(ValueError):
                S.run_scenario(scenario, path)

    def test_cli_emits_six_results_and_local_evidence_kind(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = S.main([])
        self.assertEqual(status, 0)
        payload = json.loads(output.getvalue())
        self.assertEqual(payload["evidenceKind"], "LOCAL_SIMULATION")
        self.assertEqual(len(payload["results"]), 6)
        self.assertTrue(all(r["status"] == "passed" for r in payload["results"]))
