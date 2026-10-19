# Rehydrating EX-owned facts

`rehydrate_exchange_facts` rebuilds the original in-memory Exchange structures
from the existing exact snapshot codec. The application supplies a fresh,
currently configured original Exchange as its runtime template. The function
returns a new serialized access object; it does not mutate or publish that
template or replace an existing writer.

Receipt declarations, original domain maps, direct-return rollback steps and
outcomes, signed intent references, consumed nonces, mint uniqueness indexes,
priority entries, original admission sequence and unresolved identifiers are
reconstructed. Runtime callbacks, controller and payment ports, registrar
configuration, clock, gas policy and priority journal stay the application's
current original objects. The configured mint verifier is retained without being
called. Original priority books receive new in-memory locks and the same exact
saved scope, rather than generating another order sequence.

Snapshot session observations never reconnect a wallet. The supplied runtime's
current session map is used. Current authorization observations override saved
references of the same account/chain/asset identity, so a known current revocation
is not replaced with an older reference. Consumed nonce sets are united, never
cleared. Original domain authorization, expiry and task behavior remain in their
existing methods; reconstruction adds no human approval step.

Reconstruction performs no controller enquiry, payment, signature, transaction,
queue dispatch, external journal read or database write. Subsequent explicit
calls continue through the original ports. The application still has to
reconcile its original controller and priority journals where their durable
observations may be newer than the checkpoint. No automatic effect replay,
cross-journal atomicity, installed runtime identity, native restart acceptance
or complete product delivery is claimed.

Eight synthetic regression definitions cover a second Exchange preserving a
completed direct-boundary return, UNKNOWN enquiry without replay, current sessions and revocations,
the consumed nonce union, original priority sequence, mint uniqueness and refusal
to overwrite an existing domain history. They have not been run. These model
tests reuse synthetic controller records; they do not prove an operating-system
process restart or native journal reconciliation.
