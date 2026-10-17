# Explicit observation configuration

Initial support for EX-NFR-07, T-27 and T-38: bind the existing non-secret runtime references and the host's explicit observation settings to one canonical SHA-256 descriptor. This is source authoring, not executed configuration validation, deployment or acceptance.

`exchange.observation_policy.ObservationPolicy.from_mapping` requires every field:

| Field | Unit and meaning |
| --- | --- |
| confirmation_depth | Blocks required by the host's selected test confirmation policy |
| reorg_window_blocks | Blocks in the host's selected reorganization observation window |
| rpc_timeout_ms | Milliseconds for the host's selected RPC timeout |
| registration_timeout_ms | Milliseconds for the host's selected registration timeout |
| unknown_enquiry_interval_ms | Milliseconds between host-owned unknown-outcome enquiries |
| queue_retry_interval_ms | Milliseconds between eligible host-owned queue retries |
| max_pending_operations | Host-owned pending-operation count limit |

Every value must be an explicit integer from 1 through 2147483647; booleans, fractions, zero, extra fields and missing fields are refused. These representable bounds are input constraints, not recommended operating values, production SLAs or a new resource allocation. No defaults or implicit relationship between confirmation depth and reorganization window are selected. The existing execution owner must reconcile these values with its actual implementation and approved configuration. A hash identifies supplied values; it does not prove that any provider uses or enforces them.

Compose `configuration_snapshot(existing_references, explicit_policy)` from the existing `RuntimeReferences` and `ObservationPolicy`. The output retains the explicit descriptor and a canonical JSON UTF-8 SHA-256. No credentials, URLs with tokens, private infrastructure paths or signed payloads belong in the reference descriptor. Inputs must already be the approved public or opaque non-secret references.

For a host already composing the original workbench, `PolicyRuntimeBinding` accepts the same original exchange, receipt, run and checked gateway, with required keyword arguments `references` and `observation_policy`. Its snapshot adds `configuration` beside the existing domain observation and business revision. It does not change domain state, execute a command, install a provider, replace gateway policy, start a scheduler, sleep, poll, retry or query a journal. Existing gateway authorization, confirmation, state validation and reconciliation remain authoritative. Configuration remains `PRESENT_UNVERIFIED`, operations readiness `NOT_VERIFIED`, authority `NOT_GRANTED` and provider execution `NOT_RUN`.

The host may compose this independent snapshot with its existing metrics binding rather than replace that binding. Configuration identity, business revision, build identity and original execution evidence are different values; none substitutes for another.

Independent QA command, supplied but NOT_EXECUTED by the source author:

```sh
python3 -B -m unittest integration.test_observation_policy
```

Five authored test methods cover explicit bounds and missing/extra fields, deterministic canonical hashing, changes to each setting, direct-constructor validation, and unchanged original snapshot/revision/domain/gateway identity. They do not test live provider enforcement, reorganization recovery, actual timeouts, resource capacity or deployment. Those require the original execution environment and source-bound independent evidence. No existing submitted source or producer file is modified by this initial module.
