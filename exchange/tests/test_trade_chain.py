"""T-03, T-07: the continuous chain, one valid head, and nonce replay."""
import unittest

from exchange import fixtures as F
from exchange.errors import DomainError


class ContinuousChain(unittest.TestCase):
    """T-03: A -> B -> C -> D is recorded in full, each hop filing its own request."""

    def test_every_hop_is_recorded_in_order_with_its_own_predecessor(self):
        exchange, _ = F.chain_to_d()
        legs = exchange.legs("rcpt-8415-0001")
        self.assertEqual([leg.leg_index for leg in legs], [0, 1, 2])
        self.assertEqual([(leg.seller, leg.buyer) for leg in legs],
                         [(F.A, F.B), (F.B, F.C), (F.C, F.D)])
        self.assertIsNone(legs[0].predecessor_transfer_id)
        self.assertEqual(legs[1].predecessor_transfer_id, legs[0].transfer_id)
        self.assertEqual(legs[2].predecessor_transfer_id, legs[1].transfer_id)

    def test_each_hop_files_an_independent_registration_request(self):
        exchange, _ = F.chain_to_d()
        requests = F.submit_all(exchange)
        self.assertEqual(len(requests), 3)
        self.assertEqual(len({r.request_id for r in requests}), 3)
        self.assertEqual([r.leg_index for r in requests], [0, 1, 2])
        for request, leg in zip(requests, exchange.legs("rcpt-8415-0001")):
            self.assertEqual(request.transfer_id, leg.transfer_id)
            self.assertEqual(request.predecessor_transfer_id, leg.predecessor_transfer_id)

    def test_position_is_an_occurrence_index_not_an_address_comparison(self):
        """D sells back to A: the position advances even though the address order
        of the two accounts is the reverse of the first hop."""
        exchange, _ = F.chain_to_d()
        F.hop(exchange, F.D, F.A, 4, "transfer-da", "session-d", "session-a2")
        self.assertEqual(exchange.owner_index("rcpt-8415-0001"), 4)
        self.assertEqual(exchange.owner_of("rcpt-8415-0001"), F.A)
        legs = exchange.legs("rcpt-8415-0001")
        self.assertEqual(legs[3].leg_index, 3, "a repeated address occurrence still has its own index")


class OneValidHead(unittest.TestCase):
    """T-07: replay is refused, and only one of two concurrent sales advances."""

    def test_a_replayed_nonce_is_refused(self):
        exchange, _ = F.minted()
        F.hop(exchange, F.A, F.B, 1, "transfer-ab", "session-a", "session-b")
        exchange.register_authorization(F.authorization(F.B, "auth-replay", "session-b", counterparties=(F.C,)))
        exchange.connect_wallet(F.C, "session-c")
        exchange.register_authorization(F.authorization(F.C, "auth-replay-c", "session-c", counterparties=(F.B,)))
        sell = exchange.submit_intent(F.intent("sell-replay", "sell", F.B, "auth-replay", None, 1))
        buy = exchange.submit_intent(F.intent("buy-replay", "buy", F.C, "auth-replay-c", None, 9))
        report = exchange.validate_intent(sell.intent_id)
        self.assertFalse(report["executable"])
        self.assertIn("EX_INTENT_NONCE_REPLAYED", report["reasons"])
        with self.assertRaises(DomainError) as caught:
            exchange.match_intents(sell.intent_id, buy.intent_id)
        self.assertEqual(caught.exception.code, "EX_MATCH_UNEXECUTABLE")

    def test_selling_the_same_head_to_two_buyers_advances_only_one(self):
        exchange, _ = F.minted()
        exchange.register_authorization(F.authorization(
            F.A, "auth-sell-head", "session-a", counterparties=(F.B, F.C),
            max_amount=F.PRICE + 1))
        exchange.submit_intent(F.intent(
            "sell-head", "sell", F.A, "auth-sell-head", None, 1))
        for buyer, session in ((F.B, "session-b"), (F.C, "session-c")):
            exchange.connect_wallet(buyer, session)
            exchange.register_authorization(F.authorization(
                buyer, f"auth-buy-{buyer[-1]}", session,
                counterparties=(F.A,), max_amount=F.PRICE + 1))
        exchange.submit_intent(F.intent(
            "buy-by-b", "buy", F.B, "auth-buy-b", None, 1))
        first = exchange.match_intents("sell-head", "buy-by-b")
        # The later higher bid changes the current best pair. Both proposals
        # came from the real matcher while A still held the same head.
        exchange.submit_intent(F.intent(
            "buy-by-c", "buy", F.C, "auth-buy-c", None, 1,
            limit_price=F.PRICE + 1))
        second = exchange.match_intents("sell-head", "buy-by-c")
        exchange.execute_transfer(second, "transfer-ac")
        with self.assertRaises(DomainError) as caught:
            exchange.execute_transfer(first, "transfer-ab")
        self.assertEqual(caught.exception.code, "EX_TRADE_HEAD_MOVED")
        self.assertEqual(exchange.owner_index("rcpt-8415-0001"), 1)
        self.assertEqual(exchange.owner_of("rcpt-8415-0001"), F.C)
        self.assertEqual(len(exchange.legs("rcpt-8415-0001")), 1)

    def test_a_duplicate_transfer_id_is_refused(self):
        exchange, _ = F.minted()
        F.hop(exchange, F.A, F.B, 1, "transfer-ab", "session-a", "session-b")
        exchange.register_authorization(F.authorization(F.B, "auth-dup-b", "session-b", counterparties=(F.C,)))
        exchange.connect_wallet(F.C, "session-c")
        exchange.register_authorization(F.authorization(F.C, "auth-dup-c", "session-c", counterparties=(F.B,)))
        exchange.submit_intent(F.intent("sell-dup", "sell", F.B, "auth-dup-b", None, 7))
        exchange.submit_intent(F.intent("buy-dup", "buy", F.C, "auth-dup-c", None, 7))
        match = exchange.match_intents("sell-dup", "buy-dup")
        with self.assertRaises(DomainError) as caught:
            exchange.execute_transfer(match, "transfer-ab")
        self.assertEqual(caught.exception.code, "EX_TRANSFER_DUPLICATE_REFUSED")

    def test_a_new_trade_is_refused_at_the_stop_trading_instant(self):
        clock = F.ManualClock()
        exchange, _ = F.minted(clock=clock)
        exchange.connect_wallet(F.B, "session-b")
        exchange.register_authorization(F.authorization(
            F.A, "auth-late-a", "session-a", counterparties=(F.B,)))
        exchange.register_authorization(F.authorization(
            F.B, "auth-late-b", "session-b", counterparties=(F.A,)))
        exchange.submit_intent(F.intent(
            "sell-late", "sell", F.A, "auth-late-a", None, 1))
        exchange.submit_intent(F.intent(
            "buy-late", "buy", F.B, "auth-late-b", None, 1))
        match = exchange.match_intents("sell-late", "buy-late")
        clock.now = exchange.receipt("rcpt-8415-0001").trade_stop_at
        for intent_id in ("sell-late", "buy-late"):
            report = exchange.validate_intent(intent_id)
            self.assertFalse(report["executable"])
            self.assertIn("EX_TRADE_WINDOW_CLOSED", report["reasons"])
        with self.assertRaises(DomainError) as caught:
            exchange.execute_transfer(match, "transfer-late")
        self.assertEqual(caught.exception.code, "EX_TRADE_WINDOW_CLOSED")
        self.assertEqual(exchange.owner_of("rcpt-8415-0001"), F.A)
        self.assertEqual(exchange.owner_index("rcpt-8415-0001"), 0)
        self.assertEqual(exchange.legs("rcpt-8415-0001"), ())


if __name__ == "__main__":
    unittest.main()
