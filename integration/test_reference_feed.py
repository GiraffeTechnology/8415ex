"""Synthetic source contract definitions; no live provider acceptance."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import threading
import unittest
from urllib.request import urlopen
from exchange.reference_feed import CommodityReferenceFeed, SCOPE
from exchange.workbench import RuntimeBinding, WorkbenchServer
from integration.test_nft_detail import OriginalReadOnlyDomain


class ReferenceFeedTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
        self.policy = {"provider": "synthetic-provider", "series": "explicit-spot-series",
            "commodity": "soy", "spec": "original-spec", "market": "original-market",
            "priceType": "spot-reference", "currency": "CNY", "unit": "t",
            "sourceURL": "https://example.invalid/public-series", "sourceTimezone": "UTC",
            "pollSeconds": 1, "maxSourceAgeSeconds": 3600, "maxClockSkewSeconds": 0}
        self.row = {key: self.policy[key] for key in SCOPE}
        self.row.update(price="12.50", sourceAsOf="2026-10-18T11:59:00Z", sourcePrecision="instant")

    def feed(self, read=None, policy=None):
        return CommodityReferenceFeed(policy or self.policy, read or (lambda config: deepcopy(self.row)),
            lambda config: True, clock=lambda: self.now)

    def test_unverified_policy_or_wrong_price_type_never_starts_a_reader(self):
        with self.assertRaises(ValueError):
            CommodityReferenceFeed(self.policy, lambda config: self.fail("must not fetch"), lambda config: False)
        policy = dict(self.policy, priceType="futures")
        with self.assertRaises(ValueError):
            self.feed(policy=policy)

    def test_actual_read_preserves_source_and_fetch_times_and_ages_without_refetch(self):
        feed = self.feed()
        first = feed.refresh()
        self.assertEqual(first["status"], "fresh")
        self.assertEqual(first["price"], "12.50")
        self.assertEqual(first["sourceAsOf"], "2026-10-18T11:59:00Z")
        self.assertEqual(first["fetchedAt"], "2026-10-18T12:00:00Z")
        self.now += timedelta(hours=2)
        self.assertEqual(feed.snapshot()["status"], "stale")
        self.assertEqual(feed.snapshot()["fetchedAt"], first["fetchedAt"])
        self.assertFalse(first["executableOrder"])

    def test_date_precision_is_not_fabricated_into_an_exact_source_instant(self):
        self.row.update(sourceAsOf="2026-10-18", sourcePrecision="date")
        result = self.feed().refresh()
        self.assertEqual(result["sourceAsOf"], "2026-10-18")
        self.assertEqual(result["sourcePrecision"], "date")
        self.assertEqual(result["status"], "unknown")
        self.assertEqual(result["sourceDelay"], {"minimumSeconds": 0, "maximumSeconds": 43200})

    def test_missing_zero_float_and_nondecimal_prices_are_unavailable_not_zero_quotes(self):
        for price in (None, "0", "NaN", "1e5", 12.5):
            with self.subTest(price=price):
                self.row["price"] = price
                result = self.feed().refresh()
                self.assertEqual(result["status"], "unavailable")
                self.assertIsNone(result["price"])

    def test_spec_mismatch_retains_original_value_without_silently_switching_series(self):
        feed = self.feed()
        before = feed.refresh()
        self.row.update(spec="different-grade", price="99.99")
        self.now += timedelta(minutes=1)
        after = feed.refresh()
        self.assertEqual(after["status"], "unavailable")
        self.assertEqual(after["price"], "12.50")
        self.assertEqual(after["lastSuccessful"], before["fetchedAt"])
        self.assertTrue(after["retainedValue"])
        self.assertNotIn("99.99", json.dumps(after))

    def test_failure_and_recovery_do_not_fabricate_zero_or_expose_reader_exception(self):
        def unavailable(config):
            raise OSError("private endpoint credential")
        feed = self.feed(read=unavailable)
        result = feed.refresh()
        self.assertIsNone(result["price"])
        self.assertNotIn("credential", json.dumps(result))
        feed._read = lambda config: deepcopy(self.row)
        self.assertEqual(feed.refresh()["status"], "fresh")
        self.assertEqual(len(feed.snapshot()["events"]), 2)

    def test_workbench_serving_starts_reader_and_exposes_separate_reference_route(self):
        read = threading.Event()
        feed = self.feed(read=lambda config: (read.set(), deepcopy(self.row))[1])
        server = WorkbenchServer(RuntimeBinding(OriginalReadOnlyDomain(), "receipt"),
                                 port=0, reference_feed=feed)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            self.assertTrue(read.wait(timeout=2))
            with urlopen(server.origin + "/api/reference", timeout=2) as response:
                result = json.load(response)
            self.assertEqual(result["kind"], "external-spot-reference")
            self.assertFalse(result["executableOrder"])
            self.assertEqual(result["series"], self.policy["series"])
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)
        self.assertFalse(feed._thread.is_alive())
