"""Pure owned-facts half of the original joint deferred CAS.

Trusted factories supply fresh read-only runtime/authority observations. No
checkpoint, native effect, priority acceptance, payment or UI route is invoked.
The caller MUST validate and persist the result with the same deferred bytes in
JointDeferredTransition. These callbacks alone never constitute admission.
"""
from copy import deepcopy
import json

from .deferred_settlement import DeferredSettlement
from .deferred_trade_admission import DeferredTradeAdmissionPort
from .exchange_fact_rehydration import rehydrate_exchange_facts
from .exchange_fact_snapshot import decode_exchange_snapshot
from .ids import canonical_json


class DeferredOwnedTransitionRefused(ValueError):
    pass


class DeferredOwnedTransition:
    def __init__(self, profile, verifier, *, fresh_readonly_runtime,
                 read_admission, verify_admission, read_registration=None,
                 read_rollback_authority=None):
        if not all(callable(port) for port in
                   (fresh_readonly_runtime, read_admission, verify_admission)):
            raise DeferredOwnedTransitionRefused("explicit original pure runtime/admission ports required")
        self.profile, self.verifier = profile, verifier
        self.fresh_runtime = fresh_readonly_runtime
        self.read_admission, self.verify_admission = read_admission, verify_admission
        self.read_registration = read_registration
        self.read_rollback_authority = read_rollback_authority

    def _restore(self, context, raw):
        if type(raw) is not bytes:
            raise DeferredOwnedTransitionRefused("immutable same-generation deferred bytes required")
        state = json.loads(raw.decode("utf-8"))
        if canonical_json(state).encode() != raw:
            raise DeferredOwnedTransitionRefused("canonical deferred bytes required")
        model = DeferredSettlement.restore(self.profile, self.verifier, state)
        if context.scope != self.profile.checkpoint_scope:
            raise DeferredOwnedTransitionRefused("original profile scope differs")
        access = rehydrate_exchange_facts(context.owned_before, self.fresh_runtime(context))
        # Current runtime must not silently inject nonce/session/grant changes
        # outside this aggregate generation. Reconciliation is its own command.
        if access.snapshot_bytes() != context.owned_before:
            raise DeferredOwnedTransitionRefused("runtime authority differs; reconcile before transition")
        return access, model, state

    def transition_admission(self, context, binding, deferred_after):
        access, model, state = self._restore(context, deferred_after)
        item = model.obligations[binding.obligation_id]
        if item.lock != binding.lock_id or context.obligation_id != item.identity:
            raise DeferredOwnedTransitionRefused("reserved original obligation/lock mismatch")
        facts = decode_exchange_snapshot(context.owned_before)
        intents = {intent.digest: intent for intent in facts.wallet["intents"]}
        sell, buy = intents[binding.sell_intent_digest], intents[binding.buy_intent_digest]
        match = access.match_intents(sell.intent_id, buy.intent_id, now=context.now)

        def read(request, now):
            row = deepcopy(self.read_admission(context, binding, deepcopy(request), now))
            # Ports authenticate real gas/stablecoin/consent; they cannot substitute
            # another ledger snapshot, reservation or generation for this CAS.
            row.update(request=deepcopy(request), snapshot=deepcopy(state),
                       obligationId=item.identity, scope=context.scope,
                       generation=context.generation, observedAt=now)
            return row

        def verify(request, row):
            return self.verify_admission(context, binding, request, row) is True

        port = DeferredTradeAdmissionPort(self.profile, self.verifier, read, verify)
        access.execute_transfer(match, binding.transfer_id, now=context.now,
                                deferred_admission=port)
        return access.snapshot_bytes()

    def transition_owned_facts(self, context, binding, deferred_after):
        access, model, state = self._restore(context, deferred_after)
        item = model.obligations[binding.obligation_id]
        leg = access.leg(binding.receipt_id, binding.leg_index)
        if (leg.transfer_id != binding.transfer_id
                or leg.deferred_obligation_id != item.identity
                or leg.deferred_terms_digest != item.consent
                or leg.deferred_deadline != item.deadline):
            raise DeferredOwnedTransitionRefused("original owned/deferred leg binding differs")
        if context.command == "observe_registration" or (context.command == "deadline" and item.registered):
            if not item.registered or not callable(self.read_registration):
                raise DeferredOwnedTransitionRefused("original registration cut evidence unavailable")
            evidence = self.read_registration(context, binding)
            if (evidence.receipt_id, evidence.leg_index, evidence.transfer_id) != (
                    binding.receipt_id, binding.leg_index, binding.transfer_id):
                raise DeferredOwnedTransitionRefused("original registration evidence names another leg")
            old = decode_exchange_snapshot(context.owned_before).domain["_rollbacks"][binding.receipt_id]
            if old is not None:
                for index in old["affectedLegs"]:
                    affected = access.leg(binding.receipt_id, index)
                    obligation = model.obligations.get(affected.deferred_obligation_id)
                    if obligation is None or obligation.rollback:
                        raise DeferredOwnedTransitionRefused("another suffix obligation still requires recovery")
                # Only this newly rehydrated detached instance is mutated; no public
                # SerializedExchangeAccess/live command exposes this cancellation.
                with access._lock:
                    access._exchange._cancel_prepared_deferred_rollback(binding.receipt_id, binding.leg_index)
            result = access.apply_registration_result(evidence)
            if result["disposition"] not in ("advanced", "idempotent"):
                raise DeferredOwnedTransitionRefused("cut is not a contiguous confirmed original prefix")
        elif context.command in ("deadline", "observe_rollback_authority") and item.rollback:
            if not callable(self.read_rollback_authority):
                raise DeferredOwnedTransitionRefused("original suffix rollback authority unavailable")
            authority = self.read_rollback_authority(context, binding)
            trigger = ("deferred-deadline" if context.command == "deadline"
                       else "registrar-refusal")
            access.begin_rollback(binding.receipt_id, binding.leg_index,
                                  authority, trigger=trigger, now=context.now)
        elif context.command not in ("deadline", "credit_escrow"):
            raise DeferredOwnedTransitionRefused("unsupported pure domain transition")
        # Credit/debt maturity never changes owned funding into released/paid.
        return access.snapshot_bytes()
