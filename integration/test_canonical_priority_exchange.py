"""Canonical price/time matching; local fixtures do not attest funds or chain."""
import unittest
from dataclasses import replace
from exchange import fixtures as F
from exchange.errors import DomainError


class CanonicalPriority(unittest.TestCase):
    def setUp(self):
        self.exchange, self.clock = F.minted()

    def order(self, name, side, account, price, nonce=1, counterparties=()):
        session = "session-" + account
        auth = "auth-" + name
        self.exchange.connect_wallet(account, session)
        self.exchange.register_authorization(F.authorization(
            account, auth, session, counterparties=counterparties, max_amount=1000))
        return self.exchange.submit_intent(F.intent(
            name, side, account, auth, None, nonce, limit_price=price))

    def test_higher_bid_executes_and_named_lower_bid_cannot_jump(self):
        self.order("ask", "sell", F.A, 100)
        self.order("low", "buy", F.B, 110)
        self.order("high", "buy", F.C, 120)
        with self.assertRaises(DomainError) as caught:
            self.exchange.match_intents("ask", "low")
        self.assertEqual(caught.exception.code, "EX_MATCH_PRIORITY_REFUSED")
        match = self.exchange.match_intents("ask", "high")
        self.assertEqual(match.price, 100)
        self.exchange.execute_transfer(match, "transfer-best")
        self.assertEqual(self.exchange.owner_of("rcpt-8415-0001"), F.C)
        self.assertEqual(self.exchange.holder_of("rcpt-8415-0001"), F.A)

    def test_equal_price_uses_server_acceptance_sequence(self):
        self.order("ask", "sell", F.A, 100)
        self.order("first", "buy", F.B, 110)
        self.order("second", "buy", F.C, 110)
        with self.assertRaises(DomainError):
            self.exchange.match_intents("ask", "second")
        match = self.exchange.match_intents("ask", "first")
        self.assertLess(match.basis["askSequence"], match.basis["bidSequence"])
        self.assertEqual(match.buyer, F.B)

    def test_incoming_seller_gets_best_resting_bid_price(self):
        self.order("bid", "buy", F.B, 120)
        self.order("ask", "sell", F.A, 100)
        match = self.exchange.match_intents("ask", "bid")
        self.assertEqual(match.price, 120)
        self.assertLess(match.basis["bidSequence"], match.basis["askSequence"])

    def test_lowest_eligible_ask_and_its_fifo_win(self):
        self.order("worse-ask", "sell", F.A, 110, nonce=1)
        self.order("best-ask", "sell", F.A, 100, nonce=2)
        self.order("bid", "buy", F.B, 120)
        with self.assertRaises(DomainError):
            self.exchange.match_intents("worse-ask", "bid")
        self.assertEqual(self.exchange.match_intents("best-ask", "bid").price, 100)

    def test_unexecutable_counterparty_restriction_does_not_block_eligible_pair(self):
        self.order("ask", "sell", F.A, 100)
        self.order("restricted-high", "buy", F.B, 130, counterparties=(F.D,))
        self.order("eligible", "buy", F.C, 120)
        match = self.exchange.match_intents("ask", "eligible")
        self.assertEqual(match.buyer, F.C)
        with self.assertRaises(DomainError):
            self.exchange.match_intents("ask", "restricted-high")

    def test_revocation_is_rechecked_before_execution(self):
        self.order("ask", "sell", F.A, 100)
        self.order("low", "buy", F.B, 110)
        self.order("high", "buy", F.C, 120)
        match = self.exchange.match_intents("ask", "high")
        self.exchange.revoke_authorization("auth-high")
        with self.assertRaises(DomainError):
            self.exchange.execute_transfer(match, "revoked-transfer")
        self.assertEqual(self.exchange.recorded_legs("rcpt-8415-0001"), 0)
        self.assertEqual(self.exchange.match_intents("ask", "low").buyer, F.B)

    def test_basis_and_designated_pair_cannot_forge_book_execution(self):
        self.order("ask", "sell", F.A, 100)
        self.order("bid", "buy", F.B, 110)
        match = self.exchange.match_intents("ask", "bid")
        with self.assertRaises(DomainError):
            self.exchange.execute_transfer(replace(match, basis={"rule": "forged"}), "forged")
        self.exchange.register_authorization(F.authorization(
            F.C, "auth-designated", "session-c", max_amount=120))
        self.exchange.connect_wallet(F.C, "session-c")
        self.exchange.submit_intent(F.intent("designated", "buy", F.C,
            "auth-designated", F.A, 1, limit_price=120))
        with self.assertRaises(DomainError):
            self.exchange.match_intents("ask", "designated")
        self.assertEqual(self.exchange.recorded_legs("rcpt-8415-0001"), 0)
