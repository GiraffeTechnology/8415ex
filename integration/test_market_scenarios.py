"""Synthetic scene context and privacy contracts; no live market execution."""
import unittest
from urllib.parse import parse_qs, urlsplit
from html.parser import HTMLParser

from exchange.market_scenarios import WORDS, render_scenarios, scenario_selection
from exchange.nft_directory import NftDirectory


class Links(HTMLParser):
    def __init__(self, body):
        super().__init__()
        self.links = []
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs))


class Binding:
    def __init__(self, receipt_id):
        self.receipt_id = receipt_id

    def public_detail(self):
        raise AssertionError("scene selection must not query domain or provider state")


class MarketScenariosTests(unittest.TestCase):
    def test_every_scene_and_crypto_commodity_context_remains_nonexecuting(self):
        directory = NftDirectory((), allow_empty=True)
        for scene in ("hedging", "collateral", "arbitrage"):
            for crypto in ("BTC", "ETH"):
                for commodity in ("soybean", "iron-ore"):
                    row = scenario_selection(directory, scene=scene, crypto=crypto, commodity=commodity)
                    self.assertEqual(row["scene"], scene)
                    for flag in ("executionInvoked", "receiptCommodityVerified", "assetMappingVerified",
                                 "tradeEligibilityEvaluated"):
                        self.assertIs(row[flag], False)
                    self.assertIsNone(row["economicParameters"])
                    self.assertIsNone(row["economicResult"])

    def test_absent_real_receipt_never_becomes_a_fabricated_asset(self):
        directory = NftDirectory((), allow_empty=True)
        self.assertIsNone(scenario_selection(directory)["targetNftKey"])
        with self.assertRaises(ValueError):
            scenario_selection(directory, target="0" * 64)
        self.assertEqual(directory.choices(), [])

    def test_only_original_directory_target_is_linked_without_reader_or_identity_leak(self):
        first = Binding("private-wallet-name/0x1234567890/receipt-one")
        second = Binding("private-wallet-name/0x9876543210/receipt-two")
        directory = NftDirectory((first, second))
        key = directory.key_for(second)
        body = render_scenarios(directory, target=key, scene="arbitrage")
        links = Links(body).links
        detail = [link for link in links if urlsplit(link["href"]).path == "/nft"]
        self.assertEqual(len(detail), 1)
        self.assertEqual(parse_qs(urlsplit(detail[0]["href"]).query), {"nft": [key], "lang": ["en"]})
        for secret in (first.receipt_id, second.receipt_id, "0x1234567890", "0x9876543210"):
            self.assertNotIn(secret, body)
        self.assertEqual(tuple(directory._bindings.values()), (first, second))

    def test_language_links_preserve_exact_selection_and_original_target(self):
        binding = Binding("original-receipt")
        directory = NftDirectory((binding,))
        context = dict(scene="hedging", crypto="ETH", commodity="iron-ore", target=directory.key_for(binding))
        for locale in WORDS:
            body = render_scenarios(directory, locale, **context)
            self.assertIn('lang="' + locale + '"', body)
            links = [link for link in Links(body).links if urlsplit(link["href"]).path == "/scenarios"]
            self.assertEqual(len(links), 6)
            for link in links:
                query = parse_qs(urlsplit(link["href"]).query)
                self.assertEqual(query, {"lang": [link["lang"]], **{key: [value] for key, value in context.items()}})

    def test_no_financial_inputs_or_wallet_forms_are_added_in_any_locale(self):
        directory = NftDirectory((), allow_empty=True)
        for locale, words in WORDS.items():
            body = render_scenarios(directory, locale)
            for index in (13, 15, 16, 17, 18, 19):
                from html import unescape
                self.assertIn(words[index], unescape(body))
            self.assertNotIn('method="post"', body)
            self.assertNotIn('type="number"', body)
            for field in ("price", "ltv", "rate", "amount", "wallet", "account", "grant"):
                self.assertNotIn('name="' + field + '"', body)

    def test_unknown_context_types_and_cross_directory_targets_are_refused(self):
        directory = NftDirectory((Binding("first"),))
        other = NftDirectory((Binding("second"),))
        for context in ({"scene": "future"}, {"crypto": "PYUSD"}, {"commodity": "gold"},
                        {"scene": False}, {"target": None}, {"target": next(iter(other._bindings))},
                        {"scene": '<script>alert(1)</script>'}):
            with self.subTest(context=context), self.assertRaises(ValueError):
                scenario_selection(directory, **context)
        with self.assertRaises(ValueError):
            render_scenarios(directory, "unknown")

    def test_unprovided_choices_are_not_automatic_btc_or_commodity_defaults(self):
        row = scenario_selection(NftDirectory((), allow_empty=True))
        self.assertEqual([row[key] for key in ("scene", "cryptoContext", "commodityContext", "targetNftKey")],
                         [None, None, None, None])
