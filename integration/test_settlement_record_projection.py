"""Remote-only protocol-record contracts; no real ABI/proof/financial acceptance."""
from copy import deepcopy
import json
import unittest
from exchange.gap_projection import settlement_record, PROTOCOL_GAP_STATES
from exchange.settlement_record_page import render_settlement, TEXT
from exchange.workbench import RuntimeBinding
from integration.test_nft_detail import OriginalReadOnlyDomain


def source(state=3):
    return {"receiptId": "private-r", "gap": "closed", "tokenBinding": {"tokenId": 70},
            "settlementRecord": {"projectionInterface": "0x6309e170", "settlementInterface": "0xf4a7d71b",
                "projectionSupported": True, "settlementSupported": True, "readStatus": "succeeded",
                "method": "settlement(bytes32)", "settlementId": "0x" + "1" * 64,
                "record": {"tokenId": 70, "status": state, "openedAt": 100, "deadline": 150,
                           "initiator": "private-initiator", "expectedHolder": "private-expected-holder"}}}


class ProtocolSettlementRecord(unittest.TestCase):
    def test_actual_enum_values_are_separate_from_ex_business_outcomes(self):
        for value, label in PROTOCOL_GAP_STATES.items():
            result = settlement_record(source(value))
            self.assertEqual(result["protocolGapStatus"], label)
            self.assertEqual(set(result), {"status", "protocolGapStatus", "openedAt", "deadline"})

    def test_none_rejected_bool_or_malformed_status_cannot_be_successful_record(self):
        for value in (0, 5, "REJECTED", "ADMITTED", True, None):
            self.assertEqual(settlement_record(source(value)), {"status": "unavailable"})

    def test_wrong_nft_method_or_unknown_identifier_is_not_a_closed_gap(self):
        for target in ("token", "method", "identifier", "time"):
            row = source()
            if target == "token":
                row["tokenBinding"]["tokenId"] = 71
            elif target == "method":
                row["settlementRecord"]["method"] = "cancelSettlement(bytes32,bytes32)"
            elif target == "identifier":
                row["settlementRecord"]["settlementId"] = "0x" + "0" * 64
            else:
                row["settlementRecord"]["record"]["deadline"] = 100
            self.assertEqual(settlement_record(row), {"status": "unavailable"})

    def test_absent_unsupported_or_failed_read_never_infers_from_application_gap(self):
        self.assertEqual(settlement_record({"gap": "closed", "registration": "rejected"}), {"status": "not-provided"})
        row = source()
        row["settlementRecord"]["settlementSupported"] = False
        self.assertEqual(settlement_record(row), {"status": "unsupported"})
        row["settlementRecord"].update(settlementSupported=True, readStatus="reverted")
        self.assertEqual(settlement_record(row), {"status": "unavailable"})

    def test_cancelled_source_does_not_mutate_positions_gap_funds_or_trading_eligibility(self):
        row = source(3)
        before = deepcopy(row)
        binding = RuntimeBinding(OriginalReadOnlyDomain(), "private-r", read_details=lambda rid: row,
                                 verify_details=lambda *args: True)
        detail = binding.public_detail()
        self.assertEqual(detail["settlementRecord"]["protocolGapStatus"], "CANCELLED")
        self.assertEqual(detail["positions"], {"current": None, "owner": 7, "holder": 1})
        self.assertEqual(detail["gap"], "closed")
        self.assertEqual(detail["ordinaryTransfer"]["executionEligibility"], "not-evaluated")
        self.assertFalse(detail["ordinaryTransfer"]["gapEqualityFinalityGateApplied"])
        self.assertNotIn("funds", detail)
        self.assertEqual(row, before)
        binding.verify_details = lambda *args: False
        self.assertEqual(binding.public_detail()["settlementRecord"], {"status": "unavailable"})

    def test_six_locale_panel_keeps_protocol_identifier_and_excludes_private_parties(self):
        result = settlement_record(source(3))
        for locale, text in TEXT.items():
            page = render_settlement({"settlementRecord": result}, locale)
            self.assertIn("CANCELLED", page)
            self.assertIn(text[5], page)
            self.assertNotIn("private-", page)
        self.assertNotIn("initiator", json.dumps(result))
        self.assertNotIn("expectedHolder", json.dumps(result))
