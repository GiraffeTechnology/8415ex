"""Authored for approved remote Linux; not executed by source preparation."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from exchange.aggregate_checkpoint import (AggregateCheckpointStore,
    CheckpointRefused, CheckpointCommitUnknown)


class AggregateCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "checkpoint.db"
        self.connections = []
        self.db = self.connect()
        AggregateCheckpointStore.initialize(self.db)
        self.values = {"domain": b"original-domain-bytes\x00\xff",
                       "unknown_claims": b"original-UNKNOWN-not-replayable"}

    def connect(self, factory=sqlite3.Connection):
        db = sqlite3.connect(self.path, factory=factory)
        db.execute("PRAGMA synchronous=FULL")
        self.connections.append(db)
        self.addCleanup(db.close)
        return db

    def store(self, db=None, **override):
        args = dict(components=("domain", "unknown_claims"),
                    source_commit="a" * 40, source_tree="b" * 40)
        args.update(override)
        return AggregateCheckpointStore(db or self.db, **args)

    def test_complete_bytes_survive_reopen_without_execution_authority(self):
        result = self.store().save("receipt-scope", self.values, expected_generation=0)
        self.assertFalse(result["executionAuthorized"])
        self.db.close()
        reopened = self.store(self.connect()).read("receipt-scope")
        self.assertEqual(reopened["generation"], 1)
        self.assertEqual(reopened["components"], self.values)
        self.assertFalse(reopened["executionAuthorized"])

    def test_partial_components_and_stale_writer_cannot_replace_aggregate(self):
        first = self.store()
        second = self.store(self.connect())
        first.save("receipt-scope", self.values, expected_generation=0)
        with self.assertRaises(CheckpointRefused):
            second.save("receipt-scope", self.values, expected_generation=0)
        with self.assertRaises(CheckpointRefused):
            first.save("receipt-scope", {"domain": b"partial"}, expected_generation=1)
        self.assertEqual(second.read("receipt-scope")["components"], self.values)
        self.assertEqual(second.read("receipt-scope")["generation"], 1)
        changed = dict(self.values, domain=b"next-original-domain")
        second.save("receipt-scope", changed, expected_generation=1)
        self.assertEqual(first.read("receipt-scope")["components"], changed)

    def test_corruption_is_refused_without_partial_result_or_diagnostic_leak(self):
        store = self.store()
        store.save("receipt-scope", self.values, expected_generation=0)
        payload = json.loads(self.db.execute("SELECT payload FROM ex_aggregate_checkpoint").fetchone()[0])
        payload["components"]["domain"]["sha256"] = "0" * 64
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        self.db.execute("UPDATE ex_aggregate_checkpoint SET payload=?,digest=?",
                        (encoded, hashlib.sha256(encoded.encode()).hexdigest()))
        self.db.commit()
        with self.assertRaisesRegex(CheckpointRefused, "stored aggregate is inconsistent"):
            store.read("receipt-scope")
        with self.assertRaises(CheckpointRefused):
            store.save("receipt-scope", self.values, expected_generation=1)

    def test_source_and_component_contract_mismatch_never_loads_old_bytes(self):
        self.store().save("receipt-scope", self.values, expected_generation=0)
        with self.assertRaises(CheckpointRefused):
            self.store(source_tree="c" * 40).read("receipt-scope")
        with self.assertRaises(CheckpointRefused):
            self.store(components=("domain",)).read("receipt-scope")
        with self.assertRaises(CheckpointRefused):
            self.store().save("receipt-scope", self.values, expected_generation=True)

    def test_durable_settings_and_foreign_transaction_checked_each_write(self):
        store = self.store()
        self.db.execute("PRAGMA synchronous=OFF")
        with self.assertRaises(CheckpointRefused):
            store.save("receipt-scope", self.values, expected_generation=0)
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("BEGIN")
        with self.assertRaises(CheckpointRefused):
            store.save("receipt-scope", self.values, expected_generation=0)
        self.assertTrue(self.db.in_transaction)
        self.db.rollback()
        with sqlite3.connect(":memory:") as memory:
            with self.assertRaises(CheckpointRefused):
                self.store(memory)

    def test_lost_commit_ack_is_unknown_until_original_store_is_read(self):
        class LostAcknowledgement(sqlite3.Connection):
            fail_ack = False
            def commit(self):
                super().commit()
                if self.fail_ack:
                    raise sqlite3.OperationalError("synthetic lost commit acknowledgement")
        db = self.connect(factory=LostAcknowledgement)
        store = self.store(db)
        db.fail_ack = True
        with self.assertRaises(CheckpointCommitUnknown):
            store.save("receipt-scope", self.values, expected_generation=0)
        observed = self.store(self.connect()).read("receipt-scope")
        self.assertEqual(observed["generation"], 1)
        self.assertEqual(observed["components"], self.values)
        self.assertFalse(observed["executionAuthorized"])
