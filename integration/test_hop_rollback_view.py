"""Read-only reverse-hop projection and six-locale rendering definitions."""
from copy import deepcopy
import json
import unittest

from exchange import fixtures as F
from exchange.hop_rollback_projection import project_hop_progress, HopProjectionRefused
from exchange.rollback_page import render_rollback, HOP_TEXT
from exchange.rollback_projection import rollback_projection
from exchange.tests.test_rollback import refused_at_ab


RECEIPT = "rcpt-8415-0001"


class HopRollbackViewTests(unittest.TestCase):
    def opened(self):
        exchange, _, _ = refused_at_ab()
        state = exchange.begin_rollback(RECEIPT, 0,
                    F.rollback_authority(exchange, 0, "private-sequence-authority"))
        return exchange, state

    def test_partial_cursor_and_positions_come_from_the_same_original_report(self):
        exchange, state = self.opened()
        exchange.advance_rollback(RECEIPT, max_asset_hops=1)
        value = rollback_projection(exchange, RECEIPT)
        progress = value["hopProgress"]
        self.assertEqual((progress["cursor"], progress["count"]), (1, 3))
        self.assertEqual([(h["fromPosition"], h["toPosition"]) for h in progress["hops"]],
                         [(3, 2), (2, 1), (1, 0)])
        self.assertEqual([h["status"] for h in progress["hops"]], ["done", "pending", "pending"])
        self.assertFalse(value["domainReportedComplete"])
        self.assertFalse(value["assetReturned"])
        self.assertEqual(value["ownerPosition"], 2)

    def test_unknown_is_visible_and_does_not_look_like_failure_or_done(self):
        exchange, state = self.opened()
        exchange.asset_control._outcomes[state["assetHops"][0]["key"]] = "unknown"
        exchange.advance_rollback(RECEIPT)
        value = rollback_projection(exchange, RECEIPT)
        self.assertEqual(value["hopProgress"]["cursor"], 0)
        self.assertEqual([h["status"] for h in value["hopProgress"]["hops"]],
                         ["unknown", "pending", "pending"])
        self.assertFalse(value["domainReportedComplete"])

    def test_projection_excludes_accounts_authority_keys_and_result_references(self):
        exchange, state = self.opened()
        exchange.advance_rollback(RECEIPT, max_asset_hops=1)
        value = rollback_projection(exchange, RECEIPT)
        text = json.dumps(value)
        for private in (F.A, F.B, F.C, F.D, "private-sequence-authority", state["sequenceId"],
                        state["assetHops"][0]["key"], "sim-return:"):
            self.assertNotIn(private, text)
        self.assertTrue(value["hopProgress"]["hops"][0]["hasResultReference"])

    def test_path_cursor_and_result_substitution_are_refused(self):
        exchange, state = self.opened()
        exchange.advance_rollback(RECEIPT, max_asset_hops=1)
        original = exchange.rollback_report(RECEIPT)
        for change in ("cursor", "path", "key", "missing-reference", "leg"):
            report = deepcopy(original)
            if change == "cursor": report["hopCursor"] = 2
            if change == "path": report["assetHops"][1]["fromPosition"] = 3
            if change == "key": report["hopResults"][0]["key"] = "another-key"
            if change == "missing-reference": report["hopResults"][0]["detail"]["reference"] = None
            if change == "leg": report["assetHops"][0]["legIndex"] = 0
            with self.subTest(change=change), self.assertRaises(HopProjectionRefused):
                project_hop_progress(report)

    def test_false_complete_with_partial_cursor_is_inconsistent(self):
        exchange, state = self.opened()
        exchange.advance_rollback(RECEIPT, max_asset_hops=1)
        report = exchange.rollback_report(RECEIPT)
        report["complete"] = True
        self.assertFalse(project_hop_progress(report)["consistent"])

    def test_legacy_observation_is_missing_progress_instead_of_zero_hop_success(self):
        exchange, state = self.opened()
        report = exchange.rollback_report(RECEIPT)
        for name in ("assetHops", "hopCursor", "sequenceId", "hopResults"):
            report.pop(name)
        value = project_hop_progress(report)
        self.assertFalse(value["available"])
        self.assertIsNone(value["cursor"])
        self.assertEqual(value["hops"], [])

    def test_all_six_locales_show_read_only_partial_progress(self):
        exchange, state = self.opened()
        exchange.advance_rollback(RECEIPT, max_asset_hops=1)
        before = deepcopy(state)
        self.assertEqual(set(HOP_TEXT), {"en", "zh-Hans", "zh-Hant", "fr", "es", "ja"})
        for locale, labels in HOP_TEXT.items():
            with self.subTest(locale=locale):
                body = render_rollback(exchange, RECEIPT, locale=locale)
                self.assertIn('data-hop-progress="1"', body)
                self.assertIn(labels[0], body)
                self.assertIn("1 / 3", body)
                self.assertNotIn("<form", body)
                for account in (F.A, F.B, F.C, F.D):
                    self.assertNotIn(account, body)
        self.assertEqual(state, before)
        self.assertEqual(exchange.asset_control.returns, 1)

    def test_complete_domain_hops_still_do_not_claim_native_or_chain_acceptance(self):
        exchange, state = self.opened()
        exchange.advance_rollback(RECEIPT)
        value = rollback_projection(exchange, RECEIPT)
        self.assertTrue(value["domainReportConsistent"])
        self.assertEqual(value["hopProgress"]["cursor"], 3)
        self.assertFalse(value["nativeCompletionVerified"])
        self.assertEqual(value["chainAcceptance"], "NOT_RUN")
