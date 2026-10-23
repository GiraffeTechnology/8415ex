"""Foreground entry contracts for installed original operation routes; NOT_RUN."""
import unittest
from unittest.mock import patch

from exchange.recovered_workbench_serve import serve_recovered_workbench_ui
from exchange.remint_review_workbench import RemintReviewWorkbenchServer
from integration import test_recovered_operation_observation as original_ui
from integration.test_exchange_fact_rehydration import current_runtime


class RecoveredOperationServeContracts(unittest.TestCase):
    def setUp(self):
        self.ui = original_ui.RecoveredOperationObservationContracts("runTest")
        self.ui.setUp()
        self.addCleanup(self.ui.doCleanups)
        self.host = self.ui.host

    def run_entry(self, **changes):
        fixture = self.host.fixture
        options = dict(operation_observation_inputs=self.ui.inputs(),
            gas_page=self.ui.ui.ui.gas,
            registration_sources=self.ui.ui.ui.server.registration_sources,
            current_time=lambda: 110, commit="c" * 40, tree="d" * 40, port=0)
        options.update(changes)
        return serve_recovered_workbench_ui(fixture.checkpoint, "original-instance",
            current_runtime(fixture.exchange), self.host.old.receipt.receipt_id,
            **options)

    def test_foreground_enquiry_does_not_require_current_draft_or_action(self):
        replies, servers = [], []
        changes = (self.host.fixture.claim_db.total_changes,
                   self.host.fixture.snapshot_db.total_changes)
        def loop(server, *args, **kwargs):
            servers.append(server)
            replies.append(self.ui.request(server, "/operation-observation?lang=ja"))
            replies.append(self.ui.request(server, "/remint-action?lang=ja"))
        with patch.object(RemintReviewWorkbenchServer, "serve_forever", loop):
            loaded = self.run_entry()
        self.assertEqual([r[0] for r in replies], [200, 503])
        self.assertIn('lang="ja"', replies[0][1])
        self.assertIs(loaded.server, servers[0])
        self.assertEqual(loaded.server.socket.fileno(), -1)
        self.assertEqual(self.ui.enquiries, [self.host.scope])
        self.assertEqual(self.host.calls, [])
        self.assertEqual((self.host.fixture.claim_db.total_changes,
                          self.host.fixture.snapshot_db.total_changes), changes)

    def test_installed_action_and_observation_share_one_restored_access(self):
        servers = []
        with patch.object(RemintReviewWorkbenchServer, "serve_forever",
                          lambda server: servers.append(server)):
            loaded = self.run_entry(remint_action_inputs=self.ui.ui.inputs(),
                read_draft_specifications=self.ui.ui.read_specs)
        self.assertEqual(len(servers), 1)
        server = loaded.server
        self.assertIs(server.remint_action.bridge.access, loaded.checkpoint.access)
        self.assertIs(server.checkpointed_observation.bridge.access, loaded.checkpoint.access)
        self.assertIs(server.remint_action.bridge.journal,
                      server.checkpointed_observation.bridge.journal)
        self.assertEqual(loaded.checkpoint.generation, 1)
        self.assertEqual(self.ui.enquiries, [])
        self.assertEqual(self.ui.ui.reads, [])
        self.assertEqual(self.host.calls, [])
        self.assertEqual(server.socket.fileno(), -1)

    def test_missing_observation_configuration_only_affects_its_foreground_route(self):
        replies = []
        def loop(server, *args, **kwargs):
            replies.append(self.ui.request(server, "/operation-observation"))
            replies.append(self.ui.request(server, "/market"))
        with patch.object(RemintReviewWorkbenchServer, "serve_forever", loop):
            loaded = self.run_entry(operation_observation_inputs=None)
        self.assertEqual([r[0] for r in replies], [503, 200])
        self.assertEqual(self.ui.enquiries, [])
        self.assertEqual(self.host.calls, [])
        self.assertEqual(loaded.server.socket.fileno(), -1)

    def test_native_enquiry_failure_is_generic_and_keeps_other_pages_available(self):
        replies = []
        def unavailable(scope):
            self.ui.enquiries.append(scope)
            raise RuntimeError("PRIVATE_ORIGINAL_GATEWAY_DETAIL")
        def loop(server, *args, **kwargs):
            replies.append(self.ui.request(server, "/operation-observation"))
            replies.append(self.ui.request(server, "/market"))
        with patch.object(RemintReviewWorkbenchServer, "serve_forever", loop):
            loaded = self.run_entry(
                operation_observation_inputs=self.ui.inputs(enquire_original=unavailable))
        self.assertEqual([r[0] for r in replies], [503, 200])
        self.assertNotIn("PRIVATE_ORIGINAL_GATEWAY_DETAIL", replies[0][1])
        self.assertEqual(self.ui.enquiries, [self.host.scope])
        self.assertEqual(self.host.calls, [])
        self.assertEqual(loaded.server.socket.fileno(), -1)
        self.assertEqual(self.host.fixture.claim_db.execute("SELECT 1").fetchone(), (1,))
