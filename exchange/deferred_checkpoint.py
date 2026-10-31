"""Durable deferred-module boundary using the existing aggregate CAS store.

No schema, database path, credentials, network or signing provider is selected.
Caller supplies the original aggregate store and trusted evidence verifier.
"""
from copy import deepcopy
import json

from .aggregate_checkpoint import AggregateCheckpointStore
from .deferred_settlement import DeferredSettlement, DeferredRefused
from .ids import canonical_json


class DeferredCheckpoint:
    COMPONENT = "deferred-settlement"
    COMMANDS = frozenset({"admit_lock", "reserve", "observe_registration", "observe_rollback_authority", "credit_escrow",
                          "deadline", "observe_liquidation_source", "observe_collateral_remainder", "prepare", "observe_gas_requirement", "observe_liquidation_funding", "observe_liquidation_cost", "observe_liquidation_penalty", "mark_dispatched", "confirm_nonexecution", "confirm"})

    def __init__(self, store, scope, profile, verifier):
        if not isinstance(store, AggregateCheckpointStore) or self.COMPONENT not in store.components:
            raise DeferredRefused("existing aggregate with deferred component required")
        if scope != profile.checkpoint_scope:
            raise DeferredRefused("exact original profile checkpoint scope required")
        self.store, self.scope, self.profile, self.verifier = store, scope, profile, verifier

    def initialize(self, *, original_components):
        """Explicit initial aggregate only. Never replace or silently migrate."""
        if self.store.read(self.scope) is not None:
            raise DeferredRefused("aggregate already exists")
        if type(original_components) is not dict or self.COMPONENT in original_components:
            raise DeferredRefused("original non-deferred components required")
        components = dict(original_components)
        components[self.COMPONENT] = canonical_json(DeferredSettlement(self.profile, self.verifier).snapshot()).encode()
        return self.store.save(self.scope, components, expected_generation=0)

    def read(self):
        row = self.store.read(self.scope)
        if row is None:
            raise DeferredRefused("original aggregate unavailable")
        try:
            state = json.loads(row["components"][self.COMPONENT].decode("utf-8"))
            model = DeferredSettlement.restore(self.profile, self.verifier, state)
        except DeferredRefused:
            raise
        except (ValueError, TypeError, KeyError, UnicodeError) as error:
            raise DeferredRefused("invalid deferred checkpoint") from error
        return row, model

    def view(self, obligation_id):
        row, model = self.read()
        return {"generation": row["generation"], "projection": model.public_status(obligation_id)}

    def _guard_owned_rollback(self, row, model, command, args, kwargs):
        """Close the initial rollback -> mixed-plan window in original routes.

A deferred-only aggregate retains its original behavior. Once an original owned
leg is bound, rollback effects require the same aggregate's durable plan and
first-step eligibility, including BEFORE a mixed plan has yet been prepared.
"""
        if "owned-facts" not in row["components"]:
            return
        obligation = None
        if command == "prepare" and kwargs.get("kind") == "rollback":
            obligation = args[1] if len(args) > 1 else kwargs.get("obligation_id")
        elif command == "mark_dispatched":
            identity = args[0] if args else kwargs.get("operation_id")
            op = model.operations.get(identity)
            if op is not None and op.kind == "rollback":
                obligation = op.obligation
        if obligation is None:
            return
        from .exchange_fact_snapshot import decode_exchange_snapshot
        facts = decode_exchange_snapshot(row["components"]["owned-facts"])
        bindings = [(receipt, leg) for receipt, legs in facts.domain["_legs"].items()
                    for leg in legs if leg.deferred_obligation_id == obligation]
        if not bindings:
            return
        if len(bindings) != 1:
            raise DeferredRefused("original deferred obligation has ambiguous owned occurrences")
        receipt, leg = bindings[0]
        item = model.obligations[obligation]
        state = facts.domain["_rollbacks"].get(receipt)
        if (state is None or "mixedRecovery" not in state or
                leg.leg_index not in state["affectedLegs"] or
                leg.registration_status == "confirmed" or
                item.mixed_recovery is None or not item.mixed_dispatch_allowed):
            raise DeferredRefused("original owned suffix requires prepared first-step mixed recovery")
        plan = state["mixedRecovery"]
        import hashlib
        commitment = hashlib.sha256(canonical_json(plan["binding"]).encode()).hexdigest()
        if (plan["commitment"] != commitment or item.mixed_recovery != commitment or
                plan["binding"]["scope"] != self.scope or plan["binding"]["receipt"] != receipt):
            raise DeferredRefused("original mixed recovery plan binding differs")
        first = next((step for index, step in enumerate(plan["binding"]["steps"])
                      if str(index) not in plan["confirmed"]), None)
        if (first is None or first["kind"] != "deferred-rollback" or
                first["obligation"] != obligation or first["transfer"] != leg.transfer_id or
                first["leg"] != leg.leg_index):
            raise DeferredRefused("original reverse suffix order has not reached this refund")

    def apply(self, command, *args, expected_generation, **kwargs):
        if command not in self.COMMANDS:
            raise DeferredRefused("unknown deferred command")
        row, model = self.read()
        if type(expected_generation) is not int or expected_generation != row["generation"]:
            raise DeferredRefused("stale deferred generation")
        self._guard_owned_rollback(row, model, command, args, kwargs)
        value = getattr(model, command)(*args, **kwargs)
        # Revalidate before saving. A failed or uncertain save never dispatches.
        snapshot = model.snapshot()
        DeferredSettlement.restore(self.profile, self.verifier, snapshot)
        components = dict(row["components"])
        components[self.COMPONENT] = canonical_json(snapshot).encode()
        saved = self.store.save(self.scope, components, expected_generation=expected_generation,
                                immutable_components=tuple(k for k in components if k != self.COMPONENT))
        return {"generation": saved["generation"], "result": deepcopy(value), "dispatched": False}

    def dispatch_once(self, operation_id, execution_port, *, expected_generation, now):
        prepare_original = getattr(execution_port, "prepare_original", None)
        if not callable(prepare_original):
            raise DeferredRefused("original read-only execution preflight required")
        row, model = self.read()
        if type(expected_generation) is not int or expected_generation != row["generation"]:
            raise DeferredRefused("stale deferred generation")
        operation = model.operations.get(operation_id)
        if operation is None or operation.status != "PREPARED":
            raise DeferredRefused("prepared original operation required")
        # This trusted port only resolves an existing route and authorized child.
        # It must not sign, send, reserve funds or change external state.
        try:
            execute_original = prepare_original(deepcopy(operation))
            if not callable(execute_original):
                raise DeferredRefused("original route unavailable")
        except Exception:
            return {"generation": row["generation"], "status": "BLOCKED_NOT_DISPATCHED",
                    "dispatched": False}
        # Persist UNKNOWN before execution. CAS also catches changes during the
        # read-only preflight; no prepared callback runs after a failed save.
        prepared = self.apply("mark_dispatched", operation_id, expected_generation=expected_generation, now=now)
        operation = prepared["result"]
        try:
            observation = execute_original(deepcopy(operation))
        except Exception:
            # Never classify a transport failure as non-execution or retryable.
            return {"generation": prepared["generation"], "status": "UNKNOWN", "dispatched": True}
        # An executor response is not a confirmed financial effect. The caller
        # must reconcile via confirm with authenticated destination evidence.
        return {"generation": prepared["generation"], "status": "UNKNOWN",
                "dispatched": True, "observation": observation}
