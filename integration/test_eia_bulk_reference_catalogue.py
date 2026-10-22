"""Synthetic explicit bulk lifecycle/attribution contracts; no live source."""
from copy import deepcopy
from datetime import datetime, timezone
from email.message import Message
import io
import json
import unittest
from unittest.mock import patch
import zipfile

from exchange.catalogue_serve import EmptyCatalogueServer
from exchange.eia_bulk_reference_catalogue import compose_eia_bulk_reference_catalogue
from exchange.eia_wti_bulk_reader import MANIFEST_URL
from exchange.eia_wti_bulk_series import BULK_URL
from exchange.eia_wti_spot_table import SCOPE, SOURCE_URL
from exchange.reference_catalogue_runtime import serve_reference_catalogue


class Response:
    code = 200
    def __init__(self, url, raw, kind):
        self.url, self.raw = url, raw
        self.headers = Message()
        self.headers["Content-Type"] = kind
    def geturl(self):
        return self.url
    def read(self, limit):
        return self.raw[:limit]
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False


class EIABulkCatalogueContracts(unittest.TestCase):
    def setUp(self):
        self.now, self.calls, self.queue, self.server = 100, [], [], None
        self.policy = dict(SCOPE, sourceURL=BULK_URL, sourceTimezone="unknown",
                           pollSeconds=60, maxSourceAgeSeconds=864000,
                           maxClockSkewSeconds=0)
        self.options = dict(timeout_seconds=20, user_agent="Synthetic bulk composition",
            minimum_fetch_seconds=60, failure_backoff_seconds=120,
            open_response=self.open, monotonic=lambda: self.now, wall_clock=lambda: 1000)

    def tearDown(self):
        if self.server is not None:
            self.server.server_close()
            self.server.reference_feed.close()

    def open(self, request, timeout):
        self.calls.append((request.full_url, timeout))
        return self.queue.pop(0)

    def manifest(self, changed=False):
        item = dict(identifier="PET", data_set="PET", accessURL=BULK_URL,
                    accessLevel="public", last_updated="2026-10-15T19:00:00-04:00")
        if changed:
            item["title"] = "Synthetic changed distribution"
        return Response(MANIFEST_URL, json.dumps({"dataset": {"PET": item}}).encode(),
                        "text/plain")

    def archive(self):
        row = dict(series_id="PET.RWTC.D", f="D",
            name="Cushing, OK WTI Spot Price FOB, Daily", units="Dollars per Barrel",
            unitsshort="$/bbl", geography="USA-OK", iso3166="USA-OK",
            source="Synthetic upstream", copyright="Synthetic attribution",
            last_updated="2026-10-15T18:43:40-04:00",
            start="20261014", end="20261014", data=[["20261014", 81.25]])
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("PET.txt", json.dumps(row) + "\n")
        return Response(BULK_URL, buffer.getvalue(), "application/zip")

    def compose(self, **changes):
        args = dict(policy=self.policy, verify_policy=lambda p: p == self.policy,
                    reader_options=self.options,
                    feed_clock=lambda: datetime(2026, 10, 16, tzinfo=timezone.utc),
                    port=0, commit="a"*40, tree="b"*40)
        args.update(changes)
        self.server = compose_eia_bulk_reference_catalogue(**args)
        return self.server

    def initial(self):
        self.queue.extend([self.manifest(), self.archive()])
        return self.server.reference_feed.refresh()

    def test_original_server_has_no_eager_fetch_or_worker(self):
        server = self.compose()
        self.assertIsInstance(server, EmptyCatalogueServer)
        self.assertEqual(self.calls, [])
        self.assertIsNone(server.reference_feed._thread)
        self.assertEqual(server.reference_feed.snapshot()["status"], "unavailable")

    def test_complete_archive_attribution_and_date_precision_survive_feed(self):
        self.compose()
        value = self.initial()
        self.assertEqual(value["price"], "81.25")
        self.assertEqual(value["sourceURL"], BULK_URL)
        self.assertEqual(value["sourceAsOf"], "2026-10-14")
        self.assertEqual(value["sourcePrecision"], "date")
        self.assertIsNone(value["sourceTimezone"])
        self.assertEqual(value["status"], "unknown")
        evidence = value["sourceEvidence"]
        bulk = evidence["bulkSource"]
        self.assertEqual(evidence["rawResponseSHA256"], bulk["sha256"])
        self.assertNotEqual(bulk["selectedLineSHA256"], bulk["sha256"])
        self.assertEqual(bulk["upstreamSource"], "Synthetic upstream")
        self.assertEqual(bulk["sourceCopyright"], "Synthetic attribution")
        self.assertNotEqual(bulk["sourceUpdatedAt"], bulk["datasetUpdatedAt"])
        self.assertNotIn("publicationDate", evidence)
        self.assertEqual(self.calls, [(MANIFEST_URL, 20), (BULK_URL, 20)])

    def test_unchanged_manifest_retains_evidence_without_archive_redownload(self):
        server = self.compose()
        first = self.initial()
        first["sourceEvidence"]["bulkSource"]["sourceCopyright"] = "mutated view"
        self.now += 60
        self.queue.append(self.manifest())
        current = server.reference_feed.refresh()
        self.assertEqual(len(self.calls), 3)
        self.assertEqual(current["sourceEvidence"]["bulkSource"]["sourceCopyright"],
                         "Synthetic attribution")
        reader = server.reference_feed._bulk_reader
        copied = reader.cached_source_evidence()
        copied["sourceCopyright"] = "mutated cache copy"
        self.assertEqual(reader.cached_source_evidence()["sourceCopyright"], "Synthetic attribution")

    def test_failed_changed_archive_retains_old_correlated_attribution(self):
        server = self.compose()
        first = self.initial()
        self.now += 60
        self.queue.extend([self.manifest(True), Response(BULK_URL, b"broken", "application/zip")])
        value = server.reference_feed.refresh()
        self.assertEqual(value["status"], "unavailable")
        self.assertTrue(value["retainedValue"])
        self.assertEqual(value["price"], first["price"])
        self.assertEqual(value["sourceEvidence"], first["sourceEvidence"])
        calls = list(self.calls)
        server.reference_feed.snapshot()
        self.assertEqual(self.calls, calls)

    def test_mismatched_evidence_cannot_label_retained_price_as_fresh(self):
        server = self.compose()
        self.initial()
        reader = server.reference_feed._bulk_reader
        wrong = deepcopy(reader.cached_source_evidence())
        wrong["sha256"] = "f"*64
        with patch.object(reader, "cached_source_evidence", return_value=wrong):
            value = server.reference_feed.snapshot()
        self.assertEqual(value["status"], "unavailable")
        self.assertEqual(value["sourceAttributionStatus"], "unavailable")
        self.assertNotIn("bulkSource", value["sourceEvidence"])
        self.assertEqual(len(self.calls), 2)

    def test_source_selection_never_falls_back_or_accepts_duplicate_feed(self):
        target = "exchange.eia_bulk_reference_catalogue.compose_reference_catalogue"
        for policy in (dict(self.policy, sourceURL=SOURCE_URL),
                       dict(self.policy, series="PET.RWTC.M")):
            with patch(target) as bind, self.assertRaises(ValueError):
                self.compose(policy=policy)
            bind.assert_not_called()
        with patch(target) as bind, self.assertRaises(ValueError):
            self.compose(reference_feed=object())
        bind.assert_not_called()
        self.assertEqual(self.calls, [])

    def test_source_failure_and_original_serving_lifecycle_remain_separate(self):
        server = self.compose()
        self.queue.extend([Response(MANIFEST_URL, b"broken", "text/plain")])
        self.assertEqual(server.reference_feed.refresh()["status"], "unavailable")
        with patch.object(server.reference_feed, "start") as start, \
             patch.object(server, "serve_forever") as serve, \
             patch.object(server.reference_feed, "close") as close:
            serve_reference_catalogue(server)
        start.assert_called_once()
        serve.assert_called_once()
        close.assert_called_once()

    def test_bind_cleanup_and_explicit_clock_contract_are_preserved(self):
        target = "exchange.eia_bulk_reference_catalogue"
        primary = RuntimeError("synthetic bind failure")
        with patch(target+".compose_reference_catalogue", side_effect=primary), \
             patch(target+".EIABulkReferenceFeed.close") as close:
            with self.assertRaises(RuntimeError) as raised:
                self.compose()
            self.assertIs(raised.exception, primary)
        close.assert_called_once()
        for clock in (False, 0, "clock"):
            with self.assertRaises(ValueError):
                self.compose(feed_clock=clock)
        class Clock:
            def __bool__(self):
                return False
            def __call__(self):
                return datetime(2026, 10, 16, tzinfo=timezone.utc)
        server = self.compose(feed_clock=Clock())
        self.initial()
        self.assertEqual(server.reference_feed.snapshot()["fetchedAt"], "2026-10-16T00:00:00Z")
