"""Synthetic declarations only; no live mint, storage or verifier evidence."""
from dataclasses import replace
import unittest

from exchange.model import Asset, WarehouseReceipt
from exchange.mint_specification import CommodityTemplate, RegistrationFormat, MintSpecification
from exchange.mint_specification_codec import encode_mint_facts, decode_mint_facts, MintFactsRefused
from exchange.operational_facts_codec import encode_operational_facts, decode_operational_facts


def specification():
    receipt = WarehouseReceipt("receipt-1", Asset(11155111, "0x" + "1" * 40, 7),
        "Fixture grain", 100, "kg", "warehouse-1", "REG_DIRECT", 200,
        "0x" + "2" * 40, 10, ("quote-a", "quote-b"), "original-currency-set")
    template = CommodityTemplate("fixture-template", "1", "fixture-grain", "fixture-standard",
                                 ("grade", "packing"), ("grade",))
    voucher = RegistrationFormat("fixture-voucher", "1", ("asset", "segment", "holder"), "REG_DIRECT")
    return MintSpecification(receipt, template, "bill-1", "issuer-1", "registrar-1",
        "fixture-location", (("grade", "fixture-grade"),), "Original bill terms; bill transfer only.",
        "document-map-1", "controlled-map-1", 180, "LTE", voucher)


class MintSpecificationCodecTests(unittest.TestCase):
    def test_complete_terms_and_original_currency_order_survive(self):
        original = specification()
        result = decode_mint_facts(encode_mint_facts(original))
        self.assertEqual(result.specification, original)
        self.assertEqual(result.specification.receipt.allowed_price_currencies, ("quote-a", "quote-b"))
        self.assertEqual(result.specification.controlled_access_mapping, "controlled-map-1")
        self.assertFalse(result.provenance_verified)
        self.assertFalse(result.execution_authorized)

    def test_lt_and_lte_keep_distinct_equality_semantics(self):
        for comparison, eligible in (("LT", False), ("LTE", True)):
            original = replace(specification(), registration_comparison=comparison)
            result = decode_mint_facts(encode_mint_facts(original)).specification
            self.assertEqual(result.registration_time_eligible(180), eligible)
            self.assertFalse(result.trade_eligible_at(200))

    def test_decoder_does_not_invoke_metadata_or_verification(self):
        from unittest.mock import patch
        raw = encode_mint_facts(specification())
        with patch.object(MintSpecification, "metadata", side_effect=AssertionError("must not verify")):
            self.assertEqual(decode_mint_facts(raw).specification.bill_of_lading_number, "bill-1")

    def test_input_and_decoded_instances_are_detached(self):
        original = specification()
        raw = encode_mint_facts(original)
        first = decode_mint_facts(raw).specification
        second = decode_mint_facts(raw).specification
        self.assertIsNot(first, original)
        self.assertIsNot(first, second)
        self.assertIsNot(first.template, second.template)
        self.assertIsNot(first.receipt, second.receipt)

    def test_unknown_fields_versions_and_missing_terms_refused(self):
        raw = encode_mint_facts(specification())
        for change in ("schema", "missing", "extra", "template-extra"):
            value = decode_operational_facts(raw).value
            if change == "schema": value["schema"] = "future-version"
            if change == "missing": del value["specification"]["bill_terms"]
            if change == "extra": value["specification"]["verifier"] = "untrusted"
            if change == "template-extra": value["specification"]["template"]["verified"] = True
            with self.subTest(change=change), self.assertRaises(MintFactsRefused):
                decode_mint_facts(encode_operational_facts(value))

    def test_original_constructor_binding_failures_refused(self):
        raw = encode_mint_facts(specification())
        for change in ("path", "deadline", "comparison", "attribute", "template"):
            value = decode_operational_facts(raw).value
            item = value["specification"]
            if change == "path": item["voucher_format"]["path"] = "different-path"
            if change == "deadline": item["registration_deadline"] = 10
            if change == "comparison": item["registration_comparison"] = "GUESS"
            if change == "attribute": item["public_attributes"] = (("undeclared", "value"),)
            if change == "template": item["template"]["required_fields"] = ("undeclared",)
            with self.subTest(change=change), self.assertRaises(MintFactsRefused):
                decode_mint_facts(encode_operational_facts(value))

    def test_malformed_or_mutable_encoded_input_refused(self):
        raw = encode_mint_facts(specification())
        for invalid in (raw[:-1], b"{}", bytearray(raw), raw.decode("ascii")):
            with self.subTest(kind=type(invalid).__name__), self.assertRaises(MintFactsRefused):
                decode_mint_facts(invalid)

    def test_non_specification_objects_refused_without_callback(self):
        for invalid in (None, {}, lambda: specification()):
            with self.assertRaises(MintFactsRefused):
                encode_mint_facts(invalid)
