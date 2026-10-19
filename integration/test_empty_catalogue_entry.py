"""Approved remote Linux definitions; no test execution implied by this file."""
from html import escape
import json
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from exchange.catalogue_serve import EmptyCatalogueServer
from exchange.market_page import EMPTY_MODE, WORDS, render_market
from exchange.nft_detail_page import LOCALES
from exchange.nft_directory import NftDirectory


class EmptyCatalogueEntryTests(unittest.TestCase):
    def start(self):
        server = EmptyCatalogueServer(port=0, commit="a" * 40, tree="b" * 40)
        worker = threading.Thread(target=server.serve_forever,
                                  kwargs={"poll_interval": 0.02}, daemon=True)
        worker.start()
        def close():
            server.shutdown()
            worker.join(timeout=3)
            server.server_close()
        self.addCleanup(close)
        return server

    def request(self, server, path, *, data=None, headers=None):
        return urlopen(Request(server.origin + path, data=data, headers=headers or {}), timeout=3)

    def test_empty_directory_is_explicit_and_existing_default_stays_strict(self):
        with self.assertRaises(ValueError):
            NftDirectory(())
        with self.assertRaises(ValueError):
            NftDirectory((), allow_empty="true")
        directory = NftDirectory((), allow_empty=True)
        self.assertEqual(directory.catalogue(), [])
        self.assertEqual(directory.choices(), [])
        with self.assertRaises(KeyError):
            directory.detail("a" * 64)

    def test_six_locales_show_real_empty_state_without_simulated_records(self):
        server = self.start()
        for locale in LOCALES:
            with self.subTest(locale=locale), self.request(server, "/market?lang=" + locale) as response:
                body = response.read().decode()
                self.assertEqual(response.status, 200)
                self.assertIn('lang="' + locale + '"', body)
                self.assertIn(escape(EMPTY_MODE[locale], quote=True), body)
                self.assertIn(escape(WORDS[locale][13], quote=True), body)
                self.assertNotIn('class="nft-card"', body)
                self.assertNotIn('>DEMO<', body)
                self.assertNotIn('/simulate', body)
                self.assertNotIn('href="/queue', body)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn('>DEMO<', render_market([], {"status": "not-connected"}))
        with self.assertRaises(ValueError):
            render_market([{"nftKey": "a" * 64}], {}, empty_catalogue=True)

    def test_readback_contains_no_invented_identity_price_or_readiness(self):
        server = self.start()
        with self.request(server, "/api/nfts") as response:
            self.assertEqual(json.load(response), {"nfts": []})
        with self.request(server, "/api/catalogue") as response:
            self.assertEqual(json.load(response), {"nfts": [], "reference": {
                "status": "not-connected", "price": None}})
        with self.request(server, "/healthz") as response:
            value = json.load(response)
            self.assertEqual(value["httpProcess"], "serving")
            self.assertEqual(value["operationsREADY"], "NOT_VERIFIED")
            self.assertFalse(any(value["configuredComponents"].values()))
        with self.request(server, "/api/reference") as response:
            self.assertFalse(json.load(response)["executableOrder"])

    def test_receipt_demo_and_write_paths_cannot_reach_scenario_harness(self):
        server = self.start()
        with patch("exchange.demo_ui.run_all", side_effect=AssertionError("no simulation")):
            for path in ("/demo", "/run?id=x", "/api/snapshot", "/api/operations",
                         "/nft", "/api/nft-detail?nft=" + "a" * 64, "/queue", "/evidence"):
                with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                    self.request(server, path)
                self.assertEqual(error.exception.code, 404)
                error.exception.close()
            for path in ("/simulate", "/operation", "/gas", "/anything"):
                with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                    self.request(server, path, data=b"private-untrusted-body")
                self.assertEqual(error.exception.code, 405)
                self.assertEqual(error.exception.headers["Allow"], "GET")
                self.assertEqual(error.exception.headers["Connection"], "close")
                self.assertNotIn(b"private-untrusted-body", error.exception.read())
                error.exception.close()

    def test_invalid_queries_and_foreign_host_are_refused(self):
        server = self.start()
        for path in ("/?lang=xx", "/?lang=en&lang=ja", "/market?lang=xx",
                     "/market?q=" + "x" * 65, "/api/catalogue?receipt=private",
                     "/market?lang=en&q=x&extra=y", "/healthz?lang=en"):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                self.request(server, path)
            self.assertEqual(error.exception.code, 400)
            error.exception.close()
        for data in (None, b"unread-body"):
            with self.assertRaises(HTTPError) as error:
                self.request(server, "/market", data=data, headers={"Host": "foreign.invalid"})
            self.assertEqual(error.exception.code, 421)
            error.exception.close()

    def test_initial_locale_navigation_and_existing_static_asset_are_reachable(self):
        server = self.start()
        for locale in LOCALES:
            with self.subTest(locale=locale), self.request(server, "/receipt?lang=" + locale) as response:
                self.assertIn("/market?lang=" + locale, response.url)
                self.assertIn(escape(EMPTY_MODE[locale], quote=True), response.read().decode())
        with self.request(server, "/assets/cube.svg") as response:
            self.assertEqual(response.status, 200)
            self.assertIn("image/svg+xml", response.headers["Content-Type"])
            self.assertTrue(response.read())
