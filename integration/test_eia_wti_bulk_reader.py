"""Synthetic transport contract definitions; no actual network requests."""
from email.message import Message
import io
import json
import unittest
import zipfile

from exchange.eia_wti_bulk_reader import EIAWTIBulkReader, MANIFEST_URL
from exchange.eia_wti_bulk_series import BULK_URL
from exchange.eia_wti_spot_reader import SpotSourceDeferred, SpotSourceUnavailable
from exchange.eia_wti_spot_table import SCOPE


class Response:
    def __init__(self, url, raw, kind, code=200, retry=None):
        self.url, self.raw, self.code = url, raw, code
        self.headers = Message()
        self.headers["Content-Type"] = kind
        if retry is not None:
            self.headers["Retry-After"] = retry

    def geturl(self):
        return self.url

    def read(self, count):
        return self.raw[:count]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class BulkReaderTests(unittest.TestCase):
    def setUp(self):
        self.now = 100
        self.queue, self.calls = [], []
        self.reader = EIAWTIBulkReader(
            timeout_seconds=20, user_agent="Synthetic source reader",
            minimum_fetch_seconds=60, failure_backoff_seconds=120,
            open_response=self.open, monotonic=lambda: self.now,
            wall_clock=lambda: 1000)
        self.policy = dict(SCOPE, sourceURL=BULK_URL)

    def open(self, request, timeout):
        self.calls.append((request.full_url, dict(request.header_items()), timeout))
        return self.queue.pop(0)

    def manifest(self, stamp="2026-10-15T18:43:40-04:00", **changes):
        item = dict(identifier="PET", data_set="PET", accessURL=BULK_URL,
                    accessLevel="public", last_updated=stamp)
        item.update(changes)
        return Response(MANIFEST_URL, json.dumps({"dataset": {"PET": item}}).encode(),
                        "text/plain")

    def archive(self):
        row = dict(series_id="PET.RWTC.D", f="D",
                   name="Cushing, OK WTI Spot Price FOB, Daily",
                   units="Dollars per Barrel", unitsshort="$/bbl",
                   geography="USA-OK", iso3166="USA-OK",
                   source="Synthetic source", copyright="Synthetic rights",
                   last_updated="2026-10-15T18:43:40-04:00",
                   start="20261014", end="20261014", data=[["20261014", 81.25]])
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
            info = zipfile.ZipInfo("PET.txt", (2026, 10, 15, 0, 0, 0))
            archive.writestr(info, json.dumps(row) + "\n", compress_type=zipfile.ZIP_DEFLATED)
        return Response(BULK_URL, out.getvalue(), "application/x-zip-compressed")

    def initial(self):
        self.queue.extend([self.manifest(), self.archive()])
        return self.reader(self.policy)

    def test_no_requests_before_explicit_read_and_fixed_request_order(self):
        self.assertEqual(self.calls, [])
        row = self.initial()
        self.assertEqual([x[0] for x in self.calls], [MANIFEST_URL, BULK_URL])
        self.assertEqual(row["price"], "81.25")
        self.assertNotIn("publicationDate", row)
        evidence = self.reader.transport_observation()["bulkEvidence"]
        self.assertEqual(row["rawResponseSHA256"], evidence["sha256"])
        self.assertNotEqual(row["rawResponseSHA256"], evidence["selectedLineSHA256"])
        self.assertEqual(row["responseDigestScope"], "complete-petroleum-archive")
        self.assertTrue(self.reader.transport_observation()["archiveDownloaded"])

    def test_unchanged_manifest_avoids_archive_and_preserves_observation(self):
        old = self.initial()
        self.now += 60
        self.queue.append(self.manifest())
        current = self.reader(self.policy)
        self.assertEqual(old, current)
        self.assertEqual(len(self.calls), 3)
        self.assertFalse(self.reader.transport_observation()["archiveDownloaded"])
        current["price"] = "999"
        self.now += 60
        self.queue.append(self.manifest())
        self.assertEqual(self.reader(self.policy)["price"], "81.25")

    def test_changed_petroleum_metadata_requires_full_archive(self):
        self.initial()
        self.now += 60
        self.queue.extend([self.manifest(title="Petroleum revised"), self.archive()])
        self.reader(self.policy)
        self.assertEqual(len(self.calls), 4)
        self.assertTrue(self.reader.transport_observation()["archiveDownloaded"])

    def test_spacing_and_provider_backoff(self):
        self.queue.append(Response(MANIFEST_URL, b"", "text/plain", 503, "600"))
        with self.assertRaises(SpotSourceUnavailable):
            self.reader(self.policy)
        self.now += 599
        with self.assertRaises(SpotSourceDeferred):
            self.reader(self.policy)
        self.assertEqual(len(self.calls), 1)

    def test_changed_archive_failure_does_not_replace_cache_or_marker(self):
        old = self.initial()
        self.now += 60
        changed = "2026-10-16T18:43:40-04:00"
        self.queue.extend([self.manifest(changed),
                           Response(BULK_URL, b"broken", "application/zip")])
        with self.assertRaises(SpotSourceUnavailable):
            self.reader(self.policy)
        self.assertTrue(self.reader.transport_observation()["retainedSource"])
        self.now += 120
        self.queue.extend([self.manifest(changed), self.archive()])
        self.assertEqual(self.reader(self.policy), old)
        self.assertEqual(len(self.calls), 6)

    def test_wrong_distribution_and_missing_update_offset(self):
        for changes in ({"accessURL": "https://example.invalid/PET.zip"},
                        {"accessLevel": "private"}, {"identifier": "NG"},
                        {"last_updated": "2026-10-15T18:43:40"}):
            with self.subTest(changes=changes):
                self.setUp()
                self.queue.append(self.manifest(**changes))
                with self.assertRaises(SpotSourceUnavailable):
                    self.reader(self.policy)
                self.assertEqual(len(self.calls), 1)

    def test_redirect_mime_and_manifest_bound(self):
        for response in (Response("https://example.invalid", b"{}", "text/plain"),
                         Response(MANIFEST_URL, b"<html>", "text/html"),
                         Response(MANIFEST_URL, b"x" * (256 * 1024 + 1), "text/plain")):
            self.setUp()
            self.queue.append(response)
            with self.assertRaises(SpotSourceUnavailable):
                self.reader(self.policy)
            self.assertEqual(len(self.calls), 1)

    def test_policy_mismatch_does_not_contact_source(self):
        for policy in (dict(self.policy, sourceURL=MANIFEST_URL),
                       dict(self.policy, currency="EUR")):
            with self.assertRaises(SpotSourceUnavailable):
                self.reader(policy)
        self.assertEqual(self.calls, [])

    def test_error_details_are_sanitized(self):
        def failing(request, timeout):
            raise RuntimeError("synthetic-private-detail")
        self.reader._open = failing
        with self.assertRaises(SpotSourceUnavailable) as raised:
            self.reader(self.policy)
        self.assertNotIn("synthetic-private-detail", str(raised.exception))
        self.assertNotIn("synthetic-private-detail", str(self.reader.transport_observation()))


if __name__ == "__main__":
    unittest.main()
