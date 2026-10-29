"""Original-store machine dispatch fence. Not an HTTP authorization endpoint.

The installed original Wallet exact executor holds this capability; browser
input cannot install it. A receipt is a correlation value, not transferable
proof. Every assertion rereads the original authoritative full aggregate.
"""
from copy import deepcopy
import hashlib
from .deferred_settlement import DeferredSettlement
from .exchange_fact_snapshot import decode_exchange_snapshot
from .ids import canonical_json
from .wallet_task_preparation import COMPONENT, _require, _digest, _encode

BINDING_KEYS = {'taskDigest','childDigest','operationId','chainId','actor','nonce','executorDigest','grantPolicyVersion'}


class WalletDispatchFence:
    def __init__(self, preparation, checkpoint, *, now, original_ports):
        _require(preparation.store is checkpoint.store and preparation.scope == checkpoint.scope
                 and callable(now), 'EX_TASK_FENCE_ORIGINAL_STORE_REQUIRED')
        self.preparation, self.checkpoint, self.now = preparation, checkpoint, now
        self.original_ports = original_ports
        self.asset_return = None

    def install_asset_return(self, asset):
        from .mixed_asset_return import MixedAssetReturn
        _require(type(asset) is MixedAssetReturn and asset.checkpoint is self.checkpoint, "original asset store differs")
        self.asset_return = asset

    def _asset_event(self, event):
        return (type(event) is dict and type(event.get("task")) is dict
                and event["task"].get("policy", {}).get("intent", {}).get("operation", {}).get("kind") == "erc721-transfer")

    def _context(self, event):
        _require(type(event) is dict and set(event) == {'binding','task','child'}, 'EX_TASK_FENCE_EVENT_REFUSED')
        binding = deepcopy(event['binding'])
        _require(type(binding) is dict and set(binding) == BINDING_KEYS
                 and all(_digest(binding[k]) for k in ('taskDigest','childDigest','executorDigest')), 'EX_TASK_FENCE_BINDING_REFUSED')
        row, model = self.checkpoint.read()
        _, state = self.preparation._row(row['generation'])
        candidates = [record for record in state['proposals'].values()
                      if record['proposal']['task']['digest'] == binding['taskDigest']]
        _require(len(candidates) == 1, 'EX_TASK_FENCE_ORIGINAL_PROPOSAL_REQUIRED')
        record = candidates[0]; p = record['proposal']
        _require(self.preparation._proposal(p['id']) == p and event['task'] == p['task'], 'EX_TASK_FENCE_POLICY_CHANGED')
        child = self.preparation._child(p, event['child']); c = child['child']
        _require(binding['taskDigest'] == p['task']['digest'] and binding['childDigest'] == child['digest']
                 and binding['operationId'] == c.get('operationId') and binding['nonce'] == c.get('nonce')
                 and binding['chainId'] == p['task']['policy']['chainId'] and binding['actor'] == p['task']['policy']['actor'], 'EX_TASK_FENCE_CHILD_CHANGED')
        expected = record.get('resolvedChild') or p['child']
        _require(expected is None or expected == child, 'EX_TASK_FENCE_CHILD_CHANGED')
        operations = [op for op in model.operations.values() if op.commitment == p['commitment']]
        _require(len(operations) == 1, 'EX_TASK_FENCE_ORIGINAL_OPERATION_REQUIRED')
        operation = operations[0]
        facts = decode_exchange_snapshot(row['components']['owned-facts'])
        _require(any(leg.deferred_obligation_id == operation.obligation for leg in facts.domain['_legs'].get(p['receiptId'],())), 'EX_TASK_FENCE_RECEIPT_DIFFERS')
        return row, model, state, record, p, child, binding, operation

    def claim(self, event, *, expected_generation=None):
        if self._asset_event(event):
            _require(self.asset_return is not None, "original asset fence UNBOUND")
            return self.asset_return.claim(event, expected_generation=expected_generation)
        row, model, state, record, p, child, binding, operation = self._context(event)
        _require(expected_generation is None or row['generation'] == expected_generation, 'EX_TASK_FENCE_STALE_GENERATION')
        prior = record.get('dispatchClaim')
        if prior is not None:
            _require(prior['binding'] == binding and prior['operation'] == operation.identity
                     and prior['commitment'] == operation.commitment and operation.status == 'UNKNOWN', 'EX_TASK_FENCE_CLAIM_CHANGED')
            return deepcopy(prior)
        # An UNKNOWN written by another path is not permission to re-dispatch.
        # EX's new explicit path must use this same claim before Wallet execute.
        _require(operation.status == 'PREPARED', 'EX_TASK_FENCE_UNKNOWN_WITHOUT_CLAIM')
        # Reuse the original native funding/task binding preflight for BOTH
        # background and explicit send paths, before this same-generation CAS.
        _, native = self.original_ports._bound(deepcopy(operation))
        _require(native.task_digest==binding['taskDigest'] and native.child_digest==binding['childDigest']
                 and native.operation_id==binding['operationId'] and native.source_chain==int(binding['chainId']), 'EX_TASK_FENCE_NATIVE_BINDING_DIFFERS')
        self.checkpoint._guard_owned_rollback(row, model, 'mark_dispatched', (operation.identity,), {})
        model.mark_dispatched(operation.identity, now=self.now())
        snapshot = model.snapshot()
        DeferredSettlement.restore(self.checkpoint.profile, self.checkpoint.verifier, snapshot)
        claim = {'schema':'8415-ex-dispatch-claim/1','scope':self.preparation.scope,
                 'operation':operation.identity,'commitment':operation.commitment,
                 'generation':row['generation']+1,'binding':binding}
        # Digest identifies immutable claim bytes, NOT a proof from an HTTP ack.
        claim['digest'] = hashlib.sha256(canonical_json(claim).encode()).hexdigest()
        record['resolvedChild']=child; record['reserveClaimed']=True; record['dispatchClaim']=claim
        record['phase']='outcome-unknown'
        components = dict(row['components'])
        components[COMPONENT]=_encode(state)
        components[self.checkpoint.COMPONENT]=canonical_json(snapshot).encode()
        self.preparation.store.save(self.preparation.scope,components,expected_generation=row['generation'],
            immutable_components=tuple(k for k in components if k not in (COMPONENT,self.checkpoint.COMPONENT)))
        # Never release a capability following unknown/failed persistence.
        self.assert_claim(event, claim)
        return deepcopy(claim)

    def assert_claim(self, event, receipt):
        if self._asset_event(event):
            _require(self.asset_return is not None, "original asset fence UNBOUND")
            return self.asset_return.assert_claim(event, receipt)
        row, model, state, record, p, child, binding, operation = self._context(event)
        claim=record.get('dispatchClaim')
        _require(type(receipt) is dict and claim == receipt and claim is not None
                 and claim['binding'] == binding and claim['operation'] == operation.identity
                 and claim['commitment'] == operation.commitment and row['generation'] >= claim['generation']
                 and operation.status == 'UNKNOWN', 'EX_TASK_FENCE_NOT_CURRENT')
        return deepcopy(claim)
