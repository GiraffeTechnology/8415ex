# Serial access for original domain, UI and snapshot storage

SerializedExchangeAccess composes one original Exchange instance with one RLock.
Original public methods run under that lock and return detached original results.
Private methods and runtime configuration are not exposed as method calls. No
authorization, signer, provider, database, action route or execution result is
created by this composition object.

snapshot_bytes holds the same lock across the complete owned-fact export.
write_checkpoint holds it across capture, continuity preflight and the original
storage generation CAS. It uses the existing ExchangeSnapshotCheckpoint; its
source binding, durable settings, stale generation and commit-UNKNOWN behavior
remain unchanged. Exceptions propagate once, with no blind retry or native
rollback claim. A failed save does not undo a previous independent domain call.

bind_runtime creates a RuntimeBinding-compatible object over the same access.
Each complete multi-method UI observation, public-detail read and existing checked
command holds the common lock. Locking each individual subread alone would not
make the complete UI snapshot coherent. Nested domain calls on the same thread
use the reentrant lock; the original gateway still performs enquiry, task and
authorization checks. UNKNOWN/pending outcomes remain enquiry results and are
not redispatched by this wrapper.

The host must route every relevant writer and reader through this one access
object, including any gateway closures. Keeping the raw Exchange reference or
creating multiple access objects bypasses the shared lock. This is a host
composition contract, not protection against a malicious owner of Python objects.
The host must also preserve the original gateway threading and SQLite connection
thread ownership; the wrapper changes no connection policy or asynchronous route.

Existing server constructors accept an injected RuntimeBinding; the returned
binding can use that composition point without changing their action routes.
This source stage does not install it into a running service, choose a deployment
port or claim all production gateway closures have been rewired. Domain mutation
and durable saving are still explicit separate operations, not a single crash
transaction. Native journal/effect reconciliation and controlled active restore
remain unfinished. Successful snapshots/checkpoints grant no execution authority
and do not establish complete recovery or product delivery.

Nine synthetic regression definitions cover original session behavior, detached
results, private method refusal, real checkpoint composition, workbench binding,
UNKNOWN enquiry without dispatch, concurrent observation/capture serialization,
lost commit acknowledgement and stale save behavior. They are NOT_RUN; no local
product imports, syntax/type checks, tests, builds or packaging were performed.
