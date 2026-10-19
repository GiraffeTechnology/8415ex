"""Current receipt semantics; synthetic source fixtures are not deployment evidence."""
from copy import deepcopy
from dataclasses import replace
from html import escape
import unittest

from exchange import fixtures as F, views
from exchange.ledger import Exchange
from exchange.nft_detail import receipt_detail


class CurrentReceiptView(unittest.TestCase):
    def projected_page(self, exchange, receipt_id, *, bill_terms=F.FIXTURE_BILL_TERMS):
        clauses = [
            {"label": "Original business obligations", "text": bill_terms},
            {"label": "NFT0 immutable allowed price currencies",
             "text": "Only the unchanged NFT0 currency set may price this NFT; EX provides no conversion."},
            {"label": "Separate gas", "text": "ETH only; gas remains separate from the purchase price."},
            {"label": "EX scope", "text": "Physical collection and physical-exit burning are retired from EX."},
        ]
        original = {"receiptId": receipt_id, "businessTerms": {
            "coverageVerified": True, "identityExcluded": True, "clauses": clauses}}
        def read(requested):
            self.assertEqual(requested, receipt_id)
            return deepcopy(original)
        return views.receipt_page(exchange, receipt_id, read_details=read,
            verify_details=lambda requested, row: requested == receipt_id and row == original)

    def test_receipt_reads_verified_bill_projection_without_retired_eligibility_fields(self):
        exchange, _ = F.minted()
        receipt_id = F.receipt().receipt_id
        before = deepcopy(exchange.bill_of_lading_view(receipt_id))
        def retired_gate(*args, **kwargs):
            raise AssertionError("retired eligibility must not gate the current page")
        exchange.redemption_readiness = retired_gate
        html = self.projected_page(exchange, receipt_id)
        self.assertIn(escape(F.FIXTURE_BILL_TERMS), html)
        self.assertIn("NFT0 immutable allowed price currencies", html)
        self.assertIn("ETH only", html)
        self.assertIn("retired from EX", html)
        self.assertIn("Identity-excluding business projection", html)
        self.assertEqual(exchange.bill_of_lading_view(receipt_id), before)

    def test_continuous_owner_holder_lag_does_not_become_a_physical_exit_gate(self):
        exchange, _ = F.chain_to_d()
        receipt_id = F.receipt().receipt_id
        self.assertNotEqual(exchange.owner_of(receipt_id), exchange.holder_of(receipt_id))
        html = self.projected_page(exchange, receipt_id)
        self.assertIn("openGapOF=YES does not block normal continuous trading.", html)
        self.assertIn("On-chain Owner position", html)
        self.assertIn("Registered Holder position", html)
        ordinary = receipt_detail(exchange, receipt_id)["ordinaryTransfer"]
        self.assertFalse(ordinary["gapEqualityFinalityGateApplied"])
        self.assertEqual(ordinary["executionEligibility"], "not-evaluated")
        self.assertNotIn("necessary condition", html)
        self.assertNotIn("Further checks not performed here", html)

    def test_bill_terms_are_rendered_as_text_not_executable_markup(self):
        clock = F.ManualClock()
        exchange = Exchange(clock, mint_verifier=F.verify_fixture_mint)
        receipt = F.receipt()
        specification = replace(F.mint_specification(receipt), bill_terms="<script>untrusted()</script>")
        exchange.mint(receipt, specification=specification)
        original = deepcopy(exchange.receipt_view(receipt.receipt_id)["mintDeclaration"])
        html = self.projected_page(exchange, receipt.receipt_id, bill_terms=specification.bill_terms)
        self.assertIn("&lt;script&gt;untrusted()&lt;/script&gt;", html)
        self.assertNotIn("<script>untrusted()", html)
        self.assertEqual(exchange.receipt_view(receipt.receipt_id)["mintDeclaration"], original)
        self.assertEqual(original["canonicalDeclaration"]["billTerms"], specification.bill_terms)

    def test_unbound_page_does_not_fall_back_to_the_private_mint_document(self):
        exchange, _ = F.minted()
        html = views.page(exchange, F.receipt().receipt_id, "receipt")
        self.assertIn("Original terms not provided; completeness cannot be verified.", html)
        self.assertNotIn(escape(F.FIXTURE_BILL_TERMS), html)
