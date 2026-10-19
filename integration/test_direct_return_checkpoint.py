"""Synthetic direct-boundary durability definitions; no native wallet calls."""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from exchange import fixtures as F
from exchange.aggregate_checkpoint import AggregateCheckpointStore, CheckpointCommitUnknown
from exchange.direct_return_checkpoint import DirectReturnCheckpoint, DirectReturnProgressNotSaved
from exchange.exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint, ExchangeCheckpointRefused
from exchange.serialized_exchange_access import SerializedExchangeAccess
from exchange.tests.test_rollback import refused_at_ab, ab_settled_then_c_refused


RECEIPT = "rcpt-8415-0001"
SCOPE = "synthetic-direct-return-checkpoint"


class DirectReturnCheckpointTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "progress.db"
        self.db = self.connect()
        AggregateCheckpointStore.initialize(self.db)
        self.exchange, _, _ = refused_at_ab(gas_budgets={F.B: 0, F.C: 0})
        self.bind(self.exchange, 0)

    def connect(self):
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA synchronous=FULL")
        self.addCleanup(db.close)
        return db

    def adapter(self, db):
        return ExchangeSnapshotCheckpoint(AggregateCheckpointStore(db,
            components=("owned-facts",), source_commit="a" * 40, source_tree="b" * 40))

    def bind(self, exchange, refused_index):
        self.state = exchange.begin_rollback(RECEIPT, refused_index,
            F.rollback_authority(exchange, refused_index, "direct-return"))
        self.access = SerializedExchangeAccess(exchange)
        self.checkpoint = self.adapter(self.db)
        self.bridge = DirectReturnCheckpoint(self.access, self.checkpoint, SCOPE)

    def test_original_conflict_checkpoint_subclass_composes_with_direct_return(self):
        from exchange.closed_rollback_conflict_checkpoint import ClosedRollbackConflictCheckpoint
        checkpoint = ClosedRollbackConflictCheckpoint(self.checkpoint.store)
        bridge = DirectReturnCheckpoint(self.access, checkpoint, SCOPE)
        result = bridge.advance(RECEIPT, expected_generation=0)
        self.assertTrue(result["report"]["complete"])
        self.assertEqual(result["afterCheckpoint"]["generation"], 2)
        self.assertEqual(self.exchange.asset_control.returns, 1)
        self.assertEqual(self.exchange.asset_control.hops_walked, 0)
        self.assertEqual(self.exchange.payments.movements, 3)

    def test_one_direct_asset_return_and_three_refunds_survive_database_reopen(self):
        result = self.bridge.advance(RECEIPT, expected_generation=0)
        row = self.adapter(self.connect()).read(SCOPE)
        self.assertEqual(row["generation"], 2)
        self.assertEqual(row["facts"].domain["_rollbacks"][RECEIPT]["state"], "complete")
        self.assertTrue(result["report"]["complete"])
        self.assertEqual(self.exchange.owner_of(RECEIPT), F.A)
        self.assertEqual(self.exchange.asset_control.returns, 1)
        self.assertEqual(self.exchange.asset_control.hops_walked, 0)
        self.assertEqual(self.exchange.payments.movements, 3)
        record = self.exchange.asset_control.lookup("return:" + RECEIPT + ":direct-return")
        self.assertEqual((record["fromAccount"], record["toAccount"]), (F.D, F.A))
        self.assertFalse(record["walkedIntermediateWallets"])
        self.bridge.advance(RECEIPT, expected_generation=2)
        self.assertEqual(self.exchange.asset_control.returns, 1)
        self.assertEqual(self.exchange.payments.movements, 3)

    def test_registered_settled_prefix_stays_released_and_return_stops_at_b(self):
        exchange, _, _ = ab_settled_then_c_refused()
        self.bind(exchange, 1)
        result = self.bridge.advance(RECEIPT, expected_generation=0)
        self.assertTrue(result["report"]["complete"])
        self.assertEqual(exchange.owner_of(RECEIPT), F.B)
        self.assertEqual(exchange.escrow_for_leg(RECEIPT, 0).status, "released")
        self.assertIsNone(exchange.escrow_for_leg(RECEIPT, 0).refunded_at)
        self.assertEqual(exchange.asset_control.returns, 1)
        self.assertEqual(exchange.asset_control.hops_walked, 0)
        self.assertEqual(exchange.payments.movements, 3)
        row = self.adapter(self.connect()).read(SCOPE)
        self.assertEqual(row["facts"].domain["_rollbacks"][RECEIPT]["boundaryAccount"], F.B)

    def test_stale_generation_invokes_no_further_original_operation(self):
        self.bridge.advance(RECEIPT, expected_generation=0)
        before = (self.exchange.asset_control.returns, self.exchange.payments.movements)
        with self.assertRaises(ExchangeCheckpointRefused):
            self.bridge.advance(RECEIPT, expected_generation=0)
        self.assertEqual((self.exchange.asset_control.returns,
                          self.exchange.payments.movements), before)

    def test_pre_advance_commit_unknown_is_not_retried_and_sends_nothing(self):
        unknown = CheckpointCommitUnknown("synthetic pre-advance acknowledgement unknown")
        calls = []
        def fail(*args, **kwargs):
            calls.append(kwargs["expected_generation"])
            raise unknown
        self.checkpoint.save = fail
        with self.assertRaises(CheckpointCommitUnknown) as caught:
            self.bridge.advance(RECEIPT, expected_generation=0)
        self.assertIs(caught.exception, unknown)
        self.assertEqual(calls, [0])
        self.assertEqual(self.exchange.asset_control.returns, 0)
        self.assertEqual(self.exchange.payments.movements, 0)

    def test_post_advance_unknown_retains_live_effect_and_before_generation(self):
        original = self.checkpoint.save
        unknown = CheckpointCommitUnknown("synthetic post-advance acknowledgement unknown")
        calls = []
        def fail_after(*args, **kwargs):
            calls.append(kwargs["expected_generation"])
            if len(calls) == 2:
                raise unknown
            return original(*args, **kwargs)
        self.checkpoint.save = fail_after
        with self.assertRaises(DirectReturnProgressNotSaved) as caught:
            self.bridge.advance(RECEIPT, expected_generation=0)
        self.assertIs(caught.exception.storage_error, unknown)
        self.assertTrue(caught.exception.report["complete"])
        self.assertEqual(calls, [0, 1])
        self.assertEqual(self.exchange.owner_of(RECEIPT), F.A)
        self.assertEqual(self.exchange.asset_control.returns, 1)
        self.assertEqual(self.exchange.payments.movements, 3)
        row = self.checkpoint.read(SCOPE)
        self.assertEqual(row["generation"], 1)
        self.assertEqual(row["facts"].domain["_rollbacks"][RECEIPT]["state"], "in-progress")

    def test_unknown_original_direct_return_is_enquired_without_resubmission(self):
        key = "return:" + RECEIPT + ":direct-return"
        self.exchange.asset_control._outcomes[key] = "unknown"
        self.assertFalse(self.bridge.advance(RECEIPT, expected_generation=0)["report"]["complete"])
        self.assertFalse(self.bridge.advance(RECEIPT, expected_generation=2)["report"]["complete"])
        self.assertEqual(len(self.exchange.asset_control._records), 1)
        self.assertEqual(self.exchange.asset_control.returns, 0)
        self.exchange.asset_control.resolve_unknown(key, "returned")
        result = self.bridge.advance(RECEIPT, expected_generation=4)
        self.assertTrue(result["report"]["complete"])
        self.assertEqual(self.exchange.owner_of(RECEIPT), F.A)
        self.assertEqual(len(self.exchange.asset_control._records), 1)
        self.assertEqual(self.exchange.asset_control.returns, 0)
        self.assertEqual(self.exchange.payments.movements, 3)

    def test_original_domain_error_is_preserved_after_available_facts_are_saved(self):
        failure = RuntimeError("synthetic original observation failure")
        def fail(key):
            raise failure
        self.exchange.payments.lookup = fail
        with self.assertRaises(RuntimeError) as caught:
            self.bridge.advance(RECEIPT, expected_generation=0)
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.checkpoint.read(SCOPE)["generation"], 2)
        self.assertEqual(self.exchange.asset_control.returns, 0)

    def test_both_domain_and_post_capture_failure_remain_observable(self):
        domain_error = RuntimeError("synthetic original domain failure")
        storage_error = OSError("synthetic snapshot unavailable")
        def fail(key):
            raise domain_error
        self.exchange.payments.lookup = fail
        original = self.checkpoint.save
        calls = []
        def save(*args, **kwargs):
            calls.append(kwargs["expected_generation"])
            if len(calls) == 2:
                raise storage_error
            return original(*args, **kwargs)
        self.checkpoint.save = save
        with self.assertRaises(DirectReturnProgressNotSaved) as caught:
            self.bridge.advance(RECEIPT, expected_generation=0)
        self.assertIs(caught.exception.domain_error, domain_error)
        self.assertIs(caught.exception.storage_error, storage_error)
        self.assertEqual(calls, [0, 1])
        self.assertEqual(self.exchange.payments.movements, 0)
