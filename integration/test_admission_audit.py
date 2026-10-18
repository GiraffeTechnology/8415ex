"""Actual refusal-path definitions over explicit synthetic balances only."""
from dataclasses import replace
import unittest
from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.ledger import Exchange
from integration import test_balance_refusal_amounts as amounts


class AdmissionAudit(unittest.TestCase):
    def setUp(self):
        self.amounts = amounts.BalanceRefusalAmounts()
        self.amounts.setUp()

    def ready(self, currency=F.QUOTE_ASSET):
        clock = F.ManualClock()
        exchange = Exchange(clock, price_balance_gate=F.fixture_price_balance_gate(),
                            eth_gas_gate=F.fixture_eth_gas_gate(), mint_verifier=F.verify_fixture_mint)
        receipt = F.receipt(allowed_currencies=(currency,))
        exchange.mint(receipt, specification=F.mint_specification(receipt))
        for account, label, side, nonce in ((F.A, "a", "sell", 1), (F.B, "b", "buy", 2)):
            exchange.connect_wallet(account, "session-" + label)
            grant = F.authorization(account, "grant-" + label, "session-" + label)
            exchange.register_authorization(replace(grant, quote_asset=currency))
            exchange.submit_intent(F.intent("intent-" + label, side, account, "grant-" + label,
                                           None, nonce, quote_asset=currency))
        return exchange, exchange.match_intents("intent-a", "intent-b")

    def refused(self, exchange, match, kind, code):
        before = len(exchange.receipt_timeline(F.receipt().receipt_id))
        with self.assertRaises(DomainError) as caught:
            exchange.execute_transfer(match, "refused-transfer")
        self.assertEqual(caught.exception.code, code)
        timeline = exchange.receipt_timeline(F.receipt().receipt_id)
        self.assertEqual(len(timeline), before + 1)
        event = timeline[-1]
        self.assertEqual(event["kind"], kind)
        self.assertEqual(event["detail"]["action"], "execute-transfer")
        self.assertEqual(event["detail"]["operationReference"], "refused-transfer")
        self.assertEqual(event["detail"]["code"], code)
        self.assertFalse(event["detail"]["tradeFormed"])
        self.assertFalse(event["detail"]["financialEffects"])
        self.assertEqual(exchange.recorded_legs(F.receipt().receipt_id), 0)
        self.assertFalse(exchange._escrows)
        self.assertFalse(exchange._used_nonces)
        return event

    def test_zero_eth_records_actual_warning_before_transfer_without_a_gas_charge(self):
        exchange, match = self.ready()
        exchange._eth_gas_gate = self.amounts.gas(0, 0, 7)
        event = self.refused(exchange, match, "eth-gas-admission-refused", "EX_ETH_GAS_EMPTY")
        self.assertIn("shortfall 7 wei", event["detail"]["warning"])
        self.assertEqual(event["detail"]["nativeFinancialOutcome"], "not-asserted")

    def test_selected_principal_records_its_own_currency_refusal(self):
        exchange, match = self.ready()
        exchange._price_balance_gate = self.amounts.price(4)
        event = self.refused(exchange, match, "price-currency-admission-refused", "EX_PRICE_BALANCE_INSUFFICIENT")
        self.assertEqual(event["detail"]["currency"], F.QUOTE_ASSET)
        self.assertIn("base-units", event["detail"]["warning"])

    def test_combined_eth_refusal_is_one_record_not_two_financial_effects(self):
        exchange, match = self.ready("ETH")
        exchange._eth_gas_gate = self.amounts.gas(F.PRICE, 0, 7)
        exchange._price_balance_gate = self.amounts.price(F.PRICE)
        event = self.refused(exchange, match, "combined-eth-admission-refused", "EX_ETH_COMBINED_BALANCE_INSUFFICIENT")
        self.assertIn("shortfall 7 wei", event["detail"]["warning"])

    def test_escrow_refusal_keeps_its_original_action_and_escrow_reference(self):
        exchange, match = self.ready()
        exchange._eth_gas_gate = self.amounts.gas(0, 0, 7)
        with self.assertRaises(DomainError):
            exchange.lock_escrow(match, "original-escrow")
        event = exchange.receipt_timeline(F.receipt().receipt_id)[-1]
        self.assertEqual(event["kind"], "eth-gas-admission-refused")
        self.assertEqual((event["detail"]["action"], event["detail"]["operationReference"]),
                         ("lock-escrow", "original-escrow"))
        self.assertFalse(exchange._escrows)

    def test_nft0_currency_refusal_is_recorded_at_actual_submission(self):
        exchange, clock = F.minted()
        exchange.register_authorization(F.authorization(F.A, "grant", "session-a"))
        exchange.submit_intent(F.intent("wrong-currency", "sell", F.A, "grant", None, 4,
                                       quote_asset="other-currency"))
        event = exchange.receipt_timeline(F.receipt().receipt_id)[-1]
        self.assertEqual(event["kind"], "price-currency-admission-refused")
        self.assertEqual(event["detail"]["action"], "submit-intent")
        self.assertEqual(event["detail"]["code"], "EX_NFT0_CURRENCY_MISMATCH")

    def test_validation_and_reading_do_not_append_refusal_or_duplicate_financial_events(self):
        exchange, match = self.ready()
        exchange._eth_gas_gate = self.amounts.gas(0, 0, 7)
        self.refused(exchange, match, "eth-gas-admission-refused", "EX_ETH_GAS_EMPTY")
        before = exchange.receipt_timeline(F.receipt().receipt_id)
        exchange.validate_intent("intent-a")
        exchange.receipt_view(F.receipt().receipt_id)
        self.assertEqual(exchange.receipt_timeline(F.receipt().receipt_id), before)
