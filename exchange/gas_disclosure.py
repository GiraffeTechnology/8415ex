"""Exact pre-trade gas amounts; no signing, fee policy or provider selection."""
from dataclasses import dataclass
from html import escape


class DisclosureUnavailable(ValueError):
    pass


def natural(value, name, positive=False):
    if type(value) is not int or value < (1 if positive else 0):
        raise DisclosureUnavailable(name + ': exact integer required')
    return value


def reference(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise DisclosureUnavailable(name + ': bounded source reference required')
    return value


def fixed(value, places):
    natural(value, 'amount')
    whole, fraction = divmod(value, 10 ** places)
    tail = str(fraction).zfill(places).rstrip('0')
    return str(whole) + ('.' + tail if tail else '')


@dataclass(frozen=True)
class EtherUSDQuote:
    micro_usd_per_eth: int
    quoted_at: int
    valid_until: int
    source_reference: str


@dataclass(frozen=True)
class ActionGasEstimate:
    action_id: str
    chain_id: int
    gas_units: int
    fee_per_gas_wei: int
    estimated_at: int
    valid_until: int
    source_reference: str
    conditional: bool = False


def require_disclosure(actions, quote, now):
    """Refuse absent/stale amounts before a caller builds confirmation content.

    Caller supplies authenticated estimates, rate and explicit validity bounds.
    The result neither authenticates those inputs nor authorizes a transaction.
    """
    natural(now, 'now')
    if not isinstance(quote, EtherUSDQuote):
        raise DisclosureUnavailable('ETH/USD quote unavailable')
    natural(quote.micro_usd_per_eth, 'ETH/USD rate', positive=True)
    natural(quote.quoted_at, 'quote time')
    natural(quote.valid_until, 'quote validity')
    reference(quote.source_reference, 'quote')
    if not quote.quoted_at <= now < quote.valid_until:
        raise DisclosureUnavailable('ETH/USD quote future-dated or expired')
    if type(actions) not in (tuple, list) or not actions:
        raise DisclosureUnavailable('gas estimate unavailable')
    seen = set(); rows = []; chain = None
    for action in actions:
        if not isinstance(action, ActionGasEstimate):
            raise DisclosureUnavailable('gas estimate type refused')
        reference(action.action_id, 'action')
        reference(action.source_reference, 'estimate')
        if action.action_id in seen:
            raise DisclosureUnavailable('duplicate action estimate')
        seen.add(action.action_id)
        natural(action.chain_id, 'chain', positive=True)
        natural(action.gas_units, 'gas units', positive=True)
        natural(action.fee_per_gas_wei, 'fee per gas', positive=True)
        natural(action.estimated_at, 'estimate time')
        natural(action.valid_until, 'estimate validity')
        if type(action.conditional) is not bool:
            raise DisclosureUnavailable('conditional flag refused')
        if not action.estimated_at <= now < action.valid_until:
            raise DisclosureUnavailable('gas estimate future-dated or expired')
        if chain is not None and chain != action.chain_id:
            raise DisclosureUnavailable('mixed estimate networks')
        chain = action.chain_id
        wei = action.gas_units * action.fee_per_gas_wei
        rows.append({'actionId': action.action_id, 'chainId': chain,
            'gasUnits': str(action.gas_units), 'feePerGasWei': str(action.fee_per_gas_wei),
            'estimatedWei': str(wei), 'estimatedETH': fixed(wei, 18),
            'estimatedUSD': fixed(wei * quote.micro_usd_per_eth, 24),
            'estimatedAt': action.estimated_at, 'validUntil': action.valid_until,
            'sourceReference': action.source_reference, 'conditional': action.conditional})

    return {'schema': '8415ex-gas-disclosure/1', 'chainId': chain,
        'observedAt': now, 'quoteAt': quote.quoted_at,
        'quoteValidUntil': quote.valid_until, 'quoteSource': quote.source_reference,
        'usdPerETH': fixed(quote.micro_usd_per_eth, 6), 'actions': rows,
        'validUntil': min([quote.valid_until] + [r['validUntil'] for r in rows]),
        'amountsAvailable': True, 'isEstimate': True,
        'unlistedActions': 'not estimated; never implied to cost zero',
        'authorization': 'not evaluated; original wallet bounds still apply',
        'principalConversion': 'not authorized', 'feeApportionment': 'not decided'}


def render_disclosure(disclosure):
    """Render calculated amounts without replacing original wallet permission."""
    if type(disclosure) is not dict or disclosure.get('schema') != '8415ex-gas-disclosure/1':
        raise DisclosureUnavailable('calculated disclosure required')
    rows = []
    for entry in disclosure['actions']:
        cells = (entry['actionId'], entry['estimatedETH'] + ' ETH',
                 entry['estimatedUSD'] + ' USD', entry['estimatedAt'],
                 'conditional' if entry['conditional'] else 'listed action')
        rows.append('<tr>' + ''.join('<td>' + escape(str(c)) + '</td>' for c in cells) + '</tr>')
    return ('<section><h2>Estimated gas amounts</h2><p>ETH/USD: '
        + escape(disclosure['usdPerETH']) + '; quote time: '
        + escape(str(disclosure['quoteAt'])) + '; valid until: '
        + escape(str(disclosure['validUntil'])) + ' (Unix seconds).</p>'
        + '<table><tr><th>Action</th><th>ETH</th><th>USD</th><th>Estimate time</th><th>Coverage</th></tr>'
        + ''.join(rows) + '</table><p>Estimates can change. Unlisted actions are not estimated, '
        'not zero-cost. This disclosure does not increase wallet authority, choose a fee '
        'sharing policy, convert principal or authorize payment.</p></section>')
