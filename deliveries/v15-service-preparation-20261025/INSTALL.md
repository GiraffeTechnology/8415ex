# Offline service preparation — V1.5 candidate

This bundle retains the complete source and PRD, all six stages and tests. It is not the local demo zipapp. It adds a bounded offline source installer and foreground lifecycle for the existing recovered-state service. **It is not production-ready:** the original environment-specific native host composition is missing. See `SERVICE-GAPS.json` for code versus configuration gaps. Keep V1.5 isolated from main.

## Dependencies and verification

Python 3.10+ with its standard library (including sqlite3 and TLS) is required. No pip, credential setup, package download, system service installation, database initialization or migration is performed. Obtain the bundle hash independently. Verify it before extracting into a private approved staging directory; verify `SHA256SUMS` there. Run:

```
python3 -I -B install.py --target /approved/new-version-directory
```

The parent directory must already exist and be canonical. The target must not exist. Installation verifies exact source archive bytes and Git tree, retains all source files and writes `INSTALL-RECEIPT.json`. It never overwrites a prior release. A failed install removes only its newly created directory. The staging/target parent must be private and quiescent; this is not a defense against a hostile concurrent filesystem writer. Do not put the host binding, configuration or runtime state inside the immutable installed source directory.

## Typed original host contract

The separately reviewed, explicitly authorized host Python file must define `create_original_service_binding()` returning `exchange.service_runtime.OriginalServiceBinding`:

- `checkpoint`: original `ExchangeSnapshotCheckpoint` or its composite subtype over the existing store; no replacement store.
- `scope`, `receipt_id`: exact original identities.
- `runtime`: fresh `Exchange` containing original runtime ports, not synthetic adapters or another domain history.
- `options`: exact options for `compose_recovered_operation_observation`, including real fixed port, gas page, three registration sources, clock, service commit/tree and applicable original gateway/readers. Configure remint action and observation through their existing typed inputs; HTTP cannot choose them.
- `expected_generation`, `expected_checkpoint_digest`: exact readback of the original checkpoint.
- `expected_store_commit`, `expected_store_tree`: original store provenance, separately pinned from the new service version. Do not relabel persisted state as new source.

`config/service-host.schema.json` defines the small external configuration: `schema`, absolute `hostPath`, independent `hostSha256`, installed `commit`, installed `tree`. It contains no credential field. A digest authenticates bytes only when obtained through the existing trusted route; it does not authorize arbitrary code. The host factory is trusted executable code and must itself avoid effects during construction. No placeholder factory is provided as a substitute for real adapters.

From the immutable installed directory, using an absolute Python interpreter:

```
python3 -B -m exchange.service_runtime --config /approved/existing-host.json --check
python3 -B -m exchange.service_runtime --config /approved/existing-host.json
```

The entry verifies installed inventory/tree, config and host digest before executing the exact host bytes. Check mode reads and rehydrates the original checkpoint but does not bind HTTP, write state, enquire native effects or dispatch. Health is `CONFIGURATION_VALIDATED` with `nativeAcceptance=NOT_VERIFIED`, never a claim of full readiness. Missing/corrupt/wrong-version/changed state fails closed. Host constructors remain responsible for their existing resources. Foreground mode composes the existing server, rechecks loaded generation and closes only its owned socket on termination. It does not start an external feed, signer, gateway or database lifecycle.

## Recovery and code rollback

Keep the old source release untouched. Stop the foreground service through the original supervisor or SIGTERM. Before selecting an older source release, check it against the **current** original checkpoint and verify schema/authority compatibility. If it cannot read current state, stop: do not downgrade the database, clear unresolved operations, replace checkpoints, retry UNKNOWN or alter credentials. Original journals and owners retain enquiry/recovery authority. No schema migration or data rollback is bundled.

## Outstanding completion

An operator supplying a hostname is insufficient. The missing host must compose the actual Wallet task resolver, durable journals, original verification/authority ports and mixed deferred lifecycle with the one physical aggregate. Real served-version/API/store tests and browser/chain acceptance remain outstanding. Local installer and synthetic-store tests do not close these gaps or authorize deployment.

## Deferred composition available in source

`compose_deferred_runtime` joins the existing owned/joint/deferred/mixed recovery services over one supplied physical aggregate. `OriginalDeferredPorts` explicitly separates the joint-context fresh runtime factory from the recovery-row fresh runtime factory. All authority readers/verifiers and the original native-task resolver remain mandatory. Construction reads the pinned generation and decodes owned state; it performs no authority callback or native command. The exact owned leg mapping is derived from the coordinator's original bytes and independently rechecked by the joint core. Principal allocation remains explicitly unconfigured unless its component, allocator and authenticated staged-allocation verifier are all supplied. This composition is not an authenticated proof implementation or production host.
