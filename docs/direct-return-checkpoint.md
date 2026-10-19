# Checkpointing the original direct-boundary return

Current main PRD.md v1.4 requires a single asset-control operation returning
owner directly to the current effective holder, without ordinary intermediate
wallet traversal. Principal refunds and gas reconciliation remain separate
resumable operations. Atomic old-token burn/new-token mint is a different
operation and is unchanged.

DirectReturnCheckpoint is an optional composition of the existing
SerializedExchangeAccess and ExchangeSnapshotCheckpoint. One explicit call
holds the same access lock, saves the current detached facts, invokes the
original advance_rollback once without a per-hop argument, and saves its
available resulting facts under the preceding snapshot generation. It adds no
new rollback, authority or wallet execution algorithm.

A pre-call storage refusal or commit-UNKNOWN propagates without invoking the
domain operation. If the original method raises, available facts are captured
before the original error is rethrown. If the following capture or save fails,
DirectReturnProgressNotSaved preserves that error, the preceding checkpoint,
the original error and any returned report. Live effects are never rewound,
retried, labelled absent or released by this adapter.

This is not an authorization or an installed prerequisite for permitted wallet
operations. The host must explicitly choose this optional composition; other
writers must share the same access object. Snapshot durability and external
controller journals are not one atomic transaction. Persisted facts alone do
not reconstruct an active process or reconcile native effects. Existing
generation CAS, source identity, history continuity and commit uncertainty
remain the original store's responsibility.

Eight synthetic regression definitions cover direct D-to-A return with zero
ordinary intermediate ETH, protected AB with D-to-B return, database reopen,
duplicate progress, stale generation, before/after commit uncertainty, UNKNOWN
lookup and preservation of original and storage errors. They have not run.
No native execution, browser, deployment or complete recovery is established.
