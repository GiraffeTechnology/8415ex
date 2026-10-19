"""Synthetic empty-catalogue collateral routes; no real asset or wallet calls."""
import http.client
import json
import threading
import unittest
from urllib.parse import urlencode

from exchange.catalogue_serve import EmptyCatalogueServer
from exchange.collateral_scenario import WORDS
from exchange.collateral_workbench import mount_collateral_selection


class EmptyCollateralEntryTests(unittest.TestCase):
    def server(self, enabled=False):
        server = EmptyCatalogueServer(port=0, commit="a" * 40, tree="b" * 40,
                                      collateral_selection=enabled)
        self.addCleanup(server.server_close)
        return server

    def request(self, server, path, method="GET", headers=None):
        worker = threading.Thread(target=server.serve_forever,
                                  kwargs={"poll_interval": 0.02}, daemon=True)
        worker.start()
        connection = http.client.HTTPConnection(*server.server_address, timeout=3)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.read().decode(), dict(response.getheaders())
        finally:
            connection.close()
            server.shutdown()
            worker.join(3)

    def test_default_empty_entry_retains_unmounted_route_and_original_market(self):
        server = self.server()
        self.assertEqual(self.request(server, "/collateral?lang=en")[0], 404)
        status, body, _ = self.request(server, "/market?lang=en")
        self.assertEqual(status, 200)
        self.assertNotIn('href="/collateral?', body)
        self.assertEqual(json.loads(self.request(server, "/api/nfts")[1]), {"nfts": []})

    def test_explicit_empty_selection_is_linked_in_all_six_original_market_locales(self):
        server = self.server(True)
        for locale in WORDS:
            with self.subTest(locale=locale):
                status, body, _ = self.request(server, "/market?" + urlencode({"lang": locale}))
                self.assertEqual(status, 200)
                self.assertIn('href="/collateral?lang=' + locale + '"', body)
                self.assertIn(WORDS[locale][0], body)
                status, body, _ = self.request(server, "/collateral?lang=" + locale)
                self.assertEqual(status, 200)
                self.assertIn('value="crypto"', body)
                self.assertIn('value="warehouse-nft"', body)
                self.assertIn(WORDS[locale][14], body)

    def test_crypto_choice_remains_simulation_with_no_invented_financial_values(self):
        server = self.server(True)
        for asset in ("BTC", "ETH"):
            status, body, _ = self.request(server, "/collateral?" + urlencode(
                {"lang": "en", "kind": "crypto", "asset": asset}))
            self.assertEqual(status, 200)
            self.assertIn(WORDS["en"][9], body)
            self.assertIn(WORDS["en"][10], body)
            self.assertIn(WORDS["en"][11], body)
            self.assertIn('value="' + asset + '" selected', body)
            self.assertNotIn('name="ltv"', body)
            self.assertNotIn('type="number"', body)
        self.assertEqual(server.nft_directory.choices(), [])

    def test_absent_nft_and_financing_or_duplicate_fields_do_not_become_valid_selection(self):
        server = self.server(True)
        for query in ("kind=warehouse-nft&asset=" + "0" * 64,
                      "kind=crypto&asset=ETH&ltv=50",
                      "kind=crypto&asset=ETH&target=" + "0" * 64,
                      "kind=crypto&kind=crypto&asset=ETH"):
            with self.subTest(query=query):
                status, _, _ = self.request(server, "/collateral?" + query)
                self.assertEqual(status, 400)
        self.assertEqual(json.loads(self.request(server, "/api/nfts")[1]), {"nfts": []})

    def test_selector_does_not_configure_business_components_or_open_model_command_routes(self):
        server = self.server(True)
        status, raw, _ = self.request(server, "/healthz")
        self.assertEqual(status, 200)
        health = json.loads(raw)
        self.assertEqual(health["operationsREADY"], "NOT_VERIFIED")
        self.assertEqual(health["configuredComponents"],
            {"commandGateway": False, "gasPage": False,
             "referenceFeed": False, "registrationSources": False})
        for path in ("/demo", "/snapshot", "/run"):
            self.assertEqual(self.request(server, path)[0], 404)

    def test_post_is_refused_and_connection_closed_without_dispatch(self):
        server = self.server(True)
        status, body, headers = self.request(server, "/collateral?lang=ja", "POST")
        self.assertEqual(status, 405)
        self.assertEqual(body, WORDS["ja"][13])
        self.assertEqual(headers.get("Allow"), "GET")
        self.assertEqual(headers.get("Connection"), "close")
        self.assertEqual(self.request(server, "/run", "POST")[0], 405)

    def test_original_host_guard_and_idempotent_mount_remain_effective(self):
        server = self.server(True)
        handler = server.RequestHandlerClass
        self.assertIs(mount_collateral_selection(server, allow_empty_catalogue=True), server)
        self.assertIs(server.RequestHandlerClass, handler)
        navigation = handler.native_navigation("fr")
        self.assertEqual(navigation.count("/collateral?lang=fr"), 1)
        self.assertEqual(self.request(server, "/collateral?lang=en",
                                     headers={"Host": "different.example"})[0], 421)

    def test_empty_mount_requires_explicit_bool_and_does_not_relax_default_workbench_contract(self):
        server = self.server()
        with self.assertRaises(ValueError):
            mount_collateral_selection(server)
        with self.assertRaises(ValueError):
            mount_collateral_selection(server, allow_empty_catalogue="yes")
        with self.assertRaises(ValueError):
            self.server("yes")
        mount_collateral_selection(server, allow_empty_catalogue=True)
        self.assertEqual(self.request(server, "/collateral?lang=en")[0], 200)
