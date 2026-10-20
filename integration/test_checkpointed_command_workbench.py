"""Synthetic saved EX plus original command journals; no native provider calls."""
from copy import deepcopy
import http.client
from pathlib import Path
import sqlite3
import tempfile
import threading
from unittest.mock import patch
import unittest

from exchange.checkpointed_command_workbench import compose_checkpointed_command_workbench
from exchange.checkpoint_runtime_load import load_exchange_checkpoint
from exchange.checkpointed_workbench_gateway import CheckpointedWorkbenchGateway
from exchange.durable_operation import DurableEXOperationJournal
from exchange.checkpoint_workbench_composition import CheckpointWorkbenchUnavailable
from exchange.recovered_workbench_ui import compose_recovered_workbench_ui
from integration.test_exchange_fact_rehydration import current_runtime
from integration import test_recovered_workbench_ui as original_ui


class CheckpointedCommandWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.ui = original_ui.RecoveredWorkbenchUITests("runTest")
        self.ui.setUp()
        self.addCleanup(self.ui.doCleanups)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.claims = sqlite3.connect(Path(directory.name) / "original-native-claims.db")
        self.addCleanup(self.claims.close)
        self.claims.execute("PRAGMA synchronous=FULL")
        DurableEXOperationJournal.initialize(self.claims)
        self.journal = DurableEXOperationJournal(self.claims)
        CheckpointedWorkbenchGateway.initialize(self.journal)
        self.builders, self.native_calls, self.enquiries = [], [], []

    def ports(self, access, original_gateway):
        self.builders.append((access, original_gateway))
        def resolve(action, payload, context):
            asset = access.receipt(context["receiptId"]).asset
            return {"receiptId": context["receiptId"], "chainId": asset.chain_id,
                "contract": asset.contract, "tokenId": str(asset.token_id), "globalLegId": 0,
                "action": "rollback", "nativeOperationId": "synthetic-original-native-command",
                "intentDigest": "c" * 64, "journalReference": "synthetic-original-journal"}
        def enquire(scope):
            self.enquiries.append(deepcopy(scope))
            return None
        def execute(scope):
            self.assertEqual(self.journal.lookup(scope["nativeOperationId"])["status"], "UNKNOWN")
            self.native_calls.append((access, deepcopy(scope)))
            return {"status": "pending"}
        return {"resolve_command": resolve, "enquire_original": enquire, "execute_original": execute}

    def compose(self, *, builder=None, scope="original-scope", **extra):
        options = dict(gas_page=self.ui.host.gas,
            registration_sources=self.ui.host.server.registration_sources, current_time=lambda: 110,
            commit="c" * 40, tree="d" * 40, port=0, detail_receipts=(("receipt-2", {}),),
            remint_review=self.ui.host.review, read_draft_specifications=self.ui.read_specs,
            collateral_selection=True, scenario_selection=True)
        options.update(extra)
        result = compose_checkpointed_command_workbench(self.ui.checkpoint, scope,
            current_runtime(self.ui.host.exchange), "receipt-1", operation_journal=self.journal,
            make_original_ports=self.ports if builder is None else builder, **options)
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

    def test_builder_gateway_editor_and_primary_share_one_actual_loaded_access_without_effects(self):
        before = (self.ui.db.total_changes, self.claims.total_changes)
        with patch("exchange.checkpoint_workbench_composition.load_exchange_checkpoint",
                   wraps=load_exchange_checkpoint) as load:
            result = self.compose()
        access = result.checkpoint.access
        self.assertEqual(load.call_count, 1)
        self.assertEqual(len(self.builders), 1)
        self.assertIs(self.builders[0][0], access)
        self.assertIsNot(access, self.ui.host.access)
        self.assertIs(result.server.binding.exchange, access)
        self.assertIs(result.server.binding.gateway.bridge.access, access)
        self.assertIs(result.server.draft_editor.access, access)
        self.assertEqual((self.ui.db.total_changes, self.claims.total_changes), before)
        self.assertEqual(self.ui.reads, [])
        self.assertEqual(self.enquiries, [])
        self.assertEqual(self.native_calls, [])

    def test_original_runtime_command_uses_loaded_writer_and_pre_effect_snapshot(self):
        result = self.compose()
        binding = result.server.binding
        response = binding.command("advance-rollback", "synthetic-ui-key", binding.snapshot()["revision"], {})
        self.assertEqual(response["result"], {"status": "pending"})
        self.assertEqual(len(self.native_calls), 1)
        access, scope = self.native_calls[0]
        self.assertIs(access, result.checkpoint.access)
        bridge = binding.gateway.bridge
        self.assertEqual(self.ui.checkpoint.read(bridge.pre_effect_scope(scope))["generation"], 1)
        response = binding.command("advance-rollback", "synthetic-ui-key", binding.snapshot()["revision"], {})
        self.assertTrue(response["enquired"])
        self.assertEqual(response["result"], {"status": "unknown"})
        self.assertEqual(len(self.native_calls), 1)

    def test_draft_unavailability_does_not_block_original_command_or_selector_pages(self):
        self.ui.unavailable = True
        result = self.compose()
        status, body = self.request(result.server, "/remint-draft?lang=ja")
        self.assertEqual(status, 503)
        self.assertNotIn("private declaration diagnostic", body)
        for path in ("/market", "/collateral", "/scenarios", "/gas", "/registration-source"):
            self.assertEqual(self.request(result.server, path)[0], 200)
        binding = result.server.binding
        self.assertEqual(binding.command("advance-rollback", "another-ui-key", binding.snapshot()["revision"], {})
                         ["result"], {"status": "pending"})
        self.assertEqual(len(self.native_calls), 1)

    def test_existing_primary_gateway_is_preserved_as_registration_fallback(self):
        calls = []
        class OriginalGateway:
            def enquire(self, key, context):
                calls.append(("enquire", key))
                return None
            def dispatch(self, action, payload, context):
                calls.append(("dispatch", action, payload))
                return {"status": "pending"}
        original = OriginalGateway()
        result = self.compose(runtime_options={"gateway": original})
        self.assertIs(self.builders[0][1], original)
        self.assertIs(result.server.binding.gateway.fallback_gateway, original)
        binding = result.server.binding
        value = binding.command("submit-registration", "registration-ui-key", binding.snapshot()["revision"], {"legIndex": 0})
        self.assertEqual(value["result"], {"status": "pending"})
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.enquiries, [])
        self.assertEqual(self.native_calls, [])

    def test_detail_bindings_keep_individual_original_gateway_and_loaded_source(self):
        detail_gateway = object()
        result = self.compose(detail_receipts=(("receipt-2", {"gateway": detail_gateway}),))
        details = list(result.server.nft_directory._bindings.values())
        second = next(binding for binding in details if binding.receipt_id == "receipt-2")
        self.assertIs(second.gateway, detail_gateway)
        self.assertIs(second.exchange, result.checkpoint.access)
        self.assertEqual(second.run["commit"], "c" * 40)
        self.assertIsNot(second.gateway, result.server.binding.gateway)

    def test_bad_port_builder_closes_constructed_socket_without_schema_or_native_work(self):
        captured = []
        def capture(*args, **kwargs):
            loaded = compose_recovered_workbench_ui(*args, **kwargs)
            captured.append(loaded.server)
            return loaded
        before = self.claims.total_changes
        with patch("exchange.checkpointed_command_workbench.compose_recovered_workbench_ui", side_effect=capture):
            with self.assertRaises(ValueError):
                self.compose(builder=lambda access, previous: {"resolve_command": lambda *args: None})
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].socket.fileno(), -1)
        self.assertEqual(self.claims.total_changes, before)
        self.assertEqual(self.native_calls, [])

    def test_absent_original_checkpoint_does_not_build_ports_or_create_fixture(self):
        with self.assertRaises(CheckpointWorkbenchUnavailable):
            self.compose(scope="absent-original-scope")
        self.assertEqual(self.builders, [])
        self.assertEqual(self.enquiries, [])
        self.assertEqual(self.native_calls, [])
