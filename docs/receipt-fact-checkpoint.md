# One-receipt fact checkpoint integration

This adapter connects the existing receipt declaration codec and operational
facts codec to one generation of AggregateCheckpointStore. Both components are
saved in the same original SQLite transaction with the caller's expected prior
generation. The first stored receipt declaration is immutable for that scope.
Asset identity, minted terms and the NFT0 currency declaration cannot be replaced
even by a caller with the correct current generation. The original declaration
bytes are compared inside the same write transaction as the generation check,
before any row is changed; a conflict leaves the prior generation and bytes intact.
Operational facts may still advance with the unchanged declaration. A stale writer
cannot combine a new declaration with old operational facts. Commit outcome
uncertainty propagates unchanged and is never retried.

The caller supplies stable original collections of transfers, registration
requests and observations, escrows and rollback steps. All five named collections
must be present, even when empty. Records must refer to the same receipt and
original asset/path, with unique identities and occurrence indexes. Predecessor,
request/result and escrow buyer/seller/principal/currency links are checked before
writing and again after decoding a read. Invalid collections do not replace a
previous generation. Reads require the caller's expected original asset identity.
A released or still-UNKNOWN release segment cannot be stored as refund work.

Nested mutable inputs are encoded to immutable component bytes and decoded into
detached values before cross-record validation. Data returned from a later read
is a new observation. An UNKNOWN payment stays UNKNOWN, a blocked rollback stays
blocked, and a stored registrar observation does not become current source trust.

This is an atomic checkpoint for the declared fact subset. It does not prove that
the caller captured every live Exchange collection consistently, restore an
Exchange, establish owner/holder positions, restore authorization/session grants,
verify current Oracle trust, or reconcile native journals, balances and effects.
No native callback, signing or dispatch is accepted. The result explicitly grants
no execution authority and says completeExchangeRecovery=false. Original domain
mutation wiring and full recovery/runtime acceptance remain open.

Twelve synthetic persistence integration methods are authored for reopen fidelity,
cross-receipt/source binding refusal, per-leg principal links, incomplete histories,
generation conflicts, read identity, immutable release prefixes and detached UNKNOWN/blocked facts. They are
Their execution results are tracked separately by exact commit and CI run. No local
or Windows product validation has been performed.
