"""Optional source evidence survives existing feed and six-language display."""
from datetime import datetime, timezone
import unittest

from exchange.reference_feed import CommodityReferenceFeed
from exchange.reference_provenance_page import EVIDENCE_LABELS, VALUES, render_reference_fields
from exchange.eia_wti_spot_table import SCOPE, SOURCE_URL
from exchange.eia_wti_spot_reader import EIAWTISpotReader
from integration.test_eia_wti_spot_reader import Response
from integration.test_eia_wti_spot_table import page


class ReferenceSourceEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 20, tzinfo=timezone.utc)
        self.policy = dict(SCOPE, sourceURL=SOURCE_URL, sourceTimezone="UTC",
                           pollSeconds=30, maxSourceAgeSeconds=7 * 86400,
                           maxClockSkewSeconds=0)
        self.row = dict(SCOPE, price="1.20", sourceAsOf="2026-10-14",
                        sourcePrecision="date", publicationDate="2026-10-15",
                        sourceURL=SOURCE_URL, rawResponseSHA256="a" * 64)
        self.reads = []

    def feed(self, rows):
        values = list(rows)
        def read(policy):
            self.reads.append(policy)
            return values.pop(0)
        return CommodityReferenceFeed(self.policy, read, lambda p: p == self.policy,
                                      clock=lambda: self.now)

    def test_existing_snapshot_preserves_detached_source_evidence(self):
        feed = self.feed([self.row])
        value = feed.refresh()
        self.assertEqual(value["sourceEvidence"],
                         {"publicationDate": "2026-10-15", "rawResponseSHA256": "a" * 64})
        self.assertEqual(value["sourceAsOf"], "2026-10-14")
        self.assertEqual(value["sourcePrecision"], "date")
        value["sourceEvidence"]["publicationDate"] = "1900-01-01"
        self.row["rawResponseSHA256"] = "b" * 64
        self.assertEqual(feed.snapshot()["sourceEvidence"]["rawResponseSHA256"], "a" * 64)

    def test_old_reader_without_evidence_keeps_existing_contract(self):
        row = {key: value for key, value in self.row.items()
               if key not in ("publicationDate", "rawResponseSHA256", "sourceURL")}
        value = self.feed([row]).refresh()
        self.assertEqual(value["price"], "1.20")
        self.assertNotIn("sourceEvidence", value)
        for locale, labels in EVIDENCE_LABELS.items():
            rendered = render_reference_fields(value, locale)
            self.assertIn(labels[0], rendered)
            self.assertIn(VALUES[locale][0], rendered)

    def test_digest_failure_retains_previous_provenance_and_marks_unavailable(self):
        changed = dict(self.row, rawResponseSHA256="BAD")
        feed = self.feed([self.row, changed])
        feed.refresh()
        self.now = datetime(2026, 10, 20, 1, tzinfo=timezone.utc)
        value = feed.refresh()
        self.assertEqual(value["status"], "unavailable")
        self.assertTrue(value["retainedValue"])
        self.assertEqual(value["sourceEvidence"]["rawResponseSHA256"], "a" * 64)

    def test_publication_is_a_real_date_not_before_the_source_observation(self):
        for publication in ("2026-02-30", "2026-10-13", "2026-10-15T00:00:00Z", 123):
            with self.subTest(publication=publication):
                value = self.feed([dict(self.row, publicationDate=publication)]).refresh()
                self.assertEqual(value["status"], "unavailable")
                self.assertIsNone(value["price"])

    def test_optional_response_url_must_match_original_policy(self):
        value = self.feed([dict(self.row, sourceURL="https://example.invalid/other")]).refresh()
        self.assertEqual(value["status"], "unavailable")
        self.assertIsNone(value["lastSuccessful"])

    def test_both_evidence_values_visible_in_every_supported_locale(self):
        value = self.feed([self.row]).refresh()
        for locale, labels in EVIDENCE_LABELS.items():
            with self.subTest(locale=locale):
                rendered = render_reference_fields(value, locale)
                self.assertIn(labels[0], rendered)
                self.assertIn(labels[1], rendered)
                self.assertIn("2026-10-15", rendered)
                self.assertIn("a" * 64, rendered)

    def test_provenance_does_not_dump_nested_private_fields_or_unvalidated_hash(self):
        value = {"sourceEvidence": {"publicationDate": "2026-02-30",
                 "rawResponseSHA256": "<script>bad</script>", "privateField": "secret-sentinel"}}
        rendered = render_reference_fields(value)
        self.assertNotIn("secret-sentinel", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("2026-02-30", rendered)

    def test_conditional_read_preserves_source_evidence_with_new_fetch_time(self):
        responses = [Response(page([
            ["2026 Oct-12 to Oct-16", "1.20", "", "", "", ""],
        ]), headers={"ETag": '"one"'}), Response(code=304)]
        ticks = [0]
        reader = EIAWTISpotReader(timeout_seconds=7, user_agent="EX-evidence-test",
            minimum_fetch_seconds=10, failure_backoff_seconds=20,
            open_response=lambda request, timeout: responses.pop(0),
            monotonic=lambda: ticks[0])
        feed = CommodityReferenceFeed(self.policy, reader, lambda p: p == self.policy,
                                      clock=lambda: self.now)
        first = feed.refresh()
        ticks[0] = 30
        self.now = datetime(2026, 10, 20, 1, tzinfo=timezone.utc)
        second = feed.refresh()
        self.assertEqual(first["sourceEvidence"], second["sourceEvidence"])
        self.assertEqual(first["sourceAsOf"], second["sourceAsOf"])
        self.assertNotEqual(first["fetchedAt"], second["fetchedAt"])
        self.assertFalse(second["executableOrder"])


if __name__ == "__main__":
    unittest.main()
