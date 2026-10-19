"""Process-crash definitions with separate synthetic effect and EX databases."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from exchange import fixtures as F
from exchange.aggregate_checkpoint import AggregateCheckpointStore
from exchange.exchange_fact_snapshot import encode_exchange_snapshot
from exchange.exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint
from exchange.tests.test_rollback import refused_at_ab
from integration.direct_return_process_fixture import MARKER, RECEIPT, SCOPE


class DirectReturnProcessRecoveryTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        (self.root / "TEST-ONLY.txt").write_text(MARKER, encoding="utf-8")
        exchange, _, _ = refused_at_ab()
        exchange.begin_rollback(RECEIPT, 0, F.rollback_authority(exchange, 0, "process-recovery"))
        db = sqlite3.connect(self.root / "checkpoint.db")
        try:
            db.execute("PRAGMA synchronous=FULL")
            AggregateCheckpointStore.initialize(db)
            checkpoint = ExchangeSnapshotCheckpoint(AggregateCheckpointStore(db,
                components=("owned-facts",), source_commit="a" * 40, source_tree="b" * 40))
            checkpoint.save(SCOPE, encode_exchange_snapshot(exchange), expected_generation=0)
        finally:
            db.close()
        db = sqlite3.connect(self.root / "synthetic-native.db")
        try:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("CREATE TABLE effects(kind TEXT,operation_key TEXT,payload TEXT,"
                       "PRIMARY KEY(kind,operation_key))")
            db.commit()
        finally:
            db.close()

    def child(self, mode="advance", expected_exit=0):
        result = subprocess.run([sys.executable, "-m", "integration.direct_return_process_fixture",
            str(self.root), mode], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, expected_exit, result.stderr)
        return json.loads(result.stdout) if expected_exit == 0 else result

    def counts(self):
        db = sqlite3.connect(self.root / "synthetic-native.db")
        try:
            return dict(db.execute("SELECT kind,COUNT(*) FROM effects GROUP BY kind"))
        finally:
            db.close()

    def test_crash_after_durable_direct_return_reconciles_same_key_without_resend(self):
        self.child("crash-asset", expected_exit=71)
        self.assertEqual(self.counts(), {"payment": 3, "asset": 1})
        recovered = self.child()
        self.assertTrue(recovered["complete"])
        self.assertEqual(recovered["owner"], F.A)
        self.assertEqual(recovered["counts"], {"payment": 3, "asset": 1})
        repeated = self.child()
        self.assertTrue(repeated["complete"])
        self.assertEqual(repeated["counts"], recovered["counts"])

    def test_crash_after_first_durable_refund_does_not_refund_that_key_twice(self):
        self.child("crash-payment", expected_exit=71)
        self.assertEqual(self.counts(), {"payment": 1})
        recovered = self.child()
        self.assertTrue(recovered["complete"])
        self.assertEqual(recovered["owner"], F.A)
        self.assertEqual(recovered["counts"], {"payment": 3, "asset": 1})

    def test_unknown_survives_independent_processes_until_original_observation_changes(self):
        first = self.child("unknown-asset")
        second = self.child()
        self.assertFalse(first["complete"])
        self.assertFalse(second["complete"])
        self.assertEqual((first["owner"], second["owner"]), (F.D, F.D))
        self.assertEqual(second["counts"], {"payment": 3, "asset": 1})
        db = sqlite3.connect(self.root / "synthetic-native.db")
        try:
            key, payload = db.execute("SELECT operation_key,payload FROM effects WHERE kind='asset'").fetchone()
            record = json.loads(payload)
            self.assertEqual(record["status"], "unknown")
            self.assertEqual((record["fromAccount"], record["toAccount"]), (F.D, F.A))
            self.assertFalse(record["walkedIntermediateWallets"])
            record["status"] = "returned"
            db.execute("UPDATE effects SET payload=? WHERE kind='asset' AND operation_key=?",
                       (json.dumps(record, sort_keys=True), key))
            db.commit()
        finally:
            db.close()
        reconciled = self.child()
        self.assertTrue(reconciled["complete"])
        self.assertEqual(reconciled["owner"], F.A)
        self.assertEqual(reconciled["counts"], {"payment": 3, "asset": 1})

    def test_completed_return_reloaded_in_another_process_has_no_new_effect(self):
        final = self.child()
        self.assertTrue(final["complete"])
        repeated = self.child()
        self.assertTrue(repeated["complete"])
        self.assertEqual(repeated["owner"], F.A)
        self.assertEqual(repeated["counts"], final["counts"])
