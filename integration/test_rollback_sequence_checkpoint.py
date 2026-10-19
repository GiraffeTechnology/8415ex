"""Synthetic durable reverse-hop fact retention; no live restart or chain calls."""
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import unittest

from exchange import fixtures as F
from exchange.aggregate_checkpoint import AggregateCheckpointStore, CheckpointCommitUnknown
from exchange.exchange_fact_snapshot import encode_exchange_snapshot
from exchange.exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint, ExchangeCheckpointRefused
from exchange.operational_facts_codec import decode_operational_facts, encode_operational_facts
from exchange.rollback_sequence_checkpoint import (RollbackSequenceCheckpoint,
                                                  RollbackSequenceCheckpointRefused)
from exchange.tests.test_rollback import refused_at_ab


RECEIPT = "rcpt-8415-0001"
SCOPE = "synthetic-original-instance"


class RollbackSequenceCheckpointTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "recovery.db"
        self.db = self.connect()
        AggregateCheckpointStore.initialize(self.db)
        self.exchange, _, _ = refused_at_ab()
        self.state = self.exchange.begin_rollback(RECEIPT, 0,
            F.rollback_authority(self.exchange, 0, "sequence-checkpoint"))
        self.checkpoint = self.adapter(self.db)

    def connect(self):
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA synchronous=FULL")
        self.addCleanup(db.close)
        return db

    def adapter(self, db):
        store = AggregateCheckpointStore(db, components=("owned-facts",),
                                        source_commit="a" * 40, source_tree="b" * 40)
        return RollbackSequenceCheckpoint(ExchangeSnapshotCheckpoint(store))

    def save(self, generation):
        return self.checkpoint.save(SCOPE, encode_exchange_snapshot(self.exchange),
                                    expected_generation=generation)

    def changed(self, change):
        value = decode_operational_facts(encode_exchange_snapshot(self.exchange)).value
        change(value["domain"])
        return encode_operational_facts(value)

    def test_partial_hop_cursor_and_result_survive_database_reopen(self):
        self.exchange.advance_rollback(RECEIPT, max_asset_hops=1)
        self.save(0)
        row = self.adapter(self.connect()).read(SCOPE)
        state = row["facts"].domain["_rollbacks"][RECEIPT]
        self.assertEqual(state["sequenceId"], self.state["sequenceId"])
        self.assertEqual(state["hopCursor"], 1)
        self.assertEqual(state["assetHops"], self.state["assetHops"])
        self.assertEqual(state["steps"], self.state["steps"])
        self.assertFalse(row["executionAuthorized"])
        self.assertFalse(row["completeRecovery"])

    def test_next_confirmed_cursor_saves_with_the_original_generation_cas(self):
        self.save(0)
        self.exchange.advance_rollback(RECEIPT, max_asset_hops=1)
        self.save(1)
        self.assertEqual(self.checkpoint.read(SCOPE)["generation"], 2)
        self.assertEqual(self.checkpoint.read(SCOPE)["facts"].domain["_rollbacks"][RECEIPT]["hopCursor"], 1)

    def test_unknown_is_retained_without_querying_or_resubmitting_a_wallet_hop(self):
        key = self.state["assetHops"][0]["key"]
        self.exchange.asset_control._outcomes[key] = "unknown"
        self.exchange.advance_rollback(RECEIPT)
        self.save(0)
        def forbidden(*args):
            raise AssertionError("checkpoint invoked the asset controller")
        self.exchange.asset_control.lookup = forbidden
        self.exchange.asset_control.return_asset = forbidden
        self.save(1)
        state = self.adapter(self.connect()).read(SCOPE)["facts"].domain["_rollbacks"][RECEIPT]
        hop = next(step for step in state["steps"] if step.kind == "asset-return")
        self.assertEqual(dict(hop.detail)["returnStatus"], "unknown")
        self.assertEqual(state["hopCursor"], 0)

    def test_confirmed_cursor_cannot_regress_even_with_matching_storage_generation(self):
        self.exchange.advance_rollback(RECEIPT, max_asset_hops=1)
        self.save(0)
        def regress(domain):
            state = domain["_rollbacks"][RECEIPT]
            state["hopCursor"] = 0
            state["steps"] = [replace(step, status="pending", detail=())
                if step.kind == "asset-return" and step.status == "done" else step
                for step in state["steps"]]
        with self.assertRaises(RollbackSequenceCheckpointRefused):
            self.checkpoint.save(SCOPE, self.changed(regress), expected_generation=1)
        self.assertEqual(self.checkpoint.read(SCOPE)["generation"], 1)

    def test_completed_result_reference_cannot_be_replaced(self):
        self.exchange.advance_rollback(RECEIPT, max_asset_hops=1)
        self.save(0)
        def substitute(domain):
            state = domain["_rollbacks"][RECEIPT]
            state["steps"] = [replace(step, detail=(("reference", "substituted-reference"),))
                if step.kind == "asset-return" and step.status == "done" else step
                for step in state["steps"]]
        with self.assertRaises(RollbackSequenceCheckpointRefused):
            self.checkpoint.save(SCOPE, self.changed(substitute), expected_generation=1)

    def test_original_path_or_sequence_cannot_disappear(self):
        self.save(0)
        for change in ("drop", "path"):
            def corrupt(domain):
                if change == "drop":
                    domain["_rollbacks"][RECEIPT] = None
                else:
                    domain["_rollbacks"][RECEIPT]["assetHops"][0]["toAccount"] = F.A
            with self.subTest(change=change), self.assertRaises(RollbackSequenceCheckpointRefused):
                self.checkpoint.save(SCOPE, self.changed(corrupt), expected_generation=1)

    def test_stale_generation_does_not_overwrite_or_reset_actual_live_progress(self):
        self.save(0)
        self.exchange.advance_rollback(RECEIPT, max_asset_hops=1)
        with self.assertRaises(ExchangeCheckpointRefused):
            self.save(0)
        self.assertEqual(self.state["hopCursor"], 1)
        saved = self.checkpoint.read(SCOPE)["facts"].domain["_rollbacks"][RECEIPT]
        self.assertEqual(saved["hopCursor"], 0)

    def test_archived_closed_sequence_cannot_be_reactivated(self):
        self.exchange.advance_rollback(RECEIPT)
        original = encode_exchange_snapshot(self.exchange)
        self.save(0)
        archived = decode_operational_facts(original).value
        domain = archived["domain"]
        state = domain["_rollbacks"][RECEIPT]
        domain["_rollback_history"][RECEIPT].append({"state": state,
            "report": self.exchange.rollback_report(RECEIPT),
            "withdrawnDeferredEvidence": {}, "retiredOrders": ()})
        domain["_rollbacks"][RECEIPT] = None
        self.checkpoint.save(SCOPE, encode_operational_facts(archived), expected_generation=1)
        with self.assertRaises(RollbackSequenceCheckpointRefused):
            self.checkpoint.save(SCOPE, original, expected_generation=2)
        self.assertEqual(self.checkpoint.read(SCOPE)["generation"], 2)

    def test_original_commit_unknown_propagates_once_without_retry(self):
        unknown = CheckpointCommitUnknown("synthetic original commit acknowledgement unknown")
        calls = []
        def fail(*args, **kwargs):
            calls.append(kwargs["expected_generation"])
            raise unknown
        self.checkpoint.checkpoint.save = fail
        with self.assertRaises(CheckpointCommitUnknown) as caught:
            self.save(0)
        self.assertIs(caught.exception, unknown)
        self.assertEqual(calls, [0])
