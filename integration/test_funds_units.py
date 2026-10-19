"""Dimension and responsibility regressions; synthetic model, not chain evidence."""
import unittest
from exchange import fixtures as F

R = "rcpt-8415-0001"


class FundsUnits(unittest.TestCase):
    def prepared(self, outcomes=None):
        exchange, _ = F.rollback_chain_to_d(outcomes=outcomes)
        requests = F.submit_all(exchange)
        F.refuse(exchange, requests[0], "units-refusal")
        exchange.begin_rollback(R, 0, F.rollback_authority(exchange, 0, "units-return"))
        return exchange

    def test_refund_principal_is_not_reduced_by_larger_eth_wei_fee(self):
        exchange = self.prepared()
        fee = F.PRICE_AB + 10 ** 18
        exchange.record_gas(R, 0, "return", fee)
        row = exchange.advance_rollback(R)["funds"][0]
        self.assertTrue(row["refundedToOriginalBuyer"])
        self.assertEqual(row["netToOriginalBuyer"], str(F.PRICE_AB))
        self.assertEqual(row["principalAsset"], F.QUOTE_ASSET)
        self.assertEqual(row["principalUnit"], "base-units")
        self.assertEqual((row["gasAsset"], row["gasUnit"], row["gasTotal"]),
                         ("ETH", "wei", str(fee)))

    def test_unknown_refund_never_reports_principal_paid_or_restores_gas(self):
        exchange = self.prepared({"refund:escrow-ab": "unknown"})
        exchange.record_gas(R, 0, "failed-attempt", 21000)
        row = exchange.advance_rollback(R)["funds"][0]
        self.assertEqual(row["paymentStatus"], "unknown")
        self.assertFalse(row["refundedToOriginalBuyer"])
        self.assertEqual(row["netToOriginalBuyer"], "0")
        self.assertEqual(row["gasTotal"], "21000")
        self.assertEqual(exchange.rollback_report(R)["funds"][0]["gasTotal"], "21000")

    def test_reconciliation_preserves_each_buyer_and_separate_units(self):
        exchange = self.prepared()
        exchange.record_gas(R, 1, "registration", 40000)
        rows = exchange.reconciliation(R)["segments"]
        self.assertEqual([r["gasBorneBy"] for r in rows], [F.B, F.C, F.D])
        self.assertEqual([r["gasTotal"] for r in rows], ["0", "40000", "0"])
        for row in rows:
            self.assertEqual((row["principalAsset"], row["principalUnit"]),
                             (F.QUOTE_ASSET, "base-units"))
            self.assertEqual((row["gasAsset"], row["gasUnit"]), ("ETH", "wei"))

    def test_record_names_gas_currency_chain_unit_and_original_buyer(self):
        exchange = self.prepared()
        entry = exchange.record_gas(R, 2, "refund-attempt", 31000)
        self.assertEqual((entry["asset"], entry["unit"], entry["chainId"]),
                         ("ETH", "wei", F.CHAIN_ID))
        self.assertEqual(entry["bearer"], F.D)
        self.assertEqual(entry["amount"], 31000)
