# Closed rollback conflict observations

The original late-registration handler appends a conflict to a closed rollback's
state and updates the same archive report's conflict tuple. It neither revives
that segment nor releases its money again. The generic snapshot checkpoint's
immutable archive-prefix comparison previously refused this legitimate change.

`ClosedRollbackConflictCheckpoint` is a separate adapter using the original
owned-facts store and generation CAS. For an existing complete archive it permits
only an append to `state.conflicts`, paired with exactly the corresponding
`report.conflicts` tuple. Removing, replacing or reordering old conflicts is
refused. Every other archived field remains identical, including the original
direct-return boundary, step identities and completed outcomes. Original general
continuity checks retain events, consumed nonces,
signed terms, mint uniqueness and applied-result identities. The original store
receives the same expected generation; commit uncertainty is never retried.

This adapter does not call a registrar or wallet, create conflict evidence,
reopen a sequence, rewrite an online database, migrate a process, or restore
execution authority. The generic adapters are unchanged. A host must explicitly
compose the appropriate adapter with its existing serialized writer. The checkpoint loader can read this subclass, but an existing composition may
require the exact generic class. No such composition is silently changed here.
Source definition alone is not installed behavior or acceptance.

Seven synthetic regression definitions cover the original late-registration
handler and database reopening, retained-conflict deletion, disagreement between
the two observations, direct-return boundary or report substitution, stale generation and commit
uncertainty. They have not been run. No product test or complete recovery
acceptance is claimed.
