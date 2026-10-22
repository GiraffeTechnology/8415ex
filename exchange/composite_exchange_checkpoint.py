"""Opt-in owned-facts access to an existing original deferred aggregate row."""
from .aggregate_checkpoint import AggregateCheckpointStore
from .exchange_fact_snapshot import decode_exchange_snapshot
from .exchange_snapshot_checkpoint import (ExchangeSnapshotCheckpoint,
    ExchangeCheckpointRefused, _continuity)


class CompositeExchangeSnapshotCheckpoint(ExchangeSnapshotCheckpoint):
    """Preserve opaque companions under the original row's generation CAS.

    The host explicitly supplies the complete existing component declaration
    and original scope (the deferred profile's checkpoint_scope). No missing
    row, companion state, schema, source or scope is initialized or migrated.
    Companion bytes are not decoded, verified or promoted to proof authority.

    Existing snapshot loaders accept this explicit subtype. The ordinary
    ExchangeSnapshotCheckpoint singleton-component guard remains unchanged.
    Native command pre-effect scopes are deliberately unsupported: copying
    deferred state into a new row or replacing an earlier operation preimage
    is not a safe substitute for the original command recovery contract.
    """

    def __init__(self, store, *, scope, components):
        if (not isinstance(store, AggregateCheckpointStore)
                or type(components) not in (tuple, list)
                or any(type(name) is not str for name in components)
                or len(set(components)) != len(components)
                or tuple(sorted(components)) != store.components
                or not {"owned-facts", "deferred-settlement"} <= set(components)):
            raise ExchangeCheckpointRefused("explicit complete original deferred component set required")
        store._scope(scope)
        self.store, self.scope = store, scope

    def read(self, scope):
        if scope != self.scope:
            raise ExchangeCheckpointRefused("exact original composite scope required")
        return super().read(scope)

    def save(self, scope, snapshot_bytes, *, expected_generation):
        if type(expected_generation) is not int or not 0 <= expected_generation < 2 ** 63 - 1:
            raise ExchangeCheckpointRefused("exact bounded expected generation required")
        if type(snapshot_bytes) is not bytes:
            raise ExchangeCheckpointRefused("complete immutable snapshot bytes required")
        candidate = decode_exchange_snapshot(snapshot_bytes)
        previous = self.read(scope)
        if previous is None:
            raise ExchangeCheckpointRefused("existing original composite row required")
        if previous["generation"] != expected_generation:
            raise ExchangeCheckpointRefused("preflight belongs to another generation")
        _continuity(previous["facts"], candidate)
        components = dict(previous["components"])
        components["owned-facts"] = snapshot_bytes
        # Keep the captured complete map and generation together. Original
        # transactional CAS rejects intervening writes by either subsystem.
        # Never re-read/adopt a newer generation or retry a commit UNKNOWN.
        result = self.store.save(scope, components,
            expected_generation=expected_generation,
            immutable_components=tuple(name for name in components if name != "owned-facts"))
        return {**result, "executionAuthorized": False, "completeRecovery": False}
