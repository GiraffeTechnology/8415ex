"""Exact gas quote and accounting contracts; no provider or wallet I/O."""
from dataclasses import dataclass, asdict
from fractions import Fraction
from hashlib import sha256
import json


class GasBudgetRefused(ValueError):
    pass


def _integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise GasBudgetRefused('exact non-negative integer required')
    return value


def _text(value):
    if type(value) is not str or not value.strip():
        raise GasBudgetRefused('non-empty identity required')
    return value


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                            ensure_ascii=False).encode('utf-8')).hexdigest()


def _decimal(value, places):
    scaled = Fraction(value) * 10 ** places
    if scaled.denominator != 1:
        raise GasBudgetRefused('display precision would lose value')
    whole, tail = divmod(scaled.numerator, 10 ** places)
    return str(whole) + '.' + str(tail).zfill(places)


@dataclass(frozen=True)
class FeeSample:
    sample_id: str
    scope: str
    chain_id: int
    fee_wei: int
    observed_at: int
    block_number: int
    source: str
    raw_sha256: str

    def __post_init__(self):
        for field in ('sample_id', 'scope', 'source'):
            _text(getattr(self, field))
        for field in ('fee_wei', 'observed_at', 'block_number'):
            _integer(getattr(self, field))
        _integer(self.chain_id, 1)
        if (type(self.raw_sha256) is not str or len(self.raw_sha256) != 64
                or any(c not in '0123456789abcdef' for c in self.raw_sha256)):
            raise GasBudgetRefused('raw sample SHA-256 required')


@dataclass(frozen=True)
class GasQuote:
    quote_id: str
    version: int
    budget_id: str
    scope: str
    actions: tuple
    chain_id: int
    cap_wei: int
    samples: tuple
    window_start: int
    window_end: int
    quoted_at: int
    valid_until: int
    usd_micro_per_eth: int
    rate_observed_at: int
    rate_source: str
    rate_sha256: str

    def __post_init__(self):
        for field in ('quote_id', 'budget_id', 'scope', 'rate_source'):
            _text(getattr(self, field))
        for field in ('version', 'chain_id', 'cap_wei', 'usd_micro_per_eth'):
            _integer(getattr(self, field), 1)
        for field in ('window_start', 'window_end', 'quoted_at', 'valid_until', 'rate_observed_at'):
            _integer(getattr(self, field))
        if (type(self.actions) is not tuple or not self.actions
                or len(set(self.actions)) != len(self.actions)):
            raise GasBudgetRefused('explicit unique covered actions required')
        for action in self.actions:
            _text(action)
        if not (self.window_start <= self.window_end <= self.quoted_at < self.valid_until
                and self.rate_observed_at == self.quoted_at):
            raise GasBudgetRefused('sample window and same-instant FX required')
        if (type(self.rate_sha256) is not str or len(self.rate_sha256) != 64
                or any(c not in '0123456789abcdef' for c in self.rate_sha256)):
            raise GasBudgetRefused('raw FX SHA-256 required')
        if type(self.samples) is not tuple or len(self.samples) < 2:
            raise GasBudgetRefused('multiple applicable samples required for median')
        identities = set()
        for sample in self.samples:
            if not isinstance(sample, FeeSample):
                raise GasBudgetRefused('typed sample required')
            if (sample.sample_id in identities or sample.chain_id != self.chain_id
                    or sample.scope != self.scope
                    or not self.window_start <= sample.observed_at <= self.window_end):
                raise GasBudgetRefused('duplicate or inapplicable sample')
            identities.add(sample.sample_id)
        if self.median_wei > self.cap_wei:
            raise GasBudgetRefused('median exceeds quoted cap')

    @property
    def median_wei(self):
        values = sorted(sample.fee_wei for sample in self.samples)
        middle = len(values) // 2
        return (Fraction(values[middle]) if len(values) % 2
                else Fraction(values[middle - 1] + values[middle], 2))

    @property
    def digest(self):
        return _digest(asdict(self))

    def disclosure(self):
        def money(wei):
            return {'ETH': _decimal(Fraction(wei, 10 ** 18), 19),
                    'USD': _decimal(Fraction(wei) * self.usd_micro_per_eth / 10 ** 24, 25)}
        return {'quoteId': self.quote_id, 'version': self.version, 'digest': self.digest,
                'budgetId': self.budget_id, 'scope': self.scope, 'actions': list(self.actions),
                'chainId': self.chain_id, 'cap': money(self.cap_wei),
                'median': money(self.median_wei), 'algorithm': 'sorted-P50-middle-or-two-middle-mean',
                'sampleCount': len(self.samples), 'window': [self.window_start, self.window_end],
                'samples': [asdict(sample) for sample in self.samples],
                'rate': {'microUSDPerETH': self.usd_micro_per_eth, 'observedAt': self.rate_observed_at,
                         'source': self.rate_source, 'rawSHA256': self.rate_sha256},
                'quotedAt': self.quoted_at, 'validUntil': self.valid_until,
                'coverage': 'listed actions only; no unlisted future fees',
                'authority': 'disclosure only; verified buyer and wallet evidence required'}


@dataclass(frozen=True)
class BuyerConfirmation:
    quote_digest: str
    buyer: str
    action_digest: str
    wallet_grant: str
    confirmed_at: int
    proof_reference: str


@dataclass(frozen=True)
class GasFreeze:
    budget_id: str
    buyer: str
    chain_id: int
    amount_wei: int
    quote_digest: str
    wallet_reference: str
    status: str
    account_kind: str = 'GAS_PREPAYMENT'


@dataclass(frozen=True)
class GasConsumption:
    attempt_id: str
    transaction_hash: str
    actual_wei: int
    outcome: str
    proof_reference: str


class GasBudgetBook:
    """In-memory evidence projection; cannot freeze, debit, unfreeze or send.

    An adapter must authenticate external facts. The verifier callback is a
    caller trust boundary, not cryptographic verification by this module.
    """
    def __init__(self, verify):
        if not callable(verify):
            raise GasBudgetRefused('explicit external evidence verifier required')
        self.verify = verify
        self._budgets = {}
        self._transactions = {}
        self._action_budgets = {}

    def _verified(self, kind, evidence):
        if self.verify(kind, evidence) is not True:
            raise GasBudgetRefused('external evidence not verified: ' + kind)

    def open(self, quote, confirmation, frozen, now):
        if not (isinstance(quote, GasQuote) and isinstance(confirmation, BuyerConfirmation)
                and isinstance(frozen, GasFreeze)):
            raise GasBudgetRefused('typed quote, buyer confirmation and freeze required')
        _integer(now)
        for value in (confirmation.buyer, confirmation.action_digest, confirmation.wallet_grant,
                      confirmation.proof_reference, frozen.wallet_reference):
            _text(value)
        _integer(confirmation.confirmed_at)
        _integer(frozen.amount_wei, 1)
        if not quote.quoted_at <= confirmation.confirmed_at <= now < quote.valid_until:
            raise GasBudgetRefused('expired or premature confirmation')
        if (confirmation.quote_digest != quote.digest or frozen.quote_digest != quote.digest
                or frozen.budget_id != quote.budget_id or frozen.buyer != confirmation.buyer
                or frozen.chain_id != quote.chain_id or frozen.amount_wei != quote.cap_wei
                or frozen.account_kind != 'GAS_PREPAYMENT' or frozen.status != 'FROZEN'):
            raise GasBudgetRefused('cap-sized separate gas freeze and quote binding required')
        self._verified('buyer-confirmation', confirmation)
        self._verified('gas-freeze', frozen)
        action_key = (quote.chain_id, confirmation.buyer, confirmation.action_digest)
        assigned = self._action_budgets.get(action_key)
        if assigned is not None and assigned != quote.budget_id:
            raise GasBudgetRefused('canonical operation already has an aggregate budget')
        old = self._budgets.get(quote.budget_id)
        identity = (quote.digest, confirmation, frozen)
        if old is not None:
            if old['identity'] != identity:
                raise GasBudgetRefused('existing budget cannot reset through another quote')
            return self.snapshot(quote.budget_id)
        self._budgets[quote.budget_id] = {'identity': identity, 'quote': quote,
            'confirmation': confirmation, 'freeze': frozen, 'spent': 0,
            'attempts': {}, 'settled': {}, 'closed': False}
        self._action_budgets[action_key] = quote.budget_id
        return self.snapshot(quote.budget_id)

    def reserve(self, budget_id, attempt_id, action, maximum_wei, now):
        """Record the adapter upper bound before sending; never send here."""
        row = self._budgets[budget_id]
        quote = row['quote']
        _text(attempt_id)
        _integer(maximum_wei, 1)
        _integer(now)
        if row['closed'] or not quote.quoted_at <= now < quote.valid_until:
            raise GasBudgetRefused('closed or expired budget; refreshed confirmation required')
        if action not in quote.actions:
            raise GasBudgetRefused('action outside confirmed coverage')
        old = row['attempts'].get(attempt_id)
        identity = (action, maximum_wei)
        if old is not None:
            if old != identity:
                raise GasBudgetRefused('attempt identity changed')
            return self.snapshot(budget_id)
        if attempt_id in row['settled']:
            raise GasBudgetRefused('settled attempt cannot be sent again')
        pending = sum(value[1] for value in row['attempts'].values())
        if row['spent'] + pending + maximum_wei > quote.cap_wei:
            raise GasBudgetRefused('confirmed aggregate cap exceeded; requote and reconfirm')
        self._verified('send-bound', {'quote': quote.digest, 'budgetId': budget_id,
            'buyer': row['confirmation'].buyer, 'actionDigest': row['confirmation'].action_digest,
            'walletGrant': row['confirmation'].wallet_grant, 'freeze': row['freeze'].wallet_reference,
            'attemptId': attempt_id, 'action': action, 'maximumWei': maximum_wei, 'observedAt': now})
        row['attempts'][attempt_id] = identity
        return self.snapshot(budget_id)

    def reconcile(self, budget_id, consumption):
        if not isinstance(consumption, GasConsumption):
            raise GasBudgetRefused('typed consumption required')
        row = self._budgets[budget_id]
        _text(consumption.attempt_id)
        _text(consumption.proof_reference)
        _integer(consumption.actual_wei)
        tx = consumption.transaction_hash
        if (type(tx) is not str or len(tx) != 66 or not tx.startswith('0x')
                or any(c not in '0123456789abcdef' for c in tx[2:])):
            raise GasBudgetRefused('canonical transaction hash required')
        if consumption.outcome not in ('SUCCESS', 'FAILED'):
            raise GasBudgetRefused('unknown execution remains reserved; reconcile first')
        old = row['settled'].get(consumption.attempt_id)
        if old is not None:
            if old != consumption:
                raise GasBudgetRefused('settled consumption changed')
            return self.snapshot(budget_id)
        tx_key = (row['quote'].chain_id, tx)
        if tx_key in self._transactions:
            raise GasBudgetRefused('transaction already accounted under another attempt')
        attempt = row['attempts'].get(consumption.attempt_id)
        if attempt is None or consumption.actual_wei > attempt[1]:
            raise GasBudgetRefused('consumption missing reservation or exceeds proven bound')
        self._verified('gas-consumption', consumption)
        row['spent'] += consumption.actual_wei
        row['settled'][consumption.attempt_id] = consumption
        del row['attempts'][consumption.attempt_id]
        self._transactions[tx_key] = (budget_id, consumption.attempt_id)
        return self.snapshot(budget_id)

    def close(self, budget_id):
        row = self._budgets[budget_id]
        if row['attempts']:
            raise GasBudgetRefused('pending or unknown outcome prevents unfreeze')
        row['closed'] = True
        return self.snapshot(budget_id)

    def snapshot(self, budget_id):
        row = self._budgets[budget_id]
        remaining = row['quote'].cap_wei - row['spent']
        return {'budgetId': budget_id, 'quoteDigest': row['quote'].digest,
                'capWei': row['quote'].cap_wei, 'actualConsumedWei': row['spent'],
                'pendingBoundWei': sum(value[1] for value in row['attempts'].values()),
                'unusedWei': remaining,
                'unfreezeProposalWei': remaining if row['closed'] else None,
                'closed': row['closed'], 'walletDebit': 'NOT_RUN',
                'walletUnfreeze': 'NOT_RUN', 'transactionSend': 'NOT_RUN'}
