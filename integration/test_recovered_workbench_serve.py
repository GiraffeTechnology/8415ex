"""Synthetic saved-state foreground service entry contracts; author NOT_RUN."""
import http.client
import threading
import unittest
from unittest.mock import patch

from exchange.checkpoint_workbench_composition import CheckpointWorkbenchUnavailable
from exchange.recovered_workbench_serve import serve_recovered_workbench_ui
from exchange.remint_review_workbench import RemintReviewWorkbenchServer
from integration.test_exchange_fact_rehydration import current_runtime
from integration import test_recovered_workbench_ui as original_ui


class RecoveredWorkbenchServeContracts(unittest.TestCase):
    def setUp(self):
        self.ui = original_ui.RecoveredWorkbenchUITests("runTest")
        self.ui.setUp()
        self.addCleanup(self.ui.doCleanups)

    def run_entry(self, scope="original-scope", **options):
        return serve_recovered_workbench_ui(self.ui.checkpoint, scope,
            current_runtime(self.ui.host.exchange), "receipt-1",
            gas_page=self.ui.host.gas,
            registration_sources=self.ui.host.server.registration_sources,
            current_time=lambda: 110, commit="c" * 40, tree="d" * 40,
            detail_receipts=(("receipt-2", {}),),
            remint_review=self.ui.host.review, port=0, **options)

    def test_foreground_entry_serves_recovered_page_then_closes_only_its_socket(self):
        captured = []
        responses = []
        failures = []
        changes = self.ui.db.total_changes

        def one_request(server, *args, **kwargs):
            captured.append(server)
            def client():
                connection = http.client.HTTPConnection(*server.server_address, timeout=3)
                try:
                    connection.request("GET", "/remint-draft?lang=fr")
                    response = connection.getresponse()
                    responses.append((response.status, response.read().decode()))
                except BaseException as error:
                    failures.append(error)
                finally:
                    connection.close()
            worker = threading.Thread(target=client, daemon=True)
            worker.start()
            server.timeout = 3
            server.handle_request()
            worker.join(4)
            self.assertFalse(worker.is_alive())

        with patch.object(RemintReviewWorkbenchServer, "serve_forever", one_request):
            loaded = self.run_entry(read_draft_specifications=self.ui.read_specs,
                collateral_selection=True, scenario_selection=True)
        self.assertEqual(failures, [])
        self.assertEqual(len(captured), 1)
        self.assertEqual(responses[0][0], 200)
        self.assertIn('lang="fr"', responses[0][1])
        self.assertIs(loaded.server, captured[0])
        self.assertEqual(loaded.server.socket.fileno(), -1)
        self.assertIs(loaded.server.binding.exchange, loaded.checkpoint.access)
        self.assertEqual(loaded.checkpoint.generation, 1)
        self.assertEqual(self.ui.db.total_changes, changes)
        self.assertEqual(self.ui.db.execute("SELECT 1").fetchone(), (1,))
        self.assertEqual(self.ui.host.calls, [])

    def test_interrupt_closes_composed_socket_without_closing_original_store(self):
        captured = []
        def interrupted(server, *args, **kwargs):
            captured.append(server)
            raise KeyboardInterrupt()
        changes = self.ui.db.total_changes
        with patch.object(RemintReviewWorkbenchServer, "serve_forever", interrupted):
            with self.assertRaises(KeyboardInterrupt):
                self.run_entry()
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].socket.fileno(), -1)
        self.assertEqual(self.ui.db.execute("SELECT 1").fetchone(), (1,))
        self.assertEqual(self.ui.db.total_changes, changes)
        self.assertEqual(self.ui.host.calls, [])
        self.assertEqual(self.ui.reads, [])

    def test_missing_checkpoint_never_starts_an_empty_service_or_writes_store(self):
        changes = self.ui.db.total_changes
        with patch.object(RemintReviewWorkbenchServer, "serve_forever") as serve:
            with self.assertRaises(CheckpointWorkbenchUnavailable):
                self.run_entry(scope="missing-original-scope")
            serve.assert_not_called()
        self.assertEqual(self.ui.db.total_changes, changes)
        self.assertEqual(self.ui.host.calls, [])

    def test_loop_error_is_preserved_and_does_not_retry_or_dispatch(self):
        captured = []
        error = RuntimeError("original loop failed")
        def failed(server, *args, **kwargs):
            captured.append(server)
            raise error
        with patch.object(RemintReviewWorkbenchServer, "serve_forever", failed):
            with self.assertRaises(RuntimeError) as caught:
                self.run_entry()
        self.assertIs(caught.exception, error)
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].socket.fileno(), -1)
        self.assertEqual(self.ui.host.calls, [])
