"""Synthetic file-backed snapshots; definitions await approved remote QA."""
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import unittest

from exchange.aggregate_checkpoint import AggregateCheckpointStore, CheckpointRefused, CheckpointCommitUnknown
from exchange.exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint, ExchangeCheckpointRefused
from exchange.exchange_fact_snapshot import encode_exchange_snapshot
from exchange.fixtures import A
from exchange.ledger import Exchange
from integration.test_mint_specification_codec import specification


class ExchangeSnapshotCheckpointTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "snapshot.db"
        self.db = self.connect()
        AggregateCheckpointStore.initialize(self.db)
        self.exchange = Exchange(lambda: 20, mint_verifier=lambda kind, evidence: True)
        spec = specification()
        self.exchange.mint(spec.receipt, spec)
        self.exchange._used_nonces.add((A, 7))
        self.original = encode_exchange_snapshot(self.exchange)

    def connect(self, factory=sqlite3.Connection):
        db = sqlite3.connect(self.path, factory=factory)
        db.execute("PRAGMA synchronous=FULL")
        self.addCleanup(db.close)
        return db

    def store(self, db=None, cls=AggregateCheckpointStore, **override):
        args = dict(components=("owned-facts",), source_commit="a" * 40, source_tree="b" * 40)
        args.update(override)
        return cls(db or self.db, **args)

    def test_complete_snapshot_survives_reopen_without_authority(self):
        result = ExchangeSnapshotCheckpoint(self.store()).save("original-instance", self.original, expected_generation=0)
        self.assertEqual(result["generation"], 1)
        self.assertFalse(result["completeRecovery"])
        row = ExchangeSnapshotCheckpoint(self.store(self.connect())).read("original-instance")
        self.assertEqual(row["components"]["owned-facts"], self.original)
        self.assertEqual(row["facts"].wallet["usedNonces"], frozenset(((A, 7),)))
        self.assertFalse(row["executionAuthorized"])

    def test_existing_receipt_terms_cannot_change_at_correct_generation(self):
        checkpoint = ExchangeSnapshotCheckpoint(self.store())
        checkpoint.save("original-instance", self.original, expected_generation=0)
        self.exchange._receipts["receipt-1"] = replace(self.exchange._receipts["receipt-1"], commodity_name="Changed terms")
        candidate = encode_exchange_snapshot(self.exchange)
        with self.assertRaises(ExchangeCheckpointRefused):
            checkpoint.save("original-instance", candidate, expected_generation=1)
        row = checkpoint.read("original-instance")
        self.assertEqual(row["generation"], 1)
        self.assertEqual(row["components"]["owned-facts"], self.original)

    def test_new_receipt_can_be_appended_without_replacing_original(self):
        checkpoint = ExchangeSnapshotCheckpoint(self.store())
        checkpoint.save("original-instance", self.original, expected_generation=0)
        spec = specification()
        receipt = replace(spec.receipt, receipt_id="receipt-2", receipt_number="warehouse-2",
                          asset=replace(spec.receipt.asset, token_id=8))
        second = replace(spec, receipt=receipt, bill_of_lading_number="bill-2",
                         original_document_mapping="document-map-2", controlled_access_mapping="controlled-map-2")
        self.exchange.mint(receipt, second)
        checkpoint.save("original-instance", encode_exchange_snapshot(self.exchange), expected_generation=1)
        row = checkpoint.read("original-instance")
        self.assertEqual(row["generation"], 2)
        self.assertEqual(set(row["facts"].receipts), {"receipt-1", "receipt-2"})

    def test_consumed_nonce_and_history_prefix_cannot_disappear(self):
        checkpoint = ExchangeSnapshotCheckpoint(self.store())
        checkpoint.save("original-instance", self.original, expected_generation=0)
        self.exchange._used_nonces.clear()
        with self.assertRaises(ExchangeCheckpointRefused):
            checkpoint.save("original-instance", encode_exchange_snapshot(self.exchange), expected_generation=1)
        self.exchange._used_nonces.add((A, 7))
        self.exchange._events["receipt-1"].clear()
        with self.assertRaises(ExchangeCheckpointRefused):
            checkpoint.save("original-instance", encode_exchange_snapshot(self.exchange), expected_generation=1)
        self.assertEqual(checkpoint.read("original-instance")["generation"], 1)

    def test_intervening_writer_is_rejected_by_original_transactional_cas(self):
        winner = self.store(self.connect())
        class InterposedWriter(AggregateCheckpointStore):
            def save(inner, scope, values, *, expected_generation, **kwargs):
                if expected_generation == 1:
                    winner.save(scope, {"owned-facts": self.original}, expected_generation=1)
                return super().save(scope, values, expected_generation=expected_generation, **kwargs)
        checkpoint = ExchangeSnapshotCheckpoint(self.store(cls=InterposedWriter))
        checkpoint.save("original-instance", self.original, expected_generation=0)
        self.exchange._events["receipt-1"].append({"synthetic": "candidate event"})
        with self.assertRaises(CheckpointRefused):
            checkpoint.save("original-instance", encode_exchange_snapshot(self.exchange), expected_generation=1)
        row = checkpoint.read("original-instance")
        self.assertEqual(row["generation"], 2)
        self.assertEqual(row["components"]["owned-facts"], self.original)

    def test_lost_commit_ack_propagates_unknown_and_is_not_replayed(self):
        class LostAcknowledgement(sqlite3.Connection):
            fail_ack = False
            commits_after_loss = 0
            def commit(inner):
                super().commit()
                if inner.fail_ack:
                    inner.commits_after_loss += 1
                    raise sqlite3.OperationalError("synthetic lost acknowledgement")
        db = self.connect(factory=LostAcknowledgement)
        checkpoint = ExchangeSnapshotCheckpoint(self.store(db))
        db.fail_ack = True
        with self.assertRaises(CheckpointCommitUnknown):
            checkpoint.save("original-instance", self.original, expected_generation=0)
        self.assertEqual(db.commits_after_loss, 1)
        row = ExchangeSnapshotCheckpoint(self.store(self.connect())).read("original-instance")
        self.assertEqual(row["generation"], 1)
        self.assertEqual(row["components"]["owned-facts"], self.original)

    def test_source_mismatch_and_wrong_components_cannot_read_as_this_snapshot(self):
        ExchangeSnapshotCheckpoint(self.store()).save("original-instance", self.original, expected_generation=0)
        with self.assertRaises(CheckpointRefused):
            ExchangeSnapshotCheckpoint(self.store(self.connect(), source_commit="c" * 40)).read("original-instance")
        with self.assertRaises(ExchangeCheckpointRefused):
            ExchangeSnapshotCheckpoint(self.store(components=("unrelated",)))

    def test_stale_generation_and_mutable_bytes_do_not_write(self):
        checkpoint = ExchangeSnapshotCheckpoint(self.store())
        checkpoint.save("original-instance", self.original, expected_generation=0)
        for generation, raw in ((0, self.original), (True, self.original), (1, bytearray(self.original))):
            with self.subTest(generation=generation), self.assertRaises(ExchangeCheckpointRefused):
                checkpoint.save("original-instance", raw, expected_generation=generation)
        self.assertEqual(checkpoint.read("original-instance")["generation"], 1)
