"""Remote-only definitions; synthetic original-reader contracts, not live feed acceptance."""
from copy import deepcopy
import hashlib
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
from exchange.market_page import render_market, WORDS
from exchange.nft_detail_page import render_detail
from exchange.nft_directory import NftDirectory
from exchange.workbench import RuntimeBinding, WorkbenchServer
from integration.test_nft_detail import OriginalReadOnlyDomain


class MarketDomain(OriginalReadOnlyDomain):
    def receipt_view(self, receipt_id):
        return dict(super().receipt_view(receipt_id), allowedPriceCurrencies=("ETH",))


def protocol_read(settlement_id):
    # Explicit synthetic ABI-read fixture, independent of the EX application gap.
    return {"projectionInterface": "0x6309e170", "settlementInterface": "0xf4a7d71b",
            "projectionSupported": True, "settlementSupported": True,
            "readStatus": "succeeded", "method": "openGapOf(uint256)",
            "returnType": "bytes32", "settlementId": settlement_id}


def original(receipt="private-market-one", name="Original soy", gap="open"):
    row = {"receiptId": receipt, "currentPosition": 20, "gap": gap,
           "marketCard": {"identityExcluded": True, "name": name,
               "spec": "Original specification", "quantity": "40", "unit": "t",
               "commodityCode": "soy", "quote": {"amountBaseUnits": "100",
                   "currency": "ETH", "unit": "base-units-per-whole-nft", "source": "simulated"}},
           "businessTerms": {"coverageVerified": True, "identityExcluded": True,
               "clauses": [{"label": "Delivery", "text": "Original <unchanged> obligation."}]}}
    return RuntimeBinding(MarketDomain(), receipt, read_details=lambda rid: row,
                          verify_details=lambda *args: True), row


class MarketSourceSurface(unittest.TestCase):
    def test_original_quote_keeps_nft0_currency_base_units_and_original_bytes(self):
        binding, row = original()
        before = deepcopy(row)
        detail = binding.public_detail()
        self.assertEqual(detail["marketCard"]["quote"], row["marketCard"]["quote"])
        self.assertEqual(detail["terms"]["clauses"][0]["text"], "Original <unchanged> obligation.")
        detail["marketCard"]["name"] = "Caller edit"
        self.assertEqual(row, before)
        row["marketCard"]["quote"]["currency"] = "USDT"
        self.assertEqual(binding.public_detail()["sourceStatus"], "detail-source-unavailable")

    def test_unverified_or_identity_bearing_market_projection_is_refused(self):
        binding, row = original()
        row["marketCard"]["name"] = "0x" + "a" * 40
        self.assertEqual(binding.public_detail()["sourceStatus"], "detail-source-unavailable")
        binding, row = original()
        row["marketCard"]["identityExcluded"] = False
        self.assertEqual(binding.public_detail()["sourceStatus"], "detail-source-unavailable")

    def test_absent_originals_never_turn_design_prices_or_gap_into_observations(self):
        binding = RuntimeBinding(MarketDomain(), "private-empty")
        directory = NftDirectory((binding,))
        for locale, words in WORDS.items():
            page = render_market(directory.catalogue(), {"status": "not-connected", "price": None}, locale)
            self.assertIn('<html lang="' + locale + '">', page)
            self.assertIn(words[15], page)
            for forbidden in ("520", "3,860", "private-empty", "private-owner-name", "openGapOF=YES", "openGapOF=NO"):
                self.assertNotIn(forbidden, page)

    def test_search_and_back_links_keep_exact_nft_locale_and_independent_gap(self):
        first, _ = original()
        second, second_row = original("private-market-two", "Original ore", "closed")
        second_row["settlementProjection"] = protocol_read("0x" + "0" * 64)
        directory = NftDirectory((first, second))
        key = directory.key_for(second)
        page = render_market(directory.catalogue(), {"status": "unavailable"}, "fr", "ore")
        self.assertIn('id="nft-' + key + '"', page)
        self.assertNotIn('id="nft-' + directory.key_for(first) + '"', page)
        self.assertIn('class="badge no">openGapOF=NO', page)
        detail = render_detail(directory.detail(key), "fr", nft_key=key,
                               choices=directory.choices(), market_query="ore")
        self.assertIn('/market?lang=fr&amp;q=ore#nft-' + key, detail)
        self.assertIn("Original &lt;unchanged&gt; obligation.", detail)
        self.assertNotIn("private-market", detail)

    def test_reference_failure_preserves_original_value_separately_from_order_quote(self):
        binding, _ = original()
        reference = {"status": "unavailable", "price": "987.65", "sourceAsOf": "2026-01-01",
                     "fetchedAt": "2026-01-02T00:00:00Z", "unit": "USD/t"}
        page = render_market(NftDirectory((binding,)).catalogue(), reference)
        self.assertIn("987.65", page)
        self.assertIn("100 ETH", page)
        self.assertIn("2026-01-01", page)
        self.assertIn("2026-01-02T00:00:00Z", page)
        self.assertEqual(reference["status"], "unavailable")

    def test_http_market_catalogue_binary_asset_and_bounded_queries(self):
        binding, _ = original()
        server = WorkbenchServer(binding, port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with urlopen(server.origin + "/market?lang=ja&q=soy") as response:
                self.assertIn('<html lang="ja">', response.read().decode("utf-8"))
            with urlopen(server.origin + "/api/catalogue") as response:
                data = json.load(response)
            self.assertEqual(data["reference"]["status"], "not-connected")
            self.assertEqual(data["nfts"][0]["marketCard"]["quote"]["currency"], "ETH")
            self.assertNotIn("private-market", json.dumps(data))
            with urlopen(server.origin + "/assets/soy.png") as response:
                raw = response.read()
                self.assertEqual(response.headers["Content-Type"], "image/png")
            self.assertEqual(len(raw), 30183)
            self.assertEqual(hashlib.sha256(raw).hexdigest(),
                             "d889f0943b26929ce6a71a0cfb23492060eb927e902ee8954c02c98dd6f7e12a")
            for path, code in (("/assets/unknown.svg", 404), ("/assets/soy.png?q=x", 404),
                               ("/market?lang=en&lang=fr", 400), ("/market?q=" + "x" * 65, 400)):
                with self.assertRaises(HTTPError) as error:
                    urlopen(server.origin + path)
                self.assertEqual(error.exception.code, code)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)
