# Aggregate checkpoint storage foundation

Existing operation claims protect original operation identities across restart.
They do not reconstruct the Exchange's receipts, authorizations, sessions,
intents, escrows, transfer branches, registration observations or rollback state.
This module adds private storage for an atomic group of original component bytes.
It does not yet encode or restore those domain objects or connect their mutation
and original native effects to checkpoint transactions.

The caller supplies a dedicated file-backed SQLite connection, exact source
commit/tree, an explicit complete component-name contract and the original
aggregate scope. No path, connection, credentials, provider, signer or network is
created on import. Schema initialization is explicit and refuses an existing
table; there is no implicit migration. No production database is selected here.

Every save requires the prior generation. BEGIN IMMEDIATE serializes writers;
one row contains the entire exact component set, so a partial set is refused and
no mixture of component generations is read. The configured journal must be
persistent and synchronous mode FULL or EXTRA. The module checks these settings
again before writing without changing them. Commit acknowledgement loss raises
UNKNOWN: the caller must reconcile the original store rather than replaying a
financial operation or assuming the commit rolled back.

Immutable component bytes are preserved using base64 with per-component and
whole-envelope SHA256. Canonical encoding, component membership, source contract,
sizes, generation and checksums are checked before any loaded bytes are returned.
These checks detect inconsistent storage; they are not cryptographic source
authentication against an attacker who can rewrite the database. No pickle or
dynamic class/module loading is used. Returned observations grant no execution
authority and are never exposed through a public endpoint by this module.

Remaining work includes exact original-domain codecs, schema migration policy,
all original private journal and adapter reconciliation, atomic mutation wiring,
restart and crash acceptance, and approved runtime integration. Callers must not
pass signer credentials, private keys or unrelated service state. The required
component set must actually cover the relevant original domain; a caller's small
set cannot be advertised as complete product recovery.

Six meaningful remote-Linux test methods are authored for reopen identity,
stale/partial writes, corruption, source contracts, durability/transaction guards,
and synthetic lost commit acknowledgement. They are NOT_RUN. This stage neither
changes the existing Exchange nor claims persistent full-product acceptance.
