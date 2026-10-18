"""Approved-remote-only source/file-SQLite contracts, not live financial PASS."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from exchange.wallet_api_client import WalletAPIClient, WalletAPIRefused
from exchange.wallet_execution_attempts import WalletExecutionAttempts
from integration.test_wallet_execution_attempts import BINDING, REQUEST


def client(store=None):
    return WalletAPIClient(BINDING["origin"], BINDING["tenant"], BINDING["account"],
                           BINDING["chainId"], execution_attempts=store)


class RequiredWalletAttemptStore(unittest.TestCase):
    def test_execute_without_durable_store_is_refused_before_session_or_transport(self):
        value = client()
        calls = []
        value.session = lambda: calls.append("session")
        value._request = lambda *args: calls.append(args)
        with self.assertRaisesRegex(WalletAPIRefused, "EX_WALLET_DURABLE_ATTEMPT_STORE_REQUIRED"):
            value.task("execute", REQUEST)
        self.assertEqual(calls, [])

    def test_original_reconciliation_routes_remain_available_without_attempt_store(self):
        value = client()
        sessions, calls = [], []
        value.session = lambda: sessions.append("checked")
        value._request = lambda route, payload: calls.append((route, payload)) or {"status": "unknown"}
        for action in ("status", "recover", "observe"):
            payload = {"taskDigest": REQUEST["taskDigest"]} if action == "status" else dict(REQUEST)
            self.assertEqual(value.task(action, payload), {"status": "unknown"})
        self.assertEqual([route for route, _ in calls], ["tasks/status", "tasks/recover", "tasks/observe"])
        self.assertEqual(len(sessions), 3)

    def test_original_committed_attempt_precedes_transport_and_blocks_restarted_client(self):
        with TemporaryDirectory() as root:
            path = str(Path(root) / "explicit-attempts.sqlite")
            value = client(WalletExecutionAttempts(path))
            value.session = lambda: {"authenticated": True}
            calls = []
            def execute(route, payload):
                # A separately opened connection sees the committed claim before
                # any transport callback is allowed to represent a send.
                self.assertFalse(WalletExecutionAttempts(path).claim(BINDING, payload))
                calls.append(route)
                return {"status": "pending"}
            value._request = execute
            self.assertEqual(value.task("execute", REQUEST), {"status": "pending"})
            reopened = client(WalletExecutionAttempts(path))
            reopened.session = lambda: {"authenticated": True}
            reopened._request = lambda *args: calls.append("unexpected-second-send")
            with self.assertRaisesRegex(WalletAPIRefused, "EX_WALLET_ATTEMPT_RECONCILE_FIRST"):
                reopened.task("execute", dict(REQUEST, expectedBudgetRevision=1))
            self.assertEqual(calls, ["tasks/execute"])

    def test_failed_original_session_neither_claims_attempt_nor_sends(self):
        with TemporaryDirectory() as root:
            path = str(Path(root) / "explicit-attempts.sqlite")
            value = client(WalletExecutionAttempts(path))
            def no_session():
                raise WalletAPIRefused("EX_WALLET_LOGIN_REQUIRED")
            value.session = no_session
            calls = []
            value._request = lambda *args: calls.append(args)
            with self.assertRaisesRegex(WalletAPIRefused, "EX_WALLET_LOGIN_REQUIRED"):
                value.task("execute", REQUEST)
            self.assertEqual(calls, [])
            self.assertTrue(WalletExecutionAttempts(path).claim(BINDING, REQUEST))
