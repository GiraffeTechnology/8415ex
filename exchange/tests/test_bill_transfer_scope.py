"""v1.2 T-25/T-32/T-33: bill terms remain; physical operations are retired.

These are local model regressions, not chain or complete Stage 4 acceptance.
"""
import copy
import unittest

from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.exit import EXIT_STEPS

RECEIPT = "rcpt-8415-0001"


class BillTransferScope(unittest.TestCase):
    def setUp(self):
        self.exchange, self.clock = F.exit_exchange()

    def test_terms_survive_without_collection_or_burn(self):
        original = self.exchange.receipt_view(RECEIPT)
        timeline = copy.deepcopy(self.exchange.receipt_timeline(RECEIPT))
        view = self.exchange.bill_of_lading_view(RECEIPT)
        self.assertEqual(view["receipt"], original)
        self.assertEqual(view["prdVersion"], "1.2")
        self.assertEqual(view["scope"], "bill-of-lading-transfer")
        self.assertEqual(view["physicalActions"], ())
        self.assertTrue(view["historyPreserved"])
        self.assertEqual(timeline, self.exchange.receipt_timeline(RECEIPT))

    def test_full_legacy_grant_and_checks_cannot_start_retired_flow(self):
        before = copy.deepcopy(self.exchange.receipt_timeline(RECEIPT))
        F.redeem_authorization(self.exchange, F.A, session_id="session-a")
        for operation in (
                lambda: self.exchange.request_redemption(
                    RECEIPT, F.A, "auth-redeem", "retired-request", F.ALL_CHECKS),
                lambda: self.exchange.advance_exit(RECEIPT, through="burn"),
                lambda: self.exchange._replace_leg_free_burn(RECEIPT)):
            with self.assertRaises(DomainError) as caught:
                operation()
            self.assertEqual(caught.exception.code, "EX_PHYSICAL_FULFILLMENT_RETIRED")
        self.assertIsNone(self.exchange._exits[RECEIPT])
        self.assertEqual(before, self.exchange.receipt_timeline(RECEIPT))

    def test_direct_desk_cannot_bypass_exchange_retirement(self):
        desk = self.exchange.voucher_desk
        for step in EXIT_STEPS:
            key = "retired-" + step
            with self.assertRaises(DomainError) as caught:
                desk.act(key, step, RECEIPT, F.A)
            self.assertEqual(caught.exception.code, "EX_PHYSICAL_FULFILLMENT_RETIRED")
            self.assertIsNone(desk.lookup(key))
            self.assertEqual(desk.history(key), ())

    def test_retirement_is_not_an_owner_holder_trading_gate(self):
        F.funded_hop(self.exchange, F.A, F.B, 1, "transfer-ab",
                     "session-a", "session-b", price=F.PRICE_AB)
        report = self.exchange.redemption_readiness(RECEIPT, F.B)
        self.assertFalse(report["eligible"])
        self.assertEqual(report["reasons"], ("EX_PHYSICAL_FULFILLMENT_RETIRED",))
        self.assertNotIn("furtherChecksNotPerformedHere", report)
        F.funded_hop(self.exchange, F.B, F.C, 2, "transfer-bc",
                     "session-b", "session-c", price=F.PRICE_BC)
        view = self.exchange.bill_of_lading_view(RECEIPT)["receipt"]
        self.assertEqual(view["owner"]["account"], F.C)
        self.assertEqual(view["holder"]["account"], F.A)
        self.assertEqual(view["recordedLegs"], 2)

    def test_unknown_historical_effect_stays_queryable_without_new_attempt(self):
        desk = self.exchange.voucher_desk
        key = "historical-unknown"
        record = {"key": key, "step": "burn", "receiptId": RECEIPT,
                  "account": F.A, "status": "unknown", "attempt": 1,
                  "effect": "unknown", "retryable": False}
        desk._records[key] = dict(record)
        desk._history[key] = [dict(record)]
        with self.assertRaises(DomainError):
            desk.act(key, "burn", RECEIPT, F.A)
        self.assertEqual(desk.lookup(key), record)
        self.assertEqual(desk.history(key), (record,))
        resolved = desk.resolve_unknown(key, "failed")
        self.assertEqual(resolved["status"], "failed")
        with self.assertRaises(DomainError):
            desk.act(key, "burn", RECEIPT, F.A)
        self.assertEqual(len(desk.history(key)), 2)


if __name__ == "__main__":
    unittest.main()
