"""Compact actual-source quote, complete disclosure and unchanged refresh boundaries."""
from copy import deepcopy
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import unittest

from exchange.market_page import render_reference_panel, PROVENANCE_SUMMARY
from exchange.reference_provenance_page import render_reference_fields
from exchange.market_reference_refresh import REFERENCE_SCRIPT


class ReferenceQuoteDisclosure(unittest.TestCase):
    def test_six_locales_keep_exact_complete_provenance_without_example_prices(self):
        ref = {"status": "unknown", "price": "103.37", "spec": "WTI",
               "currency": "USD", "unit": "barrel", "provider": "Original <source>",
               "sourceAsOf": "2026-10-27", "sourcePrecision": "date",
               "sourceTimezone": None, "fetchedAt": "2026-10-31T14:47:06.585925Z",
               "sourceEvidence": {"publicationDate": "2026-10-28",
                                  "rawResponseSHA256": "a" * 64}}
        before = deepcopy(ref)
        for locale, label in PROVENANCE_SUMMARY.items():
            with self.subTest(locale=locale):
                page = render_reference_panel(ref, locale)
                self.assertIn("WTI · USD / barrel", page)
                self.assertIn(label, page)
                self.assertIn(render_reference_fields(ref, locale), page)
                self.assertIn("<details", page)
                self.assertNotIn("<details open", page)
                self.assertIn("103.37", page)
                self.assertIn("Original &lt;source&gt;", page)
                self.assertNotIn("<source>", page)
                for fake in ("3,860", "786.50", "73,420", "<script"):
                    self.assertNotIn(fake, page)
        self.assertEqual(ref, before)

    def test_missing_source_never_becomes_a_commodity_or_zero_price(self):
        for locale in PROVENANCE_SUMMARY:
            page = render_reference_panel({"status": "not-connected", "price": None}, locale)
            self.assertNotIn("WTI", page)
            self.assertNotIn("Soybeans", page)
            self.assertNotIn(">0<", page)
            self.assertIn('data-reference-status', page)
            self.assertIn('data-browser-error hidden', page)

    def test_browser_refresh_preserves_both_open_and_closed_user_disclosure_state(self):
        fixture = Path(__file__).parent / "fixtures" / "market_refresh_browser.cjs"
        for case in ("disclosure-open", "disclosure-closed", "disclosure-focus"):
            result = subprocess.run(["node", str(fixture)],
                input=json.dumps({"script": REFERENCE_SCRIPT, "case": case}),
                text=True, capture_output=True, timeout=10, check=True)
            self.assertEqual(json.loads(result.stdout), {"case": case, "passed": True})
