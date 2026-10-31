# Existing attempt stores and original host inputs

This isolated change updates only the existing attempt-store API, its tests and this document. The assembly interfaces below describe the separate service-source candidate contract; their implementations are not imported into main by this change. No candidate package/history or host implementation is added.

The packaged source deliberately does not define an environment-specific `create_original_service_binding()`. `exchange.service_runtime.load_host` executes a separately approved, hash-pinned host module and requires that function. `compose_cross_product_service` is the existing application assembly implementation; adding a function with that name that returns fixtures or a replacement empty database would not establish a real binding.

## Minimal recoverable inputs and existing consumers

| Original input to recover | Existing consumer / exact usage |
| --- | --- |
| Original aggregate SQLite connection; complete sorted component set; stored source commit/tree; scope/receipt; current generation/full-row digest | `AggregateCheckpointStore(connection,components=...,source_commit=...,source_tree=...)`, then `compose_cross_product_service(store=...,scope=...,receipt_id=...,expected_components=...,expected_generation=...,expected_digest=...)`. Do not call `initialize` for a deployed store. Stored provenance is distinct from installed source. |
| Existing original Exchange runtime constructor and payment/asset-control/registrars/gas/current-session capabilities | `create_original_runtime(row,mint_verifier=...)` must return a fresh `Exchange` installing that exact linked mint verifier. `integration.current_runtime` is a synthetic fixture helper, not a production adapter. |
| Existing deferred `verify(raw,kind=...,now=...)` authority and original mint verifier | `deferred_verifier` and `original_mint_verifier`; hashes/shape do not supply authentic authority. |
| Existing admission, rollback, terminal and native task/cancel capabilities | `OriginalDeferredPorts`: `read_admission`, `verify_admission`, `read_rollback_authority`, `verify_terminal`, `resolve_native_task`, `verify_prepared_cancel`. Composition supplies the linked registration reader and fresh runtime wiring, not these authorities. |
| Authenticated original Wallet journal callable bound to its held gate | `OriginalTaskJournalReader(original_journal)` calls its existing `get` interface. This adapter does not create or replace the original durable journal service. |
| Existing EX transport-attempt database and Wallet origin/tenant/account/base path | `WalletExecutionAttempts.open_existing(path)` then `WalletV3Connection(...,execution_attempts=...)` for each original role. This EX transport barrier is NOT the native funds/task journal. |
| Exact original Oracle origin and source/profile/finality | `oracle_origin`, `oracle_source` (chainId/projectionContract/settlementContract/registerId/verificationProfile/verifier/attestor/codeHashes), `finality_policy`. No inferred contract address. |
| Original caller authentication and service options | `authenticate_caller` returns `OriginalLinkedCaller` only for authenticated actual caller; `service_options` carries original gas/registration sources/clock/port and installed commit/tree. Wallet service login is not caller identity. |

Recovery additionally needs the actual proof-directory capability/manifest and original verifier; configured economic/asset readers require their exact approved profiles and records. Cash/PYUSD custody terminal semantics remain an explicit protocol gap; a generic ERC20 operation is not a substitute.

## Existing-only attempt opening

The legacy constructor remains available for explicitly authorized NEW local stores. Original host assembly should use `WalletExecutionAttempts.open_existing` for a pre-existing store. It opens existing bytes without issuing CREATE TABLE, validates the original two-column schema, refuses noncanonical paths/links, and pins device/inode. Subsequent claims open in SQLite `mode=rw`, refusing a missing/replaced file instead of creating an empty barrier. Existing operations stay consumed across restart; changed request content does not create a new slot.

The host must supply the actual original path and established lifecycle. This does not authenticate the file's business provenance, defend against a malicious concurrent filesystem owner, initialize a missing production store or provide a production host. No host, credential, migration, signature, native dispatch or deployment is introduced.

Compatible existing attempt tables must not have associated triggers. A trigger can suppress/delete an inserted barrier while SQLite reports statement success; this was locally reproduced. The existing-only opener refuses such a schema without altering it, and both APIs verify the inserted key/digest remains present before committing and returning success. Nine new local tests cover original record retention/restart, absent/replaced/linked/wrong-schema stores, literal URI metacharacters and suppressed inserts. These are local persistence checks, not a recovered production binding.
