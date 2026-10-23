"""Recovered operation-enquiry composition contracts; author execution NOT_RUN."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from exchange.recovered_operation_observation import (
    OriginalOperationObservationInputs, compose_recovered_operation_observation)
from exchange.checkpointed_operation_page import WORDS
from integration import test_recovered_remint_action as original_ui
from integration.test_exchange_fact_rehydration import current_runtime


class RecoveredOperationObservationContracts(unittest.TestCase):
    def setUp(self):
        self.ui = original_ui.RecoveredRemintActionContracts("runTest")
        self.ui.setUp()
        self.addCleanup(self.ui.doCleanups)
        self.host = self.ui.host
        self.enquiries = []

    def inputs(self, **changes):
        inputs = OriginalOperationObservationInputs(self.host.fixture.journal,
            self.host.scope, lambda scope: self.enquiries.append(scope),
            self.host.history)
        return replace(inputs, **changes)

    def compose(self, **changes):
        fixture = self.host.fixture
        options = dict(operation_observation_inputs=self.inputs(),
            gas_page=self.ui.ui.gas,
            registration_sources=self.ui.ui.server.registration_sources,
            current_time=lambda: 110, commit="c" * 40, tree="d" * 40, port=0)
        options.update(changes)
        loaded = compose_recovered_operation_observation(fixture.checkpoint,
            "original-instance", current_runtime(fixture.exchange),
            self.host.old.receipt.receipt_id, **options)
        self.addCleanup(loaded.server.server_close)
        return loaded

    def request(self, server, path, method="GET", body=None):
        return self.ui.request(server, path, method, body)

    def test_restore_once_reuses_original_stores_without_enquiry_or_writes(self):
        fixture = self.host.fixture
        before = (fixture.claim_db.total_changes, fixture.snapshot_db.total_changes)
        loaded = self.compose()
        observation = loaded.server.checkpointed_observation
        self.assertIs(observation.bridge.access, loaded.checkpoint.access)
        self.assertIsNot(observation.bridge.access, fixture.access)
        self.assertIs(observation.bridge.checkpoint, fixture.checkpoint)
        self.assertIs(observation.bridge.journal, fixture.journal)
        self.assertIs(observation.remint_history, self.host.history)
        self.assertEqual(observation.bridge.checkpoint_scope, loaded.checkpoint.scope)
        self.assertEqual(loaded.checkpoint.generation, 1)
        self.assertEqual(self.enquiries, [])
        self.assertEqual(self.host.calls, [])
        self.assertEqual((fixture.claim_db.total_changes, fixture.snapshot_db.total_changes), before)

    def test_original_enquiry_works_without_current_draft_or_action_configuration(self):
        loaded = self.compose()
        self.assertEqual(self.request(loaded.server, "/remint-action")[0], 503)
        status, body = self.request(loaded.server, "/operation-observation")
        self.assertEqual(status, 200)
        self.assertEqual(self.enquiries, [self.host.scope])
        self.assertNotIn(self.host.scope["nativeOperationId"], body)
        self.assertEqual(self.host.calls, [])

    def test_absent_enquiry_is_route_local_and_does_not_disable_market(self):
        server = self.compose(operation_observation_inputs=None).server
        self.assertEqual(self.request(server, "/operation-observation")[0], 503)
        self.assertEqual(self.request(server, "/market")[0], 200)
        self.assertEqual(self.enquiries, [])
        self.assertEqual(self.host.calls, [])

    def test_all_locale_links_and_failed_draft_keep_original_enquiry_independent(self):
        server = self.compose(
            remint_action_inputs=self.ui.inputs(),
            read_draft_specifications=self.ui.read_specs).server
        self.ui.unavailable = True
        for locale in WORDS:
            status, body = self.request(server, "/market?lang=" + locale)
            self.assertEqual(status, 200)
            self.assertEqual(body.count('href="/operation-observation?lang=' + locale + '"'), 1)
            self.assertEqual(self.request(server, "/remint-action?lang=" + locale)[0], 503)
            self.assertEqual(self.request(server, "/operation-observation?lang=" + locale)[0], 200)
        self.assertEqual(len(self.enquiries), len(WORDS))
        self.assertEqual(self.host.calls, [])

    def test_invalid_inputs_fail_before_checkpoint_load(self):
        with patch("exchange.recovered_operation_observation.compose_recovered_remint_action") as compose:
            for inputs in ({}, self.inputs(enquire_original=None)):
                with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                    compose_recovered_operation_observation(None, None, None, None,
                        operation_observation_inputs=inputs)
            compose.assert_not_called()

    def test_foreign_receipt_closes_new_socket_and_preserves_original_stores(self):
        from exchange.recovered_remint_action import compose_recovered_remint_action
        servers = []
        def compose(*args, **kwargs):
            loaded = compose_recovered_remint_action(*args, **kwargs)
            servers.append(loaded.server)
            return loaded
        inputs = self.inputs(binding=dict(self.host.scope, receiptId="foreign-receipt"))
        with patch("exchange.recovered_operation_observation.compose_recovered_remint_action", compose):
            with self.assertRaises(ValueError):
                self.compose(operation_observation_inputs=inputs)
        self.assertEqual(len(servers), 1)
        self.assertEqual(servers[0].socket.fileno(), -1)
        self.assertEqual(self.host.fixture.claim_db.execute("SELECT 1").fetchone(), (1,))
        self.assertEqual(self.host.fixture.checkpoint.read("original-instance")["generation"], 1)
        self.assertEqual(self.enquiries, [])
        self.assertEqual(self.host.calls, [])
