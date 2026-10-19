# Exchange-owned fact snapshots

This read-only exporter connects the receipt, wallet-reference and operational
codecs to all explicitly listed fact containers owned by the current Exchange:
receipt identity, immutable mint declarations and currency terms, original
authorization references and signed intents, session observations and consumed
nonces, transfers, active and historical occurrence indexes, owner/holder-related
indexes, registration requests/results/deferred/rejected facts, escrows, gas facts,
rollback state/history, retained legacy exit facts and event history. Mint
uniqueness maps and priority admission facts are captured separately.

Priority sequence counters, unresolved persisted-row identities and nonce maps
are preserved as observed; they are not inferred from entry count or refreshed by
reading the priority journal. No clock, verifier, registrar, payment/asset adapter,
voucher service or external persistence dependency is called. Callbacks, live
connections, credentials and current policy/configuration are excluded explicitly.
The complete current Exchange attribute membership is pinned so newly introduced
state is refused until an explicit revision handles it instead of disappearing.

The caller must serialize capture with the original single writer. This exporter
does not add a lock to Exchange, establish a database transaction, detect every
concurrent mutation, or supply native execution quiescence. It must not be used to
claim a consistent live checkpoint without that integration. Its canonical bytes
are a detached candidate component for the existing atomic store, not an attached
save hook or active recovery operation.

Decoding validates source field membership, per-receipt map coverage, immutable
currency and asset indexes, transfer occurrences, holder/active indexes and
priority signed-term references. These checks do not constitute complete semantic
validation of every nested historical object or external evidence. Unsupported
legacy object types refuse the snapshot and leave the original evidence intact;
no history is deleted or rewritten to make encoding succeed.

Decoded execution_authorized and complete_recovery are false. External native
payment/registration/asset journals, current authorization and policy, actual
provider observations, atomic mutator/save wiring and controlled live restore
remain separate required work. UNKNOWN remains UNKNOWN; this module neither
retries an effect nor releases a nonce/reservation. It reads no external database,
key or journal and performs no chain operation.

Nine synthetic regression definitions are authored and NOT_RUN. No local product
imports, syntax/type checks, tests, builds or packaging were performed.
