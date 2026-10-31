"""Synthetic source continuation; no live HTTP or financial evidence."""
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import time
import unittest
from exchange.eia_wti_spot_reader import EIAWTISpotReader, SpotSourceDeferred
from exchange.eia_wti_spot_table import SOURCE_URL, SCOPE
from exchange.reference_feed import CommodityReferenceFeed
from exchange.reference_continuation import resume_eia_reference
from integration.test_eia_wti_spot_table import page
from integration.test_eia_wti_spot_reader import Response

class ReferenceContinuation(unittest.TestCase):
    def setUp(self):
        self.time = datetime(2026, 10, 17, tzinfo=timezone.utc)
        self.monotonic = 0
        self.calls = []
        self.raw = page([["2026 Oct-12 to Oct-16", "1.10", "", "", "", ""]])
        self.policy = dict(SCOPE, sourceURL=SOURCE_URL, sourceTimezone="unknown",
                           pollSeconds=20, maxSourceAgeSeconds=86400, maxClockSkewSeconds=0)
        reader, feed = self.ports()
        self.original = feed.refresh()
        self.data = {"schema": "8415ex-eia-reference-continuation/1",
                     "capturedAt": self.time.isoformat().replace("+00:00", "Z"),
                     "sourceResponseBase64": base64.b64encode(self.raw).decode(),
                     "observation": self.original}
        self.time += timedelta(seconds=5)
        self.monotonic += 5

    def ports(self):
        def response(request, timeout):
            self.calls.append(request)
            return Response(self.raw)
        reader = EIAWTISpotReader(timeout_seconds=5, user_agent="Synthetic continuation",
                                 minimum_fetch_seconds=10, failure_backoff_seconds=20,
                                 open_response=response, wall_clock=lambda: self.time.timestamp(),
                                 monotonic=lambda: self.monotonic)
        feed = CommodityReferenceFeed(self.policy, reader, lambda row: row == self.policy,
                                      clock=lambda: self.time,
                                      observe_transport=reader.transport_observation)
        return reader, feed

    def resume(self, data=None):
        reader, feed = self.ports()
        raw = json.dumps(self.data if data is None else data).encode()
        result = resume_eia_reference(feed, reader, self.policy, raw,
                                     hashlib.sha256(raw).hexdigest(), now=self.time)
        return reader, feed, result

    def test_restore_retains_old_value_time_events_without_a_new_request(self):
        reader, feed, result = self.resume()
        restored = feed.snapshot()
        for key in ("price", "sourceAsOf", "fetchedAt", "lastSuccessful", "events", "lastAttemptAt"):
            self.assertEqual(restored[key], self.original[key])
        self.assertEqual(restored["status"], "unknown")
        self.assertTrue(restored["resumedObservation"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result["firstRefreshNotBefore"], "2026-10-17T00:00:20Z")
        with self.assertRaises(SpotSourceDeferred):
            reader(self.policy)
        self.assertEqual(len(self.calls), 1)
        self.assertIsNone(reader.transport_observation())

    def test_background_start_does_not_fetch_before_original_deadline(self):
        reader, feed, _ = self.resume()
        feed.start()
        time.sleep(0.02)
        feed.close()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(feed.snapshot()["events"], self.original["events"])

    def test_normal_due_refresh_is_new_evidence_and_keeps_prior_events(self):
        reader, feed, _ = self.resume()
        self.time += timedelta(seconds=15)
        self.monotonic += 15
        current = feed.refresh()
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(len(current["events"]), 2)
        self.assertEqual(current["events"][0], self.original["events"][0])
        self.assertEqual(current["fetchedAt"], "2026-10-17T00:00:20Z")
        self.assertEqual(current["price"], "1.10")
        self.assertNotIn("resumedObservation", current)

    def test_tampered_missing_or_failed_source_is_refused_before_network(self):
        variants = []
        for key, value in (("price", "900"), ("currency", "EUR"),
                           ("status", "unavailable"), ("retainedValue", True),
                           ("lastSuccessful", "2026-10-16T00:00:00Z")):
            row = deepcopy(self.data)
            row["observation"][key] = value
            variants.append(row)
        row = deepcopy(self.data);row["observation"]["sourceEvidence"]["rawResponseSHA256"] = "0" * 64;variants.append(row)
        row = deepcopy(self.data);row["observation"]["events"][-1]["result"] = "unavailable";variants.append(row)
        row = deepcopy(self.data);row["capturedAt"] = "2026-10-18T00:00:00Z";variants.append(row)
        row = deepcopy(self.data);row["sourceResponseBase64"] = base64.b64encode(b"invalid").decode();variants.append(row)
        for row in variants:
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.resume(row)
        self.assertEqual(len(self.calls), 1)

    def test_digest_and_duplicate_fields_are_refused_and_original_is_unchanged(self):
        before = deepcopy(self.data)
        reader, feed = self.ports()
        raw = json.dumps(self.data).encode()
        with self.assertRaises(ValueError):
            resume_eia_reference(feed, reader, self.policy, raw, "0" * 64, now=self.time)
        duplicate = raw[:-1] + b', "schema": "other"}'
        with self.assertRaises(ValueError):
            resume_eia_reference(feed, reader, self.policy, duplicate,
                                 hashlib.sha256(duplicate).hexdigest(), now=self.time)
        self.assertEqual(self.data, before)
        self.assertEqual(len(self.calls), 1)

    def test_restore_cannot_reset_an_already_used_reader_or_feed(self):
        reader, feed, _ = self.resume()
        raw = json.dumps(self.data).encode()
        with self.assertRaises(ValueError):
            resume_eia_reference(feed, reader, self.policy, raw,
                                 hashlib.sha256(raw).hexdigest(), now=self.time)
        self.assertEqual(feed.snapshot()["events"], self.original["events"])
        self.assertEqual(len(self.calls), 1)

    def test_cli_composition_uses_explicit_digest_and_preserves_cadence(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from exchange.persistent_simulation_serve import configured_reference
        config = {"version": 1, "policy": self.policy,
                  "reader": {"timeout_seconds": 5, "user_agent": "Synthetic continuation",
                             "minimum_fetch_seconds": 10, "failure_backoff_seconds": 20}}
        with TemporaryDirectory() as directory:
            config_raw = json.dumps(config).encode()
            resume_raw = json.dumps(self.data).encode()
            config_file = Path(directory) / "source.json"
            resume_file = Path(directory) / "resume.json"
            config_file.write_bytes(config_raw)
            resume_file.write_bytes(resume_raw)
            feed = configured_reference(config_file, hashlib.sha256(config_raw).hexdigest(),
                                        resume_path=resume_file,
                                        resume_sha256=hashlib.sha256(resume_raw).hexdigest())
            value = feed.snapshot()
            self.assertEqual(value["fetchedAt"], self.original["fetchedAt"])
            self.assertEqual(value["events"], self.original["events"])
            self.assertTrue(value["resumedObservation"])
            self.assertEqual(feed._policy["pollSeconds"], 20)
            self.assertEqual(feed._read._minimum, 10)
            with self.assertRaises(ValueError):
                configured_reference(config_file, hashlib.sha256(config_raw).hexdigest(),
                                     resume_path=resume_file, resume_sha256="0" * 64)
            with self.assertRaises(ValueError):
                configured_reference(None, None, resume_path=resume_file,
                                     resume_sha256=hashlib.sha256(resume_raw).hexdigest())
            feed.close()
