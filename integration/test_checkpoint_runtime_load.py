"""Synthetic file-backed and child-process checkpoint loading definitions."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from exchange import fixtures as F
from exchange.aggregate_checkpoint import AggregateCheckpointStore, CheckpointRefused
from exchange.checkpoint_runtime_load import load_exchange_checkpoint
from exchange.exchange_fact_snapshot import encode_exchange_snapshot
from exchange.exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint
from exchange.ledger import Exchange
from exchange.tests.test_rollback import refused_at_ab


R = "rcpt-8415-0001"
SCOPE = "synthetic-process-load"
COMMIT = "a" * 40
TREE = "b" * 40


class CheckpointRuntimeLoadTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "load.db"
        self.db = self.connect()
        AggregateCheckpointStore.initialize(self.db)
        self.checkpoint = self.adapter(self.db)
        self.exchange, self.clock, _ = refused_at_ab()
        self.exchange.begin_rollback(R, 0, F.rollback_authority(self.exchange, 0, "runtime-load"))
        self.exchange.advance_rollback(R)

    def connect(self):
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA synchronous=FULL")
        self.addCleanup(db.close)
        return db

    def adapter(self, db, commit=COMMIT):
        return ExchangeSnapshotCheckpoint(AggregateCheckpointStore(db,
            components=("owned-facts",), source_commit=commit, source_tree=TREE))

    def runtime(self):
        return Exchange(self.clock, mint_verifier=F.verify_fixture_mint)

    def save(self):
        return self.checkpoint.save(SCOPE, encode_exchange_snapshot(self.exchange), expected_generation=0)

    def test_missing_checkpoint_does_not_initialize_or_invent_generation(self):
        runtime = self.runtime()
        self.assertIsNone(load_exchange_checkpoint(self.checkpoint, SCOPE, runtime))
        self.assertEqual(runtime._receipts, {})
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM ex_aggregate_checkpoint").fetchone()[0], 0)

    def test_reopened_store_returns_exact_generation_digest_and_direct_boundary_owner(self):
        saved = self.save()
        loaded = load_exchange_checkpoint(self.adapter(self.connect()), SCOPE, self.runtime())
        self.assertEqual((loaded.scope, loaded.generation, loaded.digest),
                         (SCOPE, 1, saved["digest"]))
        self.assertEqual((loaded.source_commit, loaded.source_tree), (COMMIT, TREE))
        self.assertTrue(loaded.access.rollback_report(R)["complete"])
        self.assertEqual(loaded.access.owner_of(R), F.A)

    def test_actual_child_process_reconstructs_saved_facts_without_parent_objects(self):
        self.save()
        # This child definition runs only when the containing synthetic suite
        # is executed. It accepts the temporary test path, never a live DB.
        script = r'''
import json, sqlite3, sys
from exchange import fixtures as F
from exchange.aggregate_checkpoint import AggregateCheckpointStore
from exchange.checkpoint_runtime_load import load_exchange_checkpoint
from exchange.exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint
from exchange.ledger import Exchange
db = sqlite3.connect(sys.argv[1])
db.execute("PRAGMA synchronous=FULL")
store = AggregateCheckpointStore(db, components=("owned-facts",),
    source_commit="a" * 40, source_tree="b" * 40)
runtime = Exchange(F.ManualClock(), mint_verifier=F.verify_fixture_mint)
loaded = load_exchange_checkpoint(ExchangeSnapshotCheckpoint(store), "synthetic-process-load", runtime)
report = loaded.access.rollback_report("rcpt-8415-0001")
print(json.dumps({"generation": loaded.generation, "complete": report["complete"],
    "owner": loaded.access.owner_of("rcpt-8415-0001"),
    "nativePorts": [loaded.access._exchange.payments is not None,
                    loaded.access._exchange.asset_control is not None],
    "sessions": len(loaded.access._exchange._sessions)}))
db.close()
'''
        result = subprocess.run([sys.executable, "-c", script, str(self.path)],
                                capture_output=True, text=True, timeout=30, check=True)
        self.assertEqual(json.loads(result.stdout), {"generation": 1, "complete": True,
            "owner": F.A, "nativePorts": [False, False], "sessions": 0})

    def test_different_source_store_cannot_load_or_relabel_saved_facts(self):
        self.save()
        runtime = self.runtime()
        with self.assertRaises(CheckpointRefused):
            load_exchange_checkpoint(self.adapter(self.connect(), commit="c" * 40), SCOPE, runtime)
        self.assertEqual(runtime._receipts, {})

    def test_foreign_transaction_is_not_committed_or_rolled_back_by_loading(self):
        self.save()
        self.db.execute("BEGIN")
        with self.assertRaises(CheckpointRefused):
            load_exchange_checkpoint(self.checkpoint, SCOPE, self.runtime())
        self.assertTrue(self.db.in_transaction)
        self.db.rollback()

    def test_corrupt_payload_does_not_publish_or_modify_supplied_runtime(self):
        self.save()
        self.db.execute("UPDATE ex_aggregate_checkpoint SET digest=? WHERE scope=?", ("0" * 64, SCOPE))
        self.db.commit()
        runtime = self.runtime()
        with self.assertRaises(CheckpointRefused):
            load_exchange_checkpoint(self.checkpoint, SCOPE, runtime)
        self.assertEqual(runtime._receipts, {})
