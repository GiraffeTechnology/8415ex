"""Read-only market capture definitions; author execution NOT_RUN."""
import copy
import json
import unittest
from urllib.parse import parse_qs, urlsplit

from exchange.browser_materials import capture_market, pack_capture, MAX_IMAGE
from exchange.nft_detail_page import LOCALES

SOURCE = {"commit": "a" * 40, "tree": "b" * 40}
ORIGIN = "http://127.0.0.1:18415"
PNG = b"\x89PNG\r\n\x1a\nsynthetic-image"


class Response:
    def __init__(self, url, status=200, data=None):
        self.url, self.status, self.data = url, status, data

    async def body(self):
        return json.dumps(self.data).encode()


class Page:
    def __init__(self):
        self.url = ORIGIN
        self.request = self
        self.first = self
        self.gets = []
        self.visits = []
        self.health_reads = 0
        self.changed_source = False
        self.redirect = None
        self.missing = None
        self.image = PNG
        self.drift_on_screenshot = False

    async def get(self, url):
        self.gets.append(url)
        self.health_reads += 1
        source = copy.deepcopy(SOURCE)
        if self.changed_source and self.health_reads > 1:
            source["commit"] = "c" * 40
        return Response(url, data={"schema": "8415ex-http-health-observation/1",
            "httpProcess": "serving", "declaredSource": source,
            "sourceIdentity": "DECLARED_ONLY", "operationsREADY": "NOT_VERIFIED"})

    async def goto(self, url, **options):
        self.visits.append(url)
        self.url = self.redirect or url
        return Response(self.url, 404 if self.missing == urlsplit(url).path else 200)

    def locator(self, selector):
        return self

    async def wait_for(self, **options):
        pass

    async def screenshot(self, **options):
        if self.drift_on_screenshot:
            self.url = ORIGIN + "/market?lang=en"
        return self.image


class MarketCapture(unittest.IsolatedAsyncioTestCase):
    async def test_all_locales_and_original_read_only_routes(self):
        page = Page()
        captured = await capture_market(page, ORIGIN, SOURCE)
        manifest = captured["manifest"]
        self.assertEqual(len(page.visits), 3 * len(LOCALES))
        self.assertEqual(page.gets, [ORIGIN + "/healthz"] * 2)
        actual = {(urlsplit(url).path, parse_qs(urlsplit(url).query)["lang"][0])
                  for url in page.visits}
        self.assertEqual(actual, {(path, locale) for locale in LOCALES
                         for path in ("/market", "/collateral", "/scenarios")})
        self.assertEqual(len(manifest["captures"]), 3 * len(LOCALES))
        self.assertTrue(pack_capture(captured).startswith(b"PK"))
        self.assertNotIn("pendingVideo", captured)

    async def test_no_native_or_acceptance_promotion(self):
        captured = await capture_market(Page(), ORIGIN, SOURCE)
        manifest = captured["manifest"]
        self.assertEqual(manifest["schema"], "8415ex-market-browser-materials/1")
        self.assertEqual(manifest["nativeReceiptAndSixDemos"], "NOT_RUN")
        self.assertEqual(manifest["providerSigningChain"], "NOT_RUN")
        self.assertEqual(manifest["languageRendering"], "NOT_VERIFIED")
        self.assertEqual(manifest["finalProductAcceptance"], "NOT_RUN")
        self.assertEqual(manifest["sourceIdentity"], "DECLARED_ONLY")
        raw = json.loads(captured["files"]["evidence/market-start.json"])
        self.assertEqual(raw["operationsREADY"], "NOT_VERIFIED")

    async def test_changed_runtime_source_does_not_return_complete_capture(self):
        page = Page()
        page.changed_source = True
        with self.assertRaisesRegex(ValueError, "source differs"):
            await capture_market(page, ORIGIN, SOURCE)
        self.assertEqual(page.health_reads, 2)

    async def test_missing_optional_selector_is_partial_failure(self):
        page = Page()
        page.missing = "/collateral"
        with self.assertRaisesRegex(RuntimeError, "entry unavailable"):
            await capture_market(page, ORIGIN, SOURCE)
        self.assertEqual(page.health_reads, 1)

    async def test_same_origin_wrong_path_and_foreign_redirect_refused(self):
        for target in (ORIGIN + "/receipt", "https://example.invalid/market?lang=en"):
            page = Page()
            page.redirect = target
            with self.subTest(target=target), self.assertRaises(ValueError):
                await capture_market(page, ORIGIN, SOURCE)

    async def test_image_budget_and_navigation_drift_refused(self):
        page = Page()
        page.image = PNG + b"x" * MAX_IMAGE
        with self.assertRaisesRegex(ValueError, "bounded"):
            await capture_market(page, ORIGIN, SOURCE)
        page = Page()
        page.drift_on_screenshot = True
        # The first English market may remain unchanged; another fixed entry
        # necessarily differs, and must never be recorded as that selector.
        with self.assertRaisesRegex(ValueError, "navigated away"):
            await capture_market(page, ORIGIN, SOURCE)
