"""Detached EX/deferred business transitions, one original aggregate CAS.

This core does not construct a native route or publish a live in-memory Exchange.
Original authority and pure owned-facts translation are explicit injected ports.
"""
from copy import deepcopy
from dataclasses import dataclass, replace
import json

from .deferred_checkpoint import DeferredCheckpoint
from .deferred_settlement import DeferredSettlement
from .deferred_principal_allocation import DeferredPrincipalAllocator, PrincipalDestination
from .exchange_fact_snapshot import decode_exchange_snapshot
from .exchange_snapshot_checkpoint import _continuity
from .ids import canonical_json


class JointTransitionRefused(ValueError):
    pass


@dataclass(frozen=True)
class JointTransitionInput:
    scope: str
    source_commit: str
    source_tree: str
    generation: int
    aggregate_digest: str
    command: str
    obligation_id: str
    now: int
    evidence: bytes | None
    owned_before: bytes
    deferred_before: bytes
    allocation_plan: object = None


@dataclass(frozen=True)
class OriginalLegBinding:
    """Returned only by the installed original authority reader, never a form.

    IDs must name records in these exact source-generation bytes. This does not
    manufacture a mapping registry, authorize an action or verify chain evidence.
    """
    aggregate_digest: str
    obligation_id: str
    receipt_id: str
    leg_index: int
    transfer_id: str


@dataclass(frozen=True)
class DeferredTransferBinding:
    receipt_id: str
    transfer_id: str
    obligation_id: str
    lock_id: str
    sell_intent_digest: str
    buy_intent_digest: str


class JointDeferredTransition:
    COMMANDS = frozenset({"observe_registration", "observe_rollback_authority",
                          "credit_escrow", "deadline"})

    def __init__(self, checkpoint, *, resolve_original_binding=None,
                 transition_owned_facts=None, principal_component=None,
                 principal_allocator=None, verify_staged_allocation=None,
                 transition_admission=None, verify_prepared_cancel=None):
        if (not isinstance(checkpoint, DeferredCheckpoint) or
                "owned-facts" not in checkpoint.store.components):
            raise JointTransitionRefused("original complete deferred/owned-facts store required")
        self.checkpoint = checkpoint
        self.resolve_original_binding = resolve_original_binding
        self.transition_owned_facts = transition_owned_facts
        if principal_component is not None and (
                type(principal_component) is not str or
                principal_component in ("owned-facts", checkpoint.COMPONENT) or
                principal_component not in checkpoint.store.components or
                type(principal_allocator) is not DeferredPrincipalAllocator or
                principal_allocator.scope != checkpoint.scope):
            raise JointTransitionRefused("explicit existing principal component and allocator required")
        self.principal_component = principal_component
        self.principal_allocator = principal_allocator
        self.verify_staged_allocation = verify_staged_allocation
        self.transition_admission = transition_admission
        self.verify_prepared_cancel = verify_prepared_cancel

    @staticmethod
    def _leg(facts, binding, item, profile):
        if (type(binding) is not OriginalLegBinding or
                type(binding.leg_index) is not int or binding.leg_index < 0 or
                any(type(value) is not str or not value for value in
                    (binding.receipt_id, binding.transfer_id, binding.obligation_id))):
            raise JointTransitionRefused("original exact receipt/leg binding required")
        receipt = facts.receipts.get(binding.receipt_id)
        legs = facts.domain["_legs"].get(binding.receipt_id, ())
        if receipt is None or binding.leg_index >= len(legs):
            raise JointTransitionRefused("original receipt/leg unavailable")
        leg = legs[binding.leg_index]
        if ((leg.receipt_id, leg.leg_index, leg.transfer_id, leg.seller, leg.buyer,
             leg.price, leg.quote_asset) !=
                (binding.receipt_id, binding.leg_index, binding.transfer_id,
                 item.seller, item.borrower, item.principal, profile.principal_asset) or
                receipt.asset.chain_id != profile.settlement_chain):
            raise JointTransitionRefused("deferred obligation differs from original trade")
        return leg

    @staticmethod
    def _protected_prefix(before, after, binding, *, cancelled_plan=False):
        if set(before.receipts) != set(after.receipts) or before.wallet != after.wallet:
            raise JointTransitionRefused("observation cannot mint or alter wallet facts")
        mutable = {"_legs", "_holder_index", "_applied_results", "_deferred",
                   "_rejections", "_events", "_rollbacks"}
        for name in set(before.domain) - mutable:
            if before.domain[name] != after.domain[name]:
                raise JointTransitionRefused("observation cannot manufacture funds or gas effects")
        if before.priority_books != after.priority_books or before.mint_indexes != after.mint_indexes:
            raise JointTransitionRefused("observation cannot replace order books or mint indexes")
        for name in ("_legs", "_holder_index", "_rollbacks", "_deferred", "_rejections", "_events"):
            for identity, value in before.domain[name].items():
                if identity != binding.receipt_id and after.domain[name].get(identity) != value:
                    raise JointTransitionRefused("observation cannot mutate another receipt")
        for identity, old_legs in before.domain["_legs"].items():
            new_legs = after.domain["_legs"][identity]
            events = before.domain["_events"][identity]
            if after.domain["_events"][identity][:len(events)] != events:
                raise JointTransitionRefused("original event history must remain an intact prefix")
            if len(new_legs) != len(old_legs):
                raise JointTransitionRefused("observation cannot add or remove trades")
            for old, new in zip(old_legs, new_legs):
                # Only original state fields can change, never the signed trade.
                excluded = {"registration_status", "funding_status", "rollback_status"}
                if any(getattr(old, key) != getattr(new, key)
                       for key in old.__dataclass_fields__ if key not in excluded):
                    raise JointTransitionRefused("original trade identity or terms changed")
                debt_cut = (old.funding_status == "reserved-allowance" and
                    new.funding_status == "independent-debt" and
                    getattr(old, "deferred_obligation_id", None) == binding.obligation_id and
                    new.registration_status == "confirmed" and new.rollback_status == "detached")
                if (old.registration_status == "confirmed" and new.registration_status != "confirmed" or
                        old.rollback_status == "detached" and new.rollback_status != "detached" or
                        new.funding_status != old.funding_status and not debt_cut):
                    raise JointTransitionRefused("completed prefix or funds result changed")
            old_holder = before.domain["_holder_index"][identity]
            new_holder = after.domain["_holder_index"][identity]
            if type(new_holder) is not int or new_holder < old_holder:
                raise JointTransitionRefused("original holder position cannot regress")
            active = after.domain["_active_legs"][identity]
            confirmed = []
            gap = False
            for index in active:
                if new_legs[index].registration_status == "confirmed":
                    if gap:
                        raise JointTransitionRefused("registration must remain an ordered active prefix")
                    confirmed.append(index)
                else:
                    gap = True
            if new_holder != (confirmed[-1] + 1 if confirmed else 0):
                raise JointTransitionRefused("holder must match the active confirmed prefix")
            previous = before.domain["_rollbacks"][identity]
            current = after.domain["_rollbacks"][identity]
            if previous is not None and current != previous and not (
                    cancelled_plan and identity == binding.receipt_id and current is None):
                raise JointTransitionRefused("existing recovery needs original reconciliation, not replacement")
            if current is not None and any(
                    new_legs[index].registration_status == "confirmed" or
                    new_legs[index].rollback_status == "detached"
                    for index in current.get("affectedLegs", ())):
                raise JointTransitionRefused("rollback plan cannot retain a protected registered cut")
            if previous is None and current is not None:
                if (type(current) is not dict or current.get("state") != "in-progress" or
                        not current.get("steps") or
                        any(step.status != "pending" for step in current["steps"]) or
                        any(new_legs[index].registration_status == "confirmed"
                            for index in current.get("affectedLegs", ()))):
                    raise JointTransitionRefused("new rollback may only prepare unexecuted suffix steps")

    def apply(self, command, obligation_id, *, expected_generation, now, evidence=None):
        if command == "credit_escrow" and self.principal_component is not None:
            raise JointTransitionRefused("use the joint principal allocation path; no independent credit")
        row, model, context, binding = self._read_bound(
            command, obligation_id, expected_generation, now, evidence)
        if command == "deadline":
            value = model.deadline(obligation_id, now=now, registration_evidence=evidence)
        else:
            value = getattr(model, command)(obligation_id, evidence, now=now)
        return self._save_transition(row, model, context, binding, value)

    def _read_bound(self, command, obligation_id, expected_generation, now, evidence):
        if (command not in self.COMMANDS or type(obligation_id) is not str or
                type(now) is not int or now < 0 or type(expected_generation) is not int or
                not 1 <= expected_generation < 2 ** 63 - 1):
            raise JointTransitionRefused("exact supported observation and CAS required")
        if (evidence is not None and (type(evidence) is not bytes or
                not 0 < len(evidence) <= 16 * 1024 * 1024) or
                command != "deadline" and evidence is None):
            raise JointTransitionRefused("original bounded evidence bytes required")
        if not callable(self.resolve_original_binding) or not callable(self.transition_owned_facts):
            raise JointTransitionRefused("original mapping and pure domain transition ports unbound")
        service = self.checkpoint
        row, model = service.read()  # Restores a detached model; not a live reference.
        if row["generation"] != expected_generation:
            raise JointTransitionRefused("stale joint generation")
        original = row["components"]["owned-facts"]
        before = decode_exchange_snapshot(original)
        before_deferred = row["components"][service.COMPONENT]
        context = JointTransitionInput(service.scope, service.store.source["commit"],
            service.store.source["tree"], expected_generation, row["digest"], command,
            obligation_id, now, evidence, original, before_deferred)
        binding = self.resolve_original_binding(context)
        if (type(binding) is not OriginalLegBinding or binding.aggregate_digest != row["digest"] or
                binding.obligation_id != obligation_id or obligation_id not in model.obligations):
            raise JointTransitionRefused("mapping does not bind exact original aggregate and obligation")
        self._leg(before, binding, model.obligations[obligation_id], service.profile)
        return row, model, context, binding

    def allocate_principal(self, obligation_id, *, source_id, allocation_id, units,
                           expected_generation, expected_principal_revision, now, evidence):
        """Stage a real original receipt allocation and credit in ONE aggregate CAS.

        The installed verifier must authenticate existing receipt/funds authority
        and the exact conditional allocation intent. It must link that original
        evidence to the complete plan, not treat a proposed plan as a receipt.
        Neither verifier may write or publish a financial record before commit.
        """
        if self.principal_component is None or not callable(self.verify_staged_allocation):
            raise JointTransitionRefused("original principal allocation ports unbound")
        row, model, context, binding = self._read_bound(
            "credit_escrow", obligation_id, expected_generation, now, evidence)
        item = model.obligations[obligation_id]
        profile = self.checkpoint.profile
        destination = PrincipalDestination(obligation_id, item.consent,
            profile.settlement_chain, profile.principal_asset, item.borrower, profile.escrow)
        original = row["components"][self.principal_component]
        plan = self.principal_allocator.plan(original, destination,
            source_id=source_id, allocation_id=allocation_id, units=units,
            expected_revision=expected_principal_revision)
        if (plan.before != original or plan.scope != self.checkpoint.scope or
                self.principal_allocator.scope != self.checkpoint.scope or
                plan.journal_reference != self.principal_allocator.journal_reference):
            raise JointTransitionRefused("allocation plan must consume the same original component bytes")
        claim = json.loads(plan.claim_bytes)
        if claim["destination"] != destination.terms or claim["units"] != units:
            raise JointTransitionRefused("allocation destination or units changed")
        context = replace(context, allocation_plan=plan)
        fact, _, duplicate = model._fact(evidence, "principal-allocation", now)
        # A repeated plan requires the same already-recorded original evidence;
        # partial historical state is reconciliation, never an automatic repair.
        if (duplicate != plan.repeated or fact.units != units or fact.identity != allocation_id or
                self.verify_staged_allocation(context, plan, evidence, deepcopy(fact)) is not True):
            raise JointTransitionRefused("original allocation evidence/claim linkage unresolved")
        original_verifier = model.verifier
        class PinnedAllocationVerifier:
            def verify(self, raw, *, kind, now):
                if (raw != evidence or kind != "principal-allocation" or now != context.now):
                    raise JointTransitionRefused("unexpected staged evidence enquiry")
                return deepcopy(fact)
        before_credit = item.escrow
        model.verifier = PinnedAllocationVerifier()
        try:
            value = model.credit_escrow(obligation_id, evidence, now=now)
        finally:
            model.verifier = original_verifier
        if item.escrow - before_credit != (0 if plan.repeated else units):
            raise JointTransitionRefused("deferred credit differs from the exact original claim")
        return self._save_transition(row, model, context, binding, value,
                                     principal_after=plan.after)

    def admit_transfer(self, binding, reserve_arguments, *, expected_generation, now):
        """Reserve allowance and append exactly one domain leg in one CAS.

        transition_admission(context, binding, deferred_after) must use the
        original detached Exchange.execute_transfer with DeferredTradeAdmissionPort.
        That port authenticates both signed intents, the staged reservation and
        the actual independent normal-gas allocation. This core never substitutes
        a callback's Boolean for that authority and never opens a runtime route.
        """
        if (type(binding) is not DeferredTransferBinding or type(reserve_arguments) is not dict or
                not callable(self.transition_admission) or type(expected_generation) is not int or
                not 1 <= expected_generation < 2 ** 63 - 1 or type(now) is not int or now < 0):
            raise JointTransitionRefused("original admission binding, pure port and CAS required")
        if any(type(value) is not str or not value for value in vars(binding).values()):
            raise JointTransitionRefused("complete original admission identities required")
        service = self.checkpoint
        row, model = service.read()
        if row["generation"] != expected_generation:
            raise JointTransitionRefused("stale admission generation")
        before_raw = row["components"]["owned-facts"]
        before = decode_exchange_snapshot(before_raw)
        if binding.receipt_id not in before.receipts:
            raise JointTransitionRefused("original receipt unavailable")
        for legs in before.domain["_legs"].values():
            if any(leg.transfer_id == binding.transfer_id or
                   getattr(leg, "deferred_obligation_id", None) == binding.obligation_id for leg in legs):
                raise JointTransitionRefused("original transfer or reserved obligation already used; reconcile")
        arguments = deepcopy(reserve_arguments)
        if "now" in arguments and arguments.pop("now") != now:
            raise JointTransitionRefused("reservation observation time differs")
        model.reserve(binding.obligation_id, binding.lock_id, now=now, **arguments)
        state = model.snapshot()
        checked = DeferredSettlement.restore(service.profile, service.verifier, state)
        item = checked.obligations[binding.obligation_id]
        if item.registered or item.rollback or item.resolved:
            raise JointTransitionRefused("new admission requires a live unregistered reservation")
        deferred_after = canonical_json(state).encode()
        context = JointTransitionInput(service.scope, service.store.source["commit"],
            service.store.source["tree"], expected_generation, row["digest"], "admit_transfer",
            binding.obligation_id, now, None, before_raw, row["components"][service.COMPONENT])
        raw = self.transition_admission(context, binding, deferred_after)
        if type(raw) is not bytes:
            raise JointTransitionRefused("immutable detached admission snapshot required")
        after = decode_exchange_snapshot(raw)
        _continuity(before, after)
        self._admission_delta(before, after, binding, item, service.profile, now)
        components = dict(row["components"])
        components["owned-facts"], components[service.COMPONENT] = raw, deferred_after
        saved = service.store.save(service.scope, components, expected_generation=expected_generation,
            immutable_components=tuple(name for name in components
                if name not in ("owned-facts", service.COMPONENT)))
        return {"generation": saved["generation"], "digest": saved["digest"],
                "transferId": binding.transfer_id, "obligationId": binding.obligation_id,
                "dispatched": False, "executionAuthorized": False, "completeRecovery": False}

    @staticmethod
    def _admission_delta(before, after, binding, item, profile, now):
        if (before.receipts != after.receipts or before.mint_indexes != after.mint_indexes or
                before.priority_books != after.priority_books):
            raise JointTransitionRefused("admission cannot rewrite mint or original order books")
        mutable = {"_legs", "_active_legs", "_events"}
        for name, value in before.domain.items():
            if name not in mutable and after.domain[name] != value:
                raise JointTransitionRefused("admission cannot manufacture registration, funds or return")
            if name in mutable and any(after.domain[name].get(key) != old
                    for key, old in value.items() if key != binding.receipt_id):
                raise JointTransitionRefused("admission cannot change another receipt")
        old_legs = before.domain["_legs"][binding.receipt_id]
        new_legs = after.domain["_legs"][binding.receipt_id]
        if len(new_legs) != len(old_legs) + 1 or new_legs[:-1] != old_legs:
            raise JointTransitionRefused("admission must append exactly one immutable original leg")
        index = len(old_legs)
        leg_binding = OriginalLegBinding("", binding.obligation_id, binding.receipt_id,
                                         index, binding.transfer_id)
        leg = JointDeferredTransition._leg(after, leg_binding, item, profile)
        if ((leg.sell_intent_digest, leg.buy_intent_digest, leg.executed_at,
             leg.registration_status, leg.funding_status, leg.rollback_status,
             leg.deferred_obligation_id, leg.deferred_terms_digest, leg.deferred_deadline) !=
                (binding.sell_intent_digest, binding.buy_intent_digest, now, "not-submitted",
                 "reserved-allowance", "available", binding.obligation_id, item.consent, item.deadline)):
            raise JointTransitionRefused("new leg must bind exact staged deferred terms and signed intents")
        active = before.domain["_active_legs"][binding.receipt_id]
        if (after.domain["_active_legs"][binding.receipt_id] != active + [index] or
                leg.predecessor_transfer_id != (old_legs[active[-1]].transfer_id if active else None) or
                leg.seller != (old_legs[active[-1]].buyer if active else
                               before.receipts[binding.receipt_id].origin_account)):
            raise JointTransitionRefused("new leg must extend the original executable head")
        intents = {intent.digest: intent for intent in before.wallet["intents"]}
        try:
            sell, buy = intents[binding.sell_intent_digest], intents[binding.buy_intent_digest]
        except KeyError:
            raise JointTransitionRefused("original signed intents unavailable") from None
        expected = {(sell.signer, sell.nonce), (buy.signer, buy.nonce)}
        if (sell.signer != leg.seller or buy.signer != leg.buyer or
                leg.sell_authorization_id != sell.authorization_id or
                leg.buy_authorization_id != buy.authorization_id or
                expected & before.wallet["usedNonces"] or
                after.wallet["usedNonces"] != before.wallet["usedNonces"] | expected or
                any(after.wallet[name] != value for name, value in before.wallet.items()
                    if name != "usedNonces")):
            raise JointTransitionRefused("admission must consume only both original unused signed nonces")

    def _verify_prepared_cancellation(self, context, binding, before, after, checked):
        old = before.domain["_rollbacks"][binding.receipt_id]
        new = after.domain["_rollbacks"][binding.receipt_id]
        if old is None or new == old:
            return False
        item = checked.obligations[binding.obligation_id]
        if (new is not None or context.command not in ("observe_registration", "deadline")
                or not item.registered or item.rollback
                or tuple(old["affectedLegs"]) != (binding.leg_index,)
                or old["state"] != "in-progress" or old["conflicts"]
                or not old["steps"]
                or any(step.status != "pending" or step.detail for step in old["steps"])
                or not callable(self.verify_prepared_cancel)):
            raise JointTransitionRefused("only an exact untouched single-obligation plan may cancel")
        leg = before.domain["_legs"][binding.receipt_id][binding.leg_index]
        if any(old_leg != after.domain["_legs"][binding.receipt_id][index]
               for index, old_leg in enumerate(before.domain["_legs"][binding.receipt_id])
               if index != binding.leg_index):
            raise JointTransitionRefused("single cancellation cannot change another suffix leg")
        if (leg.deferred_obligation_id != item.identity or leg.rollback_status != "in-progress"
                or leg.funding_status != "reserved-allowance"
                or binding.leg_index in before.domain["_escrow_by_leg"][binding.receipt_id]):
            raise JointTransitionRefused("cancellation cannot undo any principal or native effect")
        prior = DeferredSettlement.restore(self.checkpoint.profile, self.checkpoint.verifier,
                                           json.loads(context.deferred_before))
        if not prior.obligations[item.identity].rollback:
            raise JointTransitionRefused("cancellation requires the original deferred recovery preimage")
        operations = [op for op in prior.operations.values()
                      if op.obligation == item.identity and op.kind == "rollback"]
        for op in operations:
            current = checked.operations.get(op.identity)
            if (op.status not in ("PREPARED", "FAILED") or current is None
                    or current.status != "FAILED"):
                raise JointTransitionRefused("unknown, confirmed or queued recovery cannot cancel")
        # The installed original authority must protect whole-plan absence at
        # this SAME aggregate owner/revision, including queued claims. A plain
        # RPC not-found or a pending-looking step is not absence authority.
        if self.verify_prepared_cancel(context, binding, deepcopy(old),
                canonical_json(checked.snapshot()).encode()) is not True:
            raise JointTransitionRefused("same-owner complete native claim absence unavailable")
        return True

    def _save_transition(self, row, model, context, binding, value, *, principal_after=None):
        service = self.checkpoint
        before = decode_exchange_snapshot(context.owned_before)
        obligation_id = context.obligation_id
        state = model.snapshot()
        # Revalidate after the domain call; do not accept mutable callback state.
        checked = DeferredSettlement.restore(service.profile, service.verifier, state)
        deferred_after = canonical_json(state).encode()
        raw = self.transition_owned_facts(context, binding, deferred_after)
        if type(raw) is not bytes:
            raise JointTransitionRefused("pure domain port must return immutable owned-facts bytes")
        after = decode_exchange_snapshot(raw)
        _continuity(before, after)
        cancelled_plan = self._verify_prepared_cancellation(context, binding, before, after, checked)
        self._protected_prefix(before, after, binding, cancelled_plan=cancelled_plan)
        item = checked.obligations[obligation_id]
        leg = self._leg(after, binding, item, service.profile)
        if item.registered:
            if (leg.registration_status != "confirmed" or leg.rollback_status != "detached" or
                    after.domain["_holder_index"][binding.receipt_id] < binding.leg_index + 1):
                raise JointTransitionRefused("registered cut must detach NFT rollback without waiting for debt")
        elif item.rollback:
            if leg.registration_status == "confirmed" or leg.rollback_status != "in-progress":
                raise JointTransitionRefused("unregistered rollback must remain pending, not fabricate an effect")
        elif (leg.registration_status, leg.rollback_status) != (
                self._leg(before, binding, item, service.profile).registration_status,
                self._leg(before, binding, item, service.profile).rollback_status):
            raise JointTransitionRefused("unverified observation cannot change registration or rollback")
        components = dict(row["components"])
        components["owned-facts"] = raw
        components[service.COMPONENT] = deferred_after
        changed = {"owned-facts", service.COMPONENT}
        if principal_after is not None:
            if (context.allocation_plan is None or type(principal_after) is not bytes or
                    principal_after != context.allocation_plan.after or
                    row["components"][self.principal_component] != context.allocation_plan.before):
                raise JointTransitionRefused("exact third-component preimage and plan required")
            components[self.principal_component] = principal_after
            changed.add(self.principal_component)
        # One complete-map CAS. Neither domain port may write, dispatch, update a
        # live Exchange, or save independently. No retry/adopt-new-generation.
        saved = service.store.save(service.scope, components,
            expected_generation=context.generation,
            immutable_components=tuple(name for name in components
                if name not in changed))
        return {"generation": saved["generation"], "digest": saved["digest"],
                "result": deepcopy(value), "dispatched": False,
                "executionAuthorized": False, "completeRecovery": False}
