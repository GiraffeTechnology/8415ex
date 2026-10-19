# Pre-effect Exchange snapshot on the original operation path

CheckpointedOperationBridge composes the original DurableEXOperationJournal,
SerializedExchangeAccess and ExchangeSnapshotCheckpoint with an explicitly
provided existing aggregate scope. It creates no connection, provider, signer,
runtime credential or native operation identity. Its callbacks are trusted host
ports, never request-body functions or new authority.

The original journal first validates the complete scope, enquires the original
native identity and commits its existing UNKNOWN claim. Only its new-claim
dispatch closure captures the Exchange-owned facts, checks their exact receipt
asset against that same original operation, and durably saves the complete bytes
at initial generation zero under a deterministic operation-specific data key.
The key binds the explicit original instance scope and complete validated native
operation scope. It is not a guessed tenant, new database or provisioned resource.
The original generation CAS makes that operation's preimage write-once; later
operations use different keys and cannot overwrite the first recovery record.
Only a successful save permits
entry to the original checked native gateway. One access lock covers this
sequence; all relevant domain writers still have to use that same access object.

Snapshot refusal, stale generation or uncertain snapshot commit cannot fall
through to native execution. The original operation claim stays UNKNOWN. The
bridge preserves the precise pre-effect snapshot exception even though the
original journal conservatively wraps dispatch-closure failures as native UNKNOWN.
It neither clears nor reconciles that claim. Claim commit uncertainty stops the
sequence before snapshot or native execution; native timeout leaves the durable
pre-effect snapshot and UNKNOWN claim for original read-only reconciliation.

Existing claims and original native enquiry hits never enter this closure, save
another snapshot or redispatch. An existing-claim enquiry is not blocked by a
newly unavailable domain snapshot schema. Normal replies remain observations,
not authenticated economic finality; local claims do not become RECONCILED here.

The captured bytes describe EX state before the native gate, not the resulting
chain/holder/payment state. This is not a transaction spanning independent stores
or native effects. The original gateway still owns current authorization, selected
account/chain/task scope, funds, ETH gas, nonce and authoritative atomic read-and-act.
No missing-grant waiver, new login/approval or cleanup prerequisite is added.
The bridge does not hydrate an Exchange, release reservations, mutate holder or
payments from a response, or complete whole-product recovery/acceptance. Existing
provider and real-chain prohibitions govern any actual invocation.

Ten synthetic file-backed regression definitions cover durable ordering,
existing claims, native enquiry hits, stale snapshots, lost claim/snapshot commit
acknowledgements, native timeouts, asset mismatches and enquiry despite new schema
unavailability, plus retained preimages across later original operations. They are
NOT_RUN. No local product imports, syntax/type checks,
tests, builds, packaging or real-chain actions were performed.
