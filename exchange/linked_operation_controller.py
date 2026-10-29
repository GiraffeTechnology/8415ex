"""Restricted original-host commands for already existing linked operations.

The public EX demo remains simulated. This controller is not public native
registration or a new authority issuer. A host-authenticated caller (not the
EX service's Wallet login) must be checked before every command, including
reads. No HTTP body supplies an account, scope, verifier, evidence or callback.
"""
from dataclasses import dataclass
import re
from .wallet_v3_composition import WalletV3LinkedRuntime
from .exchange_fact_snapshot import decode_exchange_snapshot
from .public_workbench import command_result


class LinkedOperationRefused(ValueError):
    pass


@dataclass(frozen=True)
class OriginalLinkedCaller:
    """Returned only by the separately approved original host auth adapter."""
    scope: str
    receipt_id: str
    tenant: str
    account: str
    allowed_actions: frozenset


class LinkedOperationController:
    ACTIONS = frozenset({'review', 'observe', 'dispatch', 'oracle-observe', 'deadline', 'task-prepare', 'task-reconcile', 'task-reserve', 'task-review', 'recovery-view', 'recovery-prepare', 'recovery-confirm', 'economic-observe', 'economic-confirm'})

    def __init__(self, linked, mapping, *, receipt_id, authenticate, current_time, task_preparation=None, recovery_workflow=None, economic_verifier=None):
        if (type(linked) is not WalletV3LinkedRuntime or not callable(authenticate)
                or not callable(current_time) or type(receipt_id) is not str or not receipt_id
                or mapping.store is not linked.runtime.checkpoint.store
                or mapping.scope != linked.runtime.checkpoint.scope):
            raise LinkedOperationRefused('same original aggregate, receipt and auth adapter required')
        self.linked, self.mapping = linked, mapping
        self.economic_verifier = economic_verifier
        if economic_verifier is not None:
            from .direct_terminal_verifier import DirectTerminalVerifier
            if (type(economic_verifier) is not DirectTerminalVerifier
                    or economic_verifier.observer.checkpoint is not linked.runtime.checkpoint
                    or economic_verifier.observer.preparation.receipt_id != receipt_id):
                raise LinkedOperationRefused('same original economic verifier required')
        self.task_preparation = task_preparation
        self.recovery_workflow = recovery_workflow
        if recovery_workflow is not None:
            from .linked_recovery_workflow import LinkedRecoveryWorkflow
            if (type(recovery_workflow) is not LinkedRecoveryWorkflow or recovery_workflow.store is not mapping.store
                    or recovery_workflow.scope != mapping.scope or recovery_workflow.receipt_id != receipt_id):
                raise LinkedOperationRefused("same original recovery scope required")
        if task_preparation is not None and (task_preparation.store is not mapping.store or task_preparation.scope != mapping.scope or task_preparation.receipt_id != receipt_id or task_preparation.client is not linked.settlement):
            raise LinkedOperationRefused("same original task preparation scope required")
        self.receipt_id, self.authenticate, self.current_time = receipt_id, authenticate, current_time

    def _guard(self, request, action):
        # The adapter must validate the actual caller on each request. A Wallet
        # client cookie belonging to this EX service is not caller identity.
        caller = self.authenticate(request)
        if (type(caller) is not OriginalLinkedCaller
                or type(caller.allowed_actions) is not frozenset
                or action not in caller.allowed_actions
                or caller.scope != self.linked.runtime.checkpoint.scope
                or caller.receipt_id != self.receipt_id
                or caller.tenant != self.linked.settlement._tenant
                or caller.account != self.linked.settlement._account):
            raise PermissionError('original linked caller authority unavailable')
        return caller

    @staticmethod
    def _identity(value):
        if type(value) is not str or re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', value) is None:
            raise LinkedOperationRefused('bounded original identity required')
        return value

    def execute(self, request, action, payload):
        if action not in self.ACTIONS or type(payload) is not dict:
            raise LinkedOperationRefused('explicit linked action required')
        self._guard(request, action)
        fields = {'generation', 'operation'} if action in ('review','observe','dispatch') else (
            {'generation','request','logIndex','version'} if action == 'oracle-observe'
            else {'generation','obligation'})
        if action.startswith('task-'):
            fields = {'generation','proposal'}
        if action.startswith('economic-'):
            fields = {'generation','operation'}
        if action.startswith('recovery-'):
            fields = {'generation'}
        if action == 'dispatch':
            fields = fields | {'confirm'}
        if set(payload) != fields or type(payload['generation']) is not int:
            raise LinkedOperationRefused('exact typed linked payload required')
        generation = payload['generation']
        row, model = self.linked.runtime.checkpoint.read()
        if row['generation'] != generation:
            raise LinkedOperationRefused('original aggregate changed; refresh')
        if action.startswith('economic-'):
            verifier = self.economic_verifier
            if verifier is None:
                raise LinkedOperationRefused('original economic verifier UNBOUND')
            operation = self._identity(payload['operation'])
            if action == 'economic-observe':
                report = verifier.observer.read(operation, expected_generation=generation)
                return {'status':'OBSERVATION_ONLY','generation':generation,
                        'economicFinality':'NOT_CONFIRMED','proofBinding':'BOUND' if verifier.bound else 'UNBOUND',
                        'dispatched':False,'confirmed':False}
            if self.linked.execution_mode != 'native-enabled':
                raise LinkedOperationRefused('native state changes disabled')
            return verifier.confirm_payment(operation, expected_generation=generation, now=self.current_time())
        if action.startswith('recovery-'):
            if self.recovery_workflow is None:
                raise LinkedOperationRefused('original recovery unavailable')
            if action == 'recovery-view':
                return self.recovery_workflow.view(generation)
            if action == 'recovery-confirm':
                if self.linked.execution_mode != 'native-enabled':
                    raise LinkedOperationRefused('native state changes disabled')
                return self.recovery_workflow.confirm_existing(generation,self.current_time())
            if action == 'recovery-prepare':
                if self.linked.execution_mode != 'native-enabled':
                    raise LinkedOperationRefused('native state changes disabled')
                return self.recovery_workflow.prepare_native(generation,self.current_time())
            raise LinkedOperationRefused('original production terminal verifier UNBOUND')
        if action.startswith('task-'):
            if self.task_preparation is None:
                raise LinkedOperationRefused('original proposal preparation unavailable')
            proposal = self._identity(payload['proposal'])
            if action == 'task-review':
                return {'status':'OWNER_TASK_REVIEW_REQUIRED','url':self.task_preparation.owner_url(proposal,generation),'dispatched':False}
            if action != 'task-reconcile' and self.linked.execution_mode != 'native-enabled':
                raise LinkedOperationRefused('native state changes disabled')
            method = {'task-prepare':'prepare','task-reconcile':'reconcile','task-reserve':'reserve'}[action]
            return getattr(self.task_preparation,method)(proposal,generation)
        facts = decode_exchange_snapshot(row['components']['owned-facts'])
        owned = {leg.deferred_obligation_id for leg in facts.domain['_legs'].get(self.receipt_id, ())}
        if action in ('review', 'observe', 'dispatch'):
            operation_id = self._identity(payload['operation'])
            operation = model.operations.get(operation_id)
            if operation is None or operation.obligation not in owned:
                raise LinkedOperationRefused('operation does not belong to original receipt')
            if action == 'review':
                return {'status':'OWNER_REVIEW_REQUIRED', 'url':self.linked.operation_review_url(
                    operation_id, expected_generation=generation), 'dispatched':False}
            if action == 'observe':
                result = self.linked.observe_operation(operation_id, expected_generation=generation)
                return {'status':'OBSERVATION_ONLY', 'observation':command_result(result),
                        'confirmed':False, 'dispatched':False}
            if payload['confirm'] != 'dispatch-existing-prepared-operation':
                raise LinkedOperationRefused('explicit existing-operation confirmation required')
            if self.task_preparation is not None and self.task_preparation.owns_operation(operation):
                if self.linked.execution_mode != 'native-enabled':
                    raise LinkedOperationRefused('native state changes disabled')
                return self.task_preparation.dispatch_operation(operation_id,generation,self.linked.runtime.wallet)
            result = self.linked.dispatch_once(operation_id, expected_generation=generation, now=self.current_time())
            return {'status':result.get('status','UNKNOWN'), 'generation':result['generation'],
                    'dispatched':result['dispatched'], 'confirmed':False}
        if self.linked.execution_mode != 'native-enabled':
            raise LinkedOperationRefused('native state changes disabled')
        if action == 'deadline':
            obligation = self._identity(payload['obligation'])
            if obligation not in owned:
                raise LinkedOperationRefused('obligation does not belong to original receipt')
            result = self.linked.runtime.joint.apply('deadline', obligation,
                expected_generation=generation, now=self.current_time())
            return {'status':'LOCAL_TRANSITION_RECORDED','generation':result['generation'],'dispatched':False}
        request_id = self._identity(payload['request'])
        original = facts.domain['_requests'].get(request_id)
        if original is None or original.receipt_id != self.receipt_id:
            raise LinkedOperationRefused('request does not belong to original receipt')
        result = self.mapping.observe(request_id, expected_generation=generation,
            log_index=payload['logIndex'], version=payload['version'], now=self.current_time())
        return {'status':'ORIGINAL_OBSERVATION_RECORDED','generation':result['generation'],'dispatched':False}
