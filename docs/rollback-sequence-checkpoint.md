# Retained reverse-hop recovery sequences

The rollback-sequence checkpoint adapter uses the existing complete Exchange
snapshot and its original generation compare-and-swap store. It preserves the
original path and sequence identity, confirmed hop cursor, per-step identities,
completed refunds and hop result references. A later snapshot cannot remove a
sequence, regress its cursor, replace a completed result or reactivate an
archived sequence. A new active sequence retains the previous sequence in
history rather than reusing or overwriting it.

UNKNOWN and blocked steps are retained as observations; this storage adapter
does not decide whether to submit another transaction. Historical single-return
state remains readable and immutable here, without being relabelled as a new
reverse-hop sequence. The original complete-snapshot rules additionally retain
receipt declarations, consumed nonces, applied results and history prefixes.

The caller's expected generation is passed unchanged to the original store.
Preflight reads do not authorize overwriting a newer writer's generation.
Original durability failures and commit-UNKNOWN exceptions propagate without a
retry or cleanup. No new store, credential, wallet approval or execution gate is
introduced.

This stage persists and validates detached facts only. It does not reconstruct
an active Exchange, import active sessions, reconcile external wallet/native
journals, or provide a complete crash-and-restart execution proof. Existing
history-prefix validation may separately refuse updates to archived report
content; this adapter does not bypass that validation to append late evidence.
Applicable integration and real execution acceptance remain outstanding.

Nine synthetic definitions cover database reopen, confirmed progress, retained
UNKNOWN, cursor regression, result replacement, immutable paths, stale writes,
closed-sequence reactivation and commit-UNKNOWN propagation. They have not been
run for this source. A database readback does not itself resume a wallet hop.
