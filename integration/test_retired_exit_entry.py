"""Synthetic retired-entry definitions; preserve historical observations."""
from types import SimpleNamespace
import unittest

from exchange.workbench import ACTIONS, RuntimeBinding, WorkbenchHandler
from integration import test_operation_transport as transport


class RetiredExitEntryTests(unittest.TestCase):
    def test_retired_action_refuses_before_revision_or_gateway_callbacks(self):
        calls = []
        gateway = SimpleNamespace(enquire=lambda *args: calls.append('enquire'),
                                  dispatch=lambda *args: calls.append('dispatch'))
        binding = RuntimeBinding(object(), 'receipt-1', gateway=gateway)
        binding.snapshot = lambda: calls.append('snapshot')
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            binding.command('advance-exit', 'historical-key', '0' * 64, {})
        self.assertEqual(calls, [])
        self.assertNotIn('advance-exit', ACTIONS)

    def test_checked_queue_form_omits_retired_action_and_keeps_suffix_recovery(self):
        binding = SimpleNamespace(gateway=object(), snapshot=lambda: {'revision': '0' * 64})
        handler = WorkbenchHandler.__new__(WorkbenchHandler)
        handler.server = SimpleNamespace(binding=binding, csrf='synthetic-csrf')
        page = handler.queue_controls()
        self.assertNotIn('advance-exit', page)
        self.assertIn('advance-rollback', page)
        self.assertIn('submit-registration', page)

    def test_http_refuses_retired_and_unknown_actions_before_command_binding(self):
        fixture = transport.OperationTransportTests('runTest')
        self.addCleanup(fixture.doCleanups)
        server = fixture.server()
        for action in ('advance-exit', 'manual-success'):
            with self.subTest(action=action):
                status, _, _ = fixture.request(server, fixture.body(server, action=action))
                self.assertEqual(status, 400)
        self.assertEqual(fixture.calls, [])
