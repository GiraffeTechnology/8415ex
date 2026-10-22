"""Position-only EX history from original predecessor links, never addresses."""
from .public_workbench import integer, amount, currency, state


class TimelineProjectionRefused(ValueError):
    pass


def _deadlines(view, receipt_id):
    result = {"tradeStopAt": integer(view.get("tradeStopAt")),
              "registrationDeadline": None, "tradeComparison": None,
              "registrationComparison": None, "registrationAlsoMustNotExceedTradeStop": None,
              "unit": None, "timezone": None, "precision": None,
              "declarationStatus": "not-provided"}
    declaration = view.get("mintDeclaration")
    if declaration is None:
        return result
    result["declarationStatus"] = "unavailable"
    if type(declaration) is not dict:
        return result
    canonical = declaration.get("canonicalDeclaration")
    if type(canonical) is not dict or canonical.get("schema") != "8415ex-mint-declaration/1":
        return result
    receipt, times = canonical.get("receipt"), canonical.get("time")
    if type(receipt) is not dict or type(times) is not dict:
        return result
    minted = integer(receipt.get("minted_at"))
    stop, registration = integer(times.get("tradeStopAt")), integer(times.get("registrationDeadline"))
    if (receipt.get("receipt_id") != receipt_id or declaration.get("receiptId") != receipt_id
            or minted is None or stop is None or registration is None
            or stop != result["tradeStopAt"] or integer(receipt.get("trade_stop_at")) != stop
            or not minted < stop or not minted < registration
            or times.get("unit") != "unix-second" or times.get("timezone") != "UTC"
            or times.get("precision") != "integer" or times.get("tradeComparison") != "LT"
            or times.get("registrationComparison") not in ("LT", "LTE")
            or times.get("registrationAlsoMustNotExceedTradeStop") is not True):
        return result
    result.update(registrationDeadline=registration, tradeComparison="LT",
                  registrationComparison=times["registrationComparison"],
                  registrationAlsoMustNotExceedTradeStop=True,
                  unit="unix-second", timezone="UTC", precision="integer",
                  declarationStatus="original-domain-declaration")
    return result


def timeline_projection(exchange, receipt_id, *, now=None):
    """Keep withdrawn branches and global leg IDs without inventing adjacency.

    The original receipt observation supplies state; the original immutable leg
    references supply predecessor identity. Neither source is a chain proof.
    A missing predecessor is unknown, not an assertion that a leg starts at zero.
    """
    view = exchange.receipt_view(receipt_id, now)
    if (type(view) is not dict or view.get('receiptId') != receipt_id
            or integer(view.get('observedAt')) is None):
        raise TimelineProjectionRefused('original receipt observation binding required')
    observations = view.get('legs')
    if type(observations) not in (tuple, list):
        raise TimelineProjectionRefused('original observed legs required')
    originals = exchange.legs(receipt_id)
    if type(originals) not in (tuple, list):
        raise TimelineProjectionRefused('original predecessor records required')
    by_id, by_index = {}, {}
    for leg in originals:
        identity = getattr(leg, 'transfer_id', None)
        index = getattr(leg, 'leg_index', None)
        if (getattr(leg, 'receipt_id', None) != receipt_id
                or type(identity) is not str or not identity or integer(index) is None
                or index + 1 >= 2**256 or identity in by_id or index in by_index):
            raise TimelineProjectionRefused('original history identity conflict')
        by_id[identity] = leg
        by_index[index] = identity
    seen = set()
    for entry in observations:
        if type(entry) is not dict:
            raise TimelineProjectionRefused('original observed leg shape required')
        index, identity = entry.get('legIndex'), entry.get('transferId')
        if (integer(index) is None or type(identity) is not str or index in seen
                or by_index.get(index) != identity):
            raise TimelineProjectionRefused('observation and original history differ')
        seen.add(index)
    if seen != set(by_index):
        raise TimelineProjectionRefused('observation and original history differ')
    active = view.get('activeLegIndices')
    withdrawn = view.get('historicalWithdrawnLegIndices')
    if (type(active) not in (tuple, list) or type(withdrawn) not in (tuple, list)
            or any(integer(index) is None for index in (*active, *withdrawn))
            or len(set(active)) != len(active) or len(set(withdrawn)) != len(withdrawn)
            or set(active) & set(withdrawn) or set(active) | set(withdrawn) != seen):
        raise TimelineProjectionRefused('original active and withdrawn history required')
    rows = []
    for entry in sorted(observations, key=lambda value: value['legIndex']):
        index = entry['legIndex']
        original = by_id[entry['transferId']]
        source = None
        if hasattr(original, 'predecessor_transfer_id'):
            predecessor = original.predecessor_transfer_id
            if predecessor is None:
                source = 0
            elif type(predecessor) is str and predecessor in by_id:
                previous = by_id[predecessor].leg_index
                if previous >= index:
                    raise TimelineProjectionRefused('predecessor is not earlier in original history')
                source = previous + 1
        rows.append({'legIndex': index, 'fromPosition': source, 'toPosition': index + 1,
                     'positionMapping': 'original-predecessor' if source is not None else 'unknown',
                     'active': index in active, 'historicalWithdrawn': index in withdrawn,
                     'price': amount(entry.get('price')), 'currency': currency(entry.get('quoteAsset')),
                     'priceUnit': 'base-units',
                     'registrationStatus': state(entry.get('registrationStatus')),
                     'fundingStatus': state(entry.get('fundingStatus')),
                     'rollbackStatus': state(entry.get('rollbackStatus')),
                     'executionStatus': 'executed' if entry.get('executionStatus') == 'executed' else 'unknown',
                     'executedAt': integer(entry.get('executedAt'))})
    return {'schema': '8415ex-domain-timeline/1', 'legs': rows,
            'ownerPosition': integer(view.get('owner', {}).get('position')),
            'holderPosition': integer(view.get('holder', {}).get('position')),
            'observedAt': integer(view.get('observedAt')),
            'deadlines': _deadlines(view, receipt_id),
            'simulatedRegistration': view.get('simulatedRegistration') is True,
            'positionSource': 'original-domain-predecessor-history',
            'chainAcceptance': 'NOT_RUN', 'protocolFinalityEstablished': False}
