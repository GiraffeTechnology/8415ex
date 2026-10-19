"""Synthetic recovered-state UI composition; no deployment or wallet signing."""
import http.client
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest

from exchange import fixtures as F
from exchange.aggregate_checkpoint import AggregateCheckpointStore
from exchange.checkpoint_workbench_composition import (compose_checkpoint_workbench,
                                                      CheckpointWorkbenchUnavailable)
from exchange.errors import DomainError
from exchange.exchange_fact_snapshot import encode_exchange_snapshot
from exchange.exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint
from exchange.tests.test_rollback import refused_at_ab
from exchange.rollback_page import WORDS as ROLLBACK_WORDS
from integration.test_exchange_fact_rehydration import current_runtime
from integration import test_serialized_workbench_composition as original_composition


R = "rcpt-8415-0001"
SCOPE = "synthetic-recovered-workbench"


class CheckpointWorkbenchCompositionTests(unittest.TestCase):
    def setUp(self):
        original = original_composition.SerializedWorkbenchCompositionTests("runTest")
        original.setUp()
        self.addCleanup(original.doCleanups)
        self.original = original
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db = sqlite3.connect(Path(directory.name) / "workbench.db")
        self.addCleanup(self.db.close)
        self.db.execute("PRAGMA synchronous=FULL")
        AggregateCheckpointStore.initialize(self.db)
        self.checkpoint = ExchangeSnapshotCheckpoint(AggregateCheckpointStore(self.db,
            components=("owned-facts",), source_commit="a" * 40, source_tree="b" * 40))
        self.exchange, self.clock, _ = refused_at_ab(return_outcomes={
            "return:" + R + ":restored-workbench": "unknown"})
        self.exchange.begin_rollback(R, 0, F.rollback_authority(self.exchange, 0, "restored-workbench"))
        self.exchange.advance_rollback(R)
        self.checkpoint.save(SCOPE, encode_exchange_snapshot(self.exchange), expected_generation=0)

    def compose(self, *, scope=SCOPE, exchange=None, receipt_id=R, **options):
        exchange = self.exchange if exchange is None else exchange
        result = compose_checkpoint_workbench(self.checkpoint, scope, current_runtime(exchange), receipt_id,
            gas_page=self.original.gas, registration_sources=self.original.server.registration_sources,
            current_time=exchange._clock, commit="c" * 40, tree="d" * 40, port=0, **options)
        self.addCleanup(result.server.server_close)
        return result

    def request(self, server, path):
        worker = threading.Thread(target=server.serve_forever,
                                  kwargs={"poll_interval": 0.02}, daemon=True)
        worker.start()
        connection = http.client.HTTPConnection(*server.server_address, timeout=3)
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            return response.status, response.read().decode()
        finally:
            connection.close()
            server.shutdown()
            worker.join(3)

    def test_primary_page_uses_loaded_unknown_direct_return_without_starting_service(self):
        result = self.compose()
        self.assertIs(result.server.binding.exchange, result.checkpoint.access)
        self.assertEqual(result.checkpoint.generation, 1)
        report = result.server.binding.snapshot()["state"]["rollback"]
        self.assertFalse(report["complete"])
        self.assertEqual(report["state"], "blocked")
        self.assertFalse(report["assetControl"]["returned"])
        self.assertEqual(result.server.source["commit"], "c" * 40)
        self.assertEqual(self.original.calls, [])
        self.assertEqual(result.server.server_address[0], "127.0.0.1")

    def test_six_locale_rollback_routes_read_unknown_without_wallet_enquiry_or_send(self):
        result = self.compose()
        before = (self.exchange.payments.movements, self.exchange.asset_control.returns)
        original_lookup = self.exchange.asset_control.lookup
        def forbidden_lookup(key):
            raise AssertionError("read-only page enquired native controller")
        self.exchange.asset_control.lookup = forbidden_lookup
        try:
            for locale in ("en", "zh-Hans", "zh-Hant", "fr", "es", "ja"):
                with self.subTest(locale=locale):
                    status, body = self.request(result.server, "/rollback?lang=" + locale)
                    self.assertEqual(status, 200)
                    self.assertIn(ROLLBACK_WORDS[locale]["heading"], body)
                    self.assertNotIn("data-hop-progress", body)
                    self.assertNotIn(F.D, body)
                    self.assertNotIn(F.A, body)
        finally:
            self.exchange.asset_control.lookup = original_lookup
        self.assertEqual(self.original.calls, [])
        self.assertEqual((self.exchange.payments.movements, self.exchange.asset_control.returns), before)

    def test_original_enquiry_completion_refreshes_same_loaded_writer_without_resend(self):
        result = self.compose()
        key = "return:" + R + ":restored-workbench"
        self.exchange.asset_control.resolve_unknown(key, "returned")
        report = result.checkpoint.access.advance_rollback(R)
        self.assertTrue(report["complete"])
        self.assertEqual(result.checkpoint.access.owner_of(R), F.A)
        self.assertTrue(result.server.binding.snapshot()["state"]["rollback"]["complete"])
        status, body = self.request(result.server, "/rollback?lang=en")
        self.assertEqual(status, 200)
        self.assertIn(ROLLBACK_WORDS["en"]["heading"], body)
        self.assertEqual(self.exchange.rollback_report(R)["state"], "blocked")
        self.assertEqual(self.exchange.asset_control.returns, 0)
        self.assertEqual(len(self.exchange.asset_control._records), 1)
        self.assertEqual(self.exchange.payments.movements, 3)

    def test_directory_bindings_share_the_same_restored_instance_and_current_source(self):
        exchange = self.original.exchange
        self.checkpoint.save("synthetic-two-receipts", encode_exchange_snapshot(exchange), expected_generation=0)
        result = self.compose(scope="synthetic-two-receipts", exchange=exchange,
            receipt_id="receipt-1", detail_receipts=(("receipt-2", {}),))
        self.assertGreaterEqual(len(result.server.nft_directory._bindings), 2)
        for binding in result.server.nft_directory._bindings.values():
            self.assertIs(binding.exchange, result.checkpoint.access)
            self.assertEqual(binding.run["commit"], "c" * 40)

    def test_original_gateway_is_forwarded_without_enquiry_or_dispatch_during_mount(self):
        class Gateway:
            def enquire(self, *args):
                raise AssertionError("mount enquired a command")
            def dispatch(self, *args):
                raise AssertionError("mount dispatched a command")
        gateway = Gateway()
        result = self.compose(runtime_options={"gateway": gateway})
        self.assertIs(result.server.binding.gateway, gateway)
        self.assertEqual(self.original.calls, [])

    def test_absent_checkpoint_is_unavailable_instead_of_fixture_or_empty_success(self):
        with self.assertRaises(CheckpointWorkbenchUnavailable):
            self.compose(scope="synthetic-absent")

    def test_receipt_not_in_saved_state_is_refused_before_mount(self):
        with self.assertRaises(DomainError):
            self.compose(receipt_id="not-in-checkpoint")
