"""Date-only observations with an explicitly unknown source calendar."""
from copy import deepcopy
from datetime import datetime, timezone
import unittest

from exchange.eia_wti_spot_table import SCOPE, SOURCE_URL
from exchange.reference_feed import CommodityReferenceFeed
from exchange.reference_provenance_page import render_reference_fields, VALUES


class UnknownCalendarTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
        self.policy = dict(SCOPE, sourceURL=SOURCE_URL, sourceTimezone="unknown",
                           pollSeconds=60, maxSourceAgeSeconds=86400,
                           maxClockSkewSeconds=0)
        self.row = dict(SCOPE, sourceURL=SOURCE_URL, price="81.25",
                        sourceAsOf="2026-10-14", sourcePrecision="date",
                        publicationDate="2026-10-15", rawResponseSHA256="a" * 64)
        self.failure = False
        self.feed = CommodityReferenceFeed(self.policy, self.read,
            lambda p: p == self.policy, clock=lambda: self.now)

    def tearDown(self):
        self.feed.close()

    def read(self, policy):
        if self.failure:
            raise ValueError("synthetic source unavailable")
        return deepcopy(self.row)

    def test_actual_date_and_price_retained_without_zone_or_delay_seconds(self):
        value = self.feed.refresh()
        self.assertEqual(value["price"], "81.25")
        self.assertEqual(value["sourceAsOf"], "2026-10-14")
        self.assertEqual(value["sourcePrecision"], "date")
        self.assertEqual(value["status"], "unknown")
        self.assertIsNone(value["sourceTimezone"])
        self.assertEqual(value["sourceDelay"],
                         {"minimumSeconds": None, "maximumSeconds": None})
        self.assertEqual(value["sourceEvidence"]["publicationDate"], "2026-10-15")

    def test_advancing_fetch_clock_does_not_create_known_freshness(self):
        first = self.feed.refresh()
        self.now = datetime(2026, 11, 16, tzinfo=timezone.utc)
        value = self.feed.snapshot()
        self.assertEqual(value["status"], "unknown")
        self.assertEqual(value["fetchedAt"], first["fetchedAt"])
        self.assertIsNone(value["sourceDelay"]["maximumSeconds"])

    def test_failure_retains_identifiable_value_and_recovery_is_unknown(self):
        first = self.feed.refresh()
        self.failure = True
        failed = self.feed.refresh()
        self.assertEqual(failed["status"], "unavailable")
        self.assertTrue(failed["retainedValue"])
        self.assertEqual(failed["sourceAsOf"], first["sourceAsOf"])
        self.failure = False
        self.assertEqual(self.feed.refresh()["status"], "unknown")

    def test_calendar_never_weakens_series_or_decimal_identity(self):
        for changes in ({"unit": "gallon"}, {"price": "0"},
                        {"sourceAsOf": "2026-02-30"}):
            self.row.update(changes)
            value = self.feed.refresh()
            self.assertEqual(value["status"], "unavailable")
            self.assertIsNone(value["price"])
            self.setUp()

    def test_impossible_future_date_and_publication_order_refused(self):
        for changes in ({"sourceAsOf": "2026-10-18", "publicationDate": "2026-10-18"},
                        {"publicationDate": "2026-10-13"},
                        {"publicationDate": "2026-10-18"}):
            self.row.update(changes)
            self.assertEqual(self.feed.refresh()["status"], "unavailable")
            self.setUp()

    def test_next_civil_day_is_possible_without_inventing_instant(self):
        self.row.update(sourceAsOf="2026-10-17", publicationDate="2026-10-17")
        value = self.feed.refresh()
        self.assertEqual(value["status"], "unknown")
        self.assertEqual(value["sourceAsOf"], "2026-10-17")

    def test_existing_known_calendar_and_timestamp_behavior_retained(self):
        policy = dict(self.policy, sourceTimezone="UTC")
        known = CommodityReferenceFeed(policy, self.read, lambda p: p == policy,
                                       clock=lambda: self.now)
        try:
            value = known.refresh()
            self.assertEqual(value["status"], "stale")
            self.assertIsInstance(value["sourceDelay"]["minimumSeconds"], int)
        finally:
            known.close()
        self.row.update(sourceAsOf="2026-10-16T11:59:00Z", sourcePrecision="instant",
                        publicationDate="2026-10-16")
        value = self.feed.refresh()
        self.assertEqual(value["status"], "fresh")
        self.assertEqual(value["sourceTimezone"], "UTC")
        self.assertEqual(value["sourceDelay"]["minimumSeconds"], 60)

    def test_exact_instant_rejects_next_day_publication_without_civil_grace(self):
        self.row.update(sourceAsOf="2026-10-16T11:59:00Z",
                        sourcePrecision="instant", publicationDate="2026-10-17")
        refused = self.feed.refresh()
        self.assertEqual(refused["status"], "unavailable")
        self.assertIsNone(refused["price"])
        self.row["publicationDate"] = "2026-10-16"
        accepted = self.feed.refresh()
        self.assertEqual(accepted["status"], "fresh")
        self.assertEqual(accepted["sourceTimezone"], "UTC")

    def test_exact_instant_retains_only_explicit_clock_skew_allowance(self):
        self.now = datetime(2026, 10, 16, 23, 59, 50, tzinfo=timezone.utc)
        self.row.update(sourceAsOf="2026-10-16T23:59:40Z",
                        sourcePrecision="instant", publicationDate="2026-10-17")
        for seconds, expected in ((9, "unavailable"), (10, "fresh")):
            policy = dict(self.policy, maxClockSkewSeconds=seconds)
            feed = CommodityReferenceFeed(policy, self.read,
                lambda p: p == policy, clock=lambda: self.now)
            try:
                self.assertEqual(feed.refresh()["status"], expected)
            finally:
                feed.close()

    def test_six_language_fields_render_missing_metadata_without_fake_zero(self):
        value = self.feed.refresh()
        for locale, values in VALUES.items():
            rendered = render_reference_fields(value, locale)
            self.assertIn(values[0], rendered)
            self.assertIn("2026-10-14", rendered)
            self.assertNotIn("None", rendered)
            self.assertNotIn("0 – 0", rendered)


if __name__ == "__main__":
    unittest.main()
