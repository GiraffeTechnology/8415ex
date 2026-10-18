# Preserve original server FIFO after restart

The existing Exchange can now receive an explicit dedicated DurablePriorityStore.
Its existing PriorityBook uses that store for committed server admission order,
scoped to receipt, exact asset, selected price currency and rollback generation.
SQLite serializes admissions from separate connections. A lost commit reply
requires reading the same original order; it does not allocate another sequence.
Initialization is explicit and refuses existing tables instead of migrating them.
File-backed FULL/EXTRA storage with a durable journal mode is required and checked
again before writes. No database is opened on module import.

A fresh Exchange restores original order identities and their original digests
through the established intent entry path. Re-entering them in a different order
does not change their first admitted FIFO sequence. Missing original terms block
matching rather than silently omitting older orders. A proposal still revalidates
current sessions, authorizations, expiry, owner and all original domain checks;
the stored sequence is not execution authority. A new rollback generation uses a
distinct book while retaining the old one; old entries are not automatically
copied into the new generation. Full used-nonce and withdrawn-state restoration
still belongs to complete exchange recovery and cannot be inferred from this store.

This is an implemented connection to Exchange/ PriorityBook, with seven authored
regression definitions using real temporary SQLite and synthetic domain orders.
They remain NOT_RUN pending approved remote Linux QA. Runtime configuration must
explicitly bind the existing protected store; no default production path, resource,
credential, service installation or migration is invented. Existing fixture mode
without a store remains an in-memory model and is not restart acceptance.

The store holds non-secret order identities, original digests, nonce references
and admission sequence only. It stores no signatures, session cookies or keys and
does not restore authorization, execute trades, move funds, query a chain or create
a scheduler. Complete exchange-state recovery, authoritative financial/Oracle
integration and live restart/chain/UI acceptance remain open.
