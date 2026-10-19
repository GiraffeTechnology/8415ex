"""Synthetic codec regression definitions, not native reconciliation evidence."""
from dataclasses import replace
import json
import unittest

from exchange.fixtures import A, B, asset
from exchange.ledger import Transfer
from exchange.operational_facts_codec import (
    MAX_BYTES, OperationalFactsRefused, decode_operational_facts, encode_operational_facts,
)
from exchange.registration import RegistrationEvidence, RegistrationRequest
from exchange.rollback import RollbackStep
from exchange.settlement import EscrowPosition


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


class OperationalFactsCodecTests(unittest.TestCase):
    def escrow(self):
        return EscrowPosition("escrow-1", "receipt-1", 0, B, A, "USD", 2 ** 128 + 1,
                              payment_key="original-1", payment_status="unknown",
                              payment_intent="release", gas_record=({"amount": 17, "asset": "ETH"},))

    def test_transfer_keeps_registration_funding_and_rollback_dimensions_separate(self):
        original = Transfer("transfer-1", "receipt-1", 0, A, B, None, 101, "USD",
                            "0x" + "1" * 64, "0x" + "2" * 64, "sell-auth", "buy-auth", 10,
                            registration_status="confirmed", funding_status="release-outcome-unknown",
                            rollback_status="detached")
        decoded = decode_operational_facts(encode_operational_facts(original)).value
        self.assertEqual(decoded, original)
        self.assertEqual(decoded.registration_status, "confirmed")
        self.assertEqual(decoded.funding_status, "release-outcome-unknown")
        self.assertEqual(decoded.rollback_status, "detached")

    def test_unknown_release_and_refund_terms_are_preserved_without_dispatch(self):
        for intent in ("release", "refund"):
            original = replace(self.escrow(), payment_intent=intent)
            result = decode_operational_facts(encode_operational_facts(original))
            self.assertEqual(result.value, original)
            self.assertEqual(result.value.payment_status, "unknown")
            self.assertFalse(result.execution_authorized)
            self.assertFalse(result.value.terminal)

    def test_registrar_identity_digest_and_simulated_flag_round_trip(self):
        request = RegistrationRequest("req-1", "receipt-1", "transfer-1", 0, None,
                                      "REG_DIRECT", asset(), 10, 50, attempt=2)
        evidence = RegistrationEvidence("result-1", "req-1", "receipt-1", "transfer-1", 0,
                                        "REG_DIRECT", "original-source", "confirmed", asset(),
                                        20, result_version=3, record_commitment="record-1", simulated=False)
        decoded = decode_operational_facts(encode_operational_facts((request, evidence))).value
        self.assertEqual(decoded, (request, evidence))
        self.assertEqual(decoded[0].content_digest, request.content_digest)
        self.assertEqual(decoded[1].content_digest, evidence.content_digest)
        self.assertFalse(decoded[1].simulated)

    def test_nonce_keys_container_types_and_blocked_steps_survive(self):
        step = RollbackStep("step-1", "refund", "receipt-1", 0, "original-key", "blocked",
                            (("reason", "UNKNOWN"),))
        original = {("receipt-1", 0): [step], "nonces": {(A, 7), (B, 8)},
                    "trustedSources": frozenset(("source-1",)), "ordered": (None, True, 0)}
        decoded = decode_operational_facts(encode_operational_facts(original)).value
        self.assertEqual(decoded, original)
        self.assertIs(type(decoded["nonces"]), set)
        self.assertIs(type(decoded["trustedSources"]), frozenset)
        self.assertIs(type(decoded["ordered"]), tuple)
        self.assertEqual(decoded[("receipt-1", 0)][0].status, "blocked")

    def test_constructor_validation_and_unknown_fields_or_classes_refused(self):
        raw = encode_operational_facts(self.escrow())
        for mutation in ("field", "tag", "status"):
            value = json.loads(raw)
            if mutation == "field": value["value"]["fields"]["futureField"] = None
            if mutation == "tag": value["value"]["kind"] = "some.module.Executable"
            if mutation == "status": value["value"]["fields"]["status"] = "invented"
            with self.subTest(mutation=mutation), self.assertRaises(OperationalFactsRefused):
                decode_operational_facts(canonical(value))
        with self.assertRaises(OperationalFactsRefused):
            encode_operational_facts(lambda: None)

    def test_duplicate_maps_sets_and_noncanonical_order_refused(self):
        raw = encode_operational_facts({"a": 1, "b": 2})
        for mutation in ("duplicate", "order"):
            value = json.loads(raw)
            if mutation == "duplicate": value["value"]["items"].append(value["value"]["items"][0])
            else: value["value"]["items"].reverse()
            with self.subTest(mutation=mutation), self.assertRaises(OperationalFactsRefused):
                decode_operational_facts(canonical(value))
        value = json.loads(encode_operational_facts({1, 2}))
        value["value"]["items"].append(1)
        with self.assertRaises(OperationalFactsRefused):
            decode_operational_facts(canonical(value))

    def test_bounds_cycles_floats_and_malformed_bytes_refused(self):
        cycle = []; cycle.append(cycle)
        for value in (cycle, 1.5, b"unregistered-bytes"):
            with self.subTest(kind=type(value)), self.assertRaises(OperationalFactsRefused):
                encode_operational_facts(value)
        for raw in (b"x" * (MAX_BYTES + 1), b'{"schema":NaN}', b"\xff", b"{}\n"):
            with self.subTest(kind=type(raw)), self.assertRaises(OperationalFactsRefused):
                decode_operational_facts(raw)
