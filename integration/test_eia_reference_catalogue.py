"""Synthetic EIA-to-original-catalogue composition; no external requests."""
from datetime import datetime, timezone
from email.message import Message
from unittest.mock import patch
import unittest

from exchange.catalogue_serve import EmptyCatalogueServer
from exchange.eia_reference_catalogue import compose_eia_reference_catalogue
from exchange.eia_wti_spot_table import SCOPE, SOURCE_URL, TITLE
from exchange.reference_catalogue_runtime import serve_reference_catalogue


class Response:
    code = 200
    def __init__(self):
        self.headers = Message()
        self.headers["Content-Type"] = "text/html"

    def geturl(self):
        return SOURCE_URL

    def read(self, limit):
        return (
            '<p>Release Date: 10/15/2026</p><table summary="' + TITLE + '">'
            '<tr><th>Week Of</th><th>Mon</th><th>Tue</th><th>Wed</th>'
            '<th>Thu</th><th>Fri</th></tr>'
            '<tr><td>2026 Oct-12 to Oct-16</td><td>79.00</td><td>80.00</td>'
            '<td>81.25</td><td></td><td></td></tr></table>'
        ).encode()[:limit]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class EIAReferenceCatalogueTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.server = None
        # UTC is an explicit synthetic test policy, not a production calendar.
        self.policy = dict(SCOPE, sourceURL=SOURCE_URL, sourceTimezone="UTC",
                           pollSeconds=60, maxSourceAgeSeconds=864000,
                           maxClockSkewSeconds=0)
        self.options = dict(timeout_seconds=20, user_agent="Synthetic EIA composition",
                            minimum_fetch_seconds=60, failure_backoff_seconds=120,
                            open_response=self.open)

    def tearDown(self):
        if self.server is not None:
            self.server.server_close()
            self.server.reference_feed.close()

    def open(self, request, timeout):
        self.calls.append((request.full_url, timeout))
        return Response()

    def compose(self, **changes):
        values = dict(policy=self.policy, verify_policy=lambda p: p == self.policy,
                      reader_options=self.options,
                      feed_clock=lambda: datetime(2026, 10, 16, tzinfo=timezone.utc),
                      port=0, commit="a" * 40, tree="b" * 40,
                      collateral_selection=True, scenario_selection=True)
        values.update(changes)
        self.server = compose_eia_reference_catalogue(**values)
        return self.server

    def test_original_server_and_no_eager_fetch_or_thread(self):
        server = self.compose()
        self.assertIsInstance(server, EmptyCatalogueServer)
        self.assertEqual(self.calls, [])
        self.assertIsNone(server.reference_feed._thread)
        self.assertEqual(server.reference_feed.snapshot()["status"], "unavailable")

    def test_original_feed_explicit_refresh_preserves_eia_source_evidence(self):
        server = self.compose()
        value = server.reference_feed.refresh()
        self.assertEqual(value["price"], "81.25")
        self.assertEqual(value["sourceAsOf"], "2026-10-14")
        self.assertEqual(value["sourcePrecision"], "date")
        self.assertEqual(value["sourceURL"], SOURCE_URL)
        self.assertEqual(value["sourceEvidence"]["publicationDate"], "2026-10-15")
        self.assertEqual(len(value["sourceEvidence"]["rawResponseSHA256"]), 64)
        self.assertEqual(self.calls, [(SOURCE_URL, 20)])

    def test_unavailable_source_does_not_prevent_original_http_serving(self):
        def fail(request, timeout):
            raise RuntimeError("synthetic source unavailable")
        server = self.compose(reader_options=dict(self.options, open_response=fail))
        self.assertEqual(server.reference_feed.refresh()["status"], "unavailable")
        with patch.object(server.reference_feed, "start") as start, \
             patch.object(server, "serve_forever") as serve, \
             patch.object(server.reference_feed, "close") as close:
            serve_reference_catalogue(server)
            start.assert_called_once()
            serve.assert_called_once()
            close.assert_called_once()

    def test_changed_series_or_source_does_not_bind_a_server(self):
        for changes in ({"currency": "EUR"}, {"sourceURL": "https://example.invalid"},
                        {"series": "PET.RWTC.M"}):
            with patch("exchange.eia_reference_catalogue.compose_reference_catalogue") as bind:
                with self.assertRaises(ValueError):
                    self.compose(policy=dict(self.policy, **changes))
                bind.assert_not_called()
        self.assertEqual(self.calls, [])

    def test_policy_verification_and_calendar_remain_original_feed_inputs(self):
        with self.assertRaises(ValueError):
            self.compose(verify_policy=lambda p: False)
        missing_calendar = dict(self.policy)
        del missing_calendar["sourceTimezone"]
        with self.assertRaises(KeyError):
            self.compose(policy=missing_calendar, verify_policy=lambda p: True)
        self.assertEqual(self.calls, [])

    def test_failed_server_composition_requests_feed_close(self):
        primary = RuntimeError("synthetic bind failed")
        with patch("exchange.eia_reference_catalogue.compose_reference_catalogue",
                   side_effect=primary), \
             patch("exchange.eia_reference_catalogue.CommodityReferenceFeed.close") as close:
            with self.assertRaises(RuntimeError) as raised:
                self.compose()
            self.assertIs(raised.exception, primary)
            close.assert_called_once()
        self.assertEqual(self.calls, [])

    def test_duplicate_feed_and_missing_reader_settings_do_not_fetch(self):
        with self.assertRaises(ValueError):
            self.compose(reference_feed=object())
        with self.assertRaises(TypeError):
            self.compose(reader_options={})
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
