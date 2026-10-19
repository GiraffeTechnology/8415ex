"""Definitions for remote-only directory, selection and route validation."""
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen
from exchange.nft_directory import NftDirectory
from exchange.nft_detail_page import render_detail
from exchange.workbench import RuntimeBinding, WorkbenchServer
from integration.test_nft_detail import OriginalReadOnlyDomain
from integration.test_market_page import protocol_read


def binding(receipt, current, gap, settlement_id=None):
    row = {"receiptId": receipt, "currentPosition": current, "gap": gap}
    if settlement_id is not None:
        row["settlementProjection"] = protocol_read(settlement_id)
    return RuntimeBinding(OriginalReadOnlyDomain(), receipt,
        read_details=lambda rid: row,
        verify_details=lambda *args: True)


class NftDirectorySelection(unittest.TestCase):
    def setUp(self):
        self.first = binding("private-original-one", 20, "open", "0x" + "0" * 63 + "1")
        self.second = binding("private-original-two", 3, "closed", "0x" + "0" * 64)
        self.directory = NftDirectory((self.first, self.second))

    def test_each_nft_keeps_its_own_original_gap_and_current(self):
        one = self.directory.detail(self.directory.key_for(self.first))
        two = self.directory.detail(self.directory.key_for(self.second))
        self.assertEqual((one["positions"]["current"], one["gap"]), (20, "open"))
        self.assertEqual((two["positions"]["current"], two["gap"]), (3, "closed"))
        self.assertEqual((one["displayGap"], two["displayGap"]), ({"state": "yes"}, {"state": "no"}))
        self.assertNotIn("receiptId", one)
        self.assertNotIn("private-original", json.dumps(self.directory.choices()))

    def test_unknown_key_never_falls_back_to_previous_nft(self):
        self.directory.detail(self.directory.key_for(self.first))
        with self.assertRaises(KeyError):
            self.directory.detail("0" * 64)

    def test_duplicate_original_binding_is_refused(self):
        with self.assertRaises(ValueError):
            NftDirectory((self.first, self.first))

    def test_one_unavailable_reader_does_not_hide_other_nft_choices(self):
        def unavailable():
            raise OSError("private resolver path")
        self.first.public_detail = unavailable
        rows = self.directory.choices()
        self.assertEqual([item["gap"] for item in rows], ["unknown", "closed"])
        self.assertNotIn("resolver", json.dumps(rows))
        failed = self.directory.detail(self.directory.key_for(self.first))
        self.assertEqual(failed["positions"], {"current": None, "owner": None, "holder": None})
        self.assertEqual(failed["sourceStatus"], "detail-source-unavailable")
        self.assertEqual(failed["displayGap"], {"state": "unknown"})

    def test_locale_links_preserve_nft_and_selector_marks_exact_current_nft(self):
        key = self.directory.key_for(self.second)
        page = render_detail(self.directory.detail(key), "fr", nft_key=key, choices=self.directory.choices())
        self.assertIn('nft=' + key + '&amp;lang=ja', page)
        self.assertIn('lang=fr&amp;nft=' + key + '" aria-current="page"', page)
        self.assertIn('class="gap no">openGapOF=NO', page)
        self.assertNotIn("private-original", page)

    def test_http_exact_selection_and_catalog_do_not_use_default_receipt(self):
        server = WorkbenchServer(self.first, port=0, detail_bindings=(self.second,))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            key = server.nft_directory.key_for(self.second)
            with urlopen(server.origin + "/api/nft-detail?nft=" + key) as response:
                detail = json.load(response)
            self.assertEqual((detail["nftKey"], detail["gap"]), (key, "closed"))
            with urlopen(server.origin + "/nft?lang=ja&nft=" + key) as response:
                page = response.read().decode("utf-8")
            self.assertIn('<html lang="ja">', page)
            self.assertIn('class="gap no">openGapOF=NO', page)
            with self.assertRaises(HTTPError) as error:
                urlopen(server.origin + "/nft?nft=" + "0" * 64)
            self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_legacy_closed_gap_without_supported_read_is_not_displayed_as_no(self):
        unobserved = binding("private-unobserved", 3, "closed")
        directory = NftDirectory((unobserved,))
        row = directory.catalogue()[0]
        self.assertEqual(row["gap"], "closed")
        self.assertEqual(row["displayGap"], {"state": "unknown"})
        self.assertNotIn('class="gap no">openGapOF=NO', render_detail(row))
