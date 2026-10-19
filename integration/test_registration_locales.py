"""Synthetic registration locale definitions; approved Linux execution only."""
import unittest
from html import escape
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import urlopen

from exchange.registration_source_locales import WORDS
from exchange.registration_source_workbench import RegistrationSourceRefused, SOURCES
from integration import test_registration_source_workbench as source_fixtures
from integration import test_integrated_runtime_inputs as http_fixtures


class RegistrationLocaleTests(unittest.TestCase):
    def fixture(self):
        fixture = source_fixtures.RegistrationSourceWorkbenchContracts("runTest")
        fixture.setUp()
        return fixture

    def test_all_source_details_translate_labels_without_changing_original_facts(self):
        fixture = self.fixture()
        self.assertEqual(set(WORDS), {"en", "zh-Hans", "zh-Hant", "fr", "es", "ja"})
        source_keys = {"REG-DIRECT": "direct", "REG-ELECTRONIC": "electronic",
                       "REG-INTERMEDIARY": "intermediary"}
        for locale, words in WORDS.items():
            for source, source_key in source_keys.items():
                with self.subTest(locale=locale, source=source):
                    html = fixture.workbench.render_source(source, "receipt-1", locale=locale)
                    for key in ("receipt", "source", "format", "fields", "operation",
                                "status", "revision", "updated", "transaction", "oracle",
                                "authority", "principal", "gas", "simulated", "boundary",
                                source_key, source_key + "Explanation"):
                        self.assertIn(escape(words[key], quote=True), html)
                    for value in ("receipt-1", source, "mint-format-1", "asset, segment, holder",
                                  source_fixtures.OPERATION, "pending", "UNBOUND", "NOT_VERIFIED"):
                        self.assertIn(escape(value, quote=True), html)
                    self.assertIn('<section lang="' + locale + '">', html)
        self.assertEqual(len(fixture.calls), 18)
        self.assertEqual({action for action, _ in fixture.calls}, {"get"})

    def test_choices_translate_and_keep_only_declared_source_ids(self):
        fixture = self.fixture()
        for locale, words in WORDS.items():
            with self.subTest(locale=locale):
                html = fixture.workbench.render_choices("receipt-1", "/registration-source", locale)
                self.assertIn(escape(words["read"], quote=True), html)
                for source in SOURCES:
                    self.assertIn('value="' + source + '"', html)
                if locale != "en":
                    self.assertIn('name="lang" value="' + locale + '"', html)
                self.assertNotIn('method="post"', html)
        self.assertEqual(fixture.calls, [])
        self.assertEqual(fixture.resolutions, [])

    def test_unsupported_locale_refused_before_original_resolver(self):
        fixture = self.fixture()
        for locale in ("de", "", "<script>", None, ["ja"]):
            with self.subTest(locale=locale):
                with self.assertRaises(RegistrationSourceRefused):
                    fixture.workbench.render_source("REG-DIRECT", "receipt-1", locale)
                with self.assertRaises(RegistrationSourceRefused):
                    fixture.workbench.render_choices("receipt-1", "/registration-source", locale)
        self.assertEqual(fixture.calls, [])
        self.assertEqual(fixture.resolutions, [])

    def server(self):
        fixture = http_fixtures.IntegratedRuntimeInputsTests("runTest")
        self.addCleanup(fixture.doCleanups)
        server = fixture.server()
        fixture.start(server)
        return fixture, server

    def test_mounted_localized_choices_and_each_original_source_route(self):
        fixture, server = self.server()
        for locale, words in WORDS.items():
            with self.subTest(locale=locale), urlopen(
                    server.origin + "/registration-source?lang=" + locale, timeout=3) as response:
                html = response.read().decode("utf-8")
                self.assertIn('<html lang="' + locale + '">', html)
                for target in WORDS:
                    self.assertIn('href="/registration-source?lang=' + target + '"', html)
                self.assertIn(escape(words["read"], quote=True), html)
            for source in SOURCES:
                query = urlencode({"receipt": "receipt-1", "source": source, "lang": locale})
                with urlopen(server.origin + "/registration-source?" + query, timeout=3) as response:
                    html = response.read().decode("utf-8")
                    self.assertIn(escape(words["boundary"], quote=True), html)
                    self.assertIn(source, html)
                    self.assertIn("NOT_VERIFIED", html)
        self.assertEqual(fixture.wallet_calls, [])

    def test_invalid_source_locale_and_unpaired_fields_do_not_resolve(self):
        fixture, server = self.server()
        calls = []
        server.registration_sources.resolve_binding = lambda *args: calls.append(args)
        for query in ("lang=de", "lang=", "lang=ja&lang=en", "lang=ja&buyer=x",
                      "lang=ja&receipt=receipt-1", "lang=ja&source=REG-DIRECT",
                      "lang=ja&receipt=other&source=REG-DIRECT"):
            with self.subTest(query=query), self.assertRaises(HTTPError) as raised:
                urlopen(server.origin + "/registration-source?" + query, timeout=3)
            self.assertEqual(raised.exception.code, 400)
        self.assertEqual(calls, [])
        self.assertEqual(fixture.wallet_calls, [])

