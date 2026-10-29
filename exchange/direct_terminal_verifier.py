"""Concrete configured trusted verifier for one approved direct ERC20 route.

Implements the original EvidenceVerifier Protocol. No new signature, keys, trust
root, RPC endpoint or economic policy. Original host approval/source/profile and
finality bindings are required deployment inputs; no token is approved by default.
"""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from .ids import canonical_json,digest,identifier
from .receipt_gas_observer import _pairs
from .deferred_settlement import Fact
from .direct_erc20_observation import DirectERC20Observation,need
from .original_deferred_proposal_source import OriginalDeferredProposalSource

PREFIX=b'EX-DIRECT-TERMINAL/1\n'
PROXY_SEMANTICS=['paxos-zeppelinos-fixed-implementation','no-fee','no-rebase','complete-transfer-events','exact-direct-transfer']
SEMANTICS=['non-proxy','no-fee','no-rebase','complete-transfer-events','exact-direct-transfer']


class DirectTerminalVerifier:
    def __init__(self, observer, original_verifier, *, approved_profile=None):
        need(type(observer) is DirectERC20Observation and callable(getattr(original_verifier,'verify',None)),
             'original observer and existing verifier required')
        self.observer,self.original=observer,original_verifier
        self._approved=deepcopy(approved_profile)
        if self._approved is not None:
            source=observer.preparation.resolve
            need(type(source) is OriginalDeferredProposalSource
                 and source.checkpoint is observer.checkpoint
                 and source.asset['contract']==observer.pin['contract']
                 and source.custody['location']==observer.checkpoint.profile.escrow,
                 'concrete original custody/principal source required')
            p=self._approved
            need(type(p) is dict and set(p)=={'schema','approvalReference','profileSha256','profile'},
                 'original approved profile envelope required')
            need(p['schema']=='ex-approved-direct-token-profile/1','explicit profile version required')
            identifier(p['approvalReference'])
            body=p['profile'];pin=observer.pin
            expected={
                'chainId':11155111,'contract':pin['contract'],'sourceSha256':pin['sourceSha256'],
                'runtimeCodeSha256':hashlib.sha256(bytes.fromhex(pin['runtimeCode'][2:])).hexdigest(),
                'semantics':PROXY_SEMANTICS if observer.proxy is not None else SEMANTICS,'route':'single-eoa-erc20-transfer',
                'finalityPolicy':'rpc-finalized-tag','trust':'original-host-configured-rpc',
                'scope':observer.checkpoint.scope,'asset':observer.checkpoint.profile.principal_asset}
            if observer.proxy is not None:
                expected['proxy']=observer.proxy.approval_terms()
            need(type(body) is dict and body==expected,'approved source/semantics/route/finality/scope differs')
            need(p['profileSha256']==hashlib.sha256(canonical_json(body).encode()).hexdigest(),
                 'approved profile byte pin differs')

    @property
    def bound(self):return self._approved is not None

    @staticmethod
    def locator(operation_id):
        identifier(operation_id)
        return PREFIX+canonical_json({'schema':'ex-direct-terminal-locator/1','operation':operation_id}).encode()

    def verify(self,evidence,*,kind,now):
        if kind!='terminal-operation-receipt':
            return self.original.verify(evidence,kind=kind,now=now)
        need(type(evidence) is bytes and 0<len(evidence)<=1048576,'bounded original evidence bytes required')
        if not evidence.startswith(PREFIX):
            return self.original.verify(evidence,kind=kind,now=now)
        # A reserved local locator prefix selects this implementation before
        # parsing; malformed marked bytes can never fall back to old authority.
        locator=json.loads(evidence[len(PREFIX):].decode('utf8'),object_pairs_hook=_pairs)
        need(type(locator) is dict,'original direct locator required')
        need(self.bound,'original token approval/source/finality UNBOUND')
        need(len(evidence)<=512 and set(locator)=={'schema','operation'}
             and locator['schema']=='ex-direct-terminal-locator/1','original direct locator required')
        identifier(locator['operation'])
        row,model=self.observer.checkpoint.read()
        report=self.observer.read(locator['operation'],expected_generation=row['generation'])
        op=model.operations[locator['operation']]
        need(type(now) is int and report['observedAt']<=now,'future chain observation')
        # Identity deliberately excludes operation: the same original tx/log
        # cannot be allocated to a different operation in original _fact ledger.
        return Fact(identity='direct:'+report['evidenceIdentity'],kind=kind,chain=op.chain,
            asset=op.asset,account=op.recipient,location=self.observer.checkpoint.profile.escrow,
            reference=op.commitment,units=report['observedTransferUnits'],observed_at=report['observedAt'],
            profile_commitment=digest(asdict(self.observer.checkpoint.profile)))

    def confirm_payment(self,operation_id,*,expected_generation,now):
        checkpoint=self.observer.checkpoint
        need(checkpoint.verifier is self,'original checkpoint must hold this exact configured verifier')
        row,model=checkpoint.read()
        need(row['generation']==expected_generation,'original generation changed')
        op=model.operations.get(operation_id)
        need(op is not None and op.kind in ('seller-payment','excess-refund'),
             'rollback requires original mixed-recovery first-step consumption')
        # Original backend verifier, evidence ledger and SAME full-row CAS own
        # the state change. A report/HTTP result is never directly credited.
        result=checkpoint.apply('confirm',operation_id,self.locator(operation_id),
                                expected_generation=expected_generation,now=now)
        return {'generation':result['generation'],'status':'ORIGINAL_PAYMENT_CONFIRMED','dispatched':False}
