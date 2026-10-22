# Existing-row EX and deferred checkpoint composition

`CompositeExchangeSnapshotCheckpoint` is an explicit adapter for an already
populated original `AggregateCheckpointStore` row containing `owned-facts`,
`deferred-settlement` and any explicitly declared original companion components.
It closes the singleton snapshot adapter's component-set incompatibility without
changing that adapter's strict default. It adds no database, schema, migration,
default state, new source of authority or provider configuration.

The trusted host supplies its original store, complete component names and the
same scope used by the deferred profile:

```python
snapshot = CompositeExchangeSnapshotCheckpoint(
    original_store,
    scope=profile.checkpoint_scope,
    components=original_component_names,
)
deferred = DeferredCheckpoint(
    original_store, profile.checkpoint_scope, profile, original_verifier,
)
loaded = load_exchange_checkpoint(
    snapshot, profile.checkpoint_scope, original_fresh_runtime,
)
```

These are existing application objects, not a recipe for creating replacement
storage or selecting a verifier. The explicit component declaration must match
the complete store declaration, with no duplicate, missing or extra name. Both
required components must already be present. The host must select the original
profile scope; `DeferredCheckpoint` continues to enforce that exact binding.
The snapshot adapter refuses any other scope and cannot create a missing row.
A missing load remains unavailable, not an empty success. Source identity,
durability, digest, byte limits and foreign-transaction checks remain those of
the original aggregate store.

## Shared generation and untouched bytes

Snapshot saving decodes and validates owned facts, retains the existing generic
history/nonce/declaration continuity checks, and captures all companion bytes
from that same read generation. It replaces only `owned-facts`, then submits the
complete map to the original transactional compare-and-swap with the same
expected generation and all other components declared immutable. Deferred
saving already follows the reciprocal rule for `deferred-settlement`.

Any competing writer advances the shared generation. The stale operation fails
rather than silently adopting the new generation, merging snapshots, overwriting
another component or retrying a commit whose acknowledgement is unknown. Opaque
companions are preserved byte-for-byte, not decoded or declared verified.
Deferred restoration and its configured verifier remain the only applicable
deferred interpretation/proof boundary; legacy deferred state is not migrated.

The loaded generation is an observation, not a lease. A previously loaded EX
object does not automatically refresh after another writer. Original host
serialization, reloading/reconciliation and fresh-state discipline remain
necessary. This is not a joint atomic EX/deferred business transition, a
cross-journal transaction, or support for the separate
`ClosedRollbackConflictCheckpoint` continuity variant.

## Command boundary remains blocked

The original checkpoint loader and recovered/command workbench factories accept
this explicit snapshot subtype, so they can load the original composite row
without another EX instance or state initialization. This is read/load
compatibility, not a usable composite native-command dispatch implementation.

`CheckpointedOperationBridge` retains one immutable pre-effect snapshot under a
derived per-operation scope. This adapter deliberately refuses that other scope:
copying deferred reservations into a second aggregate row, manufacturing empty
companions, or overwriting the original row as a substitute would not satisfy
the existing preimage and recovery contract. The bridge's original journal may
already have persisted `UNKNOWN` before that refusal. The native executor is
not called, but the conservative claim is retained, never cleared, described
as terminal nonexecution, or blindly retried. Existing claims remain eligible
for original native enquiry/reconciliation without a new snapshot or send.

The existing `DeferredCheckpoint.dispatch_once` path still persists its own
`UNKNOWN` and exact operation/reservations in the shared original row before its
executor callback. Failed saves, generation races and lost acknowledgements
never authorize its executor. An owned-facts save must preserve those exact
deferred bytes across restart.

## Evidence and remaining work

The focused integration test source covers explicit opt-in/default rejection,
read-only load, missing/wrong scopes, source identity, unchanged companions,
continuity, stale/interposed/concurrent writers, commit uncertainty, durable
deferred UNKNOWN/reopen and the blocked native-command pre-effect boundary.
Execution results require exact-candidate CI through the existing controller;
no local execution or acceptance is claimed here.

This supports the persistence/reuse portions of EX-DEFER-04, EX-DEFER-11,
EX-DEFER-12 and EX-ARCH-01 (T-88, T-95 and T-96). Production EvidenceVerifier,
native resolver composition, joined business transitions, complete existing UI
wiring, actual Hoodi/Sepolia evidence and served/runtime acceptance remain open.
Keep V1.5 isolated from V1.4/main. Neither this adapter nor green CI establishes
complete V1.5 delivery or permission to deploy or move funds.
