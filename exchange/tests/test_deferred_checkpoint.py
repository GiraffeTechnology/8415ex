"""File-backed synthetic recovery tests, executed by the existing CI only."""
from dataclasses import asdict
from pathlib import Path
import sqlite3
import tempfile
import unittest

from exchange.aggregate_checkpoint import AggregateCheckpointStore, CheckpointRefused
from exchange.deferred_checkpoint import DeferredCheckpoint
from exchange.deferred_settlement import DeferredRefused
from exchange.ids import canonical_json, digest
from exchange.tests import test_deferred_settlement as fixture_module


class SyntheticPort:
    """Test-only preflight; no real route or financial execution."""
    def __init__(self, execute):
        self.execute = execute

    def prepare_original(self, operation):
        return self.execute


class DeferredCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.DeferredTests()
        self.fixture.setUp()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.connection = sqlite3.connect(Path(self.directory.name) / "checkpoint.db")
        self.addCleanup(self.connection.close)
        self.connection.execute("PRAGMA synchronous=FULL")
        AggregateCheckpointStore.initialize(self.connection)
        self.store = AggregateCheckpointStore(self.connection,
            components=("deferred-settlement", "original"), source_commit="a" * 40, source_tree="b" * 40)
        self.store.save("case", {"original": b"original immutable component",
            "deferred-settlement": canonical_json(self.fixture.engine.snapshot()).encode()}, expected_generation=0)
        self.service = DeferredCheckpoint(self.store, "case", self.fixture.profile, self.fixture.verifier)

    def apply(self, command, *args, **kwargs):
        return self.service.apply(command, *args, expected_generation=self.service.read()[0]["generation"], **kwargs)

    def reserve(self):
        self.fixture.reserve()
        item = self.fixture.engine.obligations["ab"]
        consent = self.fixture.fact("seller-consent", reference=item.consent, account="A", units=800)
        admission = self.fixture.fact("deferred-admission", reference=item.consent, units=800)
        return self.apply("reserve", "ab", "lock-1", borrower="B", seller="A", principal=800,
                          fee=0, deadline=200, now=100, seller_consent=consent, borrower_authority=admission)

    def payment(self):
        self.reserve()
        self.apply("observe_registration", "ab", self.fixture.fact("registration-cut", at=150), now=150)
        self.apply("credit_escrow", "ab", self.fixture.fact("principal-allocation", units=800), now=150)
        return self.apply("prepare", "pay", "ab", kind="seller-payment", now=150)

    def test_complete_snapshot_retains_original_component_and_reservation(self):
        self.reserve()
        row, model = self.service.read()
        self.assertEqual(row["components"]["original"], b"original immutable component")
        self.assertEqual(model.locks["lock-1"].reserved, 800)
        self.assertEqual(model.obligations["ab"].paid, 0)

    def test_stale_generation_does_not_mutate_or_dispatch(self):
        self.payment()
        calls = []
        with self.assertRaises(DeferredRefused):
            self.service.dispatch_once("pay", SyntheticPort(calls.append), expected_generation=1)
        self.assertEqual(calls, [])
        self.assertEqual(self.service.read()[1].operations["pay"].status, "PREPARED")

    def test_unknown_is_durable_before_callback_and_restart_cannot_replay(self):
        prepared = self.payment()
        calls = []
        def uncertain(op):
            self.assertEqual(self.service.read()[1].operations["pay"].status, "UNKNOWN")
            calls.append(op.identity)
            raise TimeoutError("synthetic transport failure")
        result = self.service.dispatch_once("pay", SyntheticPort(uncertain), expected_generation=prepared["generation"])
        self.assertEqual(result["status"], "UNKNOWN")
        restarted = DeferredCheckpoint(self.store, "case", self.fixture.profile, self.fixture.verifier)
        with self.assertRaises(DeferredRefused):
            restarted.dispatch_once("pay", SyntheticPort(calls.append), expected_generation=result["generation"])
        self.assertEqual(calls, ["pay"])
        self.assertEqual(restarted.read()[1].obligations["ab"].paid, 0)

    def test_untrusted_executor_response_is_not_payment_confirmation(self):
        prepared = self.payment()
        self.service.dispatch_once("pay", SyntheticPort(lambda op: {"success": True}), expected_generation=prepared["generation"])
        model = self.service.read()[1]
        self.assertEqual(model.operations["pay"].status, "UNKNOWN")
        self.assertEqual(model.obligations["ab"].paid, 0)

    def test_malformed_state_is_refused_without_overwriting_history(self):
        row = self.store.read("case")
        components = dict(row["components"])
        components["deferred-settlement"] = b'{"schema":"forged"}'
        self.store.save("case", components, expected_generation=row["generation"])
        with self.assertRaises(DeferredRefused):
            self.service.read()

    def test_true_reopen_and_independent_connection_reject_stale_writer(self):
        self.reserve()
        second_connection = sqlite3.connect(Path(self.directory.name) / "checkpoint.db")
        self.addCleanup(second_connection.close)
        second_connection.execute("PRAGMA synchronous=FULL")
        second_store = AggregateCheckpointStore(second_connection,
            components=("deferred-settlement", "original"), source_commit="a" * 40, source_tree="b" * 40)
        second = DeferredCheckpoint(second_store, "case", self.fixture.profile, self.fixture.verifier)
        stale = second.read()[0]["generation"]
        self.apply("observe_registration", "ab", self.fixture.fact("registration-cut", at=150), now=150)
        with self.assertRaises(DeferredRefused):
            second.apply("credit_escrow", "ab", self.fixture.fact("principal-allocation", units=800),
                         now=150, expected_generation=stale)
        self.connection.close()
        self.assertTrue(second.read()[1].obligations["ab"].registered)
        self.assertEqual(second.read()[1].obligations["ab"].escrow, 0)

    def test_commit_acknowledgement_failure_never_calls_executor(self):
        from unittest.mock import patch
        from exchange.aggregate_checkpoint import CheckpointCommitUnknown
        prepared = self.payment()
        original_save = self.store.save
        def uncertain(*args, **kwargs):
            original_save(*args, **kwargs)
            raise CheckpointCommitUnknown("synthetic lost acknowledgement")
        calls = []
        with patch.object(self.store, "save", side_effect=uncertain):
            with self.assertRaises(CheckpointCommitUnknown):
                self.service.dispatch_once("pay", SyntheticPort(calls.append), expected_generation=prepared["generation"])
        self.assertEqual(calls, [])
        row, model = self.service.read()
        self.assertEqual(model.operations["pay"].status, "UNKNOWN")
        with self.assertRaises(DeferredRefused):
            self.service.dispatch_once("pay", SyntheticPort(calls.append), expected_generation=row["generation"])
        self.assertEqual(calls, [])

    def test_failure_before_save_does_not_dispatch_or_change_prepared_state(self):
        from unittest.mock import patch
        prepared = self.payment()
        calls = []
        with patch.object(self.store, "save", side_effect=CheckpointRefused("synthetic refusal")):
            with self.assertRaises(CheckpointRefused):
                self.service.dispatch_once("pay", SyntheticPort(calls.append), expected_generation=prepared["generation"])
        self.assertEqual(calls, [])
        self.assertEqual(self.service.read()[1].operations["pay"].status, "PREPARED")

    def test_same_profile_cannot_use_another_ledger_scope_to_replay_capacity(self):
        with self.assertRaises(DeferredRefused):
            DeferredCheckpoint(self.store, "another-case", self.fixture.profile, self.fixture.verifier)

    def test_missing_route_stays_prepared_without_claim_or_dispatch(self):
        prepared = self.payment()
        before = self.service.read()[0]
        class MissingRoute:
            def prepare_original(self, operation):
                raise DeferredRefused("synthetic missing route")
        result = self.service.dispatch_once("pay", MissingRoute(), expected_generation=prepared["generation"])
        self.assertEqual(result, {"generation": prepared["generation"], "status": "BLOCKED_NOT_DISPATCHED", "dispatched": False})
        after, model = self.service.read()
        self.assertEqual(after, before)
        self.assertEqual(model.operations["pay"].status, "PREPARED")
        calls = []
        self.service.dispatch_once("pay", SyntheticPort(calls.append), expected_generation=prepared["generation"])
        self.assertEqual(len(calls), 1)

    def test_legacy_callback_cannot_accidentally_execute_during_preflight(self):
        prepared = self.payment()
        calls = []
        with self.assertRaises(DeferredRefused):
            self.service.dispatch_once("pay", calls.append, expected_generation=prepared["generation"])
        self.assertEqual(calls, [])
        self.assertEqual(self.service.read()[1].operations["pay"].status, "PREPARED")

    def test_competing_change_during_read_only_preflight_blocks_execution(self):
        prepared = self.payment()
        calls = []
        service = self.service
        class ChangedRoute:
            def prepare_original(inner, operation):
                row = service.read()[0]
                service.store.save("case", row["components"], expected_generation=row["generation"])
                return calls.append
        with self.assertRaises(DeferredRefused):
            self.service.dispatch_once("pay", ChangedRoute(), expected_generation=prepared["generation"])
        self.assertEqual(calls, [])
