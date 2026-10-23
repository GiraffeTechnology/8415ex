"""Synthetic receipt locale HTTP definitions; approved Linux execution only."""
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from exchange.gas_disclosure_locales import TRANSPORT
from exchange.workbench import WorkbenchServer, RuntimeBinding
from integration import test_integrated_runtime_inputs as fixtures
from integration.test_integrated_workbench_http import COMMIT, TREE
from integration.test_nft_detail import OriginalReadOnlyDomain


class ReceiptLocaleWiringTests(unittest.TestCase):
    def fixture(self, integrated=True):
        fixture = fixtures.IntegratedRuntimeInputsTests("runTest")
        self.addCleanup(fixture.doCleanups)
        if integrated:
            server = fixture.server()
        else:
            server = WorkbenchServer(RuntimeBinding(OriginalReadOnlyDomain(), "receipt-1"),
                                     port=0, commit=COMMIT, tree=TREE)
            self.addCleanup(server.server_close)
        fixture.start(server)
        return fixture, server

    def read(self, server, path):
        with urlopen(server.origin + path, timeout=3) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            return response.read().decode("utf-8")

    def test_standalone_root_and_receipt_alias_use_existing_six_locale_renderer(self):
        _, server = self.fixture(integrated=False)
        for locale in TRANSPORT:
            for path in ("/", "/receipt"):
                with self.subTest(locale=locale, path=path):
                    html = self.read(server, path + "?lang=" + locale)
                    self.assertIn('<html lang="' + locale + '">', html)
                    self.assertNotIn("fixture-buyer", html)

    def test_integrated_receipt_links_preserve_locale_into_existing_components(self):
        fixture, server = self.fixture()
        for locale, words in TRANSPORT.items():
            suffix = "" if locale == "en" else "?lang=" + locale
            with self.subTest(locale=locale):
                html = self.read(server, "/receipt?lang=" + locale)
                self.assertIn('<html lang="' + locale + '">', html)
                self.assertIn('href="/gas' + suffix + '"', html)
                self.assertIn('href="/registration-source' + suffix + '"', html)
                for component in ("/gas", "/registration-source"):
                    page = self.read(server, component + "?lang=" + locale)
                    self.assertIn('href="/receipt' + suffix + '"', page)
        self.assertEqual(fixture.wallet_calls, [])

    def test_bad_locale_or_unrelated_fields_refuse_before_detail_reader(self):
        fixture, server = self.fixture()
        calls = []
        server.binding.public_detail = lambda: calls.append("detail")
        for path in ("/", "/receipt"):
            for query in ("lang=de", "lang=", "lang=ja&lang=en", "lang=ja&buyer=x",
                          "nft=other", "lang=" + "a" * 65):
                with self.subTest(path=path, query=query), self.assertRaises(HTTPError) as raised:
                    urlopen(server.origin + path + "?" + query, timeout=3)
                self.assertEqual(raised.exception.code, 400)
        self.assertEqual(calls, [])
        self.assertEqual(fixture.wallet_calls, [])

    def test_unsupported_legacy_locale_is_not_silently_rendered_as_english(self):
        fixture, server = self.fixture()
        with self.assertRaises(HTTPError) as raised:
            urlopen(server.origin + "/timeline?lang=ja", timeout=3)
        self.assertEqual(raised.exception.code, 400)
        self.assertEqual(fixture.wallet_calls, [])

