"""Per-original-record signature display definitions; author execution NOT_RUN."""
from copy import deepcopy
import json
import unittest

from exchange.nft_detail import receipt_detail
from exchange.nft_detail_page import LOCALES, SIGNATURE_OBSERVATION_LABELS, render_detail
from integration.test_nft_detail import OriginalReadOnlyDomain
from integration import test_signature_projection as original


class SignatureObservationDetail(unittest.TestCase):
    def record(self):
        first = deepcopy(original.ITEM)
        second = dict(first, role="historical-buyer", payloadRef="second-private-payload", status="pending")
        return {"receiptId": "r", "currentPosition": 20, "signatures": [first, second]}

    def project(self, record, verify=None):
        return receipt_detail(OriginalReadOnlyDomain(), "r", read_details=lambda rid: record,
            verify_details=lambda *args: True,
            verify_signature=verify or (lambda rid, item, row: original.verdict(item)))

    def test_same_position_original_roles_remain_separate_without_aggregate_signed_claim(self):
        detail = self.project(self.record())
        self.assertEqual(detail["sourceStatus"], "verified-original-reader")
        self.assertEqual(detail["signatureStatusByPosition"], [{"position": 2, "status": "unknown"}])
        self.assertEqual(detail["signatureObservations"], [
            {"position": 2, "observation": 1, "status": "signed"},
            {"position": 2, "observation": 2, "status": "pending"}])

    def test_each_original_verification_result_is_independent(self):
        record = self.record()
        record["signatures"][1]["status"] = "signed"
        seen = []
        def verify(rid, item, row):
            seen.append((rid, item["role"], item["payloadRef"], item["position"]))
            result = original.verdict(item)
            if item["role"] == "historical-buyer":
                result["role"] = "current-owner"
            return result
        detail = self.project(record, verify)
        self.assertEqual([item["status"] for item in detail["signatureObservations"]], ["signed", "unknown"])
        self.assertEqual(len(seen), 2)
        self.assertEqual(seen[0][1:], ("historical-seller", "original-payload", 2))
        self.assertEqual(seen[1][1:], ("historical-buyer", "second-private-payload", 2))

    def test_duplicate_complete_original_binding_is_not_two_signatures(self):
        record = self.record()
        record["signatures"] = [deepcopy(original.ITEM), deepcopy(original.ITEM)]
        detail = self.project(record)
        self.assertEqual(detail["sourceStatus"], "detail-source-unavailable")
        self.assertEqual(detail["signatureObservations"], [])
        self.assertEqual(detail["signatureStatusByPosition"], [])

    def test_incomplete_non_signed_observations_do_not_invent_original_signature_proof(self):
        record = {"receiptId": "r", "signatures": [
            {"position": 2, "status": "unsigned"},
            {"position": 2, "status": "pending"}]}
        detail = self.project(record, lambda *args: self.fail("must not verify unsigned/pending"))
        self.assertEqual([item["status"] for item in detail["signatureObservations"]], ["unsigned", "pending"])
        self.assertEqual(detail["signatureStatusByPosition"], [{"position": 2, "status": "unknown"}])

    def test_historical_position_stays_fixed_when_current_position_moves(self):
        record = self.record()
        first = self.project(record)
        record["currentPosition"] = 1000
        second = self.project(record)
        self.assertEqual(first["signatureObservations"], second["signatureObservations"])
        self.assertEqual(second["positions"]["current"], 1000)
        self.assertEqual({item["position"] for item in second["signatureObservations"]}, {2})

    def test_six_locale_rendering_keeps_both_records_without_private_bindings(self):
        detail = self.project(self.record())
        public = json.dumps(detail)
        for raw in ("historical-seller", "historical-buyer", "original-transfer",
                    "original-payload", "second-private-payload", "original-scheme"):
            self.assertNotIn(raw, public)
        for locale, words in LOCALES.items():
            with self.subTest(locale=locale):
                page = render_detail(detail, locale)
                self.assertIn(SIGNATURE_OBSERVATION_LABELS[locale] + " 1", page)
                self.assertIn(SIGNATURE_OBSERVATION_LABELS[locale] + " 2", page)
                self.assertIn(words[9], page)
                self.assertIn(words[11], page)
                self.assertNotIn("historical-seller", page)
                self.assertNotIn("private-owner-name", page)

    def test_single_record_legacy_summary_and_renderer_remain_compatible(self):
        record = {"receiptId": "r", "signatures": [deepcopy(original.ITEM)]}
        detail = self.project(record)
        self.assertEqual(detail["signatureStatusByPosition"], [{"position": 2, "status": "signed"}])
        detail.pop("signatureObservations")
        self.assertIn("Signed", render_detail(detail))
        self.assertNotIn('class="signature-observations"', render_detail(detail))

    def test_long_timeline_does_not_drop_second_records(self):
        record = self.record()
        record["signatures"] = []
        for position in range(40):
            for role in ("historical-seller", "historical-buyer"):
                record["signatures"].append(dict(original.ITEM, position=position, role=role,
                    payloadRef="private-payload-" + str(position) + "-" + role))
        detail = self.project(record)
        self.assertEqual(len(detail["signatureObservations"]), 80)
        self.assertTrue(all(row["status"] == "unknown" for row in detail["signatureStatusByPosition"]))
        page = render_detail(detail)
        self.assertEqual(page.count('class="signature-observations"'), 40)
        self.assertEqual(page.count(SIGNATURE_OBSERVATION_LABELS["en"] + " 2"), 40)
