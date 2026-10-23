"""Synthetic recovered remint route contracts; author execution NOT_RUN."""
from dataclasses import replace
import http.client
import re
import threading
import unittest
from urllib.parse import urlencode
from unittest.mock import patch

from exchange.exchange_fact_snapshot import encode_exchange_snapshot
from exchange.recovered_remint_action import (OriginalRemintActionInputs,
                                             compose_recovered_remint_action)
from exchange.remint_draft_action import WORDS
from integration import test_checkpointed_remint as original
from integration import test_serialized_workbench_composition as original_ui
from integration.test_exchange_fact_rehydration import current_runtime


class RecoveredRemintActionContracts(unittest.TestCase):
    def setUp(self):
        self.host = original.CheckpointedRemintTests("runTest")
        self.host.setUp()
        self.addCleanup(self.host.doCleanups)
        self.ui = original_ui.SerializedWorkbenchCompositionTests("runTest")
        self.ui.setUp()
        self.addCleanup(self.ui.doCleanups)
        fixture = self.host.fixture
        fixture.checkpoint.save("original-instance", encode_exchange_snapshot(fixture.exchange),
                                expected_generation=0)
        self.reads, self.enquiries = [], []
        self.unavailable = False

    def read_specs(self, receipt_id):
        self.reads.append(receipt_id)
        if self.unavailable:
            raise RuntimeError("PRIVATE_DECLARATION_DIAGNOSTIC")
        return self.host.old, self.host.new

    def inputs(self, **changes):
        value = OriginalRemintActionInputs(self.host.fixture.journal,
            self.host.history, self.host.scope, 0, self.host.verify, original.bill,
            lambda scope: self.enquiries.append(scope), self.host.execute)
        return replace(value, **changes)

    def compose(self, **changes):
        fixture = self.host.fixture
        options = dict(remint_action_inputs=self.inputs(),
            read_draft_specifications=self.read_specs, collateral_selection=True,
            scenario_selection=True, gas_page=self.ui.gas,
            registration_sources=self.ui.server.registration_sources,
            current_time=lambda: 110, commit="c" * 40, tree="d" * 40, port=0)
        options.update(changes)
        loaded = compose_recovered_remint_action(fixture.checkpoint,
            "original-instance", current_runtime(fixture.exchange),
            self.host.old.receipt.receipt_id, **options)
        self.addCleanup(loaded.server.server_close)
        return loaded

    def request(self, server, path, method="GET", body=None):
        response, errors = [], []
        headers = {} if method == "GET" else {
            "Origin": server.origin, "Content-Type": "application/x-www-form-urlencoded"}
        def client():
            connection = http.client.HTTPConnection(*server.server_address, timeout=3)
            try:
                connection.request(method, path, body=body, headers=headers)
                result = connection.getresponse()
                response.append((result.status, result.read().decode()))
            except BaseException as error:
                errors.append(error)
            finally:
                connection.close()
        worker = threading.Thread(target=client, daemon=True)
        worker.start()
        server.timeout = 3
        server.handle_request()
        worker.join(4)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        return response[0]

    def test_composition_reuses_restored_access_original_stores_and_editor_without_effects(self):
        fixture = self.host.fixture
        before = (fixture.claim_db.total_changes, fixture.snapshot_db.total_changes)
        loaded = self.compose()
        action = loaded.server.remint_action
        self.assertIs(action.bridge.access, loaded.checkpoint.access)
        self.assertIsNot(action.bridge.access, fixture.access)
        self.assertIs(action.editor, loaded.server.draft_editor)
        self.assertIs(action.bridge.checkpoint, fixture.checkpoint)
        self.assertIs(action.bridge.journal, fixture.journal)
        self.assertIs(action._history, self.host.history)
        self.assertEqual(action.bridge.checkpoint_scope, loaded.checkpoint.scope)
        self.assertEqual(loaded.checkpoint.generation, 1)
        self.assertEqual(self.reads, [])
        self.assertEqual(self.enquiries, [])
        self.assertEqual(self.host.calls, [])
        self.assertEqual((fixture.claim_db.total_changes, fixture.snapshot_db.total_changes), before)

    def test_six_locale_navigation_retains_editor_market_and_selectors(self):
        server = self.compose().server
        for locale in WORDS:
            status, body = self.request(server, "/market?lang=" + locale)
            self.assertEqual(status, 200)
            for route in ("/remint-action", "/remint-draft", "/collateral", "/scenarios"):
                self.assertEqual(body.count('href="' + route + '?lang=' + locale + '"'), 1)
                self.assertEqual(self.request(server, route + "?lang=" + locale)[0], 200)
        self.assertEqual(self.host.calls, [])
        self.assertEqual(self.enquiries, [])

    def test_recovered_form_saves_original_preimage_and_history_before_one_native_call(self):
        loaded = self.compose()
        server = loaded.server
        status, body = self.request(server, "/remint-action")
        self.assertEqual(status, 200)
        proposal = re.search('name="proposal" value="([0-9a-f]{64})"', body).group(1)
        form = urlencode(dict(csrf=server.csrf, lang="en", proposal=proposal, revision="0"))
        self.assertEqual(self.request(server, "/remint-action", "POST", form)[0], 202)
        self.assertEqual(len(self.host.calls), 1)
        self.assertIsNotNone(self.host.history.read(self.host.scope))
        bridge = server.remint_action.bridge
        self.assertEqual(self.host.fixture.checkpoint.read(
            bridge.pre_effect_scope(self.host.scope))["generation"], 1)
        self.assertEqual(self.host.fixture.checkpoint.read("original-instance")["generation"], 1)
        self.assertEqual(self.host.fixture.journal.lookup(
            self.host.scope["nativeOperationId"])["status"], "UNKNOWN")

    def test_absent_action_configuration_and_unavailable_reader_are_route_local(self):
        server = self.compose(remint_action_inputs=None, read_draft_specifications=None).server
        self.assertEqual(self.request(server, "/remint-action")[0], 503)
        self.assertEqual(self.request(server, "/market")[0], 200)
        configured = self.compose().server
        self.unavailable = True
        status, body = self.request(configured, "/remint-action")
        self.assertEqual(status, 503)
        self.assertNotIn("PRIVATE_DECLARATION_DIAGNOSTIC", body)
        self.assertEqual(self.request(configured, "/market")[0], 200)
        self.assertEqual(self.enquiries, [])
        self.assertEqual(self.host.calls, [])

    def test_invalid_config_and_missing_draft_fail_before_checkpoint_load(self):
        with patch("exchange.recovered_remint_action.compose_recovered_workbench_ui") as compose:
            for options in ({"remint_action_inputs": {}},
                            {"remint_action_inputs": self.inputs()}):
                with self.subTest(options=options), self.assertRaises(ValueError):
                    compose_recovered_remint_action(None, None, None, None, **options)
            compose.assert_not_called()

    def test_foreign_receipt_refuses_action_and_closes_only_new_socket(self):
        inputs = self.inputs(binding=dict(self.host.scope, receiptId="foreign-receipt"))
        # Retain the actual composed server to check socket ownership on failure.
        from exchange.recovered_workbench_ui import compose_recovered_workbench_ui
        servers = []
        def compose(*args, **kwargs):
            result = compose_recovered_workbench_ui(*args, **kwargs)
            servers.append(result.server)
            return result
        with patch("exchange.recovered_remint_action.compose_recovered_workbench_ui", compose):
            with self.assertRaises(ValueError):
                self.compose(remint_action_inputs=inputs)
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0].socket.fileno(), -1)
        self.assertEqual(self.host.fixture.claim_db.execute("SELECT 1").fetchone(), (1,))
        self.assertEqual(self.host.fixture.checkpoint.read("original-instance")["generation"], 1)
        self.assertEqual(self.host.calls, [])
