"""Actual model submission decisions; no signature or real execution acceptance."""
from dataclasses import replace
import unittest

from exchange import fixtures as F, views
from exchange.errors import DomainError
from exchange.model import Asset


class IntentDecisionAudit(unittest.TestCase):
    def setUp(self):
        self.exchange, self.clock = F.minted()
        self.receipt_id = F.receipt().receipt_id
        self.exchange.connect_wallet(F.B, "session-b")
        self.exchange.register_authorization(F.authorization(F.B, "grant-b", "session-b"))
        self.intent = F.intent("audit-buy", "buy", F.B, "grant-b", None, 19)

    def decisions(self):
        return [e for e in self.exchange.receipt_timeline(self.receipt_id)
                if e["kind"] in ("intent-accepted", "intent-refused")]

    def test_scope_acceptance_is_recorded_once_and_reads_do_not_append(self):
        self.exchange.submit_intent(self.intent)
        decision = self.decisions()[0]
        self.assertEqual(decision["kind"], "intent-accepted")
        self.assertEqual(decision["detail"]["signedTermsDigest"], self.intent.digest)
        self.assertFalse(decision["detail"]["executionAuthorized"])
        self.assertFalse(decision["detail"]["tradeFormed"])
        self.assertFalse(decision["detail"]["financialEffects"])
        before = self.exchange.receipt_timeline(self.receipt_id)
        for _ in range(3):
            self.exchange.validate_intent(self.intent.intent_id)
            views.page(self.exchange, self.receipt_id, "receipt")
            self.exchange.submit_intent(self.intent)
        self.assertEqual(self.exchange.receipt_timeline(self.receipt_id), before)
        self.assertEqual(self.exchange.recorded_legs(self.receipt_id), 0)

    def test_current_refusal_carries_original_reason_without_forming_an_order(self):
        expired = replace(self.intent, expires_at=self.clock.now)
        self.exchange.submit_intent(expired)
        decision = self.decisions()[0]
        self.assertEqual(decision["kind"], "intent-refused")
        self.assertIn("EX_INTENT_EXPIRED", decision["detail"]["reasonCodes"])
        self.assertFalse(decision["detail"]["executionAuthorized"])
        self.assertFalse(self.exchange._order_books)
        self.assertEqual(self.exchange.recorded_legs(self.receipt_id), 0)

    def test_conflicting_repeat_is_a_refusal_and_preserves_original_terms(self):
        self.exchange.submit_intent(self.intent)
        changed = replace(self.intent, limit_price=self.intent.limit_price + 1)
        with self.assertRaises(DomainError) as caught:
            self.exchange.submit_intent(changed)
        self.assertEqual(caught.exception.code, "EX_INTENT_CONFLICT")
        self.assertEqual(self.exchange.intent(self.intent.intent_id), self.intent)
        decision = self.decisions()[-1]
        self.assertEqual(decision["kind"], "intent-refused")
        self.assertEqual(decision["detail"]["reasonCodes"], ["EX_INTENT_CONFLICT"])
        self.assertEqual(decision["detail"]["signedTermsDigest"], self.intent.digest)
        self.assertEqual(decision["detail"]["attemptedTermsDigest"], changed.digest)

    def test_unknown_asset_does_not_invent_a_known_receipt_correlation(self):
        before = self.exchange.receipt_timeline(self.receipt_id)
        other = replace(self.intent, asset=Asset(11155111, "0x" + "2" * 40, 77))
        self.exchange.submit_intent(other)
        self.assertIn("EX_ASSET_UNKNOWN", self.exchange.validate_intent(other.intent_id)["reasons"])
        self.assertEqual(self.exchange.receipt_timeline(self.receipt_id), before)
