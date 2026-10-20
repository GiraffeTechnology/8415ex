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
            self.service.dispatch_once("pay", calls.append, expected_generation=1)
        self.assertEqual(calls, [])
        self.assertEqual(self.service.read()[1].operations["pay"].status, "PREPARED")

    def test_unknown_is_durable_before_callback_and_restart_cannot_replay(self):
        prepared = self.payment()
        calls = []
        def uncertain(op):
            self.assertEqual(self.service.read()[1].operations["pay"].status, "UNKNOWN")
            calls.append(op.identity)
            raise TimeoutError("synthetic transport failure")
        result = self.service.dispatch_once("pay", uncertain, expected_generation=prepared["generation"])
        self.assertEqual(result["status"], "UNKNOWN")
        restarted = DeferredCheckpoint(self.store, "case", self.fixture.profile, self.fixture.verifier)
        with self.assertRaises(DeferredRefused):
            restarted.dispatch_once("pay", calls.append, expected_generation=result["generation"])
        self.assertEqual(calls, ["pay"])
        self.assertEqual(restarted.read()[1].obligations["ab"].paid, 0)

    def test_untrusted_executor_response_is_not_payment_confirmation(self):
        prepared = self.payment()
        self.service.dispatch_once("pay", lambda op: {"success": True}, expected_generation=prepared["generation"])
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
