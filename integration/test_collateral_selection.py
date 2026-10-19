"""Synthetic category-selection routes, with no financing or wallet action."""
import http.client
import threading
import unittest
from urllib.parse import urlencode

from exchange.collateral_scenario import collateral_selection, render_collateral, WORDS
from exchange.collateral_workbench import mount_collateral_selection
from exchange.nft_directory import NftDirectory
from integration import test_serialized_workbench_composition as original_composition


class CollateralSelectionTests(unittest.TestCase):
    def setUp(self):
        original = original_composition.SerializedWorkbenchCompositionTests("runTest")
        original.setUp()
        self.addCleanup(original.doCleanups)
        self.original = original
        self.server = mount_collateral_selection(original.server)
        self.keys = tuple(self.server.nft_directory._bindings)

    def request(self, query="", method="GET"):
        worker = threading.Thread(target=self.server.serve_forever,
            kwargs={"poll_interval": 0.02}, daemon=True)
        worker.start()
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method, "/collateral?" + query)
            response = connection.getresponse()
            return response.status, response.read().decode()
        finally:
            connection.close()
            self.server.shutdown()
            worker.join(3)

    def test_crypto_and_whole_receipt_nft_are_both_explicit_selectable_categories(self):
        directory = self.server.nft_directory
        for asset in ("BTC", "ETH"):
            value = collateral_selection(directory, kind="crypto", asset=asset, target=self.keys[0])
            self.assertEqual(value["selected"], {"kind": "crypto", "asset": asset})
            self.assertIsNone(value["mechanismParameters"])
            self.assertFalse(value["executionInvoked"])
        value = collateral_selection(directory, kind="warehouse-nft", asset=self.keys[0], target=self.keys[1])
        self.assertEqual(value["selected"], {"kind": "warehouse-nft", "asset": self.keys[0]})
        self.assertFalse(value["ordinarySpotEligibilityEvaluated"])

    def test_six_locale_routes_preserve_selection_without_inventing_financial_terms(self):
        for locale in WORDS:
            with self.subTest(locale=locale):
                status, body = self.request(urlencode({"lang": locale,
                    "kind": "warehouse-nft", "asset": self.keys[0], "target": self.keys[1]}))
                self.assertEqual(status, 200)
                self.assertIn(WORDS[locale][9], body)
                self.assertIn('data-collateral-selection="1"', body)
                self.assertIn('method="get"', body)
                self.assertNotIn('type="number"', body)
                self.assertNotIn('name="ltv"', body)
        self.assertEqual(self.original.calls, [])

    def test_absent_receipts_do_not_turn_into_sample_nfts_or_fake_asset_mapping(self):
        directory = NftDirectory((), allow_empty=True)
        value = collateral_selection(directory, kind="crypto", asset="BTC")
        self.assertFalse(value["assetMappingVerified"])
        self.assertIn(WORDS["en"][14], render_collateral(directory))
        self.assertIsNone(collateral_selection(directory)["selected"])
        with self.assertRaises(ValueError):
            collateral_selection(directory, kind="warehouse-nft", asset="0" * 64)

    def test_unknown_assets_targets_duplicates_and_financing_parameters_are_refused(self):
        for query in (
                "kind=crypto&asset=DOGE", "kind=warehouse-nft&asset=BTC",
                "kind=crypto&asset=ETH&target=" + "0" * 64,
                "kind=crypto&kind=crypto&asset=ETH",
                "kind=crypto&asset=ETH&ltv=50", "lang=xx"):
            with self.subTest(query=query):
                self.assertEqual(self.request(query)[0], 400)
        self.assertEqual(self.original.calls, [])

    def test_selector_exposes_no_original_receipt_or_wallet_identity(self):
        body = render_collateral(self.server.nft_directory, kind="warehouse-nft", asset=self.keys[0])
        for binding in self.server.nft_directory._bindings.values():
            self.assertNotIn(binding.receipt_id, body)
        self.assertNotIn("0x", body)
        self.assertNotIn("session", body.lower())
        self.assertNotIn("authorization", body.lower())

    def test_mount_is_idempotent_and_keeps_original_native_navigation(self):
        handler = self.server.RequestHandlerClass
        self.assertIs(mount_collateral_selection(self.server), self.server)
        self.assertIs(self.server.RequestHandlerClass, handler)
        navigation = handler.native_navigation("fr")
        self.assertIn("/rollback?lang=fr", navigation)
        self.assertIn("/collateral?lang=fr", navigation)
        self.assertEqual(navigation.count("/collateral?lang=fr"), 1)

    def test_post_refuses_selection_writes_and_localizes_the_unavailable_message(self):
        status, body = self.request("lang=ja", method="POST")
        self.assertEqual(status, 405)
        self.assertEqual(body, WORDS["ja"][13])
        self.assertEqual(self.original.calls, [])
