# EX wallet-reference facts

This private codec preserves the existing EX AuthorizationReference and
TradeIntent fields, signed terms, session-map observations and consumed nonce
pairs. It reuses the operational facts codec for canonical bounded containers
and nested Asset identity. A changed model field contract requires an explicit
codec revision; missing or duplicate reference identities and cross-account or
asset intent bindings refuse.

These are EX observations of wallet references, not a wallet custody store.
Revoked and expired references stay revoked and expired. A later session is not
rewritten to the historical grant's session, and consumed nonces are never cleared
or replaced by a new nonce during decoding. The original account/nonce tuple
shape is preserved without inventing a new chain namespace or authorization.
No current-time check discards old evidence merely because it has expired.

Decoded facts have execution_authorized=false and are not installed into an
Exchange, native grant service or signer. Actual current authorization, selected
account/chain/task scope, revocation, fees/funds and UNKNOWN operation guards still
belong to the original execution path. This codec neither adds a username/tenant
login prerequisite nor refreshes authority or dispatches an operation.

No private keys, seed material, tokens, passwords, authenticator factors, live
connections or signer callbacks are accepted. No network, database or file is
opened by the module. Original domain constructors are rechecked after decoding,
but original native signature/source authentication and full aggregate recovery
remain separate uncompleted work.

Eight synthetic regression methods cover signed digest fidelity, expired/revoked
facts, session/nonce retention, detached maps, binding/identity refusal and invalid
schema/container input. They are NOT_RUN. Source preparation performs no local or
Windows product imports, syntax/type checks, tests or packaging.
