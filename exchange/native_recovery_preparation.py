"""Bound original suffix-proof consumption; never a dispatcher or proof issuer.

Pinned files are only bytes. The original configured verifier authenticates all
of them inside MixedSuffixRecovery.prepare before its single whole-row CAS.
"""
from .linked_recovery_workflow import PrivateRecoveryProofs
from .mixed_suffix_recovery import MixedSuffixRecovery, MixedRecoveryRefused


class NativeRecoveryPreparation:
    def __init__(self, recovery, receipt_id, *, proofs, original_verifier):
        if (type(recovery) is not MixedSuffixRecovery or type(receipt_id) is not str
                or not receipt_id or type(proofs) is not PrivateRecoveryProofs
                or original_verifier is not recovery.service.verifier):
            raise MixedRecoveryRefused('exact original preparation binding required')
        self.recovery, self.receipt_id, self.proofs = recovery, receipt_id, proofs
        self.checkpoint = recovery.service
        self.store, self.scope = self.checkpoint.store, self.checkpoint.scope
        self.verifier = original_verifier

    def _guard(self):
        if (self.recovery.service is not self.checkpoint
                or self.checkpoint.store is not self.store
                or self.checkpoint.scope != self.scope
                or self.checkpoint.verifier is not self.verifier):
            raise MixedRecoveryRefused('original preparation binding changed')

    def prepare(self, generation, now):
        self._guard()
        row, model, ex = self.recovery._load(generation)
        state = ex._rollbacks.get(self.receipt_id)
        if state is None:
            raise MixedRecoveryRefused('original unresolved suffix required')
        # The core validates an existing plan and returns without a write. Do
        # not re-read proofs or create any operation on a lost response/restart.
        evidence = {}
        if 'mixedRecovery' not in state:
            for index in reversed(state['affectedLegs']):
                leg = ex.leg(self.receipt_id, index)
                oid = leg.deferred_obligation_id
                if oid is not None:
                    if oid in evidence:
                        raise MixedRecoveryRefused('duplicate original suffix obligation')
                    evidence[oid] = self.proofs.read({
                        'schema':'ex-recovery-proof-key/1','scope':self.scope,
                        'receipt':self.receipt_id,'kind':'rollback-authority',
                        'authority':state['authorityId'],'obligation':oid,
                        'terms':model.obligations[oid].consent})
        self._guard()
        # Re-load, verify every authority on detached state, and CAS the full
        # original row. No partial save, new journal, task, nonce or signature.
        return self.recovery.prepare(self.receipt_id, expected_generation=generation,
                                     now=now, rollback_evidence=evidence)
