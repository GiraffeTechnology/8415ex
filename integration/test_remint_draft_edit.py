"""Unsigned synthetic term edits, not signing or native execution acceptance."""
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch
import unittest

from exchange.mint_specification import MintSpecification, MintSpecificationRefused
from exchange.remint_draft_edit import edit_remint_draft, RemintDraftEditRefused
from integration.test_mint_specification_codec import specification


class RemintDraftEditTests(unittest.TestCase):
    def setUp(self):
        self.old = specification()
        self.seed = replace(self.old, receipt=replace(self.old.receipt,
            asset=replace(self.old.receipt.asset, token_id=8)))

    def edit(self, updates):
        return edit_remint_draft(self.old, self.seed, updates)

    def test_add_and_modify_full_business_clause_text_preserves_original(self):
        text = "Changed first clause.\nAdditional full clause; no summary."
        result = self.edit({"specification": {"bill_terms": text}})
        self.assertEqual(result["specification"].bill_terms, text)
        self.assertEqual(self.old.bill_terms, "Original bill terms; bill transfer only.")
        delta = next(item for item in result["changes"] if item["path"] == "/bill_terms")
        self.assertEqual(delta["old"], self.old.bill_terms)
        self.assertEqual(delta["new"], text)

    def test_optional_commodity_attribute_can_be_added_changed_and_removed(self):
        added = self.edit({"specification": {"public_attributes":
            self.old.public_attributes + (("packing", "Original packaging clause"),)}})
        edited_seed = added["specification"]
        removed = edit_remint_draft(self.old, edited_seed,
            {"specification": {"public_attributes": (("grade", "Revised grade"),)}})
        self.assertEqual(removed["specification"].public_attributes, (("grade", "Revised grade"),))
        self.assertEqual(self.old.public_attributes, (("grade", "fixture-grade"),))

    def test_new_nft_currency_terms_do_not_mutate_old_nft_currency_set(self):
        result = self.edit({"receipt": {"allowed_price_currencies": ("quote-c",),
                                        "nft0_currency_reference": "new-currency-set"}})
        self.assertEqual(result["specification"].receipt.allowed_price_currencies, ("quote-c",))
        self.assertEqual(self.old.receipt.allowed_price_currencies, ("quote-a", "quote-b"))
        self.assertEqual(self.seed.receipt.allowed_price_currencies, ("quote-a", "quote-b"))

    def test_identity_account_and_execution_fields_cannot_be_overwritten_by_editor(self):
        for updates in ({"receipt": {"asset": self.old.receipt.asset}},
                        {"receipt": {"origin_account": "untrusted-account"}},
                        {"receipt": {"receipt_id": "other"}},
                        {"specification": {"receipt": self.old.receipt}},
                        {"authorization": "approved"}, {"receipt": []}):
            with self.subTest(updates=updates), self.assertRaises(RemintDraftEditRefused):
                self.edit(updates)

    def test_original_template_and_deadline_validation_remain_in_force(self):
        for updates in ({"specification": {"public_attributes": ()}},
                        {"specification": {"registration_comparison": "UNKNOWN"}},
                        {"specification": {"registration_deadline": 999}},
                        {"specification": {"bill_terms": ""}}):
            with self.subTest(updates=updates), self.assertRaises(MintSpecificationRefused):
                self.edit(updates)

    def test_draft_does_not_call_verifier_or_present_fact_hash_as_signature(self):
        with patch.object(MintSpecification, "metadata", side_effect=AssertionError("must not verify")):
            result = self.edit({"specification": {"bill_terms": "Unsigned proposed terms"}})
        self.assertEqual(result["signature"], "NOT_REQUESTED")
        self.assertEqual(result["metadataVerification"], "NOT_PERFORMED")
        self.assertEqual(result["execution"], "NOT_RUN")
        self.assertFalse(result["executionAuthorized"])
        self.assertNotEqual(result["originalFactSHA256"], result["proposedFactSHA256"])

    def test_returned_change_records_are_detached_from_inputs_and_next_edit(self):
        updates = {"specification": {"bill_terms": "Unchanged proposed wording"}}
        before = deepcopy(updates)
        first = self.edit(updates)
        first["changes"].clear()
        second = self.edit(updates)
        self.assertTrue(second["changes"])
        self.assertEqual(updates, before)
        self.assertEqual(self.seed.bill_terms, self.old.bill_terms)

    def test_empty_edit_is_not_an_additional_authorization_or_qualification_step(self):
        result = edit_remint_draft(self.old, self.old, {})
        self.assertEqual(result["changes"], [])
        self.assertEqual(result["originalFactSHA256"], result["proposedFactSHA256"])
        self.assertEqual(result["specification"], self.old)
        self.assertEqual(result["execution"], "NOT_RUN")
