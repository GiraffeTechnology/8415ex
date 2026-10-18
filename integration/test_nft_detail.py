"""Source definitions only until the approved remote runner executes them."""
import json
import unittest
from exchange.nft_detail import receipt_detail
from exchange.workbench import RuntimeBinding


class OriginalReadOnlyDomain:
    def receipt_view(self, receipt_id):
        return {"owner": {"position": 7, "account": "private-owner-name"},
                "holder": {"position": 1, "account": "private-holder-name"}}


class NftDetailProjection(unittest.TestCase):
    def test_missing_original_details_do_not_invent_current_gap_or_signatures(self):
        detail = RuntimeBinding(OriginalReadOnlyDomain(), "receipt-one").public_detail()
        self.assertEqual(detail["positions"], {"current": None, "owner": 7, "holder": 1})
        self.assertEqual(detail["gap"], "unknown")
        self.assertEqual(detail["signatureStatusByPosition"], [])
        self.assertEqual(detail["terms"]["status"], "not-provided")
        self.assertNotIn("private-owner-name", json.dumps(detail))

    def test_verified_positions_and_clauses_are_independent_without_identity_passthrough(self):
        row = {"receiptId": "receipt-one", "currentPosition": 20, "gap": "open",
               "walletName": "never-publish", "signatures": [
                   {"position": 1, "status": "signed", "verified": True, "signer": "never-publish"},
                   {"position": 7, "status": "pending"}],
               "businessTerms": {"coverageVerified": True, "identityExcluded": True,
                   "clauses": [{"label": "Delivery", "text": "Original obligation unchanged."}]}}
        binding = RuntimeBinding(OriginalReadOnlyDomain(), "receipt-one",
                                 read_details=lambda rid: row, verify_details=lambda rid, data: True)
        detail = binding.public_detail()
        self.assertEqual(detail["positions"], {"current": 20, "owner": 7, "holder": 1})
        self.assertEqual(detail["gap"], "open")
        self.assertFalse(detail["ordinaryTransfer"]["gapEqualityFinalityGateApplied"])
        self.assertEqual(detail["terms"]["clauses"][0]["text"], "Original obligation unchanged.")
        self.assertNotIn("never-publish", json.dumps(detail))
        detail["terms"]["clauses"][0]["text"] = "caller edit"
        self.assertEqual(row["businessTerms"]["clauses"][0]["text"], "Original obligation unchanged.")

    def test_unverified_signed_status_is_not_promoted(self):
        row = {"receiptId": "receipt-one", "signatures": [{"position": 4, "status": "signed"}]}
        detail = receipt_detail(OriginalReadOnlyDomain(), "receipt-one",
                               read_details=lambda rid: row, verify_details=lambda *args: True)
        self.assertEqual(detail["sourceStatus"], "detail-source-unavailable")
        self.assertEqual(detail["signatureStatusByPosition"], [])

    def test_identity_bearing_clause_is_refused_without_rewriting_business_text(self):
        text = "Deliver to " + "0x" + "a" * 40
        row = {"receiptId": "receipt-one", "businessTerms": {"coverageVerified": True,
               "identityExcluded": True, "clauses": [{"label": "Delivery", "text": text}]}}
        detail = receipt_detail(OriginalReadOnlyDomain(), "receipt-one",
                               read_details=lambda rid: row, verify_details=lambda *args: True)
        self.assertEqual(detail["terms"], {"status": "unavailable", "clauses": []})
        self.assertEqual(row["businessTerms"]["clauses"][0]["text"], text)

    def test_resolver_error_never_exposes_private_error_text_or_another_receipt(self):
        def read(rid):
            raise OSError("private server path and identity")
        detail = receipt_detail(OriginalReadOnlyDomain(), "receipt-one",
                               read_details=read, verify_details=lambda *args: True)
        self.assertNotIn("private server", json.dumps(detail))
        wrong = receipt_detail(OriginalReadOnlyDomain(), "receipt-one",
                               read_details=lambda rid: {"receiptId": "receipt-two"},
                               verify_details=lambda *args: True)
        self.assertEqual(wrong["sourceStatus"], "detail-source-unavailable")
