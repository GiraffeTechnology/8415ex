"""Synthetic quote availability definitions; approved Linux execution only."""
import http.client
import unittest
from urllib.parse import urlencode

from exchange.gas_confirmation_ui import GasDisclosureUnavailable
from exchange.gas_disclosure_locales import AVAILABILITY
from integration import test_gas_confirmation_ui as gas_fixtures
from integration import test_integrated_runtime_inputs as http_fixtures
from integration.test_gas_budget import quote


class GasAvailabilityTests(unittest.TestCase):
    def fixture(self):
        fixture = gas_fixtures.GasConfirmationContracts("runTest")
        fixture.setUp()
        return fixture

    def test_missing_expired_and_premature_quotes_have_fixed_distinct_reasons(self):
        fixture = self.fixture()
        cases = ((lambda: fixture.quote, fixture.quote.quoted_at - 1, "QUOTE_NOT_YET_VALID"),
                 (lambda: fixture.quote, fixture.quote.valid_until, "QUOTE_EXPIRED"),
                 (lambda: None, 110, "QUOTE_MISSING"),
                 (lambda: {}, 110, "QUOTE_MISSING"))
        for resolver, now, reason in cases:
            fixture.page.current_quote = resolver
            with self.subTest(reason=reason), self.assertRaises(GasDisclosureUnavailable) as caught:
                fixture.page.render(now, "csrf-1")
            self.assertEqual(caught.exception.code, reason)
            for locale, words in AVAILABILITY.items():
                self.assertEqual(caught.exception.message(locale), words[reason])
        self.assertEqual(fixture.calls, [])

    def test_original_quote_failure_is_sanitized_and_cannot_reach_confirmation(self):
        fixture = self.fixture()
        def fail():
            raise RuntimeError("synthetic-private-provider-token")
        fixture.page.current_quote = fail
        for call in (lambda: fixture.page.render(110, "csrf-1"),
                     lambda: fixture.page.submit(fixture.fields, 110)):
            with self.assertRaises(GasDisclosureUnavailable) as caught:
                call()
            self.assertEqual(caught.exception.code, "QUOTE_UNAVAILABLE")
            self.assertNotIn("synthetic-private", str(caught.exception))
        self.assertEqual(fixture.calls, [])

    def server(self):
        fixture = http_fixtures.IntegratedRuntimeInputsTests("runTest")
        self.addCleanup(fixture.doCleanups)
        server = fixture.server()
        fixture.start(server)
        return fixture, server

    def request(self, server, path, fields=None):
        connection = http.client.HTTPConnection(*server.server_address, timeout=3)
        try:
            headers = {}
            body = None
            if fields is not None:
                body = urlencode(fields)
                headers = {"Content-Type": "application/x-www-form-urlencoded",
                           "Origin": server.origin}
            connection.request("GET" if fields is None else "POST", path, body, headers)
            response = connection.getresponse()
            return response.status, response.read().decode("utf-8")
        finally:
            connection.close()

    def test_each_mounted_locale_discloses_missing_quote_without_form_or_fake_zero(self):
        fixture, server = self.server()
        server.gas_page.current_quote = lambda: None
        q = quote()
        server.gas_page.validate_csrf = lambda token: token == server.csrf
        fields = {"csrf": server.csrf, "quoteId": q.quote_id, "version": str(q.version),
                  "quoteDigest": q.digest, "accepted": "yes"}
        for locale, words in AVAILABILITY.items():
            for path, form in (("/gas?lang=" + locale, None),
                               ("/gas/confirm?lang=" + locale, fields)):
                with self.subTest(locale=locale, path=path):
                    status, html = self.request(server, path, form)
                    self.assertEqual(status, 503)
                    self.assertIn('data-code="QUOTE_MISSING"', html)
                    self.assertIn(words["QUOTE_MISSING"], html)
                    self.assertNotIn("<form", html)
                    self.assertNotIn("0 ETH", html)
                    self.assertNotIn(server.csrf, html)
        self.assertEqual(fixture.wallet_calls, [])

    def test_mounted_expired_and_not_yet_valid_reasons_use_original_clock(self):
        fixture, server = self.server()
        q = quote()
        for now, reason in ((q.valid_until, "QUOTE_EXPIRED"),
                            (q.quoted_at - 1, "QUOTE_NOT_YET_VALID")):
            server.current_time = lambda: now
            for locale in AVAILABILITY:
                with self.subTest(reason=reason, locale=locale):
                    status, html = self.request(server, "/gas?lang=" + locale)
                    self.assertEqual(status, 400)
                    self.assertIn('data-code="' + reason + '"', html)
                    self.assertNotIn("<form", html)
        self.assertEqual(fixture.wallet_calls, [])

    def test_failure_during_final_quote_recheck_keeps_confirmation_unaccepted(self):
        fixture = self.fixture()
        original = fixture.page.confirm_with_wallet
        def confirm_then_lose_quote(*args):
            result = original(*args)
            fixture.page.current_quote = lambda: None
            return result
        fixture.page.confirm_with_wallet = confirm_then_lose_quote
        with self.assertRaises(GasDisclosureUnavailable) as caught:
            fixture.page.submit(fixture.fields, 110)
        self.assertEqual(caught.exception.code, "QUOTE_MISSING")
        self.assertEqual(fixture.calls, [fixture.quote.digest])

