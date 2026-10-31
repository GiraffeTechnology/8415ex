"""Incremental market navigation contract; not full design acceptance."""
from html.parser import HTMLParser
import unittest
from urllib.parse import parse_qs, urlsplit
from exchange.market_page import render_market, WORDS

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "a":
            self.links.append(attrs)

class MarketFigmaNavigationTest(unittest.TestCase):
    def test_entry_destinations_preserve_locale_search_and_authority_boundary(self):
        for locale in WORDS:
            with self.subTest(locale=locale):
                html = render_market([], {"status": "unavailable", "price": None},
                                     locale, query='soy <script>"')
                parsed = Links()
                parsed.feed(html)
                wallet = [a for a in parsed.links if a.get("class") == "wallet-entry"]
                self.assertEqual(len(wallet), 1)
                self.assertEqual(wallet[0]["href"], "https://8415wallet.com")
                self.assertIn("noopener", wallet[0]["rel"])
                starts = [a for a in parsed.links if a.get("class") == "hero-start"]
                self.assertEqual(len(starts), 1)
                target = urlsplit(starts[0]["href"])
                self.assertEqual(target.path, "/terminal")
                self.assertEqual(parse_qs(target.query), {"lang": [locale], "q": ['soy <script>"']})
                self.assertIn("nfts", parsed.ids)
                active = [a for a in parsed.links if a.get("aria-current") == "page"]
                self.assertEqual(len(active), 1)
                self.assertEqual(active[0]["href"], "#nfts")
                self.assertIn('name="lang" value="' + locale + '"', html)
                self.assertIn('value="soy &lt;script&gt;&quot;"', html)
                self.assertNotIn(":9446", html)
                self.assertNotIn('<button disabled>', html)
                self.assertNotIn('method="post"', html)
                self.assertNotIn('authenticated', html)

    def test_explicit_empty_catalogue_has_no_invented_terminal_target(self):
        for locale in WORDS:
            with self.subTest(locale=locale):
                parsed = Links()
                parsed.feed(render_market([], {"status": "not-connected", "price": None},
                                          locale, empty_catalogue=True))
                starts = [a for a in parsed.links if a.get("class") == "hero-start"]
                self.assertEqual([a["href"] for a in starts], ["#nfts"])
                self.assertFalse(any(a.get("href", "").startswith("/terminal")
                                     for a in parsed.links))

if __name__ == "__main__":
    unittest.main()
