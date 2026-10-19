"""Definitions for original access/UI/checkpoint composition; no live signer."""
from pathlib import Path
import sqlite3
import tempfile
from threading import Event, Thread
import unittest

from exchange.ledger import Exchange
from exchange.fixtures import A
from exchange.workbench import RuntimeBinding
from exchange.aggregate_checkpoint import AggregateCheckpointStore, CheckpointRefused, CheckpointCommitUnknown
from exchange.exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint
from exchange.exchange_fact_snapshot import decode_exchange_snapshot
from exchange.serialized_exchange_access import SerializedExchangeAccess, SerializedAccessRefused
from integration.test_mint_specification_codec import specification


class SerializedExchangeAccessTests(unittest.TestCase):
    def setUp(self):
        self.exchange = Exchange(lambda: 20, mint_verifier=lambda kind, evidence: True)
        spec = specification()
        self.exchange.mint(spec.receipt, spec)
        self.access = SerializedExchangeAccess(self.exchange)

    def checkpoint(self, factory=sqlite3.Connection):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        db = sqlite3.connect(Path(directory.name) / "checkpoint.db", factory=factory)
        self.addCleanup(db.close)
        db.execute("PRAGMA synchronous=FULL")
        AggregateCheckpointStore.initialize(db)
        store = AggregateCheckpointStore(db, components=("owned-facts",),
                                         source_commit="a" * 40, source_tree="b" * 40)
        return db, ExchangeSnapshotCheckpoint(store)

    def test_original_public_calls_keep_session_behavior(self):
        self.access.connect_wallet(A, "original-session")
        self.assertEqual(decode_exchange_snapshot(self.access.snapshot_bytes()).wallet["sessions"][A], "original-session")
        self.access.disconnect_wallet(A)
        self.assertNotIn(A, decode_exchange_snapshot(self.access.snapshot_bytes()).wallet["sessions"])

    def test_private_methods_and_configuration_are_not_exposed_as_calls(self):
        for name in ("_record", "payments", "funding_required", "registrars", "unrecognized"):
            with self.subTest(name=name), self.assertRaises(AttributeError):
                getattr(self.access, name)

    def test_returned_original_domain_records_are_detached(self):
        result = self.access.receipt("receipt-1")
        self.assertEqual(result, self.exchange._receipts["receipt-1"])
        self.assertIsNot(result, self.exchange._receipts["receipt-1"])
        report = self.access.receipt_view("receipt-1")
        report["mintDeclaration"].clear()
        self.assertTrue(self.exchange._mint_declarations["receipt-1"])

    def test_same_access_captures_and_persists_whole_owned_snapshot(self):
        _, checkpoint = self.checkpoint()
        self.access.connect_wallet(A, "original-session")
        result = self.access.write_checkpoint(checkpoint, "original-instance", expected_generation=0)
        self.assertEqual(result["generation"], 1)
        stored = checkpoint.read("original-instance")
        self.assertEqual(stored["facts"].receipts, self.exchange._receipts)
        self.assertEqual(stored["facts"].wallet["sessions"][A], "original-session")
        self.assertFalse(stored["completeRecovery"])

    def test_original_runtime_binding_interface_is_preserved(self):
        binding = self.access.bind_runtime("receipt-1")
        self.assertIsInstance(binding, RuntimeBinding)
        snapshot = binding.snapshot()
        self.assertEqual(snapshot["state"]["receipt"]["receiptId"], "receipt-1")
        self.assertEqual(snapshot["commandGateway"], "NOT_CONFIGURED")
        with self.assertRaises(PermissionError):
            binding.command("advance-rollback", "original-key", snapshot["revision"], {})

    def test_unknown_gateway_result_is_enquired_once_without_dispatch(self):
        class Gateway:
            enquiries = 0
            dispatches = 0
            def enquire(inner, key, context):
                inner.enquiries += 1
                return {"status": "unknown"}
            def dispatch(inner, *args):
                inner.dispatches += 1
                raise AssertionError("must not replay")
        gateway = Gateway()
        binding = self.access.bind_runtime("receipt-1", gateway=gateway)
        result = binding.command("resume-payment", "original-key", binding.snapshot()["revision"], {"legIndex": 0})
        self.assertTrue(result["enquired"])
        self.assertEqual(gateway.enquiries, 1)
        self.assertEqual(gateway.dispatches, 0)

    def test_complete_ui_observation_and_snapshot_capture_share_one_lock(self):
        entered, release, capture_started, captured = Event(), Event(), Event(), Event()
        errors = []
        def clock():
            entered.set()
            if not release.wait(2):
                raise RuntimeError("synthetic observation timeout")
            return 20
        self.exchange._clock = clock
        binding = self.access.bind_runtime("receipt-1")
        def observe():
            try: binding.snapshot()
            except Exception as error: errors.append(error)
        def capture():
            capture_started.set()
            try:
                self.access.snapshot_bytes()
                captured.set()
            except Exception as error: errors.append(error)
        observer = Thread(target=observe)
        capture_thread = Thread(target=capture)
        observer.start()
        try:
            self.assertTrue(entered.wait(1))
            capture_thread.start()
            self.assertTrue(capture_started.wait(1))
            self.assertFalse(captured.wait(0.05))
        finally:
            release.set()
            observer.join(3)
            if capture_thread.ident is not None: capture_thread.join(3)
        self.assertFalse(observer.is_alive())
        self.assertFalse(capture_thread.is_alive())
        self.assertEqual(errors, [])
        self.assertTrue(captured.is_set())

    def test_commit_unknown_propagates_once_and_lock_allows_readonly_reconciliation(self):
        class LostAcknowledgement(sqlite3.Connection):
            fail_ack = False
            lost_acks = 0
            def commit(inner):
                super().commit()
                if inner.fail_ack:
                    inner.lost_acks += 1
                    raise sqlite3.OperationalError("synthetic lost acknowledgement")
        db, checkpoint = self.checkpoint(factory=LostAcknowledgement)
        db.fail_ack = True
        with self.assertRaises(CheckpointCommitUnknown):
            self.access.write_checkpoint(checkpoint, "original-instance", expected_generation=0)
        self.assertEqual(db.lost_acks, 1)
        self.assertEqual(checkpoint.read("original-instance")["generation"], 1)
        self.assertEqual(decode_exchange_snapshot(self.access.snapshot_bytes()).receipts, self.exchange._receipts)

    def test_invalid_sources_or_stale_save_do_not_replace_existing_state(self):
        with self.assertRaises(SerializedAccessRefused): SerializedExchangeAccess(object())
        with self.assertRaises(SerializedAccessRefused):
            self.access.write_checkpoint(object(), "original-instance", expected_generation=0)
        _, checkpoint = self.checkpoint()
        self.access.write_checkpoint(checkpoint, "original-instance", expected_generation=0)
        self.access.connect_wallet(A, "later-session")
        with self.assertRaises(ValueError):
            self.access.write_checkpoint(checkpoint, "original-instance", expected_generation=0)
        self.assertEqual(checkpoint.read("original-instance")["generation"], 1)
        # A failed save is not a rollback of the preceding independent domain call.
        self.assertEqual(self.exchange._sessions[A], "later-session")
