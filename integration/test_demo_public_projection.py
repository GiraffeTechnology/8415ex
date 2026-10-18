"""Synthetic projection definitions only; execute on approved remote Linux."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from exchange.demo_public import run_record
from exchange.demo_ui import DemoHandler

PRIVATE = "private-wallet-account-and-session"
ADDRESS = "0x" + "a" * 40
KEY = "demo-" + "b" * 32


def original():
    row = {"scenarioId": "DEMO-02", "title": PRIVATE, "mainPath": "REG_ELECTRONIC",
           "setup": {"accounts": {"A": ADDRESS}, "origin": PRIVATE,
                     "prices": {"AB": 1000000}, "quoteAsset": "local-test-quote"},
           "steps": [{"index": 0, "name": PRIVATE,
                      "facts": {"owner": ADDRESS, "holder": PRIVATE, "ownerPosition": 4, "holderPosition": 1,
                                "principal": "1000000", "gasTotal": "21000", "gasUnit": "gas-units",
                                "paymentStatus": "unknown", "note": PRIVATE}}],
           "expectations": [{"name": PRIVATE, "cases": ["T-11", "T-36"], "outcome": "failed",
                             "expected": {"payer": ADDRESS, "principal": "1000000", "paymentStatus": "settled"},
                             "observed": {"payer": PRIVATE, "principal": "1000000", "paymentStatus": "unknown"},
                             "detail": PRIVATE}],
           "counts": {"passed": 0, "failed": 1, "blocked": 0, "not-run": 1},
           "passed": False, "error": PRIVATE, "notes": [PRIVATE]}
    return {"runId": KEY, "source": {"commit": "c" * 40, "tree": "d" * 40, "account": PRIVATE},
            "report": {"scenarios": [row], "allPassed": False, "totals": row["counts"]},
            "rawSignature": PRIVATE, "realEvidence": {"chain": "NOT_RUN"}}


class DemoPublicProjection(unittest.TestCase):
    def test_json_excludes_raw_accounts_sessions_titles_and_free_form_diagnostics(self):
        output = json.dumps(run_record(original()))
        self.assertNotIn(PRIVATE, output)
        self.assertNotIn(ADDRESS, output)
        self.assertNotIn("rawSignature", output)
        self.assertNotIn("accounts", output)

    def test_positions_principal_original_gas_unit_and_unknown_are_preserved(self):
        row = run_record(original())["report"]["scenarios"][0]
        facts = row["steps"][0]["facts"]
        self.assertEqual((facts["ownerPosition"], facts["holderPosition"]), (4, 1))
        self.assertEqual((facts["principal"], facts["gasTotal"], facts["gasUnit"]), ("1000000", "21000", "gas-units"))
        self.assertEqual(facts["paymentStatus"], "unknown")
        self.assertEqual(row["setup"]["quoteAsset"], "local-test-quote")

    def test_failed_assertion_error_and_not_run_remain_visible_without_inherited_pass(self):
        result = run_record(original())
        row = result["report"]["scenarios"][0]
        self.assertFalse(result["report"]["allPassed"])
        self.assertFalse(row["passed"])
        self.assertEqual(row["expectations"][0]["outcome"], "failed")
        self.assertEqual(row["expectations"][0]["cases"], ["T-11", "T-36"])
        self.assertEqual(row["counts"]["failed"], 1)
        self.assertEqual(row["counts"]["not-run"], 1)
        self.assertIsNotNone(row["error"])
        self.assertEqual(set(result["realEvidence"].values()), {"NOT_RUN"})

    def test_full_original_in_memory_is_not_redacted_rewritten_or_reexecuted(self):
        raw = original()
        before = deepcopy(raw)
        public = run_record(raw)
        public["report"]["scenarios"][0]["steps"][0]["facts"]["ownerPosition"] = 999
        self.assertEqual(raw, before)
        self.assertEqual(raw["report"]["scenarios"][0]["expectations"][0]["expected"]["payer"], ADDRESS)

    def test_actual_json_handler_dispatch_returns_projection_without_executing_scenario(self):
        bodies = []
        handler = SimpleNamespace(path="/evidence?id=" + KEY, host_ok=lambda: True,
            server=SimpleNamespace(runs={KEY: original()}), send_body=lambda *args: bodies.append(args))
        DemoHandler.do_GET(handler)
        self.assertEqual(bodies[0][0], 200)
        result = json.loads(bodies[0][1])
        self.assertEqual(result["schema"], "8415ex-public-demo/2")
        self.assertNotIn(PRIVATE, bodies[0][1])

    def test_actual_html_rendering_preserves_failure_and_discloses_projection_limits(self):
        handler = SimpleNamespace(shell=lambda body: body)
        raw = original()
        before = deepcopy(raw)
        html = DemoHandler.run_page(handler, raw, 1)
        self.assertNotIn(PRIVATE, html)
        self.assertNotIn(ADDRESS, html)
        self.assertIn("LOCAL FAILURE", html)
        self.assertIn("private original retains complete", html)
        self.assertIn("unknown", html)
        self.assertIn("Public projection for this run", html)
        self.assertEqual(raw, before)

    def test_malformed_run_identity_and_unknown_count_are_not_fake_validity_or_zero(self):
        raw = original()
        raw["report"]["totals"]["passed"] = PRIVATE
        self.assertIsNone(run_record(raw)["report"]["totals"]["passed"])
        raw["runId"] = PRIVATE
        with self.assertRaises(ValueError):
            run_record(raw)
