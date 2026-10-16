"""T-09: both sides order independently; the pairing fixture changes nothing."""
import unittest

from exchange import fixtures as F
from exchange.errors import DomainError


class ExplicitPairing(unittest.TestCase):

    def setUp(self):
        self.exchange, _ = F.minted()
        self.exchange.connect_wallet(F.B, "session-b")
        self.exchange.register_authorization(
            F.authorization(F.A, "auth-a", "session-a", counterparties=(F.B,)))
        # B's grant deliberately allows more than the fixture price, so a higher
        # buy limit is tested against the pairing rule and not against the bound.
        self.exchange.register_authorization(
            F.authorization(F.B, "auth-b", "session-b", counterparties=(F.A,),
                            max_amount=F.PRICE + 500))

    def test_each_side_submits_its_own_order_and_both_are_recorded(self):
        sell = self.exchange.submit_intent(F.intent("sell-1", "sell", F.A, "auth-a", F.B, 1))
        buy = self.exchange.submit_intent(F.intent("buy-1", "buy", F.B, "auth-b", F.A, 1,
                                                   limit_price=F.PRICE + 500))
        self.assertEqual(self.exchange.intent("sell-1").signer, F.A)
        self.assertEqual(self.exchange.intent("buy-1").signer, F.B)
        self.assertEqual(sell.side, "sell")
        self.assertEqual(buy.side, "buy")

    def test_matching_reports_its_basis_and_leaves_both_limits_untouched(self):
        sell = self.exchange.submit_intent(F.intent("sell-1", "sell", F.A, "auth-a", F.B, 1))
        buy = self.exchange.submit_intent(F.intent("buy-1", "buy", F.B, "auth-b", F.A, 1,
                                                   limit_price=F.PRICE + 500))
        before = (sell.digest, buy.digest)
        match = self.exchange.match_intents("sell-1", "buy-1")
        self.assertEqual(match.basis["sellLimit"], str(F.PRICE))
        self.assertEqual(match.basis["buyLimit"], str(F.PRICE + 500))
        self.assertEqual(match.basis["executionPrice"], str(F.PRICE))
        self.assertEqual(match.basis["rule"], "explicit-pairing-limit-fixture")
        self.assertEqual((self.exchange.intent("sell-1").digest,
                          self.exchange.intent("buy-1").digest), before,
                         "matching must not rewrite a signed term")
        self.assertEqual(self.exchange.intent("buy-1").limit_price, F.PRICE + 500)

    def test_matching_is_deterministic(self):
        self.exchange.submit_intent(F.intent("sell-1", "sell", F.A, "auth-a", F.B, 1))
        self.exchange.submit_intent(F.intent("buy-1", "buy", F.B, "auth-b", F.A, 1))
        first = self.exchange.match_intents("sell-1", "buy-1", now=1_700_000_000)
        second = self.exchange.match_intents("sell-1", "buy-1", now=1_700_000_000)
        self.assertEqual(first, second)

    def test_a_buy_limit_below_the_sell_limit_does_not_match(self):
        self.exchange.submit_intent(F.intent("sell-1", "sell", F.A, "auth-a", F.B, 1))
        self.exchange.submit_intent(F.intent("buy-low", "buy", F.B, "auth-b", F.A, 1,
                                             limit_price=F.PRICE - 1))
        with self.assertRaises(DomainError) as caught:
            self.exchange.match_intents("sell-1", "buy-low")
        self.assertEqual(caught.exception.code, "EX_MATCH_PRICE_REFUSED")

    def test_an_unpaired_intent_is_refused_rather_than_matched_loosely(self):
        self.exchange.submit_intent(F.intent("sell-open", "sell", F.A, "auth-a", None, 1))
        self.exchange.submit_intent(F.intent("buy-1", "buy", F.B, "auth-b", F.A, 1))
        with self.assertRaises(DomainError) as caught:
            self.exchange.match_intents("sell-open", "buy-1")
        self.assertEqual(caught.exception.code, "EX_MATCH_PAIRING_REFUSED")

    def test_a_pairing_naming_a_third_party_is_refused(self):
        self.exchange.submit_intent(F.intent("sell-to-c", "sell", F.A, "auth-a", F.C, 1))
        self.exchange.submit_intent(F.intent("buy-1", "buy", F.B, "auth-b", F.A, 1))
        with self.assertRaises(DomainError) as caught:
            self.exchange.match_intents("sell-to-c", "buy-1")
        self.assertEqual(caught.exception.code, "EX_MATCH_PAIRING_REFUSED")

    def test_two_sells_do_not_match(self):
        self.exchange.submit_intent(F.intent("sell-1", "sell", F.A, "auth-a", F.B, 1))
        self.exchange.submit_intent(F.intent("sell-2", "sell", F.B, "auth-b", F.A, 2))
        with self.assertRaises(DomainError) as caught:
            self.exchange.match_intents("sell-1", "sell-2")
        self.assertEqual(caught.exception.code, "EX_MATCH_SIDE_REFUSED")

    def test_a_quote_asset_mismatch_is_refused(self):
        from exchange.model import TradeIntent
        self.exchange.submit_intent(F.intent("sell-1", "sell", F.A, "auth-a", F.B, 1))
        other = TradeIntent(intent_id="buy-other-quote", side="buy", signer=F.B, asset=F.asset(),
                            limit_price=F.PRICE, quote_asset="another-quote", units=1, nonce=1,
                            expires_at=1_700_800_000, authorization_id="auth-b", counterparty=F.A)
        self.exchange.submit_intent(other)
        with self.assertRaises(DomainError) as caught:
            self.exchange.match_intents("sell-1", "buy-other-quote")
        self.assertEqual(caught.exception.code, "EX_MATCH_QUOTE_ASSET_REFUSED")

    def test_a_match_is_not_a_registration_or_a_settlement(self):
        self.exchange.submit_intent(F.intent("sell-1", "sell", F.A, "auth-a", F.B, 1))
        self.exchange.submit_intent(F.intent("buy-1", "buy", F.B, "auth-b", F.A, 1))
        match = self.exchange.match_intents("sell-1", "buy-1")
        self.assertEqual(match.basis["registrationAndSettlement"], "not-performed-by-matching")
        self.assertEqual(self.exchange.owner_index("rcpt-8415-0001"), 0,
                         "a match alone moves no position")
        self.assertEqual(self.exchange.holder_index("rcpt-8415-0001"), 0)


if __name__ == "__main__":
    unittest.main()
