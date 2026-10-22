"""Read-only market refresh contracts over the original HTTP server."""
from datetime import datetime, timezone
from email.message import Message
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import build_opener, ProxyHandler, Request

from exchange.catalogue_serve import EmptyCatalogueServer
from exchange.eia_wti_spot_table import SCOPE, SOURCE_URL
from exchange.market_page import REFRESH_FAILURE
from exchange.market_reference_refresh import MARKET_CSP, SCRIPT_HASH
from exchange.reference_feed import CommodityReferenceFeed


class MarketReferenceRefreshTests(unittest.TestCase):
    def setUp(self):
        self.reads = 0
        self.row = dict(SCOPE, price="81.25", sourceAsOf="2026-10-20",
                        sourcePrecision="date")
        policy = dict(SCOPE, sourceURL=SOURCE_URL, sourceTimezone="UTC",
                      pollSeconds=60, maxSourceAgeSeconds=864000,
                      maxClockSkewSeconds=0)
        self.feed = CommodityReferenceFeed(policy, self.read, lambda p: p == policy,
            clock=lambda: datetime(2026, 10, 21, tzinfo=timezone.utc))
        self.feed.refresh()
        self.server = EmptyCatalogueServer(port=0, commit="a" * 40,
                                          tree="b" * 40, reference_feed=self.feed)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.open = build_opener(ProxyHandler({})).open

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)
        self.feed.close()

    def read(self, policy):
        self.reads += 1
        return dict(self.row)

    def get(self, path):
        try:
            response = self.open(self.server.origin + path, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.code, response.headers, response.read().decode()

    def test_market_document_enables_only_exact_refresh_script(self):
        code, headers, body = self.get("/market?lang=en")
        self.assertEqual(code, 200)
        self.assertEqual(headers.get_all("Content-Security-Policy"), [MARKET_CSP])
        self.assertIn("script-src 'sha256-" + SCRIPT_HASH + "'", MARKET_CSP)
        self.assertNotIn("script-src 'unsafe-inline'", MARKET_CSP)
        self.assertIn('id="commodity-reference"', body)
        self.assertEqual(body.count("<script>"), 1)
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_fragment_updates_original_observation_without_nft_or_script_markup(self):
        self.row["price"] = "82.00"
        self.feed.refresh()
        code, headers, body = self.get("/market?lang=en&q=soy&reference=1")
        self.assertEqual(code, 200)
        self.assertTrue(body.startswith('<section id="commodity-reference"'))
        self.assertIn("82.00", body)
        self.assertNotIn("<script", body)
        self.assertNotIn("nft-grid", body)
        self.assertNotIn("<form", body)
        self.assertNotIn("script-src", headers["Content-Security-Policy"])

    def test_six_language_fragment_failure_labels(self):
        from urllib.parse import urlencode
        for locale, failure in REFRESH_FAILURE.items():
            code, _, body = self.get("/market?" + urlencode(
                {"lang": locale, "reference": "1"}))
            self.assertEqual(code, 200)
            self.assertIn(failure, body)
            self.assertIn("data-browser-error hidden", body)

    def test_duplicate_invalid_or_foreign_fragment_queries_refused(self):
        for path in ("/market?reference=2", "/market?reference=1&reference=1",
                     "/market?reference=1&lang=xx", "/api/catalogue?reference=1",
                     "/market?reference=1&extra=1"):
            self.assertEqual(self.get(path)[0], 400)

    def test_original_catalogue_and_reference_json_remain_json(self):
        for path in ("/api/catalogue?lang=en", "/api/reference"):
            code, headers, body = self.get(path)
            self.assertEqual(code, 200)
            self.assertTrue(headers["Content-Type"].startswith("application/json"))
            self.assertIsInstance(json.loads(body), dict)
            self.assertNotIn("script-src", headers["Content-Security-Policy"])

    def test_browser_snapshot_reads_do_not_poll_external_provider(self):
        before = self.reads
        self.get("/market?reference=1")
        self.get("/market?reference=1")
        self.assertEqual(self.reads, before)
        self.assertIsNone(self.feed._thread)

    def test_source_values_remain_escaped_in_fragment(self):
        self.feed._last["provider"] = '<img src=x onerror="bad()">'
        _, _, body = self.get("/market?reference=1")
        self.assertNotIn("<img", body)
        self.assertIn("&lt;img", body)

    def test_health_policy_is_not_widened_for_market_script(self):
        code, headers, _ = self.get("/healthz")
        self.assertEqual(code, 200)
        self.assertNotIn("script-src", headers["Content-Security-Policy"])
        self.assertNotIn("connect-src", headers["Content-Security-Policy"])

    def test_refresh_query_cannot_dispatch_a_post(self):
        request = Request(self.server.origin + "/market?reference=1",
                          data=b"{}", method="POST")
        with self.assertRaises(HTTPError) as raised:
            self.open(request, timeout=5)
        self.assertEqual(raised.exception.code, 405)

    def test_search_text_is_not_embedded_in_executable_source(self):
        from urllib.parse import urlencode
        code, _, body = self.get("/market?" + urlencode(
            {"lang": "en", "q": '</script><img src=x onerror="bad()">'}))
        self.assertEqual(code, 200)
        script = body.split("<script>", 1)[1].split("</script>", 1)[0]
        self.assertNotIn("onerror", script)
        self.assertIn("&lt;/script&gt;", body)



class WorkbenchReferenceIsolationTests(unittest.TestCase):
    def test_fragment_never_reads_nft_catalogue_but_catalogue_still_does(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from exchange.workbench import WorkbenchServer
        detail = Mock(side_effect=AssertionError("NFT source must not be read by a reference refresh"))
        binding = SimpleNamespace(receipt_id="refresh-fixture", run={}, gateway=None,
                                  public_detail=detail)
        server = WorkbenchServer(binding, port=0, commit="a" * 40, tree="b" * 40)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        opener = build_opener(ProxyHandler({})).open
        try:
            with opener(server.origin + "/market?reference=1", timeout=5) as response:
                self.assertEqual(response.code, 200)
                self.assertIn(b'commodity-reference', response.read())
            detail.assert_not_called()
            with opener(server.origin + "/api/catalogue", timeout=5) as response:
                self.assertEqual(response.code, 200)
                self.assertEqual(len(json.loads(response.read())["nfts"]), 1)
            self.assertEqual(detail.call_count, 1)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)


class MarketRefreshScriptLifecycleTests(unittest.TestCase):
    def run_script_case(self, case):
        from pathlib import Path
        import subprocess
        from exchange.market_reference_refresh import REFERENCE_SCRIPT
        result = subprocess.run(
            ["node", str(Path(__file__).parent / "fixtures" / "market_refresh_browser.cjs")],
            input=json.dumps({"script": REFERENCE_SCRIPT, "case": case}),
            text=True, capture_output=True, timeout=10, check=True)
        self.assertEqual(json.loads(result.stdout), {"case": case, "passed": True})

    def test_anchor_does_not_reject_same_page_response(self):
        self.run_script_case("fragment")

    def test_every_exit_after_bfcache_restoration_aborts_active_read(self):
        self.run_script_case("repeated-exit")


if __name__ == "__main__":
    unittest.main()
