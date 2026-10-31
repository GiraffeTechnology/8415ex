"""Public market root alias contracts; no live provider or native authority."""
import http.client
import json
import threading
import unittest
from urllib.parse import urlencode
from exchange.workbench import WorkbenchServer
from exchange.market_page import WORDS
from exchange.nft_detail_page import LOCALES
from integration.test_market_page import original

class RootMarketEntry(unittest.TestCase):
    def setUp(self):
        self.binding, self.original = original()
        self.before = json.dumps(self.binding.public_detail(), sort_keys=True)
        self.server = WorkbenchServer(self.binding, port=0)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)

    def read(self, path, host=None):
        c = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            c.request("GET", path, headers={} if host is None else {"Host": host})
            r = c.getresponse()
            return r.status, dict(r.getheaders()), r.read().decode()
        finally:
            c.close()

    def test_root_is_same_source_bound_market_in_each_locale_and_search(self):
        for locale in WORDS:
            with self.subTest(locale=locale):
                query = "?" + urlencode({"lang": locale, "q": "soy"})
                code, _, body = self.read("/" + query)
                other, _, market = self.read("/market" + query)
                self.assertEqual((code, other), (200, 200))
                self.assertEqual(body, market)
                self.assertIn("Original soy", body)
                self.assertIn('href="https://8415wallet.com"', body)
                self.assertNotIn("private-market-one", body)
        self.assertEqual(self.before, json.dumps(self.binding.public_detail(), sort_keys=True))
        self.assertEqual(len(self.server.runs), 0)

    def test_explicit_receipt_and_bad_market_inputs_remain_distinct(self):
        code, _, detail = self.read("/receipt?lang=fr")
        self.assertEqual(code, 200)
        self.assertIn(LOCALES["fr"][0], detail)
        self.assertNotIn('class="market-top"', detail)
        for path in ("/?lang=en&lang=fr", "/?q=" + "x" * 65, "/?lang=missing",
                     "/?account=untrusted", "/?reference=2"):
            with self.subTest(path=path):
                self.assertEqual(self.read(path)[0], 400)
        self.assertEqual(self.read("/", host="foreign.example")[0], 421)
        self.assertEqual(len(self.server.runs), 0)
