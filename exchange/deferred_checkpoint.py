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
                          "deadline", "observe_liquidation_source", "observe_collateral_remainder", "prepare", "observe_gas_requirement", "mark_dispatched", "confirm_nonexecution", "confirm"})

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
        except (ValueError, TypeError, KeyError, UnicodeError) as error:
            raise DeferredRefused("invalid deferred checkpoint") from error
        return row, model

    def view(self, obligation_id):
        row, model = self.read()
        return {"generation": row["generation"], "projection": model.public_status(obligation_id)}

    def apply(self, command, *args, expected_generation, **kwargs):
        if command not in self.COMMANDS:
            raise DeferredRefused("unknown deferred command")
        row, model = self.read()
        if type(expected_generation) is not int or expected_generation != row["generation"]:
            raise DeferredRefused("stale deferred generation")
        value = getattr(model, command)(*args, **kwargs)
        # Revalidate before saving. A failed or uncertain save never dispatches.
        snapshot = model.snapshot()
        DeferredSettlement.restore(self.profile, self.verifier, snapshot)
        components = dict(row["components"])
        components[self.COMPONENT] = canonical_json(snapshot).encode()
        saved = self.store.save(self.scope, components, expected_generation=expected_generation,
                                immutable_components=tuple(k for k in components if k != self.COMPONENT))
        return {"generation": saved["generation"], "result": deepcopy(value), "dispatched": False}

    def dispatch_once(self, operation_id, execute_original, *, expected_generation):
        if not callable(execute_original):
            raise DeferredRefused("original bounded execution port required")
        # Persist UNKNOWN before any callback. A stale contender cannot dispatch.
        prepared = self.apply("mark_dispatched", operation_id, expected_generation=expected_generation)
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
