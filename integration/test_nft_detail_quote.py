"""Remote-only exact NFT quote display definitions; no financial execution."""
import unittest
from exchange.nft_detail_page import render_detail, QUOTE_LABELS
from exchange.nft_directory import NftDirectory
from integration.test_market_page import original, protocol_read


class NftDetailQuote(unittest.TestCase):
    def test_all_six_locales_preserve_original_base_units_currency_and_simulation_label(self):
        binding, row = original()
        row["marketCard"]["quote"]["amountBaseUnits"] = "1000000000000000001"
        directory = NftDirectory((binding,))
        detail = directory.catalogue()[0]
        for locale, labels in QUOTE_LABELS.items():
            page = render_detail(detail, locale)
            self.assertIn("1000000000000000001 ETH", page)
            self.assertIn(labels[0], page)
            self.assertIn(labels[1], page)
            self.assertIn(labels[3], page)
            self.assertNotIn("1.000000000000000001", page)

    def test_original_order_quote_is_explicit_and_does_not_change_gap_or_gate(self):
        binding, row = original()
        row["marketCard"]["quote"]["source"] = "original-order"
        row["settlementProjection"] = protocol_read("0x" + "0" * 63 + "1")
        detail = NftDirectory((binding,)).catalogue()[0]
        page = render_detail(detail)
        self.assertIn(QUOTE_LABELS["en"][2], page)
        self.assertIn('class="gap yes">openGapOF=YES', page)
        self.assertFalse(detail["ordinaryTransfer"]["gapEqualityFinalityGateApplied"])

    def test_missing_or_unverified_quote_never_borrows_another_nft_quote(self):
        binding, row = original()
        detail = NftDirectory((binding,)).catalogue()[0]
        detail["sourceStatus"] = "detail-source-unavailable"
        self.assertNotIn("100 ETH", render_detail(detail))
        row["marketCard"]["quote"] = None
        self.assertNotIn("100 ETH", render_detail(NftDirectory((binding,)).catalogue()[0]))
