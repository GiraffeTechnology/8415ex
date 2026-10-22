"""Approved-Linux contracts for original factory remint read-view wiring."""
from copy import deepcopy
import http.client
import json
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from exchange.checkpoint_workbench_composition import (
    compose_checkpoint_workbench, CheckpointWorkbenchUnavailable,
)
from exchange.remint_history_workbench import RemintChainHistoryBinding
from exchange.remint_receipt_workbench import RemintReceiptViewBinding
from exchange.remint_review_workbench import RemintReviewWorkbenchServer
from exchange.remint_workbench import RemintWorkbenchServer
from exchange.serialized_workbench_composition import compose_serialized_workbench
from integration import test_serialized_workbench_composition as original_factory
from integration import test_remint_receipt_observation as receipts


class OriginalRemintFactoryContracts(unittest.TestCase):
    def setUp(self):
        fixture = original_factory.SerializedWorkbenchCompositionTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.history_calls, self.receipt_calls = [], []
        def history(scope):
            self.history_calls.append(deepcopy(scope))
            raise RuntimeError("PRIVATE_READER_ERROR")
        self.history = RemintChainHistoryBinding("receipt-1", receipts.CONTRACT,
            receipts.REPLACEMENT["billKey"], "2", history)
        observation = receipts.RemintReceiptObservationContracts("runTest")
        observation.setUp()
        self.addCleanup(observation.doCleanups)
        def read_receipt():
            self.receipt_calls.append("read")
            return json.dumps(observation.receipt).encode()
        context = {"attempt_id":"fixture-attempt", "transaction_hash":receipts.TX,
            "proof_reference":"private-original-proof", "contract":receipts.CONTRACT,
            "operation_id":receipts.OP, "old_token_id":"2", "actor":receipts.ACTOR,
            "replacement":deepcopy(receipts.REPLACEMENT)}
        self.receipt = RemintReceiptViewBinding("receipt-1", observation.observer,
                                                read_receipt, context)
        self.options = dict(gas_page=fixture.gas,
            registration_sources=fixture.server.registration_sources,
            current_time=lambda:110, commit="a"*40, tree="b"*40, port=0,
            detail_receipts=(("receipt-2", {}),), remint_review=fixture.review)

    def compose(self, **views):
        server = compose_serialized_workbench(self.fixture.access, "receipt-1",
                                              **self.options, **views)
        self.addCleanup(server.server_close)
        return server

    def request(self, server, method, path, body=None):
        worker = threading.Thread(target=server.serve_forever,
                                  kwargs={"poll_interval":0.02}, daemon=True)
        worker.start()
        connection = http.client.HTTPConnection(*server.server_address, timeout=3)
        try:
            connection.request(method, path, body)
            response = connection.getresponse()
            return response.status, response.read().decode()
        finally:
            connection.close()
            server.shutdown()
            worker.join(3)

    def test_factory_retains_same_primary_and_directory_access_and_source(self):
        server = self.compose(remint_history=self.history, remint_receipt=self.receipt)
        self.assertIs(type(server), RemintWorkbenchServer)
        self.assertIs(server.binding.exchange, self.fixture.access)
        for binding in server.nft_directory._bindings.values():
            self.assertIs(binding.exchange, self.fixture.access)
            self.assertEqual(binding.run, server.binding.run)
        self.assertIs(server.remint_history, self.history)
        self.assertIs(server.remint_receipt, self.receipt)
        self.assertEqual(self.history_calls, [])
        self.assertEqual(self.receipt_calls, [])
        self.assertEqual(self.fixture.calls, [])

    def test_missing_optional_readers_retains_original_factory_and_routes(self):
        server = self.compose()
        self.assertIs(type(server), RemintReviewWorkbenchServer)
        self.assertEqual(self.request(server, "GET", "/gas")[0], 200)
        self.assertEqual(self.request(server, "GET", "/remint-review")[0], 200)
        self.assertEqual(self.fixture.calls, [])

    def test_history_only_is_optional_and_failure_does_not_disable_gas(self):
        server = self.compose(remint_history=self.history)
        status, body = self.request(server, "GET", "/remint-history")
        self.assertEqual(status, 503)
        self.assertNotIn("PRIVATE_READER_ERROR", body)
        self.assertEqual(len(self.history_calls), 1)
        self.assertEqual(self.request(server, "GET", "/gas")[0], 200)
        self.assertEqual(self.request(server, "GET", "/remint-result")[0], 503)
        self.assertEqual(self.receipt_calls, [])
        self.assertEqual(self.fixture.calls, [])

    def test_result_only_uses_original_receipt_without_history_preflight(self):
        server = self.compose(remint_receipt=self.receipt)
        status, body = self.request(server, "GET", "/remint-result?lang=en")
        self.assertEqual(status, 200)
        self.assertIn("9", body)
        self.assertNotIn(receipts.ACTOR, body)
        self.assertNotIn(receipts.CONTRACT, body)
        self.assertEqual(self.receipt_calls, ["read"])
        self.assertEqual(self.history_calls, [])
        self.assertEqual(self.fixture.calls, [])

    def test_post_views_never_call_original_readers_or_wallet(self):
        server = self.compose(remint_history=self.history, remint_receipt=self.receipt)
        for path in ("/remint-history", "/remint-result"):
            self.assertEqual(self.request(server, "POST", path, "retry=true")[0], 405)
        self.assertEqual(self.history_calls, [])
        self.assertEqual(self.receipt_calls, [])
        self.assertEqual(self.fixture.calls, [])

    def test_original_gateway_is_retained_without_factory_enquiry_or_dispatch(self):
        class Gateway:
            def enquire(self, *args):
                raise AssertionError("No factory preflight")
            def dispatch(self, *args):
                raise AssertionError("No factory execution")
        gateway = Gateway()
        self.options["runtime_options"] = {"gateway":gateway}
        server = self.compose(remint_history=self.history, remint_receipt=self.receipt)
        self.assertIs(server.binding.gateway, gateway)
        self.assertEqual(self.history_calls, [])
        self.assertEqual(self.receipt_calls, [])

    def test_checkpoint_loads_once_and_forwards_readers_on_same_loaded_access(self):
        original_checkpoint, scope, runtime = object(), object(), object()
        loaded = SimpleNamespace(access=self.fixture.access)
        with patch("exchange.checkpoint_workbench_composition.load_exchange_checkpoint",
                   return_value=loaded) as loader:
            result = compose_checkpoint_workbench(original_checkpoint, scope, runtime,
                "receipt-1", **self.options, remint_history=self.history,
                remint_receipt=self.receipt)
        self.addCleanup(result.server.server_close)
        loader.assert_called_once_with(original_checkpoint, scope, runtime)
        self.assertIs(result.checkpoint, loaded)
        self.assertIs(result.server.binding.exchange, loaded.access)
        self.assertIs(result.server.remint_history, self.history)
        self.assertIs(result.server.remint_receipt, self.receipt)
        self.assertEqual(self.history_calls, [])
        self.assertEqual(self.receipt_calls, [])
        self.assertEqual(self.fixture.calls, [])

    def test_absent_checkpoint_never_creates_empty_state_or_reads_native_views(self):
        with patch("exchange.checkpoint_workbench_composition.load_exchange_checkpoint",
                   return_value=None):
            with self.assertRaises(CheckpointWorkbenchUnavailable):
                compose_checkpoint_workbench(object(), object(), object(), "receipt-1",
                    **self.options, remint_history=self.history,
                    remint_receipt=self.receipt)
        self.assertEqual(self.history_calls, [])
        self.assertEqual(self.receipt_calls, [])
        self.assertEqual(self.fixture.calls, [])
