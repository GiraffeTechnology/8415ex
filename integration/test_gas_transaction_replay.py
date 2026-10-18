"""Synthetic domain accounting definitions; no receipt/provider acceptance."""
import unittest

from exchange import fixtures as F
from exchange.errors import DomainError


class GasTransactionReplayTests(unittest.TestCase):
    def setUp(self):
        self.exchange, self.clock = F.funded_chain_to_d()
        self.receipt = "rcpt-8415-0001"
        self.tx = "0x" + "1" * 64

    def record(self, amount=7, leg=0, kind="trade", shared=(), tx=None):
        return self.exchange.record_gas(self.receipt, leg, kind, amount,
            shared_with=shared, transaction_hash=self.tx if tx is None else tx)

    def total(self, leg=0):
        return self.exchange.reconciliation(self.receipt)["segments"][leg]["gasTotal"]

    def test_same_actual_transaction_replay_records_fee_and_event_once(self):
        first = self.record()
        count = len(self.exchange.receipt_timeline(self.receipt))
        second = self.record()
        self.assertEqual(second, first)
        self.assertEqual(self.total(), "7")
        self.assertEqual(len(self.exchange.receipt_timeline(self.receipt)), count)
        self.assertEqual(self.exchange.escrow_for_leg(self.receipt, 0).gas_total, 7)

    def test_reused_transaction_cannot_change_amount_kind_or_buyer_responsibility(self):
        self.record()
        for fields in ({"amount": 8}, {"kind": "refund"}, {"leg": 1}, {"shared": (1,)}):
            with self.subTest(fields=fields), self.assertRaises(DomainError) as error:
                self.record(**fields)
            self.assertEqual(error.exception.code, "EX_GAS_TRANSACTION_CONFLICT")
        self.assertEqual(self.total(), "7")
        self.assertEqual(self.total(1), "0")

    def test_distinct_shared_retry_transactions_each_count_once_without_invented_split(self):
        self.record(shared=(1,))
        self.record(amount=9, shared=(1,), tx="0x" + "2" * 64)
        self.record(amount=9, shared=(1,), tx="0x" + "2" * 64)
        report = self.exchange.reconciliation(self.receipt)
        self.assertEqual(report["segments"][0]["gasTotal"], "16")
        self.assertEqual(report["segments"][1]["gasTotal"], "0")
        self.assertEqual(report["segments"][0]["principal"], str(F.PRICE_AB))
        self.assertEqual(report["segments"][0]["gasAsset"], "ETH")
        self.assertEqual(report["segments"][0]["gasUnit"], "wei")
        self.assertTrue(all(e["apportionment"] == "undecided"
                            for e in report["segments"][0]["gasEntries"]))

    def test_returned_rows_and_escrow_reads_cannot_rewrite_recorded_fee(self):
        returned = self.record()
        returned["amount"] = 999
        report = self.exchange.reconciliation(self.receipt)
        report["segments"][0]["gasEntries"][0]["amount"] = 888
        escrow = self.exchange.escrow_for_leg(self.receipt, 0)
        escrow.gas_record[0]["amount"] = 777
        by_id = self.exchange.escrow(escrow.escrow_id)
        by_id.gas_record[0]["amount"] = 666
        self.assertEqual(self.total(), "7")
        self.assertEqual(self.exchange.escrow_for_leg(self.receipt, 0).gas_total, 7)
        self.assertEqual(self.record()["amount"], 7)

    def test_legacy_shared_record_does_not_allow_an_ambiguous_second_charge(self):
        self.exchange.record_gas(self.receipt, 0, "trade", 7, shared_with=(1,))
        with self.assertRaises(DomainError) as error:
            self.record(shared=(1,))
        self.assertEqual(error.exception.code, "EX_GAS_DOUBLE_CHARGE_REFUSED")
        self.assertEqual(self.total(), "7")

    def test_malformed_transaction_identity_cannot_create_an_accounting_row(self):
        for tx in ("", "0x123", "0x" + "G" * 64, True):
            with self.subTest(tx=tx), self.assertRaises(DomainError) as error:
                self.record(tx=tx)
            self.assertEqual(error.exception.code, "EX_GAS_TRANSACTION_REFUSED")
        self.assertEqual(self.total(), "0")
