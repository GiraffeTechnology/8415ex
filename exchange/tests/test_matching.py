"""V1.4 T09/T11: independent orders, server priority and signed-limit preservation."""
import unittest

from exchange import fixtures as F
from exchange.errors import DomainError


class ServerPriorityMatching(unittest.TestCase):
    def setUp(self):
        self.exchange, self.clock = F.minted()
        self.exchange.connect_wallet(F.B, "session-b")
        for account, grant, session, other in (
                (F.A, "auth-a", "session-a", F.B),
                (F.B, "auth-b", "session-b", F.A)):
            self.exchange.register_authorization(F.authorization(
                account, grant, session, counterparties=(other,),
                max_amount=F.PRICE + 1000))

    def sell(self, name="sell-1", price=F.PRICE, nonce=1, grant="auth-a", hint=None):
        return self.exchange.submit_intent(F.intent(
            name, "sell", F.A, grant, hint, nonce, limit_price=price))

    def buy(self, name="buy-1", price=F.PRICE, nonce=1, hint=None):
        return self.exchange.submit_intent(F.intent(
            name, "buy", F.B, "auth-b", hint, nonce, limit_price=price))

    def test_each_side_submits_its_own_unpinned_order_and_both_are_recorded(self):
        sell, buy = self.sell(), self.buy(price=F.PRICE + 500)
        self.assertEqual((sell.signer, sell.side), (F.A, "sell"))
        self.assertEqual((buy.signer, buy.side), (F.B, "buy"))
        self.assertIsNone(sell.counterparty)
        self.assertIsNone(buy.counterparty)
        self.assertEqual(self.exchange.intent(sell.intent_id), sell)
        self.assertEqual(self.exchange.intent(buy.intent_id), buy)

    def test_resting_ask_sets_price_without_rewriting_either_signed_limit(self):
        sell, buy = self.sell(), self.buy(price=F.PRICE + 500)
        before = (sell.digest, buy.digest)
        match = self.exchange.match_intents(sell.intent_id, buy.intent_id)
        self.assertEqual(match.price, F.PRICE)
        self.assertEqual(match.basis["rule"], "price-time-resting-order-limit")
        self.assertEqual(match.basis["sellLimit"], str(F.PRICE))
        self.assertEqual(match.basis["buyLimit"], str(F.PRICE + 500))
        self.assertEqual(match.basis["executionPrice"], str(F.PRICE))
        self.assertLess(match.basis["askSequence"], match.basis["bidSequence"])
        self.assertEqual((self.exchange.intent(sell.intent_id).digest,
                          self.exchange.intent(buy.intent_id).digest), before)

    def test_resting_bid_sets_price_without_changing_the_arriving_ask(self):
        buy = self.buy(price=F.PRICE + 500)
        sell = self.sell()
        match = self.exchange.match_intents(sell.intent_id, buy.intent_id)
        self.assertEqual(match.price, F.PRICE + 500)
        self.assertEqual(self.exchange.intent(sell.intent_id).limit_price, F.PRICE)
        self.assertEqual(self.exchange.intent(buy.intent_id).limit_price, F.PRICE + 500)
        self.assertLess(match.basis["bidSequence"], match.basis["askSequence"])

    def test_matching_is_deterministic_at_the_same_trusted_server_observation(self):
        sell, buy = self.sell(), self.buy()
        first = self.exchange.match_intents(sell.intent_id, buy.intent_id,
                                             now=self.clock.now)
        second = self.exchange.match_intents(sell.intent_id, buy.intent_id,
                                              now=self.clock.now)
        self.assertEqual(first, second)

    def test_a_buy_limit_below_the_sell_limit_does_not_match(self):
        sell, buy = self.sell(), self.buy(price=F.PRICE - 1)
        with self.assertRaises(DomainError) as caught:
            self.exchange.match_intents(sell.intent_id, buy.intent_id)
        self.assertEqual(caught.exception.code, "EX_MATCH_UNEXECUTABLE")
        self.assertEqual(self.exchange.owner_index("rcpt-8415-0001"), 0)

    def test_no_counterparty_hint_is_needed_for_an_authorized_crossing_pair(self):
        sell, buy = self.sell(), self.buy()
        match = self.exchange.match_intents(sell.intent_id, buy.intent_id)
        self.assertEqual((match.seller, match.buyer), (F.A, F.B))
        self.assertEqual((match.sell_intent_digest, match.buy_intent_digest),
                         (sell.digest, buy.digest))

    def test_explicit_pair_hints_cannot_substitute_for_server_book_admission(self):
        sell, buy = self.sell(hint=F.B), self.buy(hint=F.A)
        with self.assertRaises(DomainError) as caught:
            self.exchange.match_intents(sell.intent_id, buy.intent_id)
        self.assertEqual(caught.exception.code, "EX_ORDER_NOT_ACCEPTED")
        self.assertEqual(self.exchange.owner_index("rcpt-8415-0001"), 0)

    def test_two_sells_do_not_match(self):
        sell = self.sell()
        self.exchange.submit_intent(F.intent(
            "sell-2", "sell", F.B, "auth-b", None, 2))
        with self.assertRaises(DomainError) as caught:
            self.exchange.match_intents(sell.intent_id, "sell-2")
        self.assertEqual(caught.exception.code, "EX_MATCH_SIDE_REFUSED")

    def test_a_quote_asset_mismatch_is_refused(self):
        sell = self.sell()
        self.exchange.submit_intent(F.intent(
            "buy-other-quote", "buy", F.B, "auth-b", None, 1,
            quote_asset="another-quote"))
        with self.assertRaises(DomainError) as caught:
            self.exchange.match_intents(sell.intent_id, "buy-other-quote")
        self.assertEqual(caught.exception.code, "EX_MATCH_QUOTE_ASSET_REFUSED")
        self.assertEqual(self.exchange.owner_index("rcpt-8415-0001"), 0)

    def test_a_match_is_not_a_registration_or_a_settlement(self):
        sell, buy = self.sell(), self.buy()
        before_legs = self.exchange.recorded_legs("rcpt-8415-0001")
        match = self.exchange.match_intents(sell.intent_id, buy.intent_id)
        self.assertEqual(match.basis["registrationAndSettlement"],
                         "not-performed-by-matching")
        self.assertEqual(self.exchange.recorded_legs("rcpt-8415-0001"), before_legs)
        self.assertEqual(self.exchange.owner_index("rcpt-8415-0001"), 0)
        self.assertEqual(self.exchange.holder_index("rcpt-8415-0001"), 0)

    def test_a_caller_cannot_choose_a_worse_price_pair(self):
        high = self.sell("ask-high", F.PRICE + 100, 1)
        low = self.sell("ask-low", F.PRICE, 2)
        buy = self.buy(price=F.PRICE + 500)
        with self.assertRaises(DomainError) as caught:
            self.exchange.match_intents(high.intent_id, buy.intent_id)
        self.assertEqual(caught.exception.code, "EX_MATCH_PRIORITY_REFUSED")
        chosen = self.exchange.match_intents(low.intent_id, buy.intent_id)
        self.assertEqual(chosen.price, F.PRICE)
        self.assertEqual(chosen.sell_intent_digest, low.digest)

    def test_equal_price_asks_preserve_server_fifo(self):
        older = self.sell("ask-older", nonce=1)
        later = self.sell("ask-later", nonce=2)
        buy = self.buy()
        with self.assertRaises(DomainError) as caught:
            self.exchange.match_intents(later.intent_id, buy.intent_id)
        self.assertEqual(caught.exception.code, "EX_MATCH_PRIORITY_REFUSED")
        chosen = self.exchange.match_intents(older.intent_id, buy.intent_id)
        self.assertEqual(chosen.sell_intent_digest, older.digest)

    def test_resting_price_must_fit_both_original_grants(self):
        buy = self.buy(price=F.PRICE + 500)
        self.exchange.register_authorization(F.authorization(
            F.A, "auth-small", "session-a", counterparties=(F.B,),
            max_amount=F.PRICE))
        sell = self.sell(grant="auth-small")
        with self.assertRaises(DomainError) as caught:
            self.exchange.match_intents(sell.intent_id, buy.intent_id)
        self.assertEqual(caught.exception.code, "EX_MATCH_UNEXECUTABLE")
        self.assertEqual(self.exchange.intent(sell.intent_id).digest, sell.digest)
        self.assertEqual(self.exchange.intent(buy.intent_id).limit_price, F.PRICE + 500)

    def test_original_counterparty_restrictions_still_apply_to_unpinned_orders(self):
        self.exchange.register_authorization(F.authorization(
            F.A, "auth-only-c", "session-a", counterparties=(F.C,),
            max_amount=F.PRICE + 1000))
        sell = self.sell(grant="auth-only-c")
        buy = self.buy()
        with self.assertRaises(DomainError) as caught:
            self.exchange.match_intents(sell.intent_id, buy.intent_id)
        self.assertEqual(caught.exception.code, "EX_MATCH_UNEXECUTABLE")
        self.assertEqual(self.exchange.owner_index("rcpt-8415-0001"), 0)


if __name__ == "__main__":
    unittest.main()
