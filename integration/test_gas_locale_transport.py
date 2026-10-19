"""Synthetic HTTP definitions for approved Linux execution only."""
import http.client
import unittest
from urllib.parse import urlencode

from exchange.gas_budget import BuyerConfirmation
from exchange.gas_disclosure_locales import TRANSPORT
from integration import test_integrated_runtime_inputs as fixtures
from integration.test_gas_budget import quote


class GasLocaleTransportTests(unittest.TestCase):
    def server(self):
        fixture = fixtures.IntegratedRuntimeInputsTests("runTest")
        self.addCleanup(fixture.doCleanups)
        server = fixture.server()
        self.calls = []
        def confirm(q, buyer, action, grant, now):
            self.calls.append((q.digest, buyer, action, grant))
            return BuyerConfirmation(q.digest, buyer, action, grant, now, "fixture-proof")
        server.gas_page.confirm_with_wallet = confirm
        server.gas_page.validate_csrf = lambda token: token == server.csrf
        fixture.start(server)
        return server

    def request(self, server, path, fields=None, origin=None):
        connection = http.client.HTTPConnection(server.server_address[0],
                                                server.server_address[1], timeout=3)
        try:
            headers = {}
            body = None
            if fields is not None:
                body = urlencode(fields)
                headers = {"Content-Type": "application/x-www-form-urlencoded",
                           "Origin": server.origin if origin is None else origin}
            connection.request("GET" if fields is None else "POST", path, body, headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode("utf-8")
        finally:
            connection.close()

    def fields(self, server):
        q = quote()
        return {"csrf": server.csrf, "quoteId": q.quote_id, "version": str(q.version),
                "quoteDigest": q.digest, "accepted": "yes"}

    def test_each_locale_has_reachable_switch_and_retains_post_redirect(self):
        server = self.server()
        for locale in TRANSPORT:
            with self.subTest(locale=locale):
                status, _, html = self.request(server, "/gas?lang=" + locale)
                self.assertEqual(status, 200)
                for target in TRANSPORT:
                    self.assertIn('href="/gas?lang=' + target + '"', html)
                status, headers, _ = self.request(
                    server, "/gas/confirm?lang=" + locale, self.fields(server))
                self.assertEqual(status, 303)
                self.assertEqual(headers["Location"], "/gas" + (
                    "" if locale == "en" else "?lang=" + locale))
        self.assertEqual(len(self.calls), 6)
        self.assertEqual(len(set(self.calls)), 1)

    def test_locale_does_not_bypass_origin_csrf_or_exact_form(self):
        server = self.server()
        for locale, words in TRANSPORT.items():
            with self.subTest(locale=locale):
                status, _, body = self.request(server, "/gas/confirm?lang=" + locale,
                                              self.fields(server), "https://other.invalid")
                self.assertEqual(status, 403)
                self.assertEqual(body, words["originRefused"])
                for fields in (dict(self.fields(server), csrf="wrong"),
                               dict(self.fields(server), buyer="other"),
                               dict(self.fields(server), accepted="no")):
                    status, _, body = self.request(
                        server, "/gas/confirm?lang=" + locale, fields)
                    self.assertEqual(status, 400)
                    self.assertEqual(body, words["confirmationRefused"])
        self.assertEqual(self.calls, [])

    def test_bad_transport_queries_are_refused_before_wallet(self):
        server = self.server()
        for query in ("lang=de", "lang=", "lang=ja&lang=en", "lang=ja&buyer=x",
                      "buyer=x", "lang=" + "a" * 65):
            with self.subTest(query=query):
                status, _, _ = self.request(server, "/gas/confirm?" + query, self.fields(server))
                self.assertEqual(status, 403)
        self.assertEqual(self.calls, [])

    def test_unknown_wallet_result_is_localized_without_success_redirect(self):
        server = self.server()
        for failure, expected in ((TimeoutError, 408), (OSError, 503)):
            def fail(*args):
                raise failure("private diagnostic must not appear")
            server.gas_page.confirm_with_wallet = fail
            for locale, words in TRANSPORT.items():
                with self.subTest(failure=failure, locale=locale):
                    status, headers, body = self.request(
                        server, "/gas/confirm?lang=" + locale, self.fields(server))
                    self.assertEqual(status, expected)
                    self.assertNotIn("Location", headers)
                    self.assertEqual(body, words["unknown"])
                    self.assertNotIn("private diagnostic", body)
        self.assertEqual(self.calls, [])

