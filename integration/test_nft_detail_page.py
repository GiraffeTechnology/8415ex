"""Authored rendering regressions; execute only on the approved remote runner."""
import unittest
from exchange.nft_detail import receipt_detail
from exchange.nft_detail_page import LOCALES, render_detail
from integration.test_nft_detail import OriginalReadOnlyDomain


class NftDetailPage(unittest.TestCase):
    def test_all_six_locales_render_unknown_current_without_fabricated_open_gap(self):
        detail = receipt_detail(OriginalReadOnlyDomain(), "one")
        for locale, words in LOCALES.items():
            with self.subTest(locale=locale):
                html = render_detail(detail, locale)
                self.assertIn('<html lang="' + locale + '">', html)
                self.assertIn(words[0], html)
                self.assertIn(words[13], html)
                self.assertIn('class="gap">' + words[8], html)
                self.assertNotIn('class="gap">GapOf=Open', html)
                self.assertNotIn("private-owner-name", html)
                self.assertIn('/nft?lang=ja', html)

    def test_long_chain_preserves_distinct_markers_and_only_evidenced_signatures(self):
        detail = receipt_detail(OriginalReadOnlyDomain(), "one")
        detail["positions"] = {"current": 200, "owner": 199, "holder": 2}
        detail["signatureStatusByPosition"] = [{"position": 2, "status": "pending"}]
        detail["gap"] = "open"
        html = render_detail(detail)
        self.assertIn('class="gap">GapOf=Open', html)
        self.assertIn('class="position">200', html)
        self.assertIn('class="position">199', html)
        self.assertIn('class="position">2', html)
        self.assertEqual(html.count('<li class="node">'), 3)
        self.assertIn("Pending", html)
        self.assertNotIn("<p>Signed</p>", html)

    def test_signed_business_text_is_escaped_without_translation_or_summary(self):
        detail = receipt_detail(OriginalReadOnlyDomain(), "one")
        detail["terms"] = {"status": "provided-verified-projection", "clauses": [
            {"label": "Original condition", "text": "<script>must remain literal</script>\nSecond obligation."}]}
        for locale in LOCALES:
            html = render_detail(detail, locale)
            self.assertIn('&lt;script&gt;must remain literal&lt;/script&gt;\nSecond obligation.', html)
            self.assertNotIn('<script>', html)
            self.assertNotIn('download=', html)

    def test_unknown_locale_is_not_silently_translated(self):
        with self.assertRaises(ValueError):
            render_detail(receipt_detail(OriginalReadOnlyDomain(), "one"), "unknown")
