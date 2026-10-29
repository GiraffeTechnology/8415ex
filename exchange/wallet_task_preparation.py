"""Same-aggregate preparation of original Wallet exact-operation proposals.

No approval, signing, execution, ledger, policy compiler or credential is added.
The original host resolves immutable canonical envelopes from its private task
journal. The original Wallet remains the policy/child validator and sole nonce
and budget authority. This component records coordination, never economic facts.
"""
from copy import deepcopy
import json
import re
from urllib.parse import quote
from .wallet_api_client import WalletAPIClient

COMPONENT = 'wallet-task-proposals'


class TaskPreparationRefused(ValueError):
    pass


def _require(condition, code):
    if not condition:
        raise TaskPreparationRefused(code)


def _digest(value):
    return type(value) is str and re.fullmatch(r'0x[0-9a-f]{64}', value) and int(value[2:], 16) != 0


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


class WalletTaskPreparation:
    """Explicit opt-in companion in the existing full-row CAS store.

    resolve(proposal_id) must read original, immutable, canonical task/child
    envelopes and their EX commitment from the original trusted journal. It is
    not an HTTP JSON decoder or an issuer of authority. Construction performs no
    IO, initialization or migration. Original source checks remain host duties.
    """
    def __init__(self, store, scope, client, resolve, *, receipt_id):
        _require(COMPONENT in store.components and isinstance(client, WalletAPIClient)
                 and callable(resolve), 'EX_TASK_PREPARATION_BINDING_REQUIRED')
        self.store, self.scope, self.client, self.resolve = store, scope, client, resolve
        self.receipt_id = receipt_id

    def _proposal(self, proposal_id):
        _require(type(proposal_id) is str and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', proposal_id), 'EX_TASK_PROPOSAL_ID_REFUSED')
        p = deepcopy(self.resolve(proposal_id))
        _require(type(p) is dict and set(p) == {'id','scope','receiptId','commitment','task','child'}
                 and p['id'] == proposal_id and p['scope'] == self.scope and p['receiptId'] == self.receipt_id and _digest(p['commitment']), 'EX_TASK_PROPOSAL_BINDING_REFUSED')
        task, child = p['task'], p['child']
        _require(type(task) is dict and set(task) == {'policy','digest'} and _digest(task['digest']), 'EX_TASK_CANONICAL_ENVELOPES_REQUIRED')
        policy = task['policy']
        _require(type(policy) is dict and policy.get('schema') == '8415-agent-task/1'
                 and policy.get('origin') == self.client._origin and policy.get('tenant') == self.client._tenant
                 and policy.get('actor') == self.client._account and policy.get('chainId') == self.client._chain
                 and type(policy.get('intent')) is dict and policy['intent'].get('kind') == 'exact-operation'
                 and type(policy['intent'].get('operation')) is dict, 'EX_TASK_EXACT_OWNER_SCOPE_REQUIRED')
        _require(policy['intent']['operation'].get('kind') in ('native-transfer','erc20-transfer','erc721-transfer',
                 'erc1155-transfer','create-account','deposit','standalone-withdraw','complete','return-hop'), 'EX_TASK_NATIVE_OPERATION_UNSUPPORTED')
        if child is not None:
            self._child(p, child)
        _require(len(_encode(p)) <= 65536, 'EX_TASK_PROPOSAL_TOO_LARGE')
        return p

    def _child(self, p, frozen):
        _require(type(frozen) is dict and set(frozen) == {'child','digest'} and _digest(frozen['digest']), 'EX_TASK_CHILD_REFUSED')
        c = frozen['child']
        _require(type(c) is dict and c.get('schema') == '8415-agent-child/1'
                 and c.get('taskDigest') == p['task']['digest']
                 and c.get('operation') == p['task']['policy']['intent']['operation']
                 and c.get('market') is None, 'EX_TASK_CHILD_SCOPE_DIFFERS')
        return deepcopy(frozen)

    def _row(self, generation):
        row = self.store.read(self.scope)
        _require(type(generation) is int and row is not None and row['generation'] == generation, 'EX_TASK_STALE_GENERATION')
        state = json.loads(row['components'][COMPONENT])
        _require(type(state) is dict and set(state) == {'schema','proposals'}
                 and state['schema'] == '8415-ex-task-proposals/1' and type(state['proposals']) is dict, 'EX_TASK_COMPONENT_REFUSED')
        for record in state['proposals'].values():
            _require(type(record) is dict and set(record) == {'proposal','phase','reserveClaimed','resolvedChild','dispatchClaim'}
                     and type(record['reserveClaimed']) is bool, 'EX_TASK_COORDINATION_RECORD_REFUSED')
        return row, state

    def _save(self, row, state):
        values = dict(row['components']); values[COMPONENT] = _encode(state)
        self.store.save(self.scope, values, expected_generation=row['generation'],
                        immutable_components=tuple(k for k in values if k != COMPONENT))
        return self.store.read(self.scope)

    def _record(self, row, state, p, phase):
        old = state['proposals'].get(p['id'])
        _require(old is None or old['proposal'] == p, 'EX_TASK_ORIGINAL_PROPOSAL_CHANGED')
        state['proposals'][p['id']] = {'proposal': p, 'phase': phase,
            'resolvedChild': deepcopy(old.get('resolvedChild')) if old else None,
            'dispatchClaim': deepcopy(old.get('dispatchClaim')) if old else None,
            'reserveClaimed': bool(old and old.get('reserveClaimed')) or phase in ('reserve-unknown','reserved','outcome-unknown','submitted','cancelled')}
        return self._save(row, state)

    def _view(self, p, body):
        _require(type(body) is dict and body.get('task') == p['task'], 'EX_TASK_WALLET_POLICY_DIFFERS')
        return body

    def prepare(self, proposal_id, generation):
        p = self._proposal(proposal_id); row, state = self._row(generation)
        # Durable claim before remote write; even a refused or lost request is
        # reconciled through the exact task. Never erase or recreate the claim.
        _require(proposal_id not in state['proposals'], 'EX_TASK_RECONCILE_EXISTING_PROPOSAL')
        self._record(row, state, p, 'prepare-unknown')
        self._view(p, self.client.task('prepare', {'policy': deepcopy(p['task']['policy'])}))
        # Deliberately discard challengeId and all credential-bound fields.
        return {'state':'prepared-awaiting-owner', 'taskDigest':p['task']['digest'],
                'authorization':'NOT_GRANTED', 'requiresReconciliation':True}

    def reconcile(self, proposal_id, generation):
        p = self._proposal(proposal_id); row, state = self._row(generation)
        previous = state['proposals'].get(proposal_id)
        _require(previous is not None and previous['proposal'] == p, 'EX_TASK_ORIGINAL_PROPOSAL_CHANGED')
        body = self._view(p, self.client.task('status', {'taskDigest':p['task']['digest']}))
        status = body.get('effectiveStatus')
        _require(status in ('pending','authorized','revoked','expired','suspended'), 'EX_TASK_STATUS_REFUSED')
        selected = None
        expected_child = previous.get('resolvedChild') or p['child']
        if status == 'authorized':
            budget = body.get('budget')
            _require(type(budget) is dict and budget.get('taskDigest') == p['task']['digest']
                     and type(budget.get('revision')) is str and re.fullmatch(r'0|[1-9][0-9]{0,77}',budget['revision'])
                     and type(budget.get('reservations')) is list, 'EX_TASK_BUDGET_REFUSED')
            for item in budget['reservations']:
                _require(type(item) is dict, 'EX_TASK_RESERVATION_REFUSED')
                if expected_child is None or item.get('operationId') == expected_child['child']['operationId']:
                    _require(selected is None and (expected_child is None or item.get('childDigest') == expected_child['digest']), 'EX_TASK_CHILD_DIFFERS')
                    selected = item
            if selected is not None and expected_child is None:
                # The observed nonempty budget revision fences this readback:
                # a concurrent cancellation/revision change must fail at Wallet.
                envelope = self.client.task('plan-reserve', {'taskDigest':p['task']['digest'], 'expectedBudgetRevision':budget['revision']})
                child = self._planned(p, envelope)
                _require(child['digest'] == selected.get('childDigest') and child['child']['operationId'] == selected.get('operationId'), 'EX_TASK_RESERVED_CHILD_CHANGED')
                previous['resolvedChild'] = child
        phase = status
        if selected is not None:
            _require(selected.get('status') in ('reserved','outcome-unknown','submitted','cancelled'), 'EX_TASK_RESERVATION_REFUSED')
            phase = selected['status']
        # A missing reservation after an uncertain reserve does not authorize
        # replay: there may be an in-flight original request. Retain UNKNOWN.
        if previous.get('reserveClaimed') is True and selected is None:
            phase = 'reserve-unknown'
        fresh = self._record(row, state, p, phase)
        return {'state':phase,'generation':fresh['generation'], 'taskDigest':p['task']['digest'],
                'nativeOutcomeVerified':False,'executionAuthorized':False}

    def reserve(self, proposal_id, generation):
        p = self._proposal(proposal_id); row, state = self._row(generation)
        old = state['proposals'].get(proposal_id)
        _require(old is not None and old['proposal'] == p and old['phase'] == 'authorized' and old.get('reserveClaimed') is False, 'EX_TASK_AUTHORIZE_OR_RECONCILE_FIRST')
        body = self._view(p, self.client.task('status', {'taskDigest':p['task']['digest']}))
        budget = body.get('budget')
        _require(body.get('effectiveStatus') == 'authorized' and type(budget) is dict
                 and budget.get('taskDigest') == p['task']['digest'] and budget.get('reservations') == []
                 and type(budget.get('revision')) is str and re.fullmatch(r'0|[1-9][0-9]{0,77}',budget['revision']), 'EX_TASK_NOT_EMPTY_AUTHORIZED_BUDGET')
        # Refuse concurrent/revised aggregate before reserving. Original Wallet
        # atomically fences grant revocation, quota, nonce and operation identity.
        self._record(row, state, p, 'reserve-unknown')
        if p['child'] is None:
            # No nonce/wire/fee construction in EX. Original authorized Wallet
            # planner and original atomic reservation produce the exact child.
            self._planned(p, self.client.task('plan-reserve', {'taskDigest':p['task']['digest'], 'expectedBudgetRevision':budget['revision']}))
        else:
            self._view(p, self.client.task('reserve', {'taskDigest':p['task']['digest'],
                'child':deepcopy(p['child']['child']), 'expectedBudgetRevision':budget['revision']}))
        return {'state':'reserve-unknown','requiresReconciliation':True,'executionAuthorized':False}

    def _planned(self, p, envelope):
        _require(type(envelope) is dict and set(envelope) == {'schema','status','child','reservation'}
                 and envelope['schema'] == '8415-task-plan-reservation/1', 'EX_TASK_PLANNER_RESPONSE_REFUSED')
        view = self._view(p, envelope['status']); child = self._child(p, envelope['child'])
        reservation = envelope['reservation']
        _require(type(reservation) is dict and reservation.get('operationId') == child['child'].get('operationId')
                 and reservation.get('childDigest') == child['digest']
                 and reservation.get('status') in ('reserved','outcome-unknown','submitted')
                 and reservation in view.get('budget',{}).get('reservations',[]), 'EX_TASK_PLANNER_NOT_PERSISTED')
        return child

    def owns_operation(self, operation):
        if operation.kind not in ('seller-payment','excess-refund','rollback'):
            return False
        row=self.store.read(self.scope);_,state=self._row(row['generation'])
        return any(r['proposal']['commitment']==operation.commitment for r in state['proposals'].values())

    def native_binding(self, operation):
        """Read original Wallet reserved child for the exact original proposal.

        This is a source resolver for existing DeferredWalletPorts, not a new
        grant or reservation. A nonempty same-revision budget is mandatory.
        """
        from .deferred_wallet_ports import NativeTaskBinding
        row=self.store.read(self.scope);_,state=self._row(row['generation'])
        matches=[r for r in state['proposals'].values() if r['proposal']['commitment']==operation.commitment]
        _require(len(matches)==1, 'EX_TASK_ORIGINAL_PROPOSAL_REQUIRED')
        record=matches[0];p=self._proposal(record['proposal']['id'])
        _require(p==record['proposal'], 'EX_TASK_ORIGINAL_PROPOSAL_CHANGED')
        body=self._view(p,self.client.task('status',{'taskDigest':p['task']['digest']}))
        budget=body.get('budget',{});rows=budget.get('reservations',[])
        _require(len(rows)==1 and rows[0].get('status') in ('reserved','outcome-unknown','submitted'), 'EX_TASK_ORIGINAL_RESERVATION_REQUIRED')
        child=record['resolvedChild'] or p['child']
        if child is None:
            child=self._planned(p,self.client.task('plan-reserve',{'taskDigest':p['task']['digest'],'expectedBudgetRevision':budget['revision']}))
        _require(rows[0].get('childDigest')==child['digest'] and rows[0].get('operationId')==child['child']['operationId'], 'EX_TASK_RESERVED_CHILD_CHANGED')
        funding=operation.normal_funding
        _require(operation.kind in ('seller-payment','excess-refund','rollback') and funding is not None
                 and funding['chain']==11155111 and funding['asset']=='ETH', 'EX_TASK_NATIVE_FUNDING_UNSUPPORTED')
        terms=funding['terms'];fees=child['child']['fees']
        _require(int(fees['gasLimit'])*int(fees['maxFeePerGasWei'])<=terms['capWei'], 'EX_TASK_NATIVE_FUNDING_CAP_DIFFERS')
        return NativeTaskBinding(operation.commitment,11155111,p['task']['digest'],child['child']['operationId'],
            child['digest'],budget['revision'],funding_payer=terms['payer'],funding_budget=terms['budget'],
            funding_asset='ETH',funding_cap_units=terms['capWei'])

    def dispatch_operation(self, operation_id, generation, execution_port):
        """Explicit EX dispatch uses the SAME original claim as background send."""
        _require(getattr(self, 'fence', None) is not None, 'EX_TASK_FENCE_REQUIRED')
        row, model = self.fence.checkpoint.read()
        _require(row['generation'] == generation, 'EX_TASK_STALE_GENERATION')
        operation = model.operations.get(operation_id)
        _require(operation is not None, 'EX_TASK_ORIGINAL_OPERATION_REQUIRED')
        _, state = self._row(generation)
        records=[r for r in state['proposals'].values() if r['proposal']['commitment']==operation.commitment]
        _require(len(records)==1, 'EX_TASK_ORIGINAL_PROPOSAL_REQUIRED')
        record=records[0];p=record['proposal'];child=record['resolvedChild'] or p['child']
        _require(child is not None and operation.status == 'PREPARED', 'EX_TASK_RECONCILE_BEFORE_DISPATCH')
        status=self._view(p,self.client.task('status',{'taskDigest':p['task']['digest']}))
        _require(status.get('effectiveStatus')=='authorized', 'EX_TASK_NOT_AUTHORIZED')
        budget=status.get('budget',{})
        matching=[r for r in budget.get('reservations',[]) if r.get('operationId')==child['child']['operationId'] and r.get('childDigest')==child['digest'] and r.get('status')=='reserved']
        _require(len(matching)==1, 'EX_TASK_ORIGINAL_RESERVATION_REQUIRED')
        event={'task':p['task'],'child':child,'binding':{
            'taskDigest':p['task']['digest'],'childDigest':child['digest'],
            'operationId':child['child']['operationId'],'chainId':p['task']['policy']['chainId'],
            'actor':p['task']['policy']['actor'],'nonce':child['child']['nonce'],
            'executorDigest':status['executor']['digest'],
            'grantPolicyVersion':status['authorization']['grantPolicyVersion']}}
        # Original read-only binding preflight still checks native funding.
        execute=execution_port.prepare_original(deepcopy(operation))
        _require(callable(execute), 'EX_TASK_ORIGINAL_EXECUTION_PORT_REQUIRED')
        claim=self.fence.claim(event, expected_generation=generation)
        _, current=self.fence.checkpoint.read()
        try:
            execute(deepcopy(current.operations[operation_id]))
        except Exception:
            pass  # Persisted UNKNOWN is never retryable on transport failure.
        return {'status':'UNKNOWN','generation':claim['generation'],'dispatched':True,'confirmed':False}

    def owner_url(self, proposal_id, generation):
        p = self._proposal(proposal_id); row, state = self._row(generation)
        old = state['proposals'].get(proposal_id)
        _require(old is not None and old['proposal'] == p, 'EX_TASK_RECONCILE_EXISTING_PROPOSAL')
        locator = {'schema':'8415-ex-task-locator/1','tenant':self.client._tenant,
                   'chainId':self.client._chain,'taskDigest':p['task']['digest']}
        return self.client._origin + (self.client._base_path or '/v3') + '#wallet-task=' + quote(json.dumps(locator,separators=(',',':')),safe='')
