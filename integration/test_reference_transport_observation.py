"""Synthetic transport metadata wiring; no external source or runtime acceptance."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import unittest

from exchange.reference_feed import CommodityReferenceFeed, SCOPE
from exchange.eia_reference_catalogue import compose_eia_reference_catalogue
from exchange.eia_wti_spot_table import SCOPE as EIA_SCOPE, SOURCE_URL
from integration.test_eia_reference_catalogue import Response


class ReferenceTransportObservationTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 16, tzinfo=timezone.utc)
        self.policy = dict(provider="synthetic", series="fixed", commodity="oil",
            spec="WTI", market="synthetic", priceType="spot-reference", currency="USD",
            unit="barrel", sourceURL="https://example.invalid/series", sourceTimezone="UTC",
            pollSeconds=60, maxSourceAgeSeconds=864000, maxClockSkewSeconds=0)
        self.row = {key: self.policy[key] for key in SCOPE}
        self.row.update(price="81.25", sourceAsOf="2026-10-15T12:00:00Z",
                        sourcePrecision="instant")
        self.transport = {"status": "read", "httpStatus": 200, "bytes": 128,
                          "rawResponseSHA256": "a" * 64}
        self.reads, self.observations = 0, 0

    def read(self, policy):
        self.reads += 1
        return deepcopy(self.row)

    def observe(self):
        self.observations += 1
        return self.transport

    def feed(self, **changes):
        options = dict(clock=lambda: self.now, observe_transport=self.observe)
        options.update(changes)
        return CommodityReferenceFeed(self.policy, self.read, lambda policy: True, **options)

    def test_no_eager_observation_and_snapshots_never_read_or_poll(self):
        feed = self.feed()
        self.assertIsNone(feed.snapshot()["transportObservation"]["value"])
        self.assertEqual((self.reads, self.observations), (0, 0))
        value = feed.refresh()
        for _ in range(5):
            feed.snapshot()
        self.assertEqual((self.reads, self.observations), (1, 1))
        self.assertEqual(value["transportObservation"]["value"], self.transport)
        self.assertEqual(value["transportObservation"]["attemptCorrelation"], "NOT_ESTABLISHED")
        self.assertFalse(value["executableOrder"])

    def test_observer_failure_keeps_valid_price_and_hides_exception(self):
        def fail():
            raise OSError("private cookie server path")
        value = self.feed(observe_transport=fail).refresh()
        self.assertEqual(value["price"], "81.25")
        self.assertEqual(value["status"], "fresh")
        self.assertEqual(value["transportObservation"]["value"], {"status": "diagnostic-unavailable"})
        self.assertNotIn("private", json.dumps(value))
        self.assertNotIn("cookie", json.dumps(value))
        self.assertEqual(self.reads, 1)

    def test_unsafe_unknown_or_oversized_transport_metadata_never_leaks(self):
        cases = [
            dict(self.transport, headers={"Authorization": "private-secret"}),
            {"status": "unavailable", "code": "private-secret", "retainedSource": False},
            dict(self.transport, bytes=2 * 1024 * 1024 + 1),
            dict(self.transport, httpStatus=True),
            dict(self.transport, rawResponseSHA256="https://private-secret"),
            ["private-secret"],
        ]
        for diagnostic in cases:
            with self.subTest(diagnostic=repr(diagnostic)):
                self.transport = diagnostic
                value = self.feed().refresh()
                self.assertEqual(value["transportObservation"]["value"],
                                 {"status": "diagnostic-unavailable"})
                self.assertEqual(value["price"], "81.25")
                self.assertNotIn("private-secret", json.dumps(value))

    def test_transport_read_success_is_not_valid_price_or_current_attempt_proof(self):
        self.row["price"] = "0"
        value = self.feed().refresh()
        self.assertEqual(value["status"], "unavailable")
        self.assertIsNone(value["price"])
        self.assertEqual(value["transportObservation"]["value"]["httpStatus"], 200)
        self.assertEqual(value["transportObservation"]["attemptCorrelation"], "NOT_ESTABLISHED")

    def test_retained_value_and_transport_failure_stay_separate_and_detached(self):
        feed = self.feed()
        original = feed.refresh()
        self.transport = {"status": "unavailable", "code": "SPOT_SOURCE_HTTP_DEFERRED",
                          "retainedSource": True}
        def fail(policy):
            self.reads += 1
            raise OSError("private endpoint")
        feed._read = fail
        value = feed.refresh()
        self.assertEqual(value["status"], "unavailable")
        self.assertEqual(value["price"], original["price"])
        self.assertEqual(value["lastSuccessful"], original["fetchedAt"])
        self.assertTrue(value["retainedValue"])
        self.transport["code"] = "private-secret"
        self.assertEqual(value["transportObservation"]["value"]["code"], "SPOT_SOURCE_HTTP_DEFERRED")
        value["transportObservation"]["value"]["retainedSource"] = False
        self.assertTrue(feed.snapshot()["transportObservation"]["value"]["retainedSource"])
        self.assertEqual((self.reads, self.observations), (2, 2))

    def test_not_modified_does_not_invent_publication_or_replace_source_time(self):
        self.transport = {"status": "not-modified", "httpStatus": 304,
                          "rawResponseSHA256": "b" * 64}
        value = self.feed().refresh()
        self.assertEqual(value["sourceAsOf"], self.row["sourceAsOf"])
        self.assertEqual(value["transportObservation"]["value"], self.transport)
        self.assertNotIn("publicationDate", value)
        self.assertEqual(self.reads, 1)

    def test_opt_in_only_and_invalid_port_refuses_without_fetch(self):
        plain = CommodityReferenceFeed(self.policy, self.read, lambda policy: True,
                                       clock=lambda: self.now)
        self.assertNotIn("transportObservation", plain.snapshot())
        self.assertNotIn("transportObservation", plain.refresh())
        before = self.reads
        for port in ("configured", False, 0, {}, []):
            with self.subTest(port=repr(port)), self.assertRaises(ValueError):
                self.feed(observe_transport=port)
        self.assertEqual(self.reads, before)

    def test_existing_eia_composition_captures_original_reader_without_extra_request(self):
        calls = []
        def original(request, timeout):
            calls.append(request.full_url)
            return Response()
        policy = dict(EIA_SCOPE, sourceURL=SOURCE_URL, sourceTimezone="UTC",
                      pollSeconds=60, maxSourceAgeSeconds=864000, maxClockSkewSeconds=0)
        server = compose_eia_reference_catalogue(policy=policy,
            verify_policy=lambda value: value == policy,
            reader_options=dict(timeout_seconds=20, user_agent="synthetic observation",
                minimum_fetch_seconds=60, failure_backoff_seconds=120,
                open_response=original),
            feed_clock=lambda: self.now, port=0, commit="a" * 40, tree="b" * 40)
        try:
            self.assertEqual(calls, [])
            first = server.reference_feed.refresh()
            self.assertEqual(first["price"], "81.25")
            self.assertEqual(first["transportObservation"]["value"]["httpStatus"], 200)
            self.assertEqual(first["sourceEvidence"]["rawResponseSHA256"],
                             first["transportObservation"]["value"]["rawResponseSHA256"])
            # A feed-level refresh before original reader spacing must not make
            # another source request. Its retained metadata may describe the
            # previous read, so no current-attempt correlation is claimed.
            second = server.reference_feed.refresh()
            self.assertEqual(second["status"], "unavailable")
            self.assertTrue(second["retainedValue"])
            self.assertEqual(second["transportObservation"]["attemptCorrelation"], "NOT_ESTABLISHED")
            for _ in range(3):
                server.reference_feed.snapshot()
            self.assertEqual(calls, [SOURCE_URL])
        finally:
            server.server_close()
            server.reference_feed.close()


if __name__ == "__main__":
    unittest.main()
