"""Restricted original recovery orchestration; no dispatch or authority issuing.

The host must bind original proof bytes AND the original verifier. Content hashes
only pin bytes, not authority. Absent that host binding, mutation is UNBOUND.
"""
from copy import deepcopy
import hashlib
import os
import stat
from types import MappingProxyType
from .ids import canonical_json
from .mixed_suffix_recovery import MixedSuffixRecovery, MixedRecoveryRefused


def proof_key(request):
    return hashlib.sha256(canonical_json(request).encode()).hexdigest()


class PrivateRecoveryProofs:
    """Read pinned bytes through an already-held private directory capability.

    Manifest keys are derived internally, never HTTP input. The original host
    owns directory/manifest and must separately authenticate each proof through
    MixedSuffixRecovery's original verifier. No path discovery or network read.
    """
    def __init__(self, directory_fd, manifest):
        if type(directory_fd) is not int or not stat.S_ISDIR(os.fstat(directory_fd).st_mode):
            raise ValueError('held original private directory required')
        captured = deepcopy(manifest)
        if type(captured) is not dict:
            raise ValueError('explicit pinned manifest required')
        for key, entry in captured.items():
            if (type(key) is not str or len(key) != 64 or any(c not in '0123456789abcdef' for c in key)
                    or type(entry) is not dict or set(entry) != {'file','sha256'}
                    or type(entry['file']) is not str or not entry['file']
                    or entry['file'] in ('.','..') or '/' in entry['file'] or '\\' in entry['file']
                    or type(entry['sha256']) is not str or len(entry['sha256']) != 64
                    or any(c not in '0123456789abcdef' for c in entry['sha256'])):
                raise ValueError('single-level pinned evidence entries required')
        self._manifest = MappingProxyType({k:MappingProxyType(v) for k,v in captured.items()})
        self._fd = os.dup(directory_fd)

    def close(self):
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def read(self, request):
        if self._fd is None:
            raise MixedRecoveryRefused('original proof capability closed')
        entry = self._manifest.get(proof_key(request))
        if entry is None:
            raise MixedRecoveryRefused('original proof unavailable')
        fd = os.open(entry['file'], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=self._fd)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= 1048576:
                raise MixedRecoveryRefused('bounded original regular proof required')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                raw = stream.read(1048577)
            if len(raw) != info.st_size or hashlib.sha256(raw).hexdigest() != entry['sha256']:
                raise MixedRecoveryRefused('original proof bytes changed')
            return raw
        finally:
            os.close(fd)


class LinkedRecoveryWorkflow:
    def __init__(self, recovery, receipt_id, *, proofs=None, simulation=False, economic_verifier=None, asset_verifier=None, native_preparation=None):
        if type(recovery) is not MixedSuffixRecovery or type(receipt_id) is not str or not receipt_id:
            raise ValueError('original recovery and receipt required')
        if proofs is not None and type(proofs) is not PrivateRecoveryProofs:
            raise ValueError('fixed private proof source required')
        if type(simulation) is not bool:
            raise ValueError("explicit simulation mode required")
        if native_preparation is not None:
            from .native_recovery_preparation import NativeRecoveryPreparation
            if (type(native_preparation) is not NativeRecoveryPreparation
                    or native_preparation.recovery is not recovery
                    or native_preparation.receipt_id != receipt_id or simulation):
                raise ValueError("same original native preparation required")
        self.native_preparation = native_preparation
        self.economic_verifier = economic_verifier
        self.asset_verifier = asset_verifier
        self.simulation = simulation
        self.recovery, self.receipt_id, self.proofs = recovery, receipt_id, proofs
        self.store, self.scope = recovery.service.store, recovery.service.scope

    def view(self, generation):
        row, model, ex = self.recovery._load(generation)
        state = ex._rollbacks.get(self.receipt_id)
        result = {'generation':row['generation'], 'proofBinding':'SIMULATION_ONLY' if self.simulation and self.proofs else 'UNBOUND',
                  'dispatched':False,'executionAuthorized':False,'canConfirmExistingRefund':False,'canConfirmExistingAssetReturn':False}
        if state is None:
            return dict(result,status='NO_RECOVERY',index=None,kind=None)
        if 'mixedRecovery' not in state:
            return dict(result,status='UNPREPARED',index=None,kind=None)
        step = self.recovery.next_required_step(self.receipt_id,expected_generation=generation)
        if step['index'] is not None and step['requiredOutcome']['kind']=='deferred-rollback':
            try:
                self._bound_refund(generation)
                result.update(proofBinding='BOUND_DEFERRED_REFUND_ONLY',canConfirmExistingRefund=True)
            except MixedRecoveryRefused:
                pass
        if step['index'] is not None and step['requiredOutcome']['kind']=='asset-return':
            try:
                self._bound_asset(generation)
                result.update(proofBinding='BOUND_EXISTING_ASSET_RETURN_ONLY',canConfirmExistingAssetReturn=True)
            except (ValueError, MixedRecoveryRefused):
                pass
        return dict(result,status='COMPLETE' if step['index'] is None else 'PENDING',
                    index=step['index'],kind=None if step['requiredOutcome'] is None else step['requiredOutcome']['kind'])

    def _bound_asset(self,generation):
        from .mixed_asset_return import MixedAssetReturn
        asset = self.asset_verifier
        if (type(asset) is not MixedAssetReturn or not asset.bound or asset.core is not self.recovery
                or asset.receipt_id != self.receipt_id
                or getattr(self.recovery.verify_terminal,'__self__',None) is not asset):
            raise MixedRecoveryRefused('original asset verifier UNBOUND')
        asset.existing(generation)
        return asset

    def confirm_existing(self,generation,now):
        step=self.recovery.next_required_step(self.receipt_id,expected_generation=generation)
        if step['index'] is not None and step['requiredOutcome']['kind']=='asset-return':
            result=self._bound_asset(generation).confirm(generation,now)
            return self.view(result['generation'])
        return self.confirm_existing_refund(generation,now)

    def _bound_refund(self, generation):
        from .direct_terminal_verifier import DirectTerminalVerifier
        verifier = self.economic_verifier
        if (type(verifier) is not DirectTerminalVerifier or not verifier.bound
                or verifier.observer.checkpoint is not self.recovery.service
                or self.recovery.service.verifier is not verifier
                or verifier.observer.preparation.receipt_id != self.receipt_id):
            raise MixedRecoveryRefused('original configured refund verifier UNBOUND')
        step = self.recovery.next_required_step(self.receipt_id,expected_generation=generation)
        if (step['index'] is None or step['requiredOutcome']['kind'] != 'deferred-rollback'
                or len(step['reconcileOperations']) != 1):
            raise MixedRecoveryRefused('original first deferred refund UNBOUND; reconcile')
        row, model = self.recovery.service.read()
        if row['generation'] != generation:
            raise MixedRecoveryRefused('original generation changed')
        operation = model.operations[step['reconcileOperations'][0]]
        required = step['requiredOutcome']
        if ((operation.kind,operation.obligation,operation.units,operation.chain,operation.asset,operation.recipient)
                != ('rollback',required['obligation'],required['units'],required['chain'],required['asset'],required['recipient'])
                or operation.status not in ('UNKNOWN','CONFIRMED')
                or model.obligations[operation.obligation].mixed_recovery != step['plan']):
            raise MixedRecoveryRefused('original issued refund/plan differs')
        return step, operation, verifier

    def confirm_existing_refund(self, generation, now):
        # Display flags grant nothing. Every POST rechecks the concrete verifier,
        # exact original first step and issued operation against the same row.
        step, operation, verifier = self._bound_refund(generation)
        result = self.recovery.confirm(self.receipt_id,expected_generation=generation,now=now,
            confirmations={str(step['index']):{'operation':operation.identity,
                'raw':verifier.locator(operation.identity)}})
        # Exactly one existing step is consumed; no dispatch or next-step loop.
        return self.view(result['generation'])

    def prepare_native(self, generation, now):
        capability = self.native_preparation
        if (capability is None or capability.recovery is not self.recovery
                or capability.receipt_id != self.receipt_id or self.simulation):
            raise MixedRecoveryRefused('original native preparation UNBOUND')
        result = capability.prepare(generation, now)
        return self.view(result['generation'])

    def _read(self, request):
        if self.proofs is None or not self.simulation:
            raise MixedRecoveryRefused('original proof/verifier binding UNBOUND')
        return self.proofs.read(request)

    def prepare(self, generation, now):
        row, model, ex = self.recovery._load(generation)
        state = ex._rollbacks.get(self.receipt_id)
        if state is None:
            raise MixedRecoveryRefused('original unresolved suffix required')
        evidence = {}
        for index in reversed(state['affectedLegs']):
            leg = ex.leg(self.receipt_id,index)
            if leg.deferred_obligation_id is not None:
                oid = leg.deferred_obligation_id
                evidence[oid] = self._read({'schema':'ex-recovery-proof-key/1','scope':self.scope,
                    'receipt':self.receipt_id,'kind':'rollback-authority','authority':state['authorityId'],
                    'obligation':oid,'terms':model.obligations[oid].consent})
        # No partial save: original backend verifies the complete authority set.
        if self.proofs is None or not self.simulation:
            raise MixedRecoveryRefused('original proof/verifier binding UNBOUND')
        result = self.recovery.prepare(self.receipt_id,expected_generation=generation,now=now,rollback_evidence=evidence)
        return self.view(result['generation'])

    def confirm(self, generation, now):
        step = self.recovery.next_required_step(self.receipt_id,expected_generation=generation)
        if step['index'] is None:
            return self.view(generation)
        request = {'schema':'ex-recovery-proof-key/1','scope':self.scope,'receipt':self.receipt_id,
                   'kind':'terminal','plan':step['plan'],'index':step['index'],'outcome':step['requiredOutcome']}
        entry = {}
        if step['requiredOutcome']['kind'] == 'deferred-rollback':
            operations = step['reconcileOperations']
            if len(operations) != 1:
                raise MixedRecoveryRefused('one original issued rollback required; reconcile')
            row, model = self.recovery.service.read()
            if row['generation'] != generation:
                raise MixedRecoveryRefused('original generation changed')
            entry['operation'] = operations[0]
            request['operationCommitment'] = model.operations[operations[0]].commitment
        entry['raw'] = self._read(request)
        result = self.recovery.confirm(self.receipt_id,expected_generation=generation,now=now,
                                       confirmations={str(step['index']):entry})
        return self.view(result['generation'])
