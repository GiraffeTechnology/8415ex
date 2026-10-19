# Persisting a detached Exchange snapshot

ExchangeSnapshotCheckpoint connects the complete immutable bytes exported by the
owned-fact snapshot module to the existing AggregateCheckpointStore. It requires
exactly the owned-facts component and retains the original caller-selected scope,
file-backed connection, source commit/tree, durability checks and generation CAS.
It selects no database path, migrates no schema and creates no runtime resources.

Before a replacement, the adapter reads the original row and requires its
generation to equal the caller's expected generation. It compares the candidate
against that exact row, then passes the same expected generation to original
save(). An intervening normal writer increments the generation; the original
BEGIN IMMEDIATE transaction rejects the stale candidate. A preflight check is
never followed by an unconditional overwrite or a refreshed expected generation.

Existing receipt declarations, full admitted mint declarations, currency terms,
mint uniqueness identities, signed intent digests and applied-result identities
cannot disappear or change. Consumed nonce history cannot shrink, and original
event and rollback-history lists remain prefixes. New receipts and later facts
can be appended. These continuity checks do not establish every financial or
external semantic invariant, nor do hashes authenticate an attacker-controlled
database or protect against direct out-of-protocol SQL rewrites.

Snapshot bytes are captured once and cannot mutate between comparison and save.
The original store rechecks source, settings and foreign-transaction boundaries.
Uncertain commit acknowledgements propagate as CheckpointCommitUnknown without
retry, rollback claims, nonce release or native dispatch. The original row must
be reconciled to determine what actually committed.

This is actual persistence of detached facts, not a live mutation/save hook. The
caller still supplies a coherently captured snapshot under its original single
writer. No live Exchange, adapter or external journal is invoked or restored.
Read and write results retain executionAuthorized=false and completeRecovery=false.
Native effect reconciliation, runtime mutator transactions and controlled restore
remain required unfinished integration work.

Eight synthetic regression definitions cover reopen, immutable declarations,
append-only receipts, nonce/history retention, a real interposed SQLite writer,
lost commit acknowledgement, source mismatch and stale/mutable input. They have
not run; no local product tests, imports, syntax/type checks or builds occurred.
