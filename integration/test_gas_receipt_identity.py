"""Synthetic multi-receipt accounting definitions; no native fee acceptance."""
import unittest
from dataclasses import replace

from exchange import fixtures as F
from exchange.errors import DomainError


class GasReceiptIdentityTests(unittest.TestCase):
    def setUp(self):
        self.exchange, self.clock = F.funded_chain_to_d()
        self.first = "rcpt-8415-0001"
        self.second = "receipt-other"
        original = F.receipt()
        asset = replace(original.asset, token_id=original.asset.token_id + 1)
        receipt = replace(original, receipt_id=self.second, asset=asset,
                          receipt_number="WR-OTHER")
        self.exchange.mint(receipt, specification=F.mint_specification(receipt))
        self.exchange.connect_wallet(F.A, "second-seller")
        self.exchange.connect_wallet(F.B, "second-buyer")
        self.exchange.register_authorization(F.authorization(
            F.A, "auth-other-sell", "second-seller", asset_override=asset))
        self.exchange.register_authorization(F.authorization(
            F.B, "auth-other-buy", "second-buyer", asset_override=asset))
        sell = self.exchange.submit_intent(replace(F.intent(
            "other-sell", "sell", F.A, "auth-other-sell", None, 99), asset=asset))
        buy = self.exchange.submit_intent(replace(F.intent(
            "other-buy", "buy", F.B, "auth-other-buy", None, 99), asset=asset))
        match = self.exchange.match_intents(sell.intent_id, buy.intent_id)
        escrow = self.exchange.lock_escrow(match, "escrow-other")
        self.exchange.execute_transfer(match, "transfer-other", escrow_id=escrow.escrow_id)
        self.tx = "0x" + "1" * 64

    def record(self, receipt, tx=None, amount=7, kind="trade"):
        return self.exchange.record_gas(receipt, 0, kind, amount,
                                       transaction_hash=self.tx if tx is None else tx)

    def total(self, receipt):
        return self.exchange.reconciliation(receipt)["segments"][0]["gasTotal"]

    def test_same_transaction_cannot_be_charged_to_another_receipt_even_identical_fields(self):
        self.record(self.first)
        before = len(self.exchange.receipt_timeline(self.second))
        with self.assertRaises(DomainError) as raised:
            self.record(self.second)
        self.assertEqual(raised.exception.code, "EX_GAS_TRANSACTION_CONFLICT")
        self.assertEqual(self.total(self.first), "7")
        self.assertEqual(self.total(self.second), "0")
        self.assertEqual(len(self.exchange.receipt_timeline(self.second)), before)

    def test_receipt_conflict_does_not_reassign_fee_or_allow_an_invented_batch_split(self):
        self.record(self.first)
        for changes in ({"amount": 3}, {"kind": "refund"}):
            with self.subTest(changes=changes), self.assertRaises(DomainError) as raised:
                self.record(self.second, **changes)
            self.assertEqual(raised.exception.code, "EX_GAS_TRANSACTION_CONFLICT")
        self.assertEqual(self.total(self.first), "7")
        self.assertEqual(self.total(self.second), "0")
        self.assertEqual(self.record(self.first)["amount"], 7)

    def test_distinct_transactions_for_other_receipts_remain_independent(self):
        self.record(self.first)
        other = "0x" + "2" * 64
        self.record(self.second, tx=other, amount=9)
        count = len(self.exchange.receipt_timeline(self.second))
        self.record(self.second, tx=other, amount=9)
        self.assertEqual(self.total(self.first), "7")
        self.assertEqual(self.total(self.second), "9")
        self.assertEqual(len(self.exchange.receipt_timeline(self.second)), count)

