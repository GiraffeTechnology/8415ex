"""Synthetic original late-observation persistence, without chain execution."""
from pathlib import Path
from types import SimpleNamespace
import sqlite3
import tempfile
import unittest

from exchange import fixtures as F
from exchange.aggregate_checkpoint import AggregateCheckpointStore, CheckpointCommitUnknown
from exchange.closed_rollback_conflict_checkpoint import ClosedRollbackConflictCheckpoint
from exchange.exchange_fact_snapshot import encode_exchange_snapshot
from exchange.exchange_snapshot_checkpoint import ExchangeCheckpointRefused
from exchange.operational_facts_codec import decode_operational_facts, encode_operational_facts
from exchange.tests.test_rollback import refused_at_ab


R = "rcpt-8415-0001"
SCOPE = "synthetic-closed-conflict-history"


class ClosedRollbackConflictCheckpointTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "conflicts.db"
        self.db = self.connect()
        AggregateCheckpointStore.initialize(self.db)
        self.exchange, self.clock, _ = refused_at_ab()
        self.exchange.begin_rollback(R, 0, F.rollback_authority(self.exchange, 0, "closed-conflicts"))
        self.exchange.advance_rollback(R)
        original = self.exchange._mint_book.verify
        self.exchange._mint_book.verify = lambda kind, payload: (
            True if kind == "current-asset-validity" else original(kind, payload))
        self.exchange.resume_trading(R)
        self.checkpoint = self.adapter(self.db)
        self.save(0)

    def connect(self):
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA synchronous=FULL")
        self.addCleanup(db.close)
        return db

    def adapter(self, db):
        return ClosedRollbackConflictCheckpoint(AggregateCheckpointStore(db,
            components=("owned-facts",), source_commit="a" * 40, source_tree="b" * 40))

    def save(self, generation):
        return self.checkpoint.save(SCOPE, encode_exchange_snapshot(self.exchange),
                                    expected_generation=generation)

    def late(self, identity="synthetic-late-confirmed"):
        return self.exchange.record_late_registration_conflict(R, SimpleNamespace(
            result_id=identity, leg_index=0, outcome="confirmed", observed_at=self.clock()))

    def changed(self, change):
        value = decode_operational_facts(encode_exchange_snapshot(self.exchange)).value
        change(value["domain"])
        return encode_operational_facts(value)

    def test_original_closed_archive_conflict_survives_reopen_without_reviving_leg(self):
        movements = (self.exchange.payments.movements, self.exchange.asset_control.returns)
        before_legs = self.exchange.legs(R)
        result = self.late()
        self.save(1)
        row = self.adapter(self.connect()).read(SCOPE)
        archive = row["facts"].domain["_rollback_history"][R][0]
        self.assertEqual(archive["state"]["conflicts"], list(result["conflicts"]))
        self.assertEqual(archive["report"]["conflicts"], result["conflicts"])
        self.assertIsNone(row["facts"].domain["_rollbacks"][R])
        self.assertEqual(self.exchange.legs(R), before_legs)
        self.assertEqual((self.exchange.payments.movements,
                          self.exchange.asset_control.returns), movements)
        self.assertFalse(result["legRevived"])
        self.assertFalse(result["fundsReleasedAgain"])

    def test_previously_saved_conflict_cannot_be_removed_or_replaced(self):
        self.late("first-retained-result")
        self.save(1)
        self.late("second-result")
        def replace_old(domain):
            archive = domain["_rollback_history"][R][0]
            archive["state"]["conflicts"] = archive["state"]["conflicts"][1:]
            archive["report"]["conflicts"] = tuple(archive["state"]["conflicts"])
        with self.assertRaises(ExchangeCheckpointRefused):
            self.checkpoint.save(SCOPE, self.changed(replace_old), expected_generation=2)
        self.assertEqual(self.checkpoint.read(SCOPE)["generation"], 2)

    def test_report_and_state_must_retain_the_same_conflict_observation(self):
        self.late()
        def mismatch(domain):
            domain["_rollback_history"][R][0]["report"]["conflicts"] = ()
        with self.assertRaises(ExchangeCheckpointRefused):
            self.checkpoint.save(SCOPE, self.changed(mismatch), expected_generation=1)

    def test_completed_direct_return_boundary_cannot_change_with_a_new_conflict(self):
        self.late()
        def corrupt(domain):
            domain["_rollback_history"][R][0]["state"]["boundaryIndex"] = 1
        with self.assertRaises(ValueError):
            self.checkpoint.save(SCOPE, self.changed(corrupt), expected_generation=1)

    def test_other_closed_report_fields_remain_immutable(self):
        self.late()
        def corrupt(domain):
            domain["_rollback_history"][R][0]["report"]["complete"] = False
        with self.assertRaises(ExchangeCheckpointRefused):
            self.checkpoint.save(SCOPE, self.changed(corrupt), expected_generation=1)

    def test_stale_generation_does_not_discard_stored_conflict(self):
        self.late("first-result")
        self.save(1)
        self.late("second-result")
        with self.assertRaises(ExchangeCheckpointRefused):
            self.save(1)
        archive = self.checkpoint.read(SCOPE)["facts"].domain["_rollback_history"][R][0]
        self.assertEqual(len(archive["state"]["conflicts"]), 1)

    def test_original_commit_unknown_is_propagated_without_retry(self):
        self.late()
        unknown = CheckpointCommitUnknown("synthetic late-conflict commit unknown")
        calls = []
        def fail(*args, **kwargs):
            calls.append(kwargs["expected_generation"])
            raise unknown
        self.checkpoint.store.save = fail
        with self.assertRaises(CheckpointCommitUnknown) as caught:
            self.save(1)
        self.assertIs(caught.exception, unknown)
        self.assertEqual(calls, [1])
