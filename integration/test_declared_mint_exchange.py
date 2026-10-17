"""Declared mint integration; synthetic model checks, no actual NFT or Oracle."""
import copy
import unittest
from dataclasses import replace

from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.ledger import Exchange
from exchange.mint_specification import MintSpecificationRefused


class DeclaredMintIntegration(unittest.TestCase):
    def test_bare_receipt_is_no_longer_a_complete_mint_input(self):
        exchange = Exchange(F.ManualClock())
        with self.assertRaises(DomainError) as caught:
            exchange.mint(F.receipt())
        self.assertEqual(caught.exception.code, "EX_MINT_DECLARATION_REQUIRED")
        self.assertEqual(exchange._receipts, {})

    def test_external_verification_is_mandatory_and_failure_leaves_no_asset(self):
        receipt = F.receipt()
        spec = F.mint_specification(receipt)
        for verifier in (None, lambda kind, value: False):
            exchange = Exchange(F.ManualClock(), mint_verifier=verifier)
            with self.assertRaises((DomainError, MintSpecificationRefused)):
                exchange.mint(receipt, specification=spec)
            self.assertEqual(exchange._receipts, {})
            self.assertEqual(exchange._asset_keys, {})

    def test_complete_declaration_is_bound_to_original_receipt_and_view(self):
        exchange, clock = F.minted()
        view = exchange.bill_of_lading_view("rcpt-8415-0001")["receipt"]
        declaration = view["mintDeclaration"]
        self.assertEqual(declaration["canonicalDeclaration"]["receipt"]["receipt_id"], view["receiptId"])
        self.assertEqual(declaration["canonicalDeclaration"]["billTerms"], F.FIXTURE_BILL_TERMS)
        self.assertEqual(declaration["mint"], "NOT_RUN")
        self.assertEqual(declaration["assetValidity"], "NOT_ATTESTED")
        declaration["canonicalDeclaration"]["billTerms"] = "mutated caller copy"
        self.assertEqual(exchange.receipt_view(view["receiptId"])["mintDeclaration"]
                         ["canonicalDeclaration"]["billTerms"], F.FIXTURE_BILL_TERMS)

    def test_substituted_declaration_does_not_reserve_or_mint_receipt(self):
        receipt = F.receipt()
        other = replace(receipt, receipt_id="different-receipt")
        exchange = Exchange(F.ManualClock(), mint_verifier=F.verify_fixture_mint)
        with self.assertRaises(DomainError) as caught:
            exchange.mint(receipt, specification=F.mint_specification(other))
        self.assertEqual(caught.exception.code, "EX_MINT_DECLARATION_BINDING_REFUSED")
        self.assertEqual(exchange._receipts, {})

    def test_duplicate_underlying_document_is_refused_by_original_mint_path(self):
        exchange, clock = F.minted()
        other = replace(F.receipt(), receipt_id="receipt-2",
                        asset=replace(F.asset(), token_id=8416))
        with self.assertRaises(MintSpecificationRefused):
            exchange.mint(other, specification=F.mint_specification(other))
        self.assertNotIn(other.receipt_id, exchange._receipts)

