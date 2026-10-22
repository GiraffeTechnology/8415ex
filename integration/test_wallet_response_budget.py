"""Synthetic local HTTP fixtures for approved Linux CI; not live Wallet evidence."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time
import unittest

from exchange.wallet_api_client import WalletAPIClient, WalletAPIRefused
from integration.test_wallet_api_client import original_protocol, ACTOR, EXECUTE


@contextmanager
def response_source(mode):
    state = {"calls": 0, "done": threading.Event()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            state["calls"] += 1
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            if mode == "slow":
                self.send_header("Content-Length", "100")
            elif mode == "duplicate-length":
                self.send_header("Content-Length", "2")
                self.send_header("Content-Length", "2")
            elif mode == "ambiguous":
                self.send_header("Content-Length", "2")
                self.send_header("Transfer-Encoding", "chunked")
            elif mode == "oversize":
                self.send_header("Content-Length", "65537")
            elif mode == "truncated":
                self.send_header("Content-Length", "100")
            elif mode == "chunked":
                self.send_header("Transfer-Encoding", "chunked")
            else:
                self.send_header("Content-Length", "2")
            self.end_headers()
            try:
                if mode == "slow":
                    # Every byte arrives inside a per-socket inactivity timeout,
                    # but the complete body exceeds the original request budget.
                    for _ in range(100):
                        if state["done"].wait(0.03):
                            break
                        self.wfile.write(b" ")
                        self.wfile.flush()
                elif mode == "chunked":
                    self.wfile.write(b"2\r\n{}\r\n0\r\n\r\n")
                else:
                    self.wfile.write(b"{}")
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                self.close_connection = True

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever,
                              kwargs={"poll_interval": 0.01}, daemon=True)
    worker.start()
    client = WalletAPIClient("http://127.0.0.1:" + str(server.server_port),
                             "synthetic", ACTOR, 11155111,
                             timeout_seconds=0.2, allow_loopback_http=True)
    try:
        yield client, state
    finally:
        state["done"].set()
        server.shutdown()
        server.server_close()
        worker.join(2)
        if worker.is_alive():
            raise AssertionError("synthetic fixture did not stop")


class WalletResponseBudget(unittest.TestCase):
    def test_dripping_body_cannot_restart_the_original_budget(self):
        with response_source("slow") as (client, state):
            began = time.monotonic()
            with self.assertRaises(WalletAPIRefused):
                client._request("bootstrap")
            self.assertLess(time.monotonic() - began, 1.0)
            self.assertEqual(state["calls"], 1)

    def test_duplicate_or_ambiguous_framing_is_refused(self):
        for mode in ("duplicate-length", "ambiguous"):
            with self.subTest(mode=mode), response_source(mode) as (client, state):
                with self.assertRaisesRegex(WalletAPIRefused, "FRAMING_REFUSED"):
                    client._request("bootstrap")
                self.assertEqual(state["calls"], 1)

    def test_declared_oversize_is_refused(self):
        with response_source("oversize") as (client, _):
            with self.assertRaisesRegex(WalletAPIRefused, "TOO_LARGE"):
                client._request("bootstrap")

    def test_short_body_does_not_become_a_complete_object(self):
        with response_source("truncated") as (client, _):
            with self.assertRaisesRegex(WalletAPIRefused, "TRUNCATED"):
                client._request("bootstrap")

    def test_fixed_and_chunked_complete_json_remain_supported(self):
        for mode in ("fixed", "chunked"):
            with self.subTest(mode=mode), response_source(mode) as (client, state):
                self.assertEqual(client._request("bootstrap"), {})
                self.assertEqual(state["calls"], 1)

    def test_unknown_execute_guard_survives_transport_change(self):
        with original_protocol() as (client, state):
            client.login(lambda *args: "0x" + "1" * 130)
            state["mode"] = "unknown-execute"
            with self.assertRaisesRegex(WalletAPIRefused, "OUTCOME_UNKNOWN") as caught:
                client.task("execute", EXECUTE)
            self.assertEqual(caught.exception.source_code, "TASK_OUTCOME_UNKNOWN")
            self.assertEqual(caught.exception.http_status, 503)
            with self.assertRaisesRegex(WalletAPIRefused, "RECONCILE_FIRST"):
                client.task("execute", EXECUTE)
            self.assertEqual(sum(path == "/auth/tasks/execute"
                                 for _, path, _ in state["calls"]), 1)
