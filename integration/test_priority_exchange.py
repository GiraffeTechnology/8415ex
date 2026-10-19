"""Authored proposal contracts; execution evidence is recorded separately."""
import unittest
from dataclasses import replace
from types import SimpleNamespace
from exchange.model import Asset, TradeIntent
from exchange.priority_exchange import PriorityBook, PriorityRefused

OWNER = '0x' + '2' * 40
BUYER = '0x' + '3' * 40
OTHER = '0x' + '4' * 40
ASSET = Asset(11155111, '0x' + '1' * 40, 7)


class OriginalSurface:
    def __init__(self):
        self.orders = {}
        self.grants = {}
        self.invalid = set()
        self.position = 0
        self.owner = OWNER
        self.bad_digest = False

    def intent(self, key):
        return self.orders[key]

    def authorization(self, key):
        return self.grants[key]

    def receipt(self, key):
        return SimpleNamespace(asset=ASSET)

    def owner_index(self, key):
        return self.position

    def owner_of(self, key):
        return self.owner

    def validate_intent(self, key, now):
        intent = self.orders[key]
        return {'executable': key not in self.invalid and now < intent.expires_at,
                'signedTermsDigest': 'wrong' if self.bad_digest else intent.digest}


class PriorityContracts(unittest.TestCase):
    def setUp(self):
        self.original = OriginalSurface()
        self.now = 10
        self.book = PriorityBook(self.original, 'receipt-1', 'PYUSD-fixture', lambda: self.now)

    def add(self, key, side, price, nonce, signer=None, counterparty=None):
        authorization_id = 'auth-' + key
        self.original.grants[authorization_id] = SimpleNamespace(counterparties=(), max_amount=1000)
        intent = TradeIntent(key, side, signer or (OWNER if side == 'sell' else BUYER),
            ASSET, price, 'PYUSD-fixture', 1, nonce, 1000, authorization_id, counterparty)
        self.original.orders[key] = intent
        return self.book.enter(key)

    def test_price_priority_before_arrival(self):
        self.add('ask-high', 'sell', 120, 1)
        self.add('ask-low', 'sell', 100, 2)
        self.add('bid-low', 'buy', 130, 3)
        self.add('bid-high', 'buy', 150, 4)
        result = self.book.proposal()
        self.assertEqual(result['askPriority'], ['ask-low', 'ask-high'])
        self.assertEqual(result['bidPriority'], ['bid-high', 'bid-low'])
        self.assertEqual(result['selected']['buyIntentId'], 'bid-high')
        self.assertEqual(result['selected']['sellIntentId'], 'ask-low')
        self.assertEqual(result['selected']['executionPrice'], 100)
        self.assertEqual(result['selected']['priceRule'], 'price-time-resting-order-limit')
        self.assertEqual(result['execution'], 'NOT_RUN')
        self.assertEqual(result['funding'], 'NOT_RUN')
        self.assertEqual(self.original.position, 0)

    def test_equal_price_fifo_and_duplicate_delivery(self):
        first = self.add('bid-z', 'buy', 150, 1)
        self.add('bid-a', 'buy', 150, 2, OTHER)
        self.assertEqual(self.book.enter('bid-z'), first)
        self.assertEqual(self.book.proposal()['bidPriority'], ['bid-z', 'bid-a'])

    def test_changed_intent_and_reused_nonce_refused(self):
        self.add('bid-1', 'buy', 150, 1)
        self.original.orders['bid-1'] = replace(self.original.orders['bid-1'], limit_price=160)
        with self.assertRaises(PriorityRefused):
            self.book.enter('bid-1')
        with self.assertRaises(PriorityRefused):
            self.add('bid-2', 'buy', 150, 1)

    def test_designated_counterparty_cannot_skip_queue(self):
        with self.assertRaises(PriorityRefused):
            self.add('targeted', 'buy', 150, 1, counterparty=OWNER)

    def test_live_validation_excludes_revoked_and_expired(self):
        self.add('ask-1', 'sell', 100, 1)
        self.add('bid-1', 'buy', 150, 2)
        self.add('bid-2', 'buy', 140, 3, OTHER)
        self.original.invalid.add('bid-1')
        self.assertEqual(self.book.proposal()['selected']['buyIntentId'], 'bid-2')
        self.now = 1000
        self.assertIsNone(self.book.proposal()['selected'])

    def test_validation_digest_is_bound(self):
        self.original.bad_digest = True
        with self.assertRaises(PriorityRefused):
            self.add('bid-1', 'buy', 150, 1)

    def test_non_crossing_and_changed_owner_do_not_execute(self):
        self.add('ask-1', 'sell', 160, 1)
        self.add('bid-1', 'buy', 150, 2)
        self.assertEqual(self.book.proposal()['reason'], 'limits-do-not-cross')
        self.original.owner = OTHER
        self.assertEqual(self.book.proposal()['askPriority'], [])
        self.assertEqual(self.original.position, 0)

    def test_non_exact_clock_refused(self):
        self.now = True
        with self.assertRaises(PriorityRefused):
            self.add('bid-1', 'buy', 150, 1)

    def test_original_grant_counterparty_restriction_filters_the_pair(self):
        self.add('ask-1', 'sell', 100, 1)
        self.add('bid-best', 'buy', 150, 2)
        self.add('bid-eligible', 'buy', 140, 3, OTHER)
        self.original.grants['auth-ask-1'].counterparties = (OTHER,)
        result = self.book.proposal()
        self.assertEqual(result['bidPriority'], ['bid-best', 'bid-eligible'])
        self.assertEqual(result['selected']['buyIntentId'], 'bid-eligible')
        self.assertEqual(result['selected']['executionPrice'], 100)
        self.assertEqual(result['execution'], 'NOT_RUN')
        self.assertEqual(self.original.position, 0)

    def test_both_original_grant_amount_bounds_apply_to_the_resting_price(self):
        self.add('ask-1', 'sell', 100, 1)
        self.add('bid-1', 'buy', 150, 2)
        for authorization_id in ('auth-ask-1', 'auth-bid-1'):
            with self.subTest(authorization_id=authorization_id):
                grant = self.original.grants[authorization_id]
                grant.max_amount = 99
                self.assertIsNone(self.book.proposal()['selected'])
                grant.max_amount = 100
                self.assertEqual(self.book.proposal()['selected']['executionPrice'], 100)
                grant.max_amount = 1000
        self.assertEqual(self.original.position, 0)
