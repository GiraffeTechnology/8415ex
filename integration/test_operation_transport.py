"""Synthetic native command HTTP definitions; approved Linux execution only.

The injected command spy checks parser reachability, not Wallet authorization,
domain execution, financial journal persistence or real chain acceptance.
"""
import http.client
import unittest
from urllib.parse import urlencode

from exchange.demo_ui import MAX_BODY
from integration import test_integrated_runtime_inputs as fixtures


class OperationTransportTests(unittest.TestCase):
    def server(self):
        fixture = fixtures.IntegratedRuntimeInputsTests("runTest")
        self.addCleanup(fixture.doCleanups)
        server = fixture.server()
        self.calls = []
        def command(*args):
            self.calls.append(args)
            return {"enquired": True, "result": {"status": "unknown"}}
        server.binding.command = command
        fixture.start(server)
        return server

    def body(self, server, **changes):
        fields = {"csrf": server.csrf, "revision": "0" * 64,
                  "action": "advance-rollback", "key": "fixture-operation", "leg": ""}
        fields.update(changes)
        return urlencode(fields).encode("ascii")

    def request(self, server, body, lengths=None, transfer=None, origin=None):
        connection = http.client.HTTPConnection(*server.server_address, timeout=3)
        try:
            connection.putrequest("POST", "/operation")
            connection.putheader("Origin", server.origin if origin is None else origin)
            connection.putheader("Content-Type", "application/x-www-form-urlencoded")
            for length in ([str(len(body))] if lengths is None else lengths):
                connection.putheader("Content-Length", length)
            if transfer is not None:
                connection.putheader("Transfer-Encoding", transfer)
            connection.endheaders(body)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_duplicate_absent_non_decimal_and_excess_lengths_never_reach_command(self):
        server = self.server()
        body = self.body(server)
        invalid = [[], [str(len(body)), str(len(body))], [str(len(body)), "1"],
                   ["+1"], ["-1"], ["1, 1"], ["0"], [str(MAX_BODY + 1)], ["999999999"]]
        for lengths in invalid:
            with self.subTest(lengths=lengths):
                self.assertEqual(self.request(server, body, lengths=lengths)[0], 400)
        self.assertEqual(self.calls, [])

    def test_transfer_encoding_and_extra_or_duplicate_fields_never_reach_command(self):
        server = self.server()
        body = self.body(server)
        self.assertEqual(self.request(server, body, transfer="chunked")[0], 400)
        for extra in (b"&key=second", b"&success=yes", b"&buyer=other"):
            with self.subTest(extra=extra):
                self.assertEqual(self.request(server, body + extra)[0], 400)
        self.assertEqual(self.calls, [])

    def test_original_origin_csrf_revision_and_leg_checks_remain_before_command(self):
        server = self.server()
        self.assertEqual(self.request(server, self.body(server),
                                      origin="https://other.invalid")[0], 403)
        self.assertEqual(self.request(server, self.body(server, csrf="wrong"))[0], 403)
        for changes in ({"revision": "invalid"}, {"leg": "1"},
                        {"action": "submit-registration", "leg": ""}):
            with self.subTest(changes=changes):
                self.assertEqual(self.request(server, self.body(server, **changes))[0], 400)
        self.assertEqual(self.calls, [])

    def test_one_exact_bounded_request_enters_original_command_once(self):
        server = self.server()
        status, headers, body = self.request(server, self.body(server))
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/queue")
        self.assertEqual(body, b"")
        self.assertEqual(self.calls, [
            ("advance-rollback", "fixture-operation", "0" * 64, {})])
        # Redirect acknowledges the original UNKNOWN observation, not success.
        self.assertEqual(server.command_observations["fixture-operation"]["result"],
                         {"status": "unknown"})
        self.assertTrue(server.command_observations["fixture-operation"]["enquired"])

