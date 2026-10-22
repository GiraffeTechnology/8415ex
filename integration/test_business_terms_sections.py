"""Original-clause section rendering definitions; author execution NOT_RUN."""
from copy import deepcopy
from html import escape
import json
import unittest

from exchange.nft_detail import TERM_SECTION_KEYS, receipt_detail
from exchange.nft_detail_page import LOCALES, TERM_SECTION_LABELS, render_detail
from integration.test_nft_detail import OriginalReadOnlyDomain


class BusinessTermsSections(unittest.TestCase):
    def record(self, clauses):
        return {"receiptId": "r", "currentPosition": 3,
                "businessTerms": {"coverageVerified": True, "identityExcluded": True,
                                  "clauses": clauses},
                "privateOriginal": "original-private-document",
                "privateHolderName": "private-owner-name"}

    def project(self, record, verify=None):
        return receipt_detail(OriginalReadOnlyDomain(), "r",
            read_details=lambda rid: record,
            verify_details=verify or (lambda rid, row: True))

    def test_legacy_clause_schema_and_flat_rendering_remain_unchanged(self):
        clauses = [{"label": "Quality", "text": "Grade A; entire quantity only."}]
        detail = self.project(self.record(clauses))
        self.assertEqual(detail["terms"]["clauses"], clauses)
        page = render_detail(detail)
        self.assertIn('<article><h3>Quality</h3><p class="terms">Grade A; entire quantity only.</p></article>', page)
        self.assertNotIn('class="terms-navigation"', page)

    def test_every_section_has_fixed_six_locale_heading_without_translating_original(self):
        clauses = [{"label": "Original clause " + str(index),
                    "text": "Unchanged obligation " + str(index), "section": section}
                   for index, section in enumerate(TERM_SECTION_KEYS)]
        detail = self.project(self.record(clauses))
        self.assertEqual(detail["terms"]["clauses"], clauses)
        self.assertEqual(set(TERM_SECTION_LABELS), set(LOCALES))
        for locale in LOCALES:
            with self.subTest(locale=locale):
                page = render_detail(detail, locale)
                self.assertEqual(page.count('class="terms-section"'), 8)
                for label in TERM_SECTION_LABELS[locale][:-1]:
                    self.assertIn(escape(label), page)
                for clause in clauses:
                    self.assertEqual(page.count(clause["text"]), 1)
                self.assertIn('href="#business-terms-1"', page)
                self.assertIn('id="business-terms-8"', page)

    def test_mixed_and_repeated_sections_keep_every_clause_in_original_order(self):
        clauses = [
            {"label": "First", "text": "Keep original first.", "section": "additional"},
            {"label": "Second", "text": "Keep unclassified second."},
            {"label": "Third", "text": "Keep original third.", "section": "additional"},
            {"label": "Fourth", "text": "Keep fourth.", "section": "additional"}]
        detail = self.project(self.record(clauses))
        page = render_detail(detail)
        offsets = [page.index(clause["text"]) for clause in clauses]
        self.assertEqual(offsets, sorted(offsets))
        self.assertEqual(page.count('class="terms-section"'), 3)
        self.assertIn("Other supplied clauses", page)
        self.assertIn('id="business-terms-3"', page)
        self.assertNotIn('id="business-terms-4"', page)
        self.assertEqual(detail["terms"]["clauses"], clauses)

    def test_unknown_or_identity_bearing_section_is_refused_without_raw_value(self):
        for section in ("owner", "private-owner-name", "0x" + "a" * 40, "", None, [], 1):
            with self.subTest(section=section):
                detail = self.project(self.record([{"label": "Original", "text": "Original obligation",
                                                    "section": section}]))
                self.assertEqual(detail["sourceStatus"], "detail-source-unavailable")
                self.assertEqual(detail["terms"]["clauses"], [])
                self.assertNotIn("private-owner-name", json.dumps(detail))
                self.assertNotIn("0x" + "a" * 40, render_detail(detail))

    def test_categories_cannot_replace_original_coverage_or_source_verification(self):
        record = self.record([{"label": "Specification", "text": "Original goods",
                               "section": "commodity"}])
        denied = self.project(record, lambda *args: False)
        self.assertEqual(denied["terms"]["status"], "unavailable")
        record["businessTerms"]["coverageVerified"] = False
        incomplete = self.project(record)
        self.assertEqual(incomplete["terms"]["status"], "unavailable")
        self.assertNotIn("Original goods", render_detail(incomplete))

    def test_long_multiline_obligations_and_markup_are_escaped_without_shortening(self):
        text = "Whole obligation\n" + ("quality/quantity; " * 200) + "<script>obligation</script>"
        label = 'Original <label> "quoted"'
        detail = self.project(self.record([{"label": label, "text": text, "section": "signed-business-terms"}]))
        page = render_detail(detail)
        self.assertIn(escape(text), page)
        self.assertIn(escape(label, quote=True), page)
        self.assertNotIn("<script>obligation</script>", page)
        self.assertEqual(detail["terms"]["clauses"][0]["text"], text)

    def test_original_private_record_is_unchanged_and_verifier_sees_original_classification(self):
        record = self.record([{"label": "Original", "text": "Preserve this condition.",
                               "section": "revision-history"}])
        before = deepcopy(record)
        seen = []
        def verify(rid, row):
            seen.append(deepcopy(row))
            row["privateOriginal"] = "verifier-local-change"
            return True
        detail = self.project(record, verify)
        self.assertEqual(record, before)
        self.assertEqual(seen, [before])
        public = json.dumps(detail) + render_detail(detail)
        self.assertNotIn("original-private-document", public)
        self.assertNotIn("private-owner-name", public)
        self.assertFalse(detail["ordinaryTransfer"]["gapEqualityFinalityGateApplied"])

    def test_missing_terms_do_not_fabricate_sections_or_default_obligations(self):
        detail = receipt_detail(OriginalReadOnlyDomain(), "r")
        for locale in LOCALES:
            page = render_detail(detail, locale)
            self.assertNotIn('class="terms-section"', page)
            self.assertNotIn('class="terms-navigation"', page)
            self.assertIn(escape(LOCALES[locale][13]), page)
        self.assertEqual(detail["terms"]["clauses"], [])
