# Operational checkpoint facts

This codec complements the separate receipt declaration codec. It preserves
existing Asset, Transfer, RegistrationRequest, RegistrationEvidence,
EscrowPosition and RollbackStep records using a fixed class/field registry.
Nested lists, tuples, sets, frozensets and maps retain distinct types. Tuple
nonce keys, ordered observations and UNKNOWN payment status are not flattened
into strings, discarded or promoted to terminal outcomes. Map and set encodings
have deterministic order; duplicate entries and duplicate JSON fields refuse.

Input controls neither imports nor class lookup. Unsupported objects, callbacks,
floats, future fields, schema drift, cycles and excessive structure or bytes are
refused. Original record constructors run during encoding and decoding. Their
checks are not a substitute for aggregate cross-record invariants, provenance
verification or current authorization. No private key, signer, callback, live
connection or opaque adapter can be serialized by this codec.

Decoded facts carry execution_authorized=false. There is no Exchange mutation,
database opening, network request, original operation replay, signing or dispatch
in this module. A stored registration result is an observation, not renewed
source trust. An UNKNOWN release/refund or blocked rollback remains evidence to
reconcile through its original operation identity, with no duplicate submission.

This stage does not reconstruct authorization/session grants, restore an entire
Exchange, select production providers, implement migrations, connect component
transactions or reconcile original journals/adapters. It must not be presented
as complete recovery. Full runtime, UI and chain acceptance remain open.

Seven synthetic regression methods are authored for separate transfer dimensions, UNKNOWN release/refund terms,
registrar digests and flags, nonce/container/blocked-step fidelity, constructor
and schema refusal, duplicate/canonical ordering, and bounded malformed input.
They are NOT_RUN; no local or Windows product validation has been performed.
