# Explicit production host composition

`exchange.production_host` constructs the existing cross-product service from
trusted, process-owned runtime capabilities. It does not initialize a database,
issue an identity or grant, log in, create mTLS credentials, start HTTP, or certify
deployment admission. Missing real inputs raise `ProductionHostUnbound`.

The operator's already approved host exports `create_original_service_binding()`
and calls `compose_production_service` with the configuration and actual bound
capabilities. The existing `8415ex-host/1` loader still pins that host's bytes and
the installed source version. No JSON field imports a module or supplies a
callback, verifier, authentication claim or authority flag.

## Configuration

`parse_production_configuration(bytes)` rejects duplicate keys, non-JSON objects,
unknown fields, malformed source identities and mismatched original client
configuration. The exact `8415ex-production-host/1` fields are:

- `source`: `commit`, `tree` (exact lowercase 40-hex source identities).
- `aggregate`: `scope`, sorted unique `components`, `sourceCommit`, `sourceTree`,
  positive integer `generation`, lowercase 64-hex `digest`. Components must
  include `owned-facts` and `deferred-settlement` without omitting any supplied
  component. Code provenance and stored-state provenance remain separate.
- `receiptId`: the existing receipt in the selected owned-facts snapshot.
- `wallet`: HTTPS `origin`, `tenant`, public `account`, existing `basePath`, and
  canonical absolute `attemptPath`. Settlement is Sepolia; Hoodi is collateral.
- `journal`: original HTTPS operations `endpoint`, original `peerId`.
- `oracle`: HTTPS `origin`, exact original `source` and `finalityPolicy` accepted
  by `OracleAdmissionEvidenceClient`. No EIA reference feed substitutes for it.
- `executionMode`: existing `observe-only` or `native-enabled`.
- `service`: explicit `port`.

Configuration is copied at validation. Source hashes and schema validity detect
mismatches; they do not independently authenticate the source or its business
authority. No default target, placeholder authority or empty-ledger fallback is
provided. Supported new test-state initialization is a separate explicit step.

## Runtime and native ports

`OriginalRuntimeFactory(store, AggregateBinding(...), RuntimeCapabilities(...))`
is the concrete `create_original_runtime(row, mint_verifier=...)` callable. It
checks the actual aggregate source, complete component set, scope, generation
and digest before and after reading current runtime observations. It constructs
a new exact `Exchange` using actual configured payment, asset-control,
registrar, voucher, gas, pricing and priority-store capabilities. It installs
the identical supplied mint verifier. It never clones an old Exchange or
rehydrates snapshot sessions.

The three required source callbacks receive a frozen `CurrentAuthorityContext`
containing scope/generation/digest/store-source identities and the exact tuple
of referenced authorization IDs, not snapshot session data. `read_current_sessions` returns the actual current account/session
map; `read_current_authorizations` returns original `AuthorizationReference`
objects; `read_current_gas_budgets` returns current original gas budgets. An
empty result is an assertion by that actual bound source, not a generated
default. External source failures are sanitized and refused. The original
rehydrator remains responsible for restoring owned facts and preserving UNKNOWN.
Every saved authorization must have an explicit current record. Omitted grants
remain unknown and refuse construction; they never regain validity through the
rehydrator's retained references. Signed constraints under an existing ID cannot
change, and recorded revocation cannot be undone. An explicit current revocation
is retained without silently rewriting the physical checkpoint.

Six `NativeAuthorityPorts` callbacks remain required actual inputs:
`read_admission`, `verify_admission`, `read_rollback_authority`, `verify_terminal`,
`resolve_native_task`, `verify_prepared_cancel`. The existing cross-product
composition supplies both fresh runtime ports and installs its real
`OracleRegistrationReader` as `read_registration`, completing the original nine
ports. Shape is not proof of authority; the operator must bind approved sources.

## Caller, held journal and durable attempts

`ScopedCaller` invokes the original authenticated-caller adapter for every
request, then checks exact `OriginalLinkedCaller` type, aggregate scope,
receipt, Wallet tenant/account and existing action set. No EX service Wallet
session is substituted for browser caller authentication. Authentication
failures are sanitized, with no fallback identity.

The host constructs the existing `OriginalTaskJournalWire` and
`OriginalTaskJournalReader` using the real original mTLS transport and SAME held
grant `with_capability`. It creates no token, transport credential or grant and
does not bypass the wire's bounded get-only response validation. The supplied
transport and grant gate still require independent original binding evidence.

Wallet clients share `WalletExecutionAttempts.open_existing(attemptPath)` from
the existing-only safety patch. A missing/replaced attempt file never creates
a new send slot or schema. Constructor and composition do not log in, broadcast,
reconcile an UNKNOWN automatically, or bind a listener. Final service-binding
validation rechecks the same pinned startup generation before returning.

## Evidence

`integration.test_production_host` tests the new construction/configuration and
safety logic with real Exchange/checkpoint/attempt implementations in isolated
temporary Linux databases. Synthetic authority callbacks and intercepted
composition are unit-test evidence only. They are not production source,
identity, chain, deployment or end-to-end runtime acceptance.

## Existing runtime validation entry

For an already bound original host, the source entry point accepts:

```sh
python3 -B -m exchange.service_runtime --config /private/ex/host-config.json --check
```

`--check` validates the pinned original host and checkpoint without binding HTTP.
It initializes no state, creates no credential and preserves a refusal as a
failure. Starting a listener is a separate authorized deployment action after
source admission and real capability binding.
