"""Authored synthetic persistence integration; never runs a native operation."""
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import unittest

from exchange.aggregate_checkpoint import AggregateCheckpointStore, CheckpointRefused
from exchange.fixtures import A, B, receipt
from exchange.ledger import Transfer
from exchange.model import Asset
from exchange.receipt_fact_checkpoint import ReceiptFactCheckpoint, ReceiptFactCheckpointRefused
from exchange.registration import RegistrationRequest, RegistrationEvidence
from exchange.rollback import RollbackStep
from exchange.settlement import EscrowPosition


class ReceiptFactCheckpointTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "checkpoint.db"
        self.db = self.connection()
        AggregateCheckpointStore.initialize(self.db)
        self.original = receipt(allowed_currencies=("USD", "ETH"))
        self.transfer = Transfer("transfer-1", self.original.receipt_id, 0, A, B, None, 103,
                                 "USD", "0x" + "1" * 64, "0x" + "2" * 64,
                                 "sell-auth", "buy-auth", 10,
                                 registration_status="confirmed", funding_status="release-outcome-unknown")
        self.request = RegistrationRequest("request-1", self.original.receipt_id, "transfer-1", 0,
                                           None, "REG_DIRECT", self.original.asset, 10, 100)
        self.evidence = RegistrationEvidence("result-1", "request-1", self.original.receipt_id,
                                             "transfer-1", 0, "REG_DIRECT", "original-source",
                                             "confirmed", self.original.asset, 20)
        self.escrow = EscrowPosition("escrow-1", self.original.receipt_id, 0, B, A, "USD", 103,
                                     payment_key="original-payment", payment_status="unknown",
                                     payment_intent="release", gas_record=({"amount": 7, "asset": "ETH"},))
        self.facts = {"transfers": (self.transfer,), "registrationRequests": (self.request,),
                      "registrationEvidence": (self.evidence,), "escrows": (self.escrow,),
                      "rollbackSteps": ()}

    def connection(self):
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA synchronous=FULL")
        self.addCleanup(db.close)
        return db

    def adapter(self, db=None):
        return ReceiptFactCheckpoint(AggregateCheckpointStore(db or self.db,
            components=("declaration", "operations"), source_commit="a" * 40, source_tree="b" * 40))

    def test_receipt_and_unknown_operational_facts_reopen_as_one_generation(self):
        result = self.adapter().save(self.original, self.facts, expected_generation=0)
        self.assertEqual(result["generation"], 1)
        read = self.adapter(self.connection()).read(self.original.receipt_id, expected_asset=self.original.asset)
        self.assertEqual(read["receipt"], self.original)
        self.assertEqual(read["facts"], self.facts)
        self.assertEqual(read["facts"]["escrows"][0].payment_status, "unknown")
        self.assertFalse(read["executionAuthorized"])
        self.assertFalse(read["completeExchangeRecovery"])

    def test_cross_receipt_request_asset_or_observation_binding_never_writes(self):
        for group, changed in (
            ("escrows", replace(self.escrow, receipt_id="other-receipt")),
            ("registrationRequests", replace(self.request, asset=Asset(11155111, "0x" + "1" * 40, 99))),
            ("registrationEvidence", replace(self.evidence, request_id="other-request")),
        ):
            with self.subTest(group=group), self.assertRaises(ReceiptFactCheckpointRefused):
                self.adapter().save(self.original, dict(self.facts, **{group: (changed,)}), expected_generation=0)
        self.assertIsNone(self.adapter().read(self.original.receipt_id, expected_asset=self.original.asset))

    def test_segment_amount_party_currency_and_duplicate_occurrences_refused(self):
        for changed in (replace(self.escrow, principal=104), replace(self.escrow, payer=A, payee=B),
                        replace(self.escrow, quote_asset="ETH")):
            with self.subTest(position=changed), self.assertRaises(ReceiptFactCheckpointRefused):
                self.adapter().save(self.original, dict(self.facts, escrows=(changed,)), expected_generation=0)
        with self.assertRaises(ReceiptFactCheckpointRefused):
            self.adapter().save(self.original, dict(self.facts, transfers=(self.transfer, self.transfer)), expected_generation=0)

    def test_missing_groups_and_dangling_predecessor_leave_old_generation_intact(self):
        self.adapter().save(self.original, self.facts, expected_generation=0)
        invalid = dict(self.facts); del invalid["rollbackSteps"]
        for candidate in (invalid, dict(self.facts, transfers=(replace(self.transfer, predecessor_transfer_id="missing"),))):
            with self.assertRaises(ReceiptFactCheckpointRefused):
                self.adapter().save(self.original, candidate, expected_generation=1)
        self.assertEqual(self.adapter().read(self.original.receipt_id, expected_asset=self.original.asset)["generation"], 1)

    def test_stale_writer_cannot_mix_new_declaration_and_old_operational_state(self):
        first = self.adapter(); second = self.adapter(self.connection())
        first.save(self.original, self.facts, expected_generation=0)
        updated = replace(self.original, commodity_name="Updated original declaration")
        with self.assertRaises(CheckpointRefused):
            second.save(updated, self.facts, expected_generation=0)
        recovered = first.read(self.original.receipt_id, expected_asset=self.original.asset)
        self.assertEqual(recovered["receipt"], self.original)
        self.assertEqual(recovered["facts"], self.facts)

    def test_expected_asset_and_embedded_receipt_identity_are_rechecked_on_read(self):
        adapter = self.adapter(); adapter.save(self.original, self.facts, expected_generation=0)
        with self.assertRaises(ReceiptFactCheckpointRefused):
            adapter.read(self.original.receipt_id, expected_asset=Asset(11155111, "0x" + "1" * 40, 99))
        self.db.execute("UPDATE ex_aggregate_checkpoint SET scope='different-receipt'")
        self.db.commit()
        with self.assertRaises(ReceiptFactCheckpointRefused):
            adapter.read("different-receipt", expected_asset=self.original.asset)

    def test_blocked_original_rollback_step_stays_blocked_and_mutable_inputs_detach(self):
        step = RollbackStep("refund-1", "refund", self.original.receipt_id, 0, "original-refund", "blocked")
        facts = dict(self.facts, rollbackSteps=(step,),
                     escrows=(replace(self.escrow, payment_intent="refund"),))
        adapter = self.adapter(); adapter.save(self.original, facts, expected_generation=0)
        self.escrow.gas_record[0]["amount"] = 999
        result = adapter.read(self.original.receipt_id, expected_asset=self.original.asset)
        self.assertEqual(result["facts"]["escrows"][0].gas_record[0]["amount"], 7)
        self.assertEqual(result["facts"]["rollbackSteps"][0].status, "blocked")
        self.assertEqual(result["nativeReconciliation"], "NOT_PERFORMED")

    def test_released_or_unknown_release_prefix_cannot_be_stored_as_refund_work(self):
        step = RollbackStep("refund-1", "refund", self.original.receipt_id, 0, "original-refund")
        for position in (self.escrow, replace(self.escrow, status="released", payment_status="settled")):
            with self.subTest(position=position), self.assertRaises(ReceiptFactCheckpointRefused):
                self.adapter().save(self.original, dict(self.facts, escrows=(position,), rollbackSteps=(step,)),
                                    expected_generation=0)

    def test_correct_generation_cannot_replace_the_receipts_original_asset(self):
        adapter = self.adapter()
        adapter.save(self.original, self.facts, expected_generation=0)
        before = self.db.execute("SELECT * FROM ex_aggregate_checkpoint").fetchall()
        other_asset = Asset(self.original.asset.chain_id, self.original.asset.contract, 99)
        other_receipt = replace(self.original, asset=other_asset)
        other_facts = dict(self.facts,
            registrationRequests=(replace(self.request, asset=other_asset),),
            registrationEvidence=(replace(self.evidence, asset=other_asset),))
        with self.assertRaises(ReceiptFactCheckpointRefused):
            adapter.save(other_receipt, other_facts, expected_generation=1)
        self.assertEqual(self.db.execute("SELECT * FROM ex_aggregate_checkpoint").fetchall(), before)
        recovered = adapter.read(self.original.receipt_id, expected_asset=self.original.asset)
        self.assertEqual(recovered["generation"], 1)
        self.assertEqual(recovered["receipt"], self.original)
        self.assertEqual(recovered["facts"], self.facts)

    def test_correct_generation_cannot_rewrite_minted_terms_or_currency_declaration(self):
        adapter = self.adapter()
        adapter.save(self.original, self.facts, expected_generation=0)
        before = self.db.execute("SELECT * FROM ex_aggregate_checkpoint").fetchall()
        for changed in (
                replace(self.original, commodity_name="Different minted terms"),
                replace(self.original, allowed_price_currencies=("USD",)),
                replace(self.original, nft0_currency_reference="different-original-reference")):
            with self.subTest(receipt=changed), self.assertRaises(ReceiptFactCheckpointRefused):
                adapter.save(changed, self.facts, expected_generation=1)
            self.assertEqual(self.db.execute("SELECT * FROM ex_aggregate_checkpoint").fetchall(), before)
        recovered = adapter.read(self.original.receipt_id, expected_asset=self.original.asset)
        self.assertEqual(recovered["generation"], 1)
        self.assertEqual(recovered["receipt"], self.original)

    def test_same_declaration_can_advance_operational_facts_without_resolving_unknown(self):
        adapter = self.adapter()
        adapter.save(self.original, self.facts, expected_generation=0)
        changed = dict(self.facts, escrows=(replace(self.escrow,
            gas_record=({"amount": 9, "asset": "ETH"},)),))
        saved = adapter.save(self.original, changed, expected_generation=1)
        self.assertEqual(saved["generation"], 2)
        recovered = self.adapter(self.connection()).read(self.original.receipt_id,
                                                        expected_asset=self.original.asset)
        self.assertEqual(recovered["receipt"], self.original)
        self.assertEqual(recovered["facts"], changed)
        self.assertEqual(recovered["facts"]["escrows"][0].payment_status, "unknown")
        self.assertFalse(recovered["executionAuthorized"])
        self.assertFalse(recovered["completeExchangeRecovery"])
