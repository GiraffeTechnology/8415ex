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
        sell = exchange.submit_intent(F.intent("sell-replay", "sell", F.B, "auth-replay", F.C, 1))
        buy = exchange.submit_intent(F.intent("buy-replay", "buy", F.C, "auth-replay-c", F.B, 9))
        report = exchange.validate_intent(sell.intent_id)
        self.assertFalse(report["executable"])
        self.assertIn("EX_INTENT_NONCE_REPLAYED", report["reasons"])
        with self.assertRaises(DomainError) as caught:
            exchange.match_intents(sell.intent_id, buy.intent_id)
        self.assertEqual(caught.exception.code, "EX_MATCH_UNEXECUTABLE")

    def test_selling_the_same_head_to_two_buyers_advances_only_one(self):
        exchange, _ = F.minted()
        for buyer, session, nonce in ((F.B, "session-b", 1), (F.C, "session-c", 2)):
            exchange.connect_wallet(buyer, session)
            exchange.register_authorization(F.authorization(buyer, f"auth-buy-{buyer[-1]}", session,
                                                            counterparties=(F.A,)))
            exchange.register_authorization(F.authorization(F.A, f"auth-sell-{buyer[-1]}", "session-a",
                                                            counterparties=(buyer,)))
            exchange.submit_intent(F.intent(f"sell-to-{buyer[-1]}", "sell", F.A,
                                            f"auth-sell-{buyer[-1]}", buyer, nonce))
            exchange.submit_intent(F.intent(f"buy-by-{buyer[-1]}", "buy", buyer,
                                            f"auth-buy-{buyer[-1]}", F.A, nonce))
        first = exchange.match_intents("sell-to-b", "buy-by-b")
        second = exchange.match_intents("sell-to-c", "buy-by-c")
        exchange.execute_transfer(first, "transfer-ab")
        with self.assertRaises(DomainError) as caught:
            exchange.execute_transfer(second, "transfer-ac")
        self.assertEqual(caught.exception.code, "EX_TRADE_HEAD_MOVED")
        self.assertEqual(exchange.owner_index("rcpt-8415-0001"), 1)
        self.assertEqual(exchange.owner_of("rcpt-8415-0001"), F.B)

    def test_a_duplicate_transfer_id_is_refused(self):
        exchange, _ = F.minted()
        F.hop(exchange, F.A, F.B, 1, "transfer-ab", "session-a", "session-b")
        exchange.register_authorization(F.authorization(F.B, "auth-dup-b", "session-b", counterparties=(F.C,)))
        exchange.connect_wallet(F.C, "session-c")
        exchange.register_authorization(F.authorization(F.C, "auth-dup-c", "session-c", counterparties=(F.B,)))
        exchange.submit_intent(F.intent("sell-dup", "sell", F.B, "auth-dup-b", F.C, 7))
        exchange.submit_intent(F.intent("buy-dup", "buy", F.C, "auth-dup-c", F.B, 7))
        match = exchange.match_intents("sell-dup", "buy-dup")
        with self.assertRaises(DomainError) as caught:
            exchange.execute_transfer(match, "transfer-ab")
        self.assertEqual(caught.exception.code, "EX_TRANSFER_DUPLICATE_REFUSED")

    def test_a_new_trade_is_refused_at_the_stop_trading_instant(self):
        clock = F.ManualClock()
        exchange, _ = F.minted(clock=clock)
        clock.now = exchange.receipt("rcpt-8415-0001").trade_stop_at
        with self.assertRaises(DomainError) as caught:
            F.hop(exchange, F.A, F.B, 1, "transfer-late", "session-a", "session-b")
        self.assertIn(caught.exception.code, ("EX_MATCH_UNEXECUTABLE", "EX_TRADE_WINDOW_CLOSED"))


if __name__ == "__main__":
    unittest.main()
