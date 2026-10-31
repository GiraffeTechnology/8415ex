"""Selected read-only terminal book HTTP; synthetic original-source ports only."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import build_opener, ProxyHandler, Request

from exchange.errors import DomainError
from exchange.nft_directory import NftDirectory
from exchange.workbench import WorkbenchServer


def snapshot(currency, price="100"):
    return {"schema": "8415ex-public-order-book/1", "currency": currency,
        "priceUnit": "base-units-per-whole-nft", "observedAt": 1700000000,
        "asks": {"rows": [{"priority": 1, "priceBaseUnits": price, "wholeNFTs": "1"}],
                 "total": 1, "hasMore": False},
        "bids": {"rows": [], "total": 0, "hasMore": False},
        "execution": "NOT_RUN", "funding": "NOT_RUN", "conversionPerformed": False,
        "meaning": "original domain price/time observation; no signing or execution"}


class OriginalBook:
    def __init__(self, price):
        self.price = price
        self.calls = []
        self.response = None
        self.error = None

    def order_book_view(self, receipt_id, currency, *, limit=20):
        self.calls.append((receipt_id, currency, limit))
        if self.error:
            raise self.error
        if currency != "local-test-quote":
            raise DomainError("EX_PUBLIC_BOOK_CURRENCY_REFUSED", "private backend detail")
        return deepcopy(self.response if self.response is not None else snapshot(currency, self.price))


class PublicOrderBookHTTP(unittest.TestCase):
    def setUp(self):
        self.sources = [OriginalBook("100"), OriginalBook("200")]
        self.bindings = [SimpleNamespace(exchange=source, receipt_id="private-receipt-" + str(i),
            run={}, gateway=None, public_detail=Mock(side_effect=AssertionError("detail read forbidden")))
            for i, source in enumerate(self.sources)]
        self.server = WorkbenchServer(self.bindings[0], detail_bindings=(self.bindings[1],),
                                      port=0, commit="a" * 40, tree="b" * 40)
        self.keys = [self.server.nft_directory.key_for(binding) for binding in self.bindings]
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.open = build_opener(ProxyHandler({})).open

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)

    def get(self, path):
        try:
            response = self.open(self.server.origin + path, timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.code, response.headers, response.read().decode()

    def path(self, key=None, **extra):
        return "/api/order-book?" + urlencode(dict(
            nft=key or self.keys[0], currency="local-test-quote", **extra))

    def test_exact_selected_source_and_original_currency_without_detail_or_identity(self):
        for i, key in enumerate(self.keys):
            code, headers, raw = self.get(self.path(key, limit="1"))
            self.assertEqual(code, 200)
            self.assertTrue(headers["Content-Type"].startswith("application/json"))
            self.assertEqual(headers["Cache-Control"], "no-store")
            value = json.loads(raw)
            self.assertEqual(value["nftKey"], key)
            self.assertEqual(value["asks"]["rows"][0]["priceBaseUnits"], str((i + 1) * 100))
            self.assertEqual(self.sources[i].calls, [(self.bindings[i].receipt_id, "local-test-quote", 1)])
            self.assertNotIn("private-receipt", raw)
            self.assertNotIn("private backend", raw)
            self.bindings[i].public_detail.assert_not_called()

    def test_invalid_queries_refuse_before_any_source_read(self):
        queries = ("", "nft=" + self.keys[0], "currency=local-test-quote",
            "nft=bad&currency=local-test-quote",
            "nft=" + self.keys[0] + "&currency=local-test-quote&nft=" + self.keys[1],
            "nft=" + self.keys[0] + "&currency=local-test-quote&limit=0",
            "nft=" + self.keys[0] + "&currency=local-test-quote&limit=101",
            "nft=" + self.keys[0] + "&currency=local-test-quote&limit=1.5",
            "nft=" + self.keys[0] + "&currency=local-test-quote&outcome=success")
        for query in queries:
            self.assertEqual(self.get("/api/order-book?" + query)[0], 400)
        self.assertEqual([source.calls for source in self.sources], [[], []])

    def test_unknown_key_never_falls_back_to_previous_selection(self):
        self.assertEqual(self.get(self.path())[0], 200)
        self.assertEqual(self.get(self.path("f" * 64))[0], 404)
        self.assertEqual(len(self.sources[0].calls), 1)
        self.assertEqual(self.sources[1].calls, [])

    def test_rejected_currency_does_not_echo_backend_details(self):
        path = "/api/order-book?" + urlencode({"nft": self.keys[0], "currency": "other"})
        code, _, body = self.get(path)
        self.assertEqual(code, 400)
        self.assertNotIn("private backend", body)

    def test_missing_or_unresolved_source_is_unavailable_not_empty_success(self):
        self.sources[0].error = DomainError("EX_PUBLIC_BOOK_UNAVAILABLE", "private unresolved")
        self.assertEqual(self.get(self.path())[0], 503)
        self.bindings[0].exchange = object()
        code, _, body = self.get(self.path())
        self.assertEqual(code, 503)
        self.assertNotIn("private", body)

    def test_extra_private_fields_and_malformed_prices_fail_closed(self):
        for mutate in (
            lambda row: row.update(signer="private-party"),
            lambda row: row["asks"]["rows"][0].update(intentId="private-order"),
            lambda row: row["asks"]["rows"][0].update(priceBaseUnits="1e3"),
            lambda row: row["asks"]["rows"][0].update(priceBaseUnits=100),
            lambda row: row["asks"].update(total=3),
            lambda row: row.update(execution="PASSED"),
        ):
            row = snapshot("local-test-quote")
            mutate(row)
            self.sources[0].response = row
            code, _, body = self.get(self.path())
            self.assertEqual(code, 503)
            self.assertNotIn("private-party", body)
            self.assertNotIn("private-order", body)

    def test_projection_copies_rows_and_never_rewrites_original_observation(self):
        original = snapshot("local-test-quote")
        self.sources[0].response = original
        before = deepcopy(original)
        result = self.server.nft_directory.order_book(self.keys[0], "local-test-quote")
        result["asks"]["rows"][0]["priceBaseUnits"] = "999"
        self.assertEqual(original, before)

    def test_post_is_not_an_order_or_dispatch_entry(self):
        request = Request(self.server.origin + self.path(), data=b"{}", method="POST")
        with self.assertRaises(HTTPError) as error:
            self.open(request, timeout=5)
        self.assertIn(error.exception.code, (403, 404))
        self.assertEqual([source.calls for source in self.sources], [[], []])
