"""Original catalogue composition/lifecycle with synthetic source ports."""
from unittest.mock import patch
import unittest

from exchange.catalogue_serve import EmptyCatalogueServer
from exchange.reference_catalogue_runtime import compose_reference_catalogue, serve_reference_catalogue
from exchange.reference_feed import CommodityReferenceFeed
from exchange.eia_wti_spot_table import SCOPE, SOURCE_URL


class ReferenceCatalogueRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.reads = []
        policy = dict(SCOPE, sourceURL=SOURCE_URL, sourceTimezone="UTC",
                      pollSeconds=30, maxSourceAgeSeconds=86400, maxClockSkewSeconds=0)
        self.feed = CommodityReferenceFeed(policy,
            lambda p: self.reads.append(p), lambda p: p == policy)
        self.server = None

    def tearDown(self):
        if self.server is not None:
            self.server.server_close()
        self.feed.close()

    def compose(self, **options):
        self.server = compose_reference_catalogue(self.feed, port=0,
            commit="a" * 40, tree="b" * 40, **options)
        return self.server

    def test_composition_uses_original_server_without_source_read_or_worker(self):
        server = self.compose(collateral_selection=True, scenario_selection=True)
        self.assertIsInstance(server, EmptyCatalogueServer)
        self.assertIs(server.reference_feed, self.feed)
        self.assertIsNone(self.feed._thread)
        self.assertEqual(self.reads, [])
        self.assertEqual(self.feed.snapshot()["status"], "unavailable")

    def test_explicit_serve_starts_before_http_and_closes_both_resources(self):
        server = self.compose()
        events = []
        close = server.server_close
        def close_server():
            events.append("server-close")
            close()
        with patch.object(self.feed, "start", side_effect=lambda: events.append("feed-start")), \
             patch.object(server, "serve_forever", side_effect=lambda: events.append("serve")), \
             patch.object(server, "server_close", side_effect=close_server), \
             patch.object(self.feed, "close", side_effect=lambda: events.append("feed-close")):
            serve_reference_catalogue(server)
        self.assertEqual(events, ["feed-start", "serve", "server-close", "feed-close"])
        self.assertEqual(self.reads, [])

    def test_serving_error_preserves_failure_and_stops_original_feed(self):
        server = self.compose()
        with patch.object(self.feed, "start"), \
             patch.object(server, "serve_forever", side_effect=RuntimeError("serving failed")), \
             patch.object(self.feed, "close") as close_feed:
            with self.assertRaisesRegex(RuntimeError, "serving failed"):
                serve_reference_catalogue(server)
            close_feed.assert_called_once()
        self.assertEqual(server.fileno(), -1)

    def test_source_start_error_does_not_leak_bound_server(self):
        server = self.compose()
        with patch.object(self.feed, "start", side_effect=RuntimeError("start failed")), \
             patch.object(server, "serve_forever") as serve, \
             patch.object(self.feed, "close") as close_feed:
            with self.assertRaisesRegex(RuntimeError, "start failed"):
                serve_reference_catalogue(server)
            serve.assert_not_called()
            close_feed.assert_called_once()
        self.assertEqual(server.fileno(), -1)

    def test_server_close_error_still_requests_source_stop(self):
        server = self.compose()
        original_close = server.server_close
        def failing_close():
            original_close()
            raise RuntimeError("close failed")
        with patch.object(self.feed, "start"), patch.object(server, "serve_forever"), \
             patch.object(server, "server_close", side_effect=failing_close), \
             patch.object(self.feed, "close") as close_feed:
            with self.assertRaisesRegex(RuntimeError, "close failed"):
                serve_reference_catalogue(server)
            close_feed.assert_called_once()

    def test_foreign_or_missing_feed_refused_without_starting_another_source(self):
        with self.assertRaises(ValueError):
            compose_reference_catalogue(object(), port=0, commit="a" * 40, tree="b" * 40)
        with self.assertRaises(ValueError):
            serve_reference_catalogue(object())
        server = self.compose()
        server.reference_feed = None
        with patch.object(self.feed, "start") as start:
            with self.assertRaises(ValueError):
                serve_reference_catalogue(server)
            start.assert_not_called()
        self.assertEqual(self.reads, [])


if __name__ == "__main__":
    unittest.main()
