"""Original mixed-suffix recovery plan and terminal projections, one aggregate CAS.

No effect is dispatched here. Original effect commands must durably claim UNKNOWN
through their original atomic owner before dispatch; this core consumes their
terminal evidence, never a successful call/timeout/notification. No second store.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib

from .deferred_checkpoint import DeferredCheckpoint
from .deferred_settlement import DeferredSettlement
from .exchange_fact_rehydration import rehydrate_exchange_facts
from .exchange_fact_snapshot import encode_exchange_snapshot
from .ids import canonical_json


class MixedRecoveryRefused(ValueError):
    pass


def _need(condition, message):
    if not condition:
        raise MixedRecoveryRefused(message)


def _commit(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


class MixedSuffixRecovery:
    """verify_terminal(request, raw, now) authenticates original terminal effects.

The verifier returns an exact copy of request plus status='CONFIRMED' and a
nonempty original evidenceReference. It must validate canonical finality,
original operation identity/UNKNOWN claim, exact amount and destination and
absence of conflicting outcomes. For asset-return only, NOOP_BOUNDARY_CONFIRMED
is permitted when from==recipient and the original proof verifies exact boundary
occurrence, continuous custody and no unresolved future return claim. It proves
zero effects, not a fabricated transaction or equality-of-addresses alone. It may not send, sign, claim, pay or mutate.
A request is a required outcome, not evidence. The proof lives in raw bytes.

fresh_readonly_runtime(row) is a new configured original runtime, not the live
writer. Constructor/rehydration refuses persisted history or authority drift.
"""
    def __init__(self, checkpoint, *, fresh_readonly_runtime, verify_terminal):
        _need(isinstance(checkpoint, DeferredCheckpoint)
              and "owned-facts" in checkpoint.store.components
              and callable(fresh_readonly_runtime) and callable(verify_terminal),
              "explicit original aggregate/runtime/terminal verifier required")
        self.service = checkpoint
        self.fresh_runtime = fresh_readonly_runtime
        self.verify_terminal = verify_terminal

    def _load(self, expected_generation):
        row, model = self.service.read()
        _need(type(expected_generation) is int and row["generation"] == expected_generation,
              "stale original recovery generation")
        access = rehydrate_exchange_facts(row["components"]["owned-facts"], self.fresh_runtime(row))
        _need(access.snapshot_bytes() == row["components"]["owned-facts"],
              "original authority drift requires reconciliation")
        return row, model, access._exchange

    @staticmethod
    def _advance_eligibility(plan, model):
        for step in plan["binding"]["steps"]:
            if step["kind"] == "deferred-rollback":
                model.obligations[step["obligation"]].mixed_dispatch_allowed = False
        for index, step in enumerate(plan["binding"]["steps"]):
            if str(index) not in plan["confirmed"]:
                if step["kind"] == "deferred-rollback":
                    item = model.obligations[step["obligation"]]
                    _need(item.mixed_recovery == plan["commitment"], "dispatch plan fence mismatch")
                    item.mixed_dispatch_allowed = True
                break

    def _save(self, row, model, exchange):
        state = model.snapshot()
        DeferredSettlement.restore(self.service.profile, self.service.verifier, state)
        parts = dict(row["components"])
        parts["owned-facts"] = encode_exchange_snapshot(exchange)
        parts[self.service.COMPONENT] = canonical_json(state).encode()
        saved = self.service.store.save(self.service.scope, parts,
            expected_generation=row["generation"],
            immutable_components=tuple(k for k in parts if k not in ("owned-facts", self.service.COMPONENT)))
        # Commit UNKNOWN propagates without retry or live publication.
        return {"generation": saved["generation"], "dispatched": False}

    def prepare(self, receipt_id, *, expected_generation, now, rollback_evidence):
        row, model, ex = self._load(expected_generation)
        state = ex._rollbacks.get(receipt_id)
        _need(state is not None and state["state"] != "complete", "original unresolved suffix required")
        if "mixedRecovery" in state:
            prior = state["mixedRecovery"]
            _need(prior["commitment"] == _commit(prior["binding"])
                  and prior["binding"]["receipt"] == receipt_id
                  and prior["binding"]["scope"] == self.service.scope
                  and prior["binding"]["affected"] == list(state["affectedLegs"]), "existing mixed plan drift")
            return {"generation": row["generation"], "plan": deepcopy(state["mixedRecovery"]),
                    "dispatched": False, "repeated": True}
        affected = tuple(state["affectedLegs"])
        _need(affected and type(rollback_evidence) is dict, "complete suffix authority required")
        steps, deferred_ids = [], set()
        for index in reversed(affected):
            leg = ex.leg(receipt_id, index)
            _need(leg.registration_status != "confirmed" and leg.rollback_status == "in-progress",
                  "registered/protected prefix cannot enter mixed recovery")
            if leg.deferred_obligation_id is not None:
                oid = leg.deferred_obligation_id
                _need(oid not in deferred_ids, "duplicate obligation occurrence")
                deferred_ids.add(oid)
                item = model.obligations[oid]
                _need((item.consent, item.borrower, item.seller, item.principal, item.deadline) ==
                      (leg.deferred_terms_digest, leg.buyer, leg.seller, leg.price, leg.deferred_deadline)
                      and not item.registered and not item.resolved and not model._pending(oid),
                      "original deferred obligation conflicts with suffix")
                _need(oid in rollback_evidence, "each deferred suffix leg needs original authority")
                model.observe_rollback_authority(oid, rollback_evidence[oid], now=now)
                steps.append({"kind": "deferred-rollback", "leg": index, "transfer": leg.transfer_id,
                    "obligation": oid, "terms": item.consent, "lock": item.lock,
                    "principal": item.principal, "units": item.escrow,
                    "chain": model.profile.settlement_chain, "asset": model.profile.principal_asset,
                    "recipient": item.borrower})
            else:
                escrow = ex.escrow_for_leg(receipt_id, index)
                _need(escrow is not None and escrow.status not in ("released", "refunded")
                      and escrow.payment_intent != "release"
                      and escrow.payment_key in (None, "refund:" + escrow.escrow_id),
                      "original refundable cash escrow required")
                steps.append({"kind": "cash-refund", "leg": index, "transfer": leg.transfer_id,
                    "escrow": escrow.escrow_id, "key": "refund:" + escrow.escrow_id,
                    "units": escrow.principal, "chain": ex.receipt(receipt_id).asset.chain_id,
                    "asset": escrow.quote_asset, "recipient": escrow.payer})
        _need(set(rollback_evidence) == deferred_ids and deferred_ids,
              "exact deferred suffix authority set required")
        returns = [step for step in state["steps"] if step.kind == "asset-return"]
        _need(len(returns) == 1, "one original direct return operation required")
        steps.append({"kind": "asset-return", "key": returns[0].key,
            "asset": list(ex.receipt(receipt_id).asset.key), "from": ex.owner_of(receipt_id),
            "recipient": state["boundaryAccount"], "boundary": state["boundaryIndex"], "units": 1})
        binding = {"scope": self.service.scope, "receipt": receipt_id,
                   "authority": state["authorityId"], "affected": list(affected), "steps": steps}
        plan = {"binding": binding, "commitment": _commit(binding), "confirmed": {}}
        for oid in deferred_ids:
            _need(model.obligations[oid].mixed_recovery is None, "another mixed recovery already owns obligation")
            model.obligations[oid].mixed_recovery = plan["commitment"]
        state["mixedRecovery"] = plan
        self._advance_eligibility(plan, model)
        result = self._save(row, model, ex)
        return {**result, "plan": deepcopy(plan), "repeated": False}

    def next_required_step(self, receipt_id, *, expected_generation):
        """Read-only required-outcome projection, never authorization to dispatch.

The original pre-effect claim must recheck this plan commitment and earliest
unconfirmed index in its SAME transaction as UNKNOWN. Native routes may not
execute later steps merely because their descriptors are visible in the plan.
"""
        row, model, ex = self._load(expected_generation)
        state = ex._rollbacks.get(receipt_id)
        _need(state is not None and "mixedRecovery" in state, "original mixed plan required")
        plan = state["mixedRecovery"]
        _need(plan["commitment"] == _commit(plan["binding"]), "mixed plan binding drift")
        for index, step in enumerate(plan["binding"]["steps"]):
            if str(index) in plan["confirmed"]:
                continue
            pending = []
            if step["kind"] == "deferred-rollback":
                pending = [op.identity for op in model.operations.values()
                           if op.obligation == step["obligation"] and op.kind == "rollback"
                           and op.status in ("UNKNOWN", "CONFIRMED")]
            return {"generation": row["generation"], "plan": plan["commitment"],
                    "index": index, "requiredOutcome": deepcopy(step),
                    "reconcileOperations": tuple(pending), "executionAuthorized": False}
        return {"generation": row["generation"], "plan": plan["commitment"],
                "index": None, "requiredOutcome": None, "executionAuthorized": False}

    def confirm(self, receipt_id, *, expected_generation, now, confirmations):
        """Record any terminal progress; finalize only after every required effect.

confirmations maps decimal step index to {raw: bytes, operation: id} for deferred
rollback or {raw: bytes} for original cash-refund/asset-return. Missing entries
remain pending. Original UNKNOWN operation receipts are never inferred.
"""
        row, model, ex = self._load(expected_generation)
        state = ex._rollbacks.get(receipt_id)
        _need(state is not None and "mixedRecovery" in state, "original mixed plan required")
        plan = state["mixedRecovery"]
        binding = plan["binding"]
        _need(plan["commitment"] == _commit(binding)
              and binding["scope"] == self.service.scope and binding["receipt"] == receipt_id
              and binding["authority"] == state["authorityId"]
              and binding["affected"] == list(state["affectedLegs"]), "mixed plan binding drift")
        _need(type(confirmations) is dict, "exact terminal confirmation map required")
        steps = binding["steps"]
        for index in binding["affected"]:
            leg = ex.leg(receipt_id, index)
            _need(leg.registration_status != "confirmed" and leg.rollback_status in ("in-progress", "returned"),
                  "protected registered prefix cannot be refunded")
        _need(set(confirmations) <= {str(i) for i in range(len(steps))}, "unknown recovery step")
        was_complete = state["state"] == "complete"
        progressed = False
        for key in sorted(confirmations, key=int):
            entry = confirmations[key]
            step = steps[int(key)]
            fields = {"raw", "operation"} if step["kind"] == "deferred-rollback" else {"raw"}
            _need(type(entry) is dict and set(entry) == fields and type(entry["raw"]) is bytes,
                  "complete original terminal proof required")
            fingerprint = _commit({"step": step, "proof": hashlib.sha256(entry["raw"]).hexdigest(),
                                   "operation": entry.get("operation")})
            if key in plan["confirmed"]:
                _need(plan["confirmed"][key] == fingerprint, "conflicting repeated recovery outcome")
                continue
            _need(not was_complete, "completed plan cannot accept a new outcome")
            _need(all(str(i) in plan["confirmed"] for i in range(int(key))),
                  "reverse suffix refunds must precede earlier refunds and asset return")
            if step["kind"] == "deferred-rollback":
                op = model.operations[entry["operation"]]
                _need((op.kind, op.obligation, op.units, op.chain, op.asset, op.recipient) ==
                      ("rollback", step["obligation"], step["units"], step["chain"], step["asset"], step["recipient"])
                      and op.status in ("UNKNOWN", "CONFIRMED"), "exact issued original rollback required")
                _need(model.obligations[step["obligation"]].mixed_recovery == plan["commitment"],
                      "persistent collateral recovery fence missing")
                model.confirm(op.identity, entry["raw"], now=now)
                item = model.obligations[step["obligation"]]
                _need(item.rollback_confirmed and item.resolved and item.escrow == 0
                      and item.paid == 0 and not item.registered,
                      "principal refund and allowance release not confirmed")
            else:
                lifecycle = ex.asset_lifecycle(receipt_id)
                retired_asset = step["kind"] == "asset-return" and lifecycle["state"] != "ACTIVE"
                if retired_asset:
                    from .retired_asset_recovery import request_for, verify_marker
                    # PENDING fails closed; RETIRED needs a real original burn or
                    # boundary proof, never a newly issued return on a burned NFT.
                    request = request_for(ex, receipt_id, state)
                    outcome = self.verify_terminal(deepcopy(request), entry["raw"], now)
                    marker = verify_marker(request, entry["raw"], outcome)
                    _need(marker["status"] != "NOOP_BOUNDARY_CONFIRMED" or
                          step["from"] == step["recipient"], "NOOP cannot replace an actual return")
                    prior_terminal = state.get("retiredAssetTerminal")
                    _need(prior_terminal is None or prior_terminal == marker,
                          "conflicting retired asset terminal")
                    state["retiredAssetTerminal"] = marker
                else:
                    request = {"plan": plan["commitment"], "scope": self.service.scope,
                               "receipt": receipt_id, "step": deepcopy(step)}
                    outcome = self.verify_terminal(deepcopy(request), entry["raw"], now)
                    statuses = {"CONFIRMED"}
                    if step["kind"] == "asset-return" and step["from"] == step["recipient"]:
                        statuses.add("NOOP_BOUNDARY_CONFIRMED")
                    _need(type(outcome) is dict and set(outcome) == {"request", "status", "evidenceReference"}
                          and outcome["request"] == request and outcome["status"] in statuses
                          and type(outcome["evidenceReference"]) is str and outcome["evidenceReference"],
                          "original terminal receipt is unavailable/unconfirmed")
                if step["kind"] == "cash-refund":
                    escrow = ex._escrows[step["escrow"]]
                    _need(escrow.principal == step["units"] and escrow.payer == step["recipient"]
                          and escrow.status != "released" and escrow.payment_intent != "release"
                          and escrow.payment_key in (None, step["key"])
                          and escrow.settled_at is None, "original cash escrow no longer refundable")
                    ex._escrows[escrow.escrow_id] = replace(escrow, status="refunded", refunded_at=now,
                        payment_key=step["key"], payment_status="settled", payment_intent="refund",
                        payment_reference=outcome["evidenceReference"])
                    ex._replace_leg(receipt_id, step["leg"], funding_status="refunded")
            plan["confirmed"][key] = fingerprint
            progressed = True
        complete = len(plan["confirmed"]) == len(steps)
        if was_complete:
            _need(complete and all(ex.leg(receipt_id, i).rollback_status == "returned"
                                  for i in binding["affected"]), "completed recovery state inconsistent")
            return {"generation": row["generation"], "dispatched": False, "complete": True,
                    "confirmed": len(plan["confirmed"]), "required": len(steps), "repeated": True}
        if not complete and not progressed:
            # Replays and empty reconciliation still pass the original row,
            # suffix, ordering and fingerprint checks above. With no new
            # terminal evidence there is nothing to publish or CAS; preserve
            # the exact generation for a lost-response retry.
            return {"generation": row["generation"], "dispatched": False, "complete": False,
                    "confirmed": len(plan["confirmed"]), "required": len(steps), "repeated": True}
        if complete:
            for step in steps:
                if step["kind"] == "deferred-rollback":
                    item = model.obligations[step["obligation"]]
                    _need(item.mixed_recovery == plan["commitment"] and item.rollback_confirmed
                          and item.resolved and item.escrow == 0, "complete recovery lacks secured refund")
                    item.mixed_recovery = None
                    item.mixed_dispatch_allowed = False
            for index in binding["affected"]:
                leg = ex.leg(receipt_id, index)
                _need(leg.registration_status != "confirmed" and leg.rollback_status == "in-progress",
                      "confirmed prefix cannot be overwritten by recovery")
                ex._replace_leg(receipt_id, index, rollback_status="returned")
            ex._returned_to[receipt_id] = (state["boundaryIndex"], state["boundaryAccount"])
            state["steps"] = [replace(step, status="done") for step in state["steps"]]
            state["state"] = "complete"
            ex._record(receipt_id, "mixed-recovery-confirmed", {
                "plan": plan["commitment"], "effectsVerified": len(steps), "dispatched": False})
        if not complete:
            self._advance_eligibility(plan, model)
        result = self._save(row, model, ex)
        return {**result, "complete": complete, "confirmed": len(plan["confirmed"]), "required": len(steps)}
