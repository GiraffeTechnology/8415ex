"""Remote-only file-SQLite/source-client contracts, not native financial acceptance."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from exchange.wallet_api_client import WalletAPIClient, WalletAPIRefused
from exchange.wallet_execution_attempts import WalletExecutionAttempts


BINDING = {"origin": "https://wallet.example.invalid", "tenant": "ex",
           "account": "0x" + "1" * 40, "chainId": "11155111"}
REQUEST = {"taskDigest": "task", "operationId": "operation", "childDigest": "child", "expectedBudgetRevision": 0}


class WalletAttemptRecovery(unittest.TestCase):
    def test_reopen_and_changed_child_or_revision_cannot_create_second_send_slot(self):
        with TemporaryDirectory() as root:
            path = str(Path(root) / "attempts.sqlite")
            self.assertTrue(WalletExecutionAttempts(path).claim(BINDING, REQUEST))
            recovered = WalletExecutionAttempts(path)
            self.assertFalse(recovered.claim(BINDING, dict(REQUEST)))
            self.assertFalse(recovered.claim(BINDING, dict(REQUEST, childDigest="changed", expectedBudgetRevision=1)))
            self.assertTrue(recovered.claim(BINDING, dict(REQUEST, operationId="other-original-operation")))

    def test_concurrent_clients_have_only_one_committed_transport_attempt(self):
        with TemporaryDirectory() as root:
            path = str(Path(root) / "attempts.sqlite")
            stores = [WalletExecutionAttempts(path) for _ in range(4)]
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda store: store.claim(BINDING, REQUEST), stores))
            self.assertEqual(results.count(True), 1)

    def test_unknown_after_send_remains_blocked_on_new_client_but_original_recover_is_available(self):
        with TemporaryDirectory() as root:
            path = str(Path(root) / "attempts.sqlite")
            def client():
                value = WalletAPIClient(BINDING["origin"], BINDING["tenant"], BINDING["account"], BINDING["chainId"],
                                        execution_attempts=WalletExecutionAttempts(path))
                value.session = lambda: {"authenticated": True}
                return value
            first = client()
            def unavailable(*args):
                raise OSError("unknown after dispatch")
            first._request = unavailable
            with self.assertRaisesRegex(WalletAPIRefused, "EX_WALLET_EXECUTION_OUTCOME_UNKNOWN"):
                first.task("execute", REQUEST)
            second = client()
            calls = []
            second._request = lambda route, row: calls.append(route) or {"status": "unknown"}
            with self.assertRaisesRegex(WalletAPIRefused, "EX_WALLET_ATTEMPT_RECONCILE_FIRST"):
                second.task("execute", dict(REQUEST, expectedBudgetRevision=1))
            self.assertEqual(calls, [])
            self.assertEqual(second.task("recover", REQUEST), {"status": "unknown"})
            self.assertEqual(calls, ["tasks/recover"])

    def test_unavailable_store_never_reaches_execute_transport(self):
        with TemporaryDirectory() as root:
            store = WalletExecutionAttempts(str(Path(root) / "attempts.sqlite"))
            value = WalletAPIClient(BINDING["origin"], BINDING["tenant"], BINDING["account"], BINDING["chainId"], execution_attempts=store)
            value.session = lambda: {"authenticated": True}
            calls = []
            value._request = lambda *args: calls.append(args)
            store.claim = lambda *args: (_ for _ in ()).throw(OSError("private path"))
            with self.assertRaisesRegex(WalletAPIRefused, "EX_WALLET_ATTEMPT_STORE_UNAVAILABLE"):
                value.task("execute", REQUEST)
            self.assertEqual(calls, [])
