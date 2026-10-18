"""Synthetic proposal/canonical-match agreement definitions; approved Linux only."""
import unittest

from exchange import fixtures as F
from exchange.errors import DomainError


class ExecutableProposalTests(unittest.TestCase):
    def setUp(self):
        self.exchange, self.clock = F.minted()

    def order(self, label, signer, side, price, *, counterparties=(), maximum=None):
        session = 'session-' + label
        grant = 'grant-' + label
        self.exchange.connect_wallet(signer, session)
        self.exchange.register_authorization(F.authorization(
            signer, grant, session, counterparties=counterparties,
            max_amount=price if maximum is None else maximum))
        return self.exchange.submit_intent(F.intent(
            'intent-' + label, side, signer, grant, None,
            len(self.exchange._intents) + 1, limit_price=price))

    def proposal(self):
        return self.exchange._order_books[('rcpt-8415-0001', F.QUOTE_ASSET)].proposal()

    def assert_canonical(self, report):
        selected = report['selected']
        match = self.exchange.match_intents(selected['sellIntentId'], selected['buyIntentId'])
        self.assertEqual(selected['priceRule'], match.basis['rule'])
        self.assertEqual(selected['executionPrice'], match.price)
        self.assertEqual(selected['sellDigest'], match.sell_intent_digest)
        self.assertEqual(selected['buyDigest'], match.buy_intent_digest)
        self.assertEqual(report['execution'], 'NOT_RUN')
        self.assertEqual(report['funding'], 'NOT_RUN')
        self.assertEqual(self.exchange.legs('rcpt-8415-0001'), ())

    def test_restricted_best_bid_does_not_hide_executable_next_bid(self):
        self.order('ask', F.A, 'sell', 80, counterparties=(F.C,), maximum=100)
        self.order('best', F.B, 'buy', 100)
        self.order('next', F.C, 'buy', 90)
        report = self.proposal()
        self.assertEqual(report['bidPriority'], ['intent-best', 'intent-next'])
        self.assertEqual(report['selected']['buyIntentId'], 'intent-next')
        self.assert_canonical(report)
        with self.assertRaises(DomainError) as raised:
            self.exchange.match_intents('intent-ask', 'intent-best')
        self.assertEqual(raised.exception.code, 'EX_MATCH_PRIORITY_REFUSED')

    def test_resting_bid_price_over_grant_is_skipped_without_changing_limits(self):
        self.order('old-bid', F.B, 'buy', 100)
        ask = self.order('ask', F.A, 'sell', 80)
        self.order('new-bid', F.C, 'buy', 90)
        report = self.proposal()
        self.assertEqual(report['selected']['buyIntentId'], 'intent-new-bid')
        self.assertEqual(report['selected']['executionPrice'], 80)
        self.assertEqual(self.exchange.intent(ask.intent_id).digest, ask.digest)
        self.assert_canonical(report)

    def test_unrestricted_resting_bid_and_resting_ask_prices_match_canonical(self):
        self.order('bid', F.B, 'buy', 100)
        self.order('ask', F.A, 'sell', 80, maximum=100)
        report = self.proposal()
        self.assertEqual(report['selected']['executionPrice'], 100)
        self.assert_canonical(report)

    def test_crossing_but_mutually_restricted_orders_have_no_selected_pair(self):
        self.order('ask', F.A, 'sell', 80, counterparties=(F.C,), maximum=100)
        self.order('bid', F.B, 'buy', 100)
        report = self.proposal()
        self.assertIsNone(report['selected'])
        self.assertEqual(report['reason'], 'no-executable-crossing-pair')
        with self.assertRaises(DomainError) as raised:
            self.exchange.match_intents('intent-ask', 'intent-bid')
        self.assertEqual(raised.exception.code, 'EX_MATCH_UNEXECUTABLE')

    def test_non_crossing_limits_remain_unselected(self):
        self.order('ask', F.A, 'sell', 100)
        self.order('bid', F.B, 'buy', 80)
        report = self.proposal()
        self.assertIsNone(report['selected'])
        self.assertEqual(report['reason'], 'limits-do-not-cross')
