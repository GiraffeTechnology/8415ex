"""Price/time proposals using the existing intent and authorization model.

This book does not execute, reserve funds or replace canonical transfer checks.
"""
from threading import RLock
from .model import TradeIntent
from .errors import DomainError


class PriorityRefused(ValueError):
    pass


class PriorityBook:
    def __init__(self, exchange, receipt_id, quote_asset, clock):
        if not callable(clock) or not isinstance(quote_asset, str) or not quote_asset:
            raise PriorityRefused('explicit clock and quote asset required')
        self.exchange = exchange
        self.receipt_id = receipt_id
        self.asset = exchange.receipt(receipt_id).asset
        self.quote_asset = quote_asset
        self.clock = clock
        self._entries = {}
        self._nonces = {}
        self._sequence = 0
        self._lock = RLock()

    def _now(self):
        now = self.clock()
        if type(now) is not int or now < 0:
            raise PriorityRefused('exact trusted observation time required')
        return now

    def _reason(self, intent, now):
        if not isinstance(intent, TradeIntent):
            return 'intent-type-refused'
        if intent.asset.key != self.asset.key or intent.quote_asset != self.quote_asset:
            return 'asset-or-quote-mismatch'
        if intent.counterparty is not None:
            return 'designated-counterparty-not-an-order-book-priority'
        try:
            report = self.exchange.validate_intent(intent.intent_id, now=now)
        except DomainError as error:
            return error.code
        if type(report) is not dict or report.get('executable') is not True:
            return 'original-intent-validation-refused'
        if report.get('signedTermsDigest') != intent.digest:
            return 'validation-digest-mismatch'
        return None

    def enter(self, intent_id):
        """Assign receipt-local server sequence; no client timestamp is accepted."""
        with self._lock:
            intent = self.exchange.intent(intent_id)
            if not isinstance(intent, TradeIntent):
                raise PriorityRefused('intent-type-refused')
            old = self._entries.get(intent_id)
            if old is not None:
                if old[0].digest != intent.digest:
                    raise PriorityRefused('same intent id with different content')
                return old[1]
            reason = self._reason(intent, self._now())
            if reason:
                raise PriorityRefused(reason)
            key = (intent.signer, intent.nonce)
            if key in self._nonces:
                raise PriorityRefused('nonce reused by another order')
            self._sequence += 1
            self._entries[intent_id] = (intent, self._sequence)
            self._nonces[key] = intent_id
            return self._sequence

    def proposal(self):
        """Revalidate current orders and report priority, never move the head."""
        with self._lock:
            now = self._now()
            head = (self.exchange.owner_index(self.receipt_id),
                    self.exchange.owner_of(self.receipt_id))
            bids = []; asks = []; excluded = []
            for intent, sequence in self._entries.values():
                current = self.exchange.intent(intent.intent_id)
                reason = ('accepted-intent-content-changed' if current.digest != intent.digest
                          else self._reason(intent, now))
                if not reason and intent.side == 'sell' and intent.signer != head[1]:
                    reason = 'seller-is-not-current-owner'
                if not reason and intent.side == 'buy' and intent.signer == head[1]:
                    reason = 'self-trade-refused'
                if reason:
                    excluded.append({'intentId': intent.intent_id, 'reason': reason})
                else:
                    (asks if intent.side == 'sell' else bids).append((intent, sequence))
            asks.sort(key=lambda row: (row[0].limit_price, row[1]))
            bids.sort(key=lambda row: (-row[0].limit_price, row[1]))
            if head != (self.exchange.owner_index(self.receipt_id),
                        self.exchange.owner_of(self.receipt_id)):
                raise PriorityRefused('trade head changed while proposing')
            result = {'schema': '8415ex-price-time-proposal/1', 'receiptId': self.receipt_id,
                'asset': list(self.asset.key), 'quoteAsset': self.quote_asset,
                'headPosition': head[0], 'owner': head[1], 'observedAt': now,
                'askPriority': [i.intent_id for i, s in asks],
                'bidPriority': [i.intent_id for i, s in bids], 'excluded': excluded,
                'selected': None, 'execution': 'NOT_RUN', 'funding': 'NOT_RUN',
                'validationSource': 'existing exchange intent projection, not provider attestation'}
            if not asks or not bids:
                result['reason'] = 'no-eligible-ask-or-bid'
                return result
            ask, ask_sequence = asks[0]
            bid, bid_sequence = bids[0]
            if bid.limit_price < ask.limit_price:
                result['reason'] = 'limits-do-not-cross'
                return result
            result['selected'] = {
                'sellIntentId': ask.intent_id, 'buyIntentId': bid.intent_id,
                'sellDigest': ask.digest, 'buyDigest': bid.digest,
                'askLimit': ask.limit_price, 'bidLimit': bid.limit_price,
                'askSequence': ask_sequence, 'bidSequence': bid_sequence,
                'priceRule': 'UNRESOLVED_INTEGRATION',
                'executionPrice': None,
            }
            result['reason'] = 'priority-selected-execution-pending'
            return result
