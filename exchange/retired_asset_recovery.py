"""Pure exact retired-generation terminal proof contract; no asset dispatch."""
from copy import deepcopy
from hashlib import sha256
from .ids import canonical_json


class RetiredRecoveryRefused(ValueError):
    pass


def request_for(exchange, receipt_id, state):
    lifecycle = exchange.asset_lifecycle(receipt_id)
    asset = list(exchange.receipt(receipt_id).asset.key)
    returns = [step for step in state['steps'] if step.kind == 'asset-return']
    if (lifecycle.get('state') != 'RETIRED' or lifecycle.get('asset') != asset
            or not lifecycle.get('operationId') or not lifecycle.get('historyDigest')
            or not lifecycle.get('successor') or len(returns) != 1):
        raise RetiredRecoveryRefused('exact persisted terminal remint generation required')
    return dict(receipt=receipt_id, asset=asset, returnKey=returns[0].key,
                boundaryIndex=state['boundaryIndex'], boundaryAccount=state['boundaryAccount'],
                affectedLegs=list(state['affectedLegs']), lifecycle=deepcopy(lifecycle),
                requireNoFutureReturnClaim=True)


def verify_marker(request, raw, outcome):
    """Original verifier authenticates canonical burn and exact operation/history,
    or historical exact boundary occurrence/custody NOOP, AND absence/resolution
    of every old native return claim. A remint status does not cancel UNKNOWN.
    The caller cannot substitute bool/labels for the original evidence port.
    """
    if (type(raw) is not bytes or not raw or type(outcome) is not dict
            or set(outcome) != {'request', 'status', 'evidenceReference'}
            or canonical_json(outcome['request']) != canonical_json(request)
            or outcome['status'] not in {'RETIRED_BURN_CONFIRMED', 'NOOP_BOUNDARY_CONFIRMED'}
            or type(outcome['evidenceReference']) is not str or not outcome['evidenceReference']):
        raise RetiredRecoveryRefused('original retired asset terminal proof refused')
    return dict(request=deepcopy(request), status=outcome['status'],
                evidenceReference=outcome['evidenceReference'], proofSha256=sha256(raw).hexdigest())
