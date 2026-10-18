"""Approved-Linux-only definitions; no live Wallet or financial acceptance."""
import unittest
from html import escape
from urllib.error import HTTPError
from urllib.request import urlopen

from exchange.gas_budget import GasBudgetRefused
from exchange.gas_disclosure_locales import WORDS
from integration import test_gas_confirmation_ui as gas_fixtures
from integration import test_integrated_runtime_inputs as http_fixtures


class GasDisclosureLocaleTests(unittest.TestCase):
    def fixture(self):
        fixture = gas_fixtures.GasConfirmationContracts("runTest")
        fixture.setUp()
        return fixture

    def test_six_locales_show_exact_quote_money_provenance_and_consent(self):
        self.assertEqual(set(WORDS), {"en", "zh-Hans", "zh-Hant", "fr", "es", "ja"})
        fixture = self.fixture()
        for locale, words in WORDS.items():
            with self.subTest(locale=locale):
                html = fixture.page.render(110, "csrf-1", locale=locale)
                self.assertIn('lang="' + locale + '"', html)
                for value in words.values():
                    self.assertIn(escape(value, quote=True), html)
                data = fixture.quote.disclosure()
                for amount in (data["cap"], data["median"]):
                    self.assertIn(amount["ETH"] + " ETH / $" + amount["USD"] + " USD", html)
                for value in (fixture.quote.digest, fixture.quote.quote_id,
                              fixture.quote.rate_sha256, fixture.quote.scope,
                              "sorted-P50-middle-or-two-middle-mean"):
                    self.assertIn(escape(str(value), quote=True), html)
                self.assertIn('action="/existing-route"', html)
                self.assertEqual(fixture.calls, [])

    def test_locale_cannot_change_confirmation_fields_or_trusted_binding(self):
        fixture = self.fixture()
        for locale in WORDS:
            fixture.page.render(110, "csrf-1", locale=locale)
        with self.assertRaises(GasBudgetRefused):
            fixture.page.submit(dict(fixture.fields, lang="ja"), 110)
        self.assertEqual(fixture.calls, [])
        result = fixture.page.submit(fixture.fields, 110)
        self.assertEqual(result.buyer, "buyer-1")
        self.assertEqual(result.wallet_grant, "existing-grant-1")
        self.assertEqual(fixture.calls, [fixture.quote.digest])

    def test_unsupported_locale_refused_without_wallet_call(self):
        fixture = self.fixture()
        for locale in ("de", "", "<script>", None, ["en"]):
            with self.subTest(locale=locale), self.assertRaises(GasBudgetRefused):
                fixture.page.render(110, "csrf-1", locale=locale)
        self.assertEqual(fixture.calls, [])

    def test_mounted_gas_get_uses_locale_without_wallet_dispatch(self):
        fixture = http_fixtures.IntegratedRuntimeInputsTests("runTest")
        self.addCleanup(fixture.doCleanups)
        server = fixture.server()
        fixture.start(server)
        for locale, words in WORDS.items():
            with self.subTest(locale=locale), urlopen(
                    server.origin + "/gas?lang=" + locale, timeout=3) as response:
                html = response.read().decode("utf-8")
                self.assertIn('<html lang="' + locale + '">', html)
                self.assertIn(escape(words["heading"], quote=True), html)
                self.assertIn('action="/gas/confirm"', html)
        for query in ("lang=de", "lang=", "lang=ja&lang=en", "lang=ja&buyer=other",
                      "buyer=other"):
            with self.subTest(query=query), self.assertRaises(HTTPError) as raised:
                urlopen(server.origin + "/gas?" + query, timeout=3)
            self.assertEqual(raised.exception.code, 400)
        self.assertEqual(fixture.wallet_calls, [])

