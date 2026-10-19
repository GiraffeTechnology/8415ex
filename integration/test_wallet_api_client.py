"""Synthetic HTTP protocol tests only; never installed Wallet/financial evidence."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest

from exchange.wallet_api_client import WalletAPIClient, WalletAPIRefused
from exchange.wallet_execution_attempts import WalletExecutionAttempts

ACTOR = "0x" + "a" * 40
OTHER = "0x" + "b" * 40
NOW = 1900000000000
EXECUTE = {"taskDigest": "0x" + "a" * 64, "operationId": "synthetic-operation",
           "childDigest": "0x" + "b" * 64, "expectedBudgetRevision": "0"}


@contextmanager
def original_protocol(*, durable_attempts=True):
    state = {"now": NOW, "calls": [], "mode": None}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.handle_route()

        def do_POST(self):
            self.handle_route()

        def handle_route(self):
            path = self.path
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))) or b"{}")
            state["calls"].append((self.command, path, body))
            if self.headers.get("X-Wallet-Tenant") != "synthetic" or self.headers.get("Origin") != state["origin"]:
                return self.reply({"error": "AUTH_ORIGIN_REFUSED"}, status=403)
            if path == "/auth/bootstrap":
                if state["mode"] == "duplicate-json":
                    return self.reply(b'{"csrf":"a","csrf":"b"}')
                return self.reply({"csrf": "p" * 43}, cookie="pre=synthetic-pre; Path=/; HttpOnly; SameSite=Strict")
            preauth = "pre=synthetic-pre" in self.headers.get("Cookie", "")
            csrf = self.headers.get("X-Wallet-CSRF")
            if path == "/auth/challenge":
                if not preauth or csrf != "p" * 43:
                    return self.reply({"error": "AUTH_REFUSED"}, status=401)
                if state["mode"] == "redirect":
                    self.send_response(302)
                    self.send_header("Location", state["origin"] + "/redirect-target")
                    self.end_headers()
                    return
                state["challenge_count"] = state.get("challenge_count", 0) + 1
                c = {"origin": state["origin"], "tenant": "synthetic", "account": ACTOR,
                     "chainId": "11155111", "id": f'{state["challenge_count"]:043d}',
                     "nonce": "syntheticNonce" + str(state["challenge_count"]),
                     "method": "wallet", "issuedAt": NOW, "expiresAt": NOW + 120000}
                iso = lambda value: datetime.fromtimestamp(value / 1000, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
                c["message"] = (f'{c["origin"]} wants you to sign in with your Ethereum account:\n{ACTOR}\n\n'
                    'Log in to 8415wallet to view assets and history. This does not authorize a transaction or standing access.\n\n'
                    f'URI: {c["origin"]}\nVersion: 1\nChain ID: 11155111\nNonce: {c["nonce"]}\n'
                    f'Issued At: {iso(NOW)}\nExpiration Time: {iso(NOW + 120000)}\nResources:\n'
                    f'- urn:8415wallet:tenant:synthetic\n- urn:8415wallet:purpose:login\n- urn:8415wallet:request:{c["id"]}')
                mode = state["mode"]
                if mode == "wrong-message":
                    c["message"] += "\nAuthorize arbitrary transactions"
                elif mode == "wrong-account":
                    c["account"] = OTHER
                elif mode == "wrong-chain":
                    c["chainId"] = "560048"
                elif mode == "wrong-tenant":
                    c["tenant"] = "other"
                elif mode == "expired":
                    c["expiresAt"] = NOW
                state["challenge"] = c
                return self.reply(c)
            if path == "/auth/proof":
                if not preauth or csrf != "p" * 43 or body.get("id") != state["challenge"]["id"]:
                    return self.reply({"error": "AUTH_REFUSED"}, status=401)
                state["proof"] = body
                return self.reply(self.session_row(), cookie="session=synthetic-session; Path=/; HttpOnly; SameSite=Strict")
            authenticated = "session=synthetic-session" in self.headers.get("Cookie", "") and csrf == "s" * 43
            if not authenticated:
                return self.reply({"error": "AUTH_REFUSED"}, status=401)
            if path == "/auth/session":
                row = self.session_row()
                mutate = state.pop("mutate_during_session", None)
                if mutate is not None:
                    mutate()
                if state["mode"] == "changed-session":
                    row["account"] = OTHER
                return self.reply(row)
            if path == "/auth/logout":
                return self.reply({"ok": True}, cookie="session=; Path=/; Max-Age=0")
            if path == "/auth/tasks/execute" and state["mode"] == "unknown-execute":
                return self.reply({"error": "TASK_OUTCOME_UNKNOWN"}, status=503)
            if path.startswith("/auth/tasks/"):
                return self.reply({"action": path.rsplit("/", 1)[1], "accepted": True,
                                   "realFinancialExecution": False})
            return self.reply({"error": "AUTH_ROUTE_REFUSED"}, status=404)

        def session_row(self):
            return {"id": "i" * 43, "tenant": "synthetic", "origin": state["origin"],
                    "username": "synthetic-user", "account": ACTOR, "chainId": "11155111",
                    "kind": "wallet", "issuedAt": NOW, "expiresAt": NOW + 900000, "csrf": "s" * 43}

        def reply(self, row, status=200, cookie=None):
            data = row if type(row) is bytes else json.dumps(row).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            if cookie:
                self.send_header("Set-Cookie", cookie)
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state["origin"] = "http://127.0.0.1:" + str(server.server_port)
    worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    attempt_directory = TemporaryDirectory(prefix="8415ex-wallet-api-test-")
    worker.start()
    try:
        attempts = (WalletExecutionAttempts(str(Path(attempt_directory.name) / "attempts.sqlite3"))
                    if durable_attempts else None)
        client = WalletAPIClient(state["origin"], "synthetic", ACTOR, 11155111,
                                 clock_ms=lambda: state["now"], allow_loopback_http=True,
                                 execution_attempts=attempts)
        yield client, state
    finally:
        server.shutdown()
        server.server_close()
        worker.join(2)
        attempt_directory.cleanup()
        if worker.is_alive():
            raise AssertionError("synthetic server did not stop")


class WalletAPIClientContracts(unittest.TestCase):
    def signer(self, message, account, chain):
        self.assertIn("urn:8415wallet:purpose:login", message)
        self.assertEqual((account, chain), (ACTOR, "11155111"))
        return "0x" + "1" * 130

    def test_cookie_and_rotated_csrf_reach_original_task_routes(self):
        with original_protocol() as (client, state):
            self.assertEqual(client.login(self.signer), {"authenticated": True, "chainId": "11155111"})
            self.assertEqual(client.task("prepare", {"policy": {"synthetic": True}})["action"], "prepare")
            self.assertEqual(client.task("status", {"taskDigest": EXECUTE["taskDigest"]})["action"], "status")
            self.assertNotIn("csrf", client.session())
            self.assertEqual(state["proof"]["signature"], "0x" + "1" * 130)

    def test_altered_identity_or_message_is_refused_before_signing(self):
        for mode in ("wrong-message", "wrong-account", "wrong-chain", "wrong-tenant", "expired"):
            with self.subTest(mode=mode), original_protocol() as (client, state):
                state["mode"] = mode
                with self.assertRaises(WalletAPIRefused):
                    client.login(lambda *args: self.fail("unbound challenge reached signer"))
                self.assertNotIn("proof", state)

    def test_expiration_during_message_signing_prevents_proof(self):
        with original_protocol() as (client, state):
            def delayed(*args):
                state["now"] += 120000
                return "0x" + "1" * 130
            with self.assertRaises(WalletAPIRefused):
                client.login(delayed)
            self.assertNotIn("proof", state)

    def test_changed_session_stops_task_before_any_mutation(self):
        with original_protocol() as (client, state):
            client.login(self.signer)
            state["mode"] = "changed-session"
            with self.assertRaises(WalletAPIRefused):
                client.task("reserve", {"taskDigest": EXECUTE["taskDigest"], "child": {}, "expectedBudgetRevision": "0"})
            self.assertFalse(any("/tasks/" in path for _, path, _ in state["calls"]))

    def test_execute_without_durable_store_is_refused_before_any_request(self):
        with original_protocol(durable_attempts=False) as (client, state):
            client.login(self.signer)
            before = list(state["calls"])
            with self.assertRaisesRegex(WalletAPIRefused, "^EX_WALLET_DURABLE_ATTEMPT_STORE_REQUIRED$"):
                client.task("execute", EXECUTE)
            self.assertEqual(state["calls"], before)

    def test_unknown_execution_never_automatically_retries_or_resends(self):
        with original_protocol() as (client, state):
            client.login(self.signer)
            state["mode"] = "unknown-execute"
            with self.assertRaisesRegex(WalletAPIRefused, "OUTCOME_UNKNOWN") as caught:
                client.task("execute", EXECUTE)
            self.assertEqual(caught.exception.source_code, "TASK_OUTCOME_UNKNOWN")
            self.assertEqual(caught.exception.http_status, 503)
            with self.assertRaisesRegex(WalletAPIRefused, "RECONCILE_FIRST"):
                client.task("execute", EXECUTE)
            self.assertEqual(sum(path == "/auth/tasks/execute" for _, path, _ in state["calls"]), 1)
            self.assertEqual(client.task("recover", EXECUTE)["action"], "recover")
            with self.assertRaisesRegex(WalletAPIRefused, "RECONCILE_FIRST"):
                client.task("execute", EXECUTE)

    def test_capability_discovery_and_caller_exemption_are_not_routes(self):
        with original_protocol() as (client, state):
            for action, body in (("capabilities", {}), ("prepare", {"policy": {}, "approvalFactor": "server-test-scope"})):
                with self.assertRaises(WalletAPIRefused):
                    client.task(action, body)
            self.assertEqual(state["calls"], [])

    def test_concurrent_same_operation_does_not_resend_after_unknown(self):
        with original_protocol() as (client, state):
            client.login(self.signer)
            state["mode"] = "unknown-execute"
            ready = threading.Barrier(2)

            def execute_once():
                ready.wait(timeout=5)
                try:
                    client.task("execute", EXECUTE)
                except WalletAPIRefused as error:
                    return str(error)
                return "UNEXPECTED_SUCCESS"

            with ThreadPoolExecutor(max_workers=2) as workers:
                pending = [workers.submit(execute_once) for _ in range(2)]
                results = [future.result(timeout=10) for future in pending]
            self.assertCountEqual(results, ["EX_WALLET_EXECUTION_OUTCOME_UNKNOWN",
                                           "EX_WALLET_UNKNOWN_RECONCILE_FIRST"])
            self.assertEqual(sum(path == "/auth/tasks/execute" for _, path, _ in state["calls"]), 1)

    def test_relogin_does_not_erase_unknown_operation(self):
        with original_protocol() as (client, state):
            client.login(self.signer)
            state["mode"] = "unknown-execute"
            with self.assertRaisesRegex(WalletAPIRefused, "OUTCOME_UNKNOWN"):
                client.task("execute", EXECUTE)
            client.logout()
            state["mode"] = None
            client.login(self.signer)
            with self.assertRaisesRegex(WalletAPIRefused, "RECONCILE_FIRST"):
                client.task("execute", EXECUTE)
            self.assertEqual(sum(path == "/auth/tasks/execute" for _, path, _ in state["calls"]), 1)

    def test_external_payload_mutation_cannot_change_bound_execute_request(self):
        with original_protocol() as (client, state):
            client.login(self.signer)
            requested = dict(EXECUTE)
            state["mode"] = "unknown-execute"

            def mutate_request():
                requested["operationId"] = "different-operation"
                requested["childDigest"] = "0x" + "c" * 64

            state["mutate_during_session"] = mutate_request
            with self.assertRaisesRegex(WalletAPIRefused, "OUTCOME_UNKNOWN"):
                client.task("execute", requested)
            sent = [body for _, path, body in state["calls"] if path == "/auth/tasks/execute"]
            self.assertEqual(sent, [EXECUTE])
            with self.assertRaisesRegex(WalletAPIRefused, "RECONCILE_FIRST"):
                client.task("execute", dict(EXECUTE))
            self.assertEqual(sum(path == "/auth/tasks/execute" for _, path, _ in state["calls"]), 1)

    def test_logout_discards_local_cookie_and_csrf(self):
        with original_protocol() as (client, state):
            client.login(self.signer)
            client.logout()
            with self.assertRaisesRegex(WalletAPIRefused, "LOGIN_REQUIRED"):
                client.session()

    def test_redirect_is_refused_without_requesting_its_target(self):
        with original_protocol() as (client, state):
            state["mode"] = "redirect"
            with self.assertRaises(WalletAPIRefused):
                client.login(self.signer)
            self.assertFalse(any(path == "/redirect-target" for _, path, _ in state["calls"]))

    def test_duplicate_json_does_not_reach_signer(self):
        with original_protocol() as (client, state):
            state["mode"] = "duplicate-json"
            with self.assertRaises(WalletAPIRefused):
                client.login(lambda *args: self.fail("invalid bootstrap reached signer"))

    def test_other_network_and_non_tls_remote_origins_are_refused(self):
        for origin, chain in (("http://example.invalid", 11155111), ("https://example.invalid", 560048),
                              ("https://user:secret@example.invalid", 11155111),
                              ("https://example.invalid/auth", 11155111)):
            with self.subTest(origin=origin, chain=chain), self.assertRaises(WalletAPIRefused):
                WalletAPIClient(origin, "synthetic", ACTOR, chain)
