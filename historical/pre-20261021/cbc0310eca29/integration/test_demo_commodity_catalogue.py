"""Synthetic display/HTTP definitions, not real goods, prices or chain assets."""
from copy import deepcopy
from html import escape
import http.client
import json
import re
import threading
import unittest
from urllib.parse import urlencode

from exchange.demo_commodities import COMMODITY_ORDER, NAMES, DISPLAY_WORDS
from exchange.catalogue_serve import EmptyCatalogueServer
from exchange.market_page import render_market
from exchange.nft_detail_page import render_detail
from exchange.nft_directory import NftDirectory
from exchange.workbench import WorkbenchServer
from integration.test_market_page import original


def catalogue():
    bindings, sources = [], []
    for index, code in enumerate(COMMODITY_ORDER):
        binding, source = original("private-commodity-" + str(index), "Synthetic " + NAMES["en"][index])
        source["marketCard"]["commodityCode"] = code
        bindings.append(binding)
        sources.append(source)
    return bindings, sources


class DemoCommodityCatalogueTests(unittest.TestCase):
    def test_read_only_demo_navigation_preserves_empty_original_catalogue(self):
        server = EmptyCatalogueServer(port=0, commit="a" * 40, tree="b" * 40)
        worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        worker.start()

        def request(method, path):
            connection = http.client.HTTPConnection(*server.server_address, timeout=3)
            try:
                connection.request(method, path)
                response = connection.getresponse()
                return response.status, response.read().decode()
            finally:
                connection.close()

        try:
            for locale in NAMES:
                for code in COMMODITY_ORDER:
                    status, body = request("GET", "/demo-commodity?" + urlencode(
                        {"lang": locale, "commodity": code, "q": "gold & corn"}))
                    self.assertEqual(status, 200)
                    self.assertIn('<html lang="' + locale + '">', body)
                    self.assertIn("SIMULATED", body)
                    self.assertIn("/market?" + escape(urlencode(
                        {"lang": locale, "q": "gold & corn"})), body)
            status, body = request("GET", "/demo-commodity?commodity=gold")
            self.assertEqual(status, 200)
            self.assertIn('<html lang="en">', body)
            for query in ("commodity=wheat", "commodity=gold&lang=xx",
                          "commodity=gold&commodity=corn", "commodity=gold&q=%00",
                          "commodity=gold&wallet=private-account"):
                status, body = request("GET", "/demo-commodity?" + query)
                self.assertEqual(status, 400)
                self.assertNotIn("private-account", body)
            for path in ("/api/nfts", "/api/catalogue"):
                status, body = request("GET", path)
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["nfts"], [])
            status, _ = request("POST", "/demo-commodity?commodity=gold")
            self.assertEqual(status, 405)
            self.assertEqual(server.nft_directory.catalogue(), [])
        finally:
            server.shutdown()
            worker.join(3)
            server.server_close()

    def test_exact_eight_codes_and_english_order(self):
        self.assertEqual(COMMODITY_ORDER,
            ("gold", "silver", "copper", "iron-ore", "crude-oil", "coal", "soy", "corn"))
        self.assertEqual(NAMES["en"],
            ("Gold", "Silver", "Copper", "Iron Ore", "Crude Oil", "Coal", "Soybeans", "Corn"))

    def test_six_language_category_labels_keep_the_same_eight_positions(self):
        self.assertEqual(set(NAMES), {"en", "zh-Hans", "zh-Hant", "fr", "es", "ja"})
        for locale, names in NAMES.items():
            with self.subTest(locale=locale):
                page = render_market([], {"status": "not-connected"}, locale, empty_catalogue=True)
                self.assertEqual(re.findall(r'data-demo-commodity="([^"]+)"', page), list(COMMODITY_ORDER))
                positions = [page.index('<h3>' + escape(name) + '</h3>') for name in names]
                self.assertEqual(positions, sorted(positions))
                self.assertIn(escape(DISPLAY_WORDS[locale][1]), page)

    def test_empty_directory_keeps_static_examples_separate_from_original_inventory(self):
        page = render_market([], {"status": "not-connected", "price": None}, empty_catalogue=True)
        self.assertEqual(len(re.findall('data-demo-commodity=', page)), 8)
        self.assertNotIn('id="nft-', page)
        self.assertNotIn('class="nft-card"', page)
        self.assertNotIn('class="quote">0', page)
        self.assertIn('src="/assets/soy.png"', page)
        self.assertIn("SIMULATED · not a live feed", page)
        self.assertIn("Original NFT observations", page)

    def test_original_projection_accepts_all_eight_without_changing_quotes_or_terms(self):
        bindings, sources = catalogue()
        before = deepcopy(sources)
        for binding, source in zip(bindings, sources):
            detail = binding.public_detail()
            self.assertEqual(detail["sourceStatus"], "verified-original-reader")
            self.assertEqual(detail["marketCard"]["commodityCode"], source["marketCard"]["commodityCode"])
            self.assertEqual(detail["marketCard"]["quote"], source["marketCard"]["quote"])
            self.assertEqual(detail["terms"]["clauses"][0]["text"], "Original <unchanged> obligation.")
        self.assertEqual(sources, before)

    def test_nft_card_display_order_follows_categories_without_mutating_directory(self):
        bindings, sources = catalogue()
        directory = NftDirectory(tuple(reversed(bindings)))
        entries = directory.catalogue()
        before = deepcopy(entries)
        page = render_market(entries, {"status": "not-connected"})
        positions = [page.index('id="nft-' + directory.key_for(binding) + '"') for binding in bindings]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(entries, before)
        self.assertEqual([s["marketCard"]["quote"]["amountBaseUnits"] for s in sources], ["100"] * 8)

    def test_replaced_other_category_is_hidden_but_original_history_is_retained(self):
        binding, source = original("private-old-category", "Replaced wheat display")
        source["marketCard"]["commodityCode"] = "other"
        directory = NftDirectory((binding,))
        page = render_market(directory.catalogue(), {"status": "unavailable"})
        self.assertNotIn("Replaced wheat display", page)
        self.assertNotIn('data-demo-commodity="other"', page)
        self.assertEqual(directory.detail(directory.key_for(binding))["marketCard"]["name"], "Replaced wheat display")

    def test_code_and_localized_search_select_the_same_actual_receipt(self):
        bindings, _ = catalogue()
        directory = NftDirectory(bindings)
        for locale, names in NAMES.items():
            for index, code in enumerate(COMMODITY_ORDER):
                for query in (code, names[index]):
                    with self.subTest(locale=locale, code=code, query=query):
                        page = render_market(directory.catalogue(), {"status": "unavailable"}, locale, query)
                        self.assertIn('id="nft-' + directory.key_for(bindings[index]) + '"', page)
                        self.assertIn(escape(urlencode({"lang": locale, "nft": directory.key_for(bindings[index]), "q": query})), page)

    def test_directory_detail_navigation_keeps_commodity_labels_and_exact_nft_keys(self):
        bindings, _ = catalogue()
        directory = NftDirectory(bindings)
        self.assertEqual([row["commodityCode"] for row in directory.choices()], list(COMMODITY_ORDER))
        for locale, names in NAMES.items():
            for index, binding in enumerate(bindings):
                key = directory.key_for(binding)
                body = render_detail(directory.detail(key), locale, nft_key=key,
                    choices=directory.choices(), market_query=COMMODITY_ORDER[index])
                self.assertIn('DEMO · ' + escape(names[index]), body)
                self.assertIn('/market?' + escape(urlencode({"lang": locale, "q": COMMODITY_ORDER[index]}))
                              + '#nft-' + key, body)
                self.assertIn("Original &lt;unchanged&gt; obligation.", body)
                self.assertNotIn("private-commodity-", body)

    def test_actual_original_http_market_to_detail_and_back_for_each_category(self):
        bindings, _ = catalogue()
        server = WorkbenchServer(bindings[0], detail_bindings=bindings[1:], commit="a" * 40, tree="b" * 40)
        worker = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        worker.start()
        def get(path):
            connection = http.client.HTTPConnection(*server.server_address, timeout=3)
            try:
                connection.request("GET", path)
                response = connection.getresponse()
                return response.status, response.read().decode()
            finally:
                connection.close()
        try:
            for index, code in enumerate(COMMODITY_ORDER):
                key = server.nft_directory.key_for(bindings[index])
                status, market = get('/market?' + urlencode({"lang": "es", "q": code}))
                self.assertEqual(status, 200)
                self.assertIn('id="nft-' + key + '"', market)
                status, detail = get('/nft?' + urlencode({"lang": "es", "nft": key, "q": code}))
                self.assertEqual(status, 200)
                self.assertIn('DEMO · ' + escape(NAMES["es"][index]), detail)
                self.assertIn('/market?' + escape(urlencode({"lang": "es", "q": code})) + '#nft-' + key, detail)
        finally:
            server.shutdown()
            worker.join(3)
            server.server_close()

    def test_unknown_quote_and_reference_are_not_replaced_by_demo_category_data(self):
        bindings, sources = catalogue()
        for source in sources:
            source["marketCard"]["quote"] = None
        directory = NftDirectory(bindings)
        page = render_market(directory.catalogue(), {"status": "not-connected", "price": None})
        self.assertNotIn('class="quote">100 ETH', page)
        self.assertIn("Not connected", page)
        self.assertIn("SIMULATED · not a live feed", page)
        self.assertIn("520", page)
        for entry in directory.catalogue():
            self.assertIsNone(entry["marketCard"]["quote"])
