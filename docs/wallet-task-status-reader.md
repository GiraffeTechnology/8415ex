# Original Wallet exact-task status reader

`WalletTaskStatusReader` uses the existing authenticated `WalletAPIClient`
`tasks/status` action. It correlates the original task digest, selected-chain
exact-operation intent, complete budget revision and Wallet operation/child
identities. Wallet operation IDs and EX native operation IDs remain separate
explicit correlations; neither is guessed from the other.

The actual exact-task budget states are reserved, outcome-unknown, submitted and
cancelled. Submitted retains its transaction hash but does not prove inclusion,
success, finality, principal settlement or Oracle registration. A missing
reservation is returned as not-observed, never authenticated native absence or
permission to resend. Duplicate IDs, changed child identities and inconsistent
status/hash pairs refuse the read. Cancelled tombstones are retained rather than
treated as fresh unused operation IDs.

The reader does not call prepare, reserve, execute, recover, observe or capability
discovery. It creates no session, grant, task, store or retry. The original client
retains its existing session/transport behavior, and failures propagate without
fallback. Only selected budget facts and original non-secret scope correlations
are returned; authorization/capability objects and other raw status fields are
not copied. Output is an internal application observation, not a frontend payload
or an artfi-task-journal/1 record.

This is another concrete original-interface integration step for T-46 and
unknown-result recovery. The trusted composition must supply the actual original
operation/mapping. Shape checks are not source attestation or a new Wallet
approval. Independent native enquiry and existing execution checks remain
separate, and no local UNKNOWN is reconciled or removed by this read.

Seven synthetic definitions exercise actual states, identities, missing records,
duplicate/inconsistent budgets, failure propagation and detached copies.
Author execution is NOT_RUN. Existing integration CI discovers the module;
installed runtime, real provider and chain acceptance remain OPEN.
