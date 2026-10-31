"""Read original owned facts without projecting away aggregate CAS identity.

The complete component set is pinned by the original host. Writes must enter
its existing joint coordinators; this view cannot independently save owned
facts while leaving deferred obligations or registration mappings behind.
"""
from .aggregate_checkpoint import AggregateCheckpointStore
from .exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint, ExchangeCheckpointRefused
from .exchange_fact_snapshot import decode_exchange_snapshot


class LinkedCheckpointView(ExchangeSnapshotCheckpoint):
    REQUIRED = frozenset({'owned-facts', 'deferred-settlement', 'registration-task-mapping'})

    def __init__(self, store, *, expected_components):
        if (type(store) is not AggregateCheckpointStore
                or type(expected_components) is not tuple
                or any(type(name) is not str for name in expected_components)
                or tuple(sorted(set(expected_components))) != expected_components
                or store.components != expected_components
                or not self.REQUIRED <= set(expected_components)):
            raise ExchangeCheckpointRefused('exact complete linked component set required')
        self.store = store
        self.expected_components = expected_components

    def read(self, scope):
        if self.store.components != self.expected_components:
            raise ExchangeCheckpointRefused('original linked component set changed')
        row = self.store.read(scope)
        if row is None:
            return None
        if set(row['components']) != set(self.expected_components):
            raise ExchangeCheckpointRefused('complete linked aggregate required')
        return {**row, 'facts': decode_exchange_snapshot(row['components']['owned-facts']),
                'executionAuthorized': False, 'completeRecovery': False}

    def save(self, scope, snapshot_bytes, *, expected_generation):
        raise ExchangeCheckpointRefused('linked owned facts require original joint CAS transition')
