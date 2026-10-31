"""Original selected-source terminal UI, synthetic Linux sources only."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import build_opener, ProxyHandler
from exchange.errors import DomainError
from exchange.market_page import render_market, render_terminal, WORDS
from exchange.workbench import WorkbenchServer
from integration import test_public_order_book_http as original


class TerminalSource:
    def __init__(self, currency, price):
        self.currency, self.price = currency, price
        self.calls, self.receipt_reads = [], []
        self.currency_error = False

    def receipt(self, receipt_id):
        self.receipt_reads.append(receipt_id)
        if self.currency_error:
            raise OSError("private source unavailable")
        return SimpleNamespace(allowed_price_currencies=(self.currency,))

    def order_book_view(self, receipt_id, currency, *, limit=20):
        self.calls.append((receipt_id, currency, limit))
        if currency != self.currency:
            raise DomainError("EX_PUBLIC_BOOK_CURRENCY_REFUSED", "private rejected currency")
        return original.snapshot(currency, self.price)


class TerminalUI(unittest.TestCase):
    def setUp(self):
        self.sources = [TerminalSource("local-test-quote", "100"),
                        TerminalSource("second-fixture-currency", "200")]
        self.detail = {"schema": "8415ex-public-nft-detail/1",
            "positions": {"current": None, "owner": None, "holder": None},
            "gap": "unknown", "displayGap": {"state": "unknown"},
            "terms": {"status": "not-provided", "clauses": []}}
        self.bindings = [SimpleNamespace(exchange=source, receipt_id="private-terminal-" + str(i),
            run={}, gateway=None, public_detail=Mock(return_value=deepcopy(self.detail)))
            for i, source in enumerate(self.sources)]
        self.server = WorkbenchServer(self.bindings[0], detail_bindings=(self.bindings[1],), port=0)
        self.keys = [self.server.nft_directory.key_for(binding) for binding in self.bindings]
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.open = build_opener(ProxyHandler({})).open

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)

    def get(self, path):
        try:
            response = self.open(self.server.origin + path, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.code, response.read().decode()

    def test_six_locales_use_selected_original_book_and_keep_missing_history_quote(self):
        for locale, words in WORDS.items():
            code, body = self.get("/terminal?" + urlencode(
                {"lang": locale, "nft": self.keys[0], "currency": self.sources[0].currency}))
            self.assertEqual(code, 200)
            self.assertIn('<html lang="' + locale + '">', body)
            self.assertIn('class="terminal-layout"', body)
            self.assertIn('class="terminal-book"', body)
            self.assertIn('class="terminal-ticket"', body)
            self.assertIn(words[23], body)
            self.assertIn(words[11], body)
            self.assertIn('<button disabled>', body)
            self.assertIn('<td>100</td>', body)
            product = body.split('class="terminal-product"', 1)[1].split('class="terminal-chart"', 1)[0]
            self.assertNotIn('class="quote">100<', product)
            for fake in ("private-terminal-", "private rejected", "3860", "0.0020", "candlestick", "<script"):
                self.assertNotIn(fake, body)

    def test_receipt_selection_resets_only_view_to_that_receipts_original_currency(self):
        code, body = self.get("/terminal?" + urlencode({"nft": self.keys[1], "lang": "fr"}))
        self.assertEqual(code, 200)
        self.assertIn("second-fixture-currency", body)
        self.assertIn("<td>200</td>", body)
        self.assertNotIn("<td>100</td>", body)
        self.assertEqual(self.sources[0].calls, [])
        self.assertEqual(self.sources[1].calls, [(self.bindings[1].receipt_id, self.sources[1].currency, 20)])

    def test_invalid_context_refuses_before_any_original_read(self):
        for fields in ({"lang": "xx"}, {"side": "execute"}, {"q": "x" * 65},
                       {"currency": ""}, {"outcome": "PASSED"}):
            self.assertEqual(self.get("/terminal?" + urlencode(fields))[0], 400)
        self.assertEqual(self.get("/terminal?nft=" + "f" * 64)[0], 404)
        for source, binding in zip(self.sources, self.bindings):
            self.assertEqual(source.calls, [])
            self.assertEqual(source.receipt_reads, [])
            binding.public_detail.assert_not_called()

    def test_explicit_foreign_currency_never_falls_back_or_reads_detail(self):
        code, _ = self.get("/terminal?" + urlencode(
            {"nft": self.keys[1], "currency": self.sources[0].currency}))
        self.assertEqual(code, 400)
        self.assertEqual(self.sources[1].calls, [])
        self.bindings[1].public_detail.assert_not_called()

    def test_missing_original_currencies_show_unknown_without_invented_default_or_empty_book(self):
        self.sources[0].currency_error = True
        code, body = self.get("/terminal?lang=en")
        self.assertEqual(code, 200)
        self.assertIn(WORDS["en"][32], body)
        self.assertIn(WORDS["en"][22], body)
        self.assertNotIn("private source", body)
        self.assertNotIn('<select name="currency">', body)
        self.assertEqual(self.sources[0].calls, [])

    def test_language_side_detail_back_keep_selected_nft_currency_and_query(self):
        code, body = self.get("/terminal?" + urlencode(
            {"lang": "en", "nft": self.keys[1], "currency": self.sources[1].currency,
             "q": "soy <search>", "side": "sell"}))
        self.assertEqual(code, 200)
        self.assertIn("soy+%3Csearch%3E", body)
        self.assertIn("nft=" + self.keys[1], body)
        self.assertIn("currency=second-fixture-currency", body)
        self.assertIn('lang="zh-Hans"', body)
        self.assertIn("side=sell", body)
        self.assertIn('/nft?lang=en&amp;nft=' + self.keys[1], body)
        self.assertNotIn("soy <search>", body)

    def test_market_trade_navigation_targets_real_terminal_but_empty_catalogue_does_not(self):
        page = render_market([], {"status": "not-connected", "price": None}, "en", "soy")
        self.assertIn('class="hero-start" href="/terminal?lang=en&amp;q=soy"', page)
        empty = render_market([], {"status": "not-connected", "price": None},
                              "en", empty_catalogue=True)
        self.assertIn('class="hero-start" href="#nfts"', empty)

    def test_renderer_refuses_invalid_locale_side_and_currency_without_promoting_authority(self):
        for kwargs in ({"locale": "xx"}, {"side": "execute"},
                       {"currency": "foreign"}, {"evidence_kind": "REAL"}):
            with self.assertRaises(ValueError):
                render_terminal(self.detail, [{"nftKey": self.keys[0]}],
                    ("local-test-quote",), original.snapshot("local-test-quote"),
                    nft_key=self.keys[0], **kwargs)
