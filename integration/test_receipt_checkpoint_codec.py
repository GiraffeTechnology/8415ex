"""Synthetic definitions only; no live registry, wallet or database is used."""
from dataclasses import replace
import json
import unittest

from exchange.fixtures import receipt
from exchange.model import Asset
from exchange.receipt_checkpoint_codec import (
    MAX_BYTES, ReceiptCheckpointRefused, decode_receipt_facts, encode_receipt_facts,
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


class ReceiptCheckpointCodecTests(unittest.TestCase):
    def test_all_declaration_fields_and_currency_order_round_trip(self):
        original = replace(receipt(allowed_currencies=("USD", "ETH")),
                           commodity_name="Original \u4ed3\u5355", commodity_quantity=17)
        raw = encode_receipt_facts(original)
        recovered = decode_receipt_facts(raw)
        self.assertEqual(recovered.receipt, original)
        self.assertEqual(recovered.receipt.allowed_price_currencies, ("USD", "ETH"))
        self.assertFalse(recovered.execution_authorized)
        self.assertEqual(encode_receipt_facts(recovered.receipt), raw)

    def test_optional_and_legacy_empty_currency_facts_are_not_invented(self):
        original = replace(receipt(), allowed_price_currencies=(), nft0_currency_reference=None)
        decoded = decode_receipt_facts(encode_receipt_facts(original))
        self.assertEqual(decoded.receipt, original)
        self.assertFalse(decoded.execution_authorized)
        self.assertEqual(decoded.receipt.allowed_price_currencies, ())

    def test_large_token_and_quantity_remain_exact_integers(self):
        original = replace(receipt(), asset=Asset(11155111, "0x" + "1" * 40, 2 ** 255 + 19),
                           commodity_quantity=2 ** 128 + 11)
        self.assertEqual(decode_receipt_facts(encode_receipt_facts(original)).receipt, original)

    def test_unknown_missing_version_and_duplicate_fields_are_refused(self):
        raw = encode_receipt_facts(receipt())
        base = json.loads(raw)
        cases = []
        value = json.loads(raw); value["schema"] = "8415ex-receipt-facts/2"; cases.append(canonical(value))
        value = json.loads(raw); value["receipt"]["holder"] = "invented"; cases.append(canonical(value))
        value = json.loads(raw); del value["receipt"]["nft0_currency_reference"]; cases.append(canonical(value))
        cases.append(raw[:-1] + b',"schema":"8415ex-receipt-facts/1"}')
        for invalid in cases:
            with self.subTest(invalid=invalid), self.assertRaises(ReceiptCheckpointRefused):
                decode_receipt_facts(invalid)
        self.assertEqual(base["schema"], "8415ex-receipt-facts/1")

    def test_invalid_domain_boolean_float_and_currency_duplicates_refused(self):
        raw = encode_receipt_facts(receipt())
        for key, invalid in (("commodity_quantity", True), ("commodity_quantity", 1.0),
                             ("trade_stop_at", 0), ("registration_path", "INVENTED"),
                             ("allowed_price_currencies", ["ETH", "ETH"])):
            value = json.loads(raw); value["receipt"][key] = invalid
            with self.subTest(key=key, invalid=invalid), self.assertRaises(ReceiptCheckpointRefused):
                decode_receipt_facts(canonical(value))

    def test_noncanonical_oversize_mutable_and_truncated_inputs_refused(self):
        raw = encode_receipt_facts(receipt())
        for invalid in (raw + b"\n", bytearray(raw), raw[:-1], b"x" * (MAX_BYTES + 1),
                        b'{"schema":NaN}', b"\xff"):
            with self.subTest(kind=type(invalid)), self.assertRaises(ReceiptCheckpointRefused):
                decode_receipt_facts(invalid)
