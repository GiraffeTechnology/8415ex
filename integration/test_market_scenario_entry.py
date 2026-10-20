"""Synthetic scenario HTTP composition; no wallet, finance or reference reader."""
import http.client
import json
import threading
import unittest
from urllib.parse import urlencode

from exchange.catalogue_serve import EmptyCatalogueServer
from exchange.market_scenarios import WORDS
from exchange.market_scenario_workbench import mount_market_scenarios


class MarketScenarioEntryTests(unittest.TestCase):
    def server(self, *, scenes=True, collateral=False):
        server = EmptyCatalogueServer(port=0, commit="a" * 40, tree="b" * 40,
            scenario_selection=scenes, collateral_selection=collateral)
        worker = threading.Thread(target=server.serve_forever,
            kwargs={"poll_interval": 0.02}, daemon=True)
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(worker.join, 3)
        self.addCleanup(server.shutdown)
        return server

    def request(self, server, path, method="GET", headers=None, body=None):
        connection = http.client.HTTPConnection(*server.server_address, timeout=3)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.read().decode(), dict(response.getheaders())
        finally:
            connection.close()

    def test_default_startup_keeps_existing_empty_entry_and_no_scenario_route(self):
        server = self.server(scenes=False)
        self.assertEqual(self.request(server, "/scenarios")[0], 404)
        status, body, _ = self.request(server, "/market")
        self.assertEqual(status, 200)
        self.assertNotIn('href="/scenarios?', body)

    def test_six_languages_have_market_navigation_and_each_confirmed_scene(self):
        server = self.server()
        for locale, words in WORDS.items():
            status, market, _ = self.request(server, "/market?lang=" + locale)
            self.assertEqual(status, 200)
            self.assertIn('href="/scenarios?lang=' + locale + '"', market)
            for scene in ("hedging", "collateral", "arbitrage"):
                status, body, _ = self.request(server, "/scenarios?" + urlencode(
                    dict(lang=locale, scene=scene, crypto="ETH", commodity="soybean")))
                self.assertEqual(status, 200)
                self.assertIn('lang="' + locale + '"', body)
                self.assertIn('value="' + scene + '" selected', body)
                self.assertIn(words[13], body)

    def test_original_collateral_and_scenario_mounts_coexist_once_on_same_listener(self):
        server = self.server(collateral=True)
        handler = server.RequestHandlerClass
        self.assertIs(mount_market_scenarios(server, allow_empty_catalogue=True), server)
        self.assertIs(server.RequestHandlerClass, handler)
        status, market, _ = self.request(server, "/market?lang=fr")
        self.assertEqual(status, 200)
        self.assertEqual(market.count('href="/scenarios?lang=fr"'), 1)
        self.assertEqual(market.count('href="/collateral?lang=fr"'), 1)
        self.assertEqual(self.request(server, "/collateral?lang=fr")[0], 200)

    def test_query_rejects_wrong_missing_duplicate_and_economic_fields(self):
        server = self.server()
        for query in ("scene=arbitrage&scene=hedging", "lang=unknown", "scene=futures",
                      "crypto=PYUSD", "commodity=gold", "rate=5", "scene=arbitrage&profit=1",
                      "target=" + "0" * 64, "broken", "scene=" + "x" * 1025):
            with self.subTest(query=query):
                status, body, _ = self.request(server, "/scenarios?" + query)
                self.assertEqual(status, 400)
                self.assertEqual(body, WORDS["en"][20])

    def test_host_guard_precedes_get_and_post_query_handling(self):
        server = self.server()
        for method in ("GET", "POST"):
            status, body, _ = self.request(server, "/scenarios?lang=unknown", method,
                headers={"Host": "different.example"})
            self.assertEqual(status, 421)
            self.assertEqual(body, "host refused")

    def test_post_closes_unread_body_without_dispatch_and_remains_localized(self):
        server = self.server()
        status, body, headers = self.request(server, "/scenarios?lang=ja", "POST", body="arbitrary-body")
        self.assertEqual(status, 405)
        self.assertEqual(body, WORDS["ja"][20])
        self.assertEqual(headers.get("Allow"), "GET")
        self.assertEqual(headers.get("Connection"), "close")

    def test_business_components_and_empty_directory_do_not_become_ready(self):
        server = self.server()
        self.request(server, "/scenarios?scene=arbitrage&crypto=BTC&commodity=iron-ore")
        status, body, _ = self.request(server, "/healthz")
        self.assertEqual(status, 200)
        health = json.loads(body)
        self.assertEqual(health["operationsREADY"], "NOT_VERIFIED")
        self.assertEqual(health["configuredComponents"], {"commandGateway": False,
            "gasPage": False, "referenceFeed": False, "registrationSources": False})
        self.assertEqual(json.loads(self.request(server, "/api/nfts")[1]), {"nfts": []})
        for path in ("/run", "/demo", "/snapshot", "/api/operations"):
            self.assertEqual(self.request(server, path)[0], 404)

    def test_empty_mount_remains_explicit_and_boolean(self):
        server = self.server(scenes=False)
        with self.assertRaises(ValueError):
            mount_market_scenarios(server)
        with self.assertRaises(ValueError):
            mount_market_scenarios(server, allow_empty_catalogue="yes")
        with self.assertRaises(ValueError):
            self.server(scenes="yes")
        mount_market_scenarios(server, allow_empty_catalogue=True)
        self.assertEqual(self.request(server, "/scenarios")[0], 200)
