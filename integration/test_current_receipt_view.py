"""Current receipt semantics; synthetic rendering is not deployed UI acceptance."""
from dataclasses import replace
import unittest

from exchange import fixtures as F, views
from exchange.ledger import Exchange


class CurrentReceiptView(unittest.TestCase):
    def test_receipt_reads_bill_contract_without_retired_eligibility_fields(self):
        exchange, _ = F.minted()
        def retired_gate(*args, **kwargs):
            raise AssertionError("retired eligibility must not gate the current page")
        exchange.redemption_readiness = retired_gate
        html = views.page(exchange, F.receipt().receipt_id, "receipt")
        self.assertIn(F.FIXTURE_BILL_TERMS, html)
        self.assertIn("NFT0 immutable allowed price currencies", html)
        self.assertIn(F.QUOTE_ASSET, html)
        self.assertIn("ETH only", html)
        self.assertIn("retired from EX", html)
        self.assertEqual(exchange.bill_of_lading_view(F.receipt().receipt_id)["prdVersion"], "1.3")

    def test_continuous_owner_holder_lag_does_not_become_a_physical_exit_gate(self):
        exchange, _ = F.chain_to_d()
        self.assertNotEqual(exchange.owner_of(F.receipt().receipt_id), exchange.holder_of(F.receipt().receipt_id))
        html = views.page(exchange, F.receipt().receipt_id, "receipt")
        self.assertIn("owner and holder need not agree", html)
        self.assertIn("requires holder possession and holder = owner", html)
        self.assertNotIn("necessary condition", html)
        self.assertNotIn("Further checks not performed here", html)

    def test_bill_terms_are_rendered_as_text_not_executable_markup(self):
        clock = F.ManualClock()
        exchange = Exchange(clock, mint_verifier=F.verify_fixture_mint)
        receipt = F.receipt()
        specification = replace(F.mint_specification(receipt), bill_terms="<script>untrusted()</script>")
        exchange.mint(receipt, specification=specification)
        html = views.page(exchange, receipt.receipt_id, "receipt")
        self.assertIn("&lt;script&gt;untrusted()&lt;/script&gt;", html)
        self.assertNotIn("<script>untrusted()", html)
