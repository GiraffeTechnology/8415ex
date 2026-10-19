"""v1.3 immutable allowed currencies; model evidence only, never chain evidence."""
from dataclasses import FrozenInstanceError, replace
import unittest
from exchange import fixtures as F
from exchange.ledger import Exchange
from exchange.errors import DomainError

R = "rcpt-8415-0001"
OTHER = "synthetic-second-currency"


class NFT0AllowedCurrencies(unittest.TestCase):
    def exchange(self, currencies=(F.QUOTE_ASSET, OTHER), verifier=None):
        clock = F.ManualClock()
        ex = Exchange(clock, mint_verifier=verifier or F.verify_fixture_mint,
                      eth_gas_gate=F.fixture_eth_gas_gate(),
                      price_balance_gate=F.fixture_price_balance_gate())
        receipt = F.receipt(allowed_currencies=currencies)
        ex.mint(receipt, F.mint_specification(receipt))
        return ex

    def order(self, ex, key, side, actor, price, currency, nonce):
        session = "session-" + actor[-1]
        ex.connect_wallet(actor, session)
        auth = replace(F.authorization(actor, "auth-" + key, session), quote_asset=currency)
        ex.register_authorization(auth)
        return ex.submit_intent(F.intent(key, side, actor, auth.authorization_id, None, nonce,
                                         limit_price=price, quote_asset=currency))

    def test_one_and_multiple_currencies_are_preserved_without_default_selection(self):
        for currencies in ((F.QUOTE_ASSET,), (F.QUOTE_ASSET, OTHER)):
            ex = self.exchange(currencies)
            view = ex.receipt_view(R)
            self.assertEqual(view["allowedPriceCurrencies"], currencies)
            self.assertEqual(view["nft0CurrencyReference"], F.NFT0_CURRENCY_SET_REF)
            self.assertFalse(view["conversionAvailable"])
            self.assertNotIn("selectedPriceCurrency", view)

    def test_minted_currency_tuple_and_reference_are_immutable(self):
        ex = self.exchange()
        receipt = ex.receipt(R)
        with self.assertRaises(FrozenInstanceError):
            receipt.allowed_price_currencies = (OTHER,)
        ex._receipts[R] = replace(receipt, allowed_price_currencies=(OTHER,))
        order = self.order(ex, "changed-set", "buy", F.B, 100, OTHER, 1)
        report = ex.validate_intent(order.intent_id)
        self.assertIn("EX_NFT0_CURRENCY_IMMUTABILITY_REFUSED", report["reasons"])

    def test_outside_currency_is_not_accepted_or_converted(self):
        ex = self.exchange()
        order = self.order(ex, "outside", "buy", F.B, 100, "not-allowed", 1)
        self.assertIn("EX_NFT0_CURRENCY_MISMATCH", ex.validate_intent(order.intent_id)["reasons"])
        self.assertNotIn((R, "not-allowed"), ex._order_books)

    def test_both_sides_must_explicitly_select_the_same_currency(self):
        ex = self.exchange()
        sell = self.order(ex, "ask-one", "sell", F.A, 100, F.QUOTE_ASSET, 1)
        buy = self.order(ex, "bid-two", "buy", F.B, 100, OTHER, 1)
        with self.assertRaises(DomainError) as caught:
            ex.match_intents(sell.intent_id, buy.intent_id)
        self.assertEqual(caught.exception.code, "EX_MATCH_QUOTE_ASSET_REFUSED")

    def test_each_currency_has_independent_price_fifo_priority(self):
        ex = self.exchange()
        one_sell = self.order(ex, "ask-one", "sell", F.A, 100, F.QUOTE_ASSET, 1)
        two_sell = self.order(ex, "ask-two", "sell", F.A, 1, OTHER, 2)
        one_buy = self.order(ex, "bid-one", "buy", F.B, 110, F.QUOTE_ASSET, 1)
        two_buy = self.order(ex, "bid-two", "buy", F.C, 999, OTHER, 1)
        match = ex.match_intents(one_sell.intent_id, one_buy.intent_id)
        self.assertEqual((match.buyer, match.price, match.quote_asset), (F.B, 100, F.QUOTE_ASSET))
        other = ex.match_intents(two_sell.intent_id, two_buy.intent_id)
        self.assertEqual((other.buyer, other.price, other.quote_asset), (F.C, 1, OTHER))

    def test_signed_order_binds_original_currency_set_reference(self):
        ex = self.exchange()
        order = self.order(ex, "bound", "buy", F.B, 100, F.QUOTE_ASSET, 1)
        changed = replace(order, intent_id="missing-reference", currency_set_reference=None)
        self.assertNotEqual(order.digest, changed.digest)
        ex.submit_intent(changed)
        self.assertIn("EX_NFT0_CURRENCY_REFERENCE_REFUSED",
                      ex.validate_intent(changed.intent_id)["reasons"])

    def test_currency_schema_verification_is_required_before_mint_admission(self):
        def verifier(kind, evidence):
            return kind != "existing-nft0-currency-schema" and F.verify_fixture_mint(kind, evidence)
        with self.assertRaises(ValueError):
            self.exchange(verifier=verifier)

    def test_regular_resale_does_not_require_holder_to_catch_owner(self):
        ex = self.exchange()
        sell = self.order(ex, "sell-ab", "sell", F.A, 100, F.QUOTE_ASSET, 1)
        buy = self.order(ex, "buy-ab", "buy", F.B, 100, F.QUOTE_ASSET, 1)
        ex.execute_transfer(ex.match_intents(sell.intent_id, buy.intent_id), "transfer-ab")
        self.assertEqual((ex.owner_of(R), ex.holder_of(R)), (F.B, F.A))
        sell = self.order(ex, "sell-bc", "sell", F.B, 110, OTHER, 2)
        buy = self.order(ex, "buy-bc", "buy", F.C, 110, OTHER, 1)
        ex.execute_transfer(ex.match_intents(sell.intent_id, buy.intent_id), "transfer-bc")
        self.assertEqual((ex.owner_of(R), ex.holder_of(R)), (F.C, F.A))
