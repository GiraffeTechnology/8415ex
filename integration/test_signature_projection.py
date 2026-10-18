"""Remote-only verifier contracts; fixtures do not prove actual signature validity."""
from copy import deepcopy
import json
import unittest
from exchange.signature_projection import signature_status
from exchange.workbench import RuntimeBinding
from integration.test_nft_detail import OriginalReadOnlyDomain


ITEM = {"position": 2, "status": "signed", "verified": True, "role": "historical-seller",
        "transferRef": "original-transfer", "payloadRef": "original-payload", "schemeRef": "original-scheme"}


def verdict(item):
    return {key: item[key] for key in ("verified", "position", "role", "transferRef", "payloadRef", "schemeRef")}


class HistoricalSignatureProjection(unittest.TestCase):
    def test_boolean_flag_or_boolean_callback_cannot_establish_signed(self):
        self.assertEqual(signature_status("r", ITEM, {}, None), "unknown")
        self.assertEqual(signature_status("r", ITEM, {}, lambda *args: True), "unknown")

    def test_original_result_must_bind_role_position_transfer_payload_and_scheme(self):
        for key, changed in (("position", 9), ("role", "current-owner"), ("transferRef", "other"),
                             ("payloadRef", "other"), ("schemeRef", "other"), ("verified", False)):
            result = dict(verdict(ITEM), **{key: changed})
            self.assertEqual(signature_status("r", ITEM, {}, lambda *args: result), "unknown")
        for key in ("role", "transferRef", "payloadRef", "schemeRef"):
            incomplete = dict(ITEM)
            del incomplete[key]
            self.assertEqual(signature_status("r", incomplete, {}, lambda *args: verdict(ITEM)), "unknown")

    def test_historical_binding_is_preserved_when_current_position_moves(self):
        original = {"receiptId": "r", "currentPosition": 20, "signatures": [deepcopy(ITEM)]}
        seen = []
        def verify(rid, item, record):
            seen.append((rid, item["position"], record["currentPosition"]))
            return verdict(item)
        binding = RuntimeBinding(OriginalReadOnlyDomain(), "r", read_details=lambda rid: original,
                                 verify_details=lambda *args: True, verify_signature=verify)
        self.assertEqual(binding.public_detail()["signatureStatusByPosition"], [{"position": 2, "status": "signed"}])
        original["currentPosition"] = 25
        self.assertEqual(binding.public_detail()["signatureStatusByPosition"], [{"position": 2, "status": "signed"}])
        self.assertEqual(seen, [("r", 2, 20), ("r", 2, 25)])

    def test_private_binding_fields_and_verifier_errors_never_reach_public_detail(self):
        record = {"receiptId": "r", "signatures": [deepcopy(ITEM)]}
        def unavailable(*args):
            raise OSError("private signer identity and resolver path")
        binding = RuntimeBinding(OriginalReadOnlyDomain(), "r", read_details=lambda rid: record,
                                 verify_details=lambda *args: True, verify_signature=unavailable)
        result = binding.public_detail()
        self.assertEqual(result["signatureStatusByPosition"], [{"position": 2, "status": "unknown"}])
        for forbidden in ("private signer", "original-payload", "historical-seller", "original-transfer", "original-scheme"):
            self.assertNotIn(forbidden, json.dumps(result))

    def test_verifier_receives_detached_record_without_changing_original(self):
        item, record = deepcopy(ITEM), {"currentPosition": 20}
        def verify(rid, detached, context):
            result = verdict(detached)
            detached["role"] = "tampered"
            context["currentPosition"] = 0
            return result
        self.assertEqual(signature_status("r", item, record, verify), "signed")
        self.assertEqual(item, ITEM)
        self.assertEqual(record, {"currentPosition": 20})

    def test_unknown_pending_unsigned_are_not_promoted_by_a_verifier(self):
        def forbidden(*args):
            raise AssertionError("no cryptographic success should be inferred")
        for state in ("unknown", "pending", "unsigned"):
            self.assertEqual(signature_status("r", dict(ITEM, status=state), {}, forbidden), state)
