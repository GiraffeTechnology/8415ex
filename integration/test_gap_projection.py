"""Remote-only semantic contracts; no real ABI discovery or chain acceptance."""
from copy import deepcopy
import unittest
from exchange.gap_projection import display_gap, gap_label, GAP_LABELS
from exchange.nft_directory import NftDirectory
from exchange.nft_detail_page import render_detail
from exchange.market_page import render_market
from integration.test_market_page import original


def observation(value):
    return {"projectionInterface": "0x6309e170", "settlementInterface": "0xf4a7d71b",
            "projectionSupported": True, "settlementSupported": True,
            "readStatus": "succeeded", "method": "openGapOf(uint256)",
            "returnType": "bytes32", "settlementId": value}


class GapProjection(unittest.TestCase):
    def test_successful_supported_bytes32_is_required_for_yes_and_no(self):
        self.assertEqual(display_gap({"settlementProjection": observation("0x" + "0" * 64)}), {"state": "no"})
        self.assertEqual(display_gap({"settlementProjection": observation("0x" + "0" * 63 + "1")}), {"state": "yes"})

    def test_legacy_gap_and_equal_positions_never_supply_a_protocol_no(self):
        for gap in ("open", "closed", "unknown"):
            row = {"gap": gap, "currentPosition": 3, "ownerPosition": 3, "holderPosition": 3}
            self.assertEqual(display_gap(row), {"state": "unknown"})

    def test_unsupported_loading_error_and_missing_support_stay_distinct(self):
        base = observation("0x" + "0" * 64)
        for changes, expected in (({"settlementSupported": False}, "unsupported"),
                                  ({"projectionSupported": False}, "unsupported"),
                                  ({"settlementSupported": None}, "unknown"),
                                  ({"readStatus": "loading"}, "loading"), ({"readStatus": "error"}, "error")):
            self.assertEqual(display_gap({"settlementProjection": dict(base, **changes)}), {"state": expected})

    def test_bool_malformed_bytes_and_ui_spelling_are_not_abi_results(self):
        for value in (False, True, "0x00", "0x" + "g" * 64, None):
            self.assertEqual(display_gap({"settlementProjection": observation(value)}), {"state": "error"})
        value = observation("0x" + "0" * 64)
        value["method"] = "openGapOF(uint256)"
        self.assertEqual(display_gap({"settlementProjection": value}), {"state": "error"})

    def test_projection_is_read_only_and_has_no_trade_or_finality_assertion(self):
        row = {"settlementProjection": observation("0x" + "0" * 64)}
        before = deepcopy(row)
        result = display_gap(row)
        self.assertEqual(row, before)
        self.assertEqual(set(result), {"state"})

    def test_original_verifier_is_required_before_interpreting_source_record(self):
        binding, row = original()
        row["settlementProjection"] = observation("0x" + "0" * 64)
        binding.verify_details = lambda *args: False
        self.assertEqual(binding.public_detail()["displayGap"], {"state": "unknown"})

    def test_six_locale_market_detail_and_selector_keep_each_nft_protocol_state(self):
        one, first = original()
        two, second = original("private-second", "Original ore", "open")
        first["settlementProjection"] = observation("0x" + "0" * 63 + "1")
        second["settlementProjection"] = observation("0x" + "0" * 64)
        directory = NftDirectory((one, two))
        for locale in GAP_LABELS:
            page = render_market(directory.catalogue(), {"status": "not-connected"}, locale)
            self.assertIn('class="badge yes">openGapOF=YES', page)
            self.assertIn('class="badge no">openGapOF=NO', page)
            key = directory.key_for(two)
            detail = directory.detail(key)
            self.assertEqual(detail["gap"], "open")
            self.assertEqual(detail["displayGap"], {"state": "no"})
            rendered = render_detail(detail, locale, nft_key=key, choices=directory.choices())
            self.assertIn('class="gap no">openGapOF=NO', rendered)
            self.assertFalse(detail["ordinaryTransfer"]["gapEqualityFinalityGateApplied"])
            self.assertNotIn("private-second", rendered)

    def test_unknown_states_have_neither_yes_nor_no_visual_class(self):
        for locale in GAP_LABELS:
            for state in ("unknown", "unsupported", "loading", "error"):
                label, style = gap_label({"displayGap": {"state": state}}, locale)
                self.assertEqual(style, "unverified")
                self.assertNotIn("=NO", label)
                self.assertNotIn("=YES", label)
