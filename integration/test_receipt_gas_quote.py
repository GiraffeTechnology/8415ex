"""Synthetic receipt-to-quote-to-page composition; no live funds or provider."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from html import escape
import unittest

from exchange.gas_budget import GasBudgetRefused
from exchange.gas_confirmation_ui import GasConfirmationPage
from exchange.gas_disclosure_locales import WORDS
from exchange.original_gas_receipt_reader import OriginalGasReceiptReader
from exchange.receipt_gas_quote import quote_from_original_receipts
from integration import test_receipt_fee_samples as receipts
from integration import test_original_gas_receipt_reader as original_reader


class OriginalReceiptGasQuoteContracts(unittest.TestCase):
    def setUp(self):
        self.values = receipts.population()
        self.fields = dict(quote_id="original-quote", version=1,
            budget_id="original-budget", scope="original-transfer-scope",
            actions=("transfer",), chain_id=11155111, cap_wei=100000,
            window_start=90, window_end=99, quoted_at=100, valid_until=200,
            usd_micro_per_eth=3000000000, rate_observed_at=100,
            rate_source="original-fx-source", rate_sha256="c"*64)
        self.verified = []

    def quote(self, verify=None):
        if verify is None:
            verify = lambda binding:self.verified.append(deepcopy(binding)) or True
        return quote_from_original_receipts(self.values,
            original_quote_fields=self.fields, verify_applicability=verify)

    def test_explicit_cap_and_complete_failed_success_population_reach_existing_p50(self):
        quote = self.quote()
        self.assertEqual(quote.cap_wei, 100000)
        self.assertEqual(quote.median_wei, Fraction(73500))
        self.assertEqual(tuple(sample.fee_wei for sample in quote.samples), (63000,84000))
        self.assertEqual(len(self.verified), 1)
        self.assertEqual(self.verified[0]["population"][1]["observation"]["outcome"], "FAILED")
        self.assertEqual(quote.actions, ("transfer",))
        self.assertEqual(quote.disclosure()["window"], [90,99])

    def test_six_locale_page_discloses_exact_receipt_samples_without_confirmation_or_private_proof(self):
        quote = self.quote()
        confirmations = []
        page = GasConfirmationPage(lambda:quote, lambda *args:confirmations.append(args),
            "PRIVATE-BUYER", "PRIVATE-ACTION", "PRIVATE-GRANT", "/gas-confirm",
            lambda value:True)
        before = deepcopy((self.values,self.fields))
        for locale, words in WORDS.items():
            body = page.render(110, "synthetic-csrf", locale)
            self.assertIn(escape(words["heading"]), body)
            self.assertIn(escape(words["median"]), body)
            self.assertIn("sorted-P50-middle-or-two-middle-mean", body)
            self.assertIn("63000", body)
            self.assertIn("84000", body)
            for private in ("PRIVATE-BUYER","PRIVATE-ACTION","PRIVATE-GRANT",
                            "private-attempt-1","private-proof-1"):
                self.assertNotIn(private, body)
        self.assertEqual(confirmations, [])
        self.assertEqual((self.values,self.fields),before)

    def test_cap_below_p50_is_not_raised_and_invalid_original_rate_is_not_replaced(self):
        self.fields["cap_wei"] = 70000
        before = deepcopy(self.fields)
        with self.assertRaises(GasBudgetRefused):
            self.quote()
        self.assertEqual(self.fields,before)
        self.fields["cap_wei"] = 100000
        self.fields["usd_micro_per_eth"] = 0
        with self.assertRaises(GasBudgetRefused):
            self.quote()
        self.assertEqual(self.fields["usd_micro_per_eth"],0)

    def test_missing_extra_foreign_chain_and_address_labels_refuse_without_population_verification(self):
        baseline = deepcopy(self.fields)
        for change in ("missing","samples","chain","label","actions"):
            self.fields = deepcopy(baseline)
            if change == "missing":
                del self.fields["cap_wei"]
            elif change == "samples":
                self.fields["samples"] = ()
            elif change == "chain":
                self.fields["chain_id"] = 560048
            elif change == "label":
                self.fields["rate_source"] = "0x"+"a"*40
            else:
                self.fields["actions"] = ["transfer"]
            with self.subTest(change=change), self.assertRaises(GasBudgetRefused):
                self.quote()
        self.assertEqual(self.verified,[])

    def test_verifier_cannot_mutate_captured_quote_fields_or_receipt_amounts(self):
        before = deepcopy(self.values)
        def verify(binding):
            self.fields["cap_wei"] = 1
            self.fields["actions"] = ("other-action",)
            binding["population"][0]["sample"]["fee_wei"] = 0
            return True
        quote = self.quote(verify)
        self.assertEqual(quote.cap_wei,100000)
        self.assertEqual(quote.actions,("transfer",))
        self.assertEqual(quote.median_wei,Fraction(73500))
        self.assertEqual(self.values,before)

    def test_unavailable_population_is_not_fabricated_as_zero_or_echoed_into_quote(self):
        for result in (False,None,1):
            with self.subTest(result=result), self.assertRaises(GasBudgetRefused):
                self.quote(lambda binding:result)
        def unavailable(binding):
            raise RuntimeError("PRIVATE-POPULATION-SOURCE")
        with self.assertRaises(GasBudgetRefused) as raised:
            self.quote(unavailable)
        self.assertNotIn("PRIVATE-POPULATION-SOURCE",str(raised.exception))
        self.values = []
        with self.assertRaises(GasBudgetRefused):
            self.quote()

    def test_half_wei_p50_remains_exact_and_never_rounds_the_explicit_cap(self):
        self.values[1]["observation"] = replace(self.values[1]["observation"],
            gas_used=1,effective_gas_price=63001,actual_wei=63001)
        quote = self.quote()
        self.assertEqual(quote.median_wei,Fraction(126001,2))
        self.assertEqual(quote.cap_wei,100000)
        self.assertEqual(quote.disclosure()["median"]["ETH"],"0.0000000000000630005")

    def test_original_observed_failed_receipt_reaches_disclosure_without_more_rpc(self):
        rpc = original_reader.RpcFixture(original_reader.sequence())
        observed = OriginalGasReceiptReader(rpc,lambda evidence:True).read(
            attempt_id="original-fixture-attempt",transaction_hash=original_reader.TX,
            proof_reference="original-fixture-proof")
        calls = deepcopy(rpc.calls)
        self.values[0]["observation"] = observed
        quote = self.quote()
        self.assertEqual(observed.outcome,"FAILED")
        self.assertEqual(quote.samples[0].fee_wei,observed.actual_wei)
        self.assertEqual(quote.disclosure()["sampleCount"],2)
        self.assertEqual(rpc.calls,calls)
