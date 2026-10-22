# Signature observations within a historical position

An NFT position can have more than one original role/transfer/payload signature
record. The detail projection now verifies and retains each original record
independently rather than rejecting all second records at the same position.
Each signed observation still uses the original signature_status callback
contract: the original verifier must match role, historical position, transfer,
unchanged payload and applicable scheme reference. Unknown verification does
not become signed and does not promote another record.

The public additive signatureObservations array contains only position, a
position-local observation ordinal and status. Private roles, actor identities,
payloads, scheme/transfer references and original verification inputs remain
private. The ordinal is presentation order in this observation, not a durable
native operation ID, proof, signing reference or inferred transaction type.
Incomplete unsigned/pending records remain observations without invented proof.
An exact duplicate complete original binding is inconsistent, not a second
signature.

The older signatureStatusByPosition list remains compatible for a single record.
For multiple records its summary stays unknown even if all observed records are
signed: a partial source list cannot prove every required role completed.
The detail page renders each separate observation with six-language fixed
labels and status. It does not move historical signatures to today's Owner or
Holder or infer them from matching positions, admission, registration or gap.

Existing source/receipt verification, original private payload custody and the
identity-free terms projection remain. This change adds no signer, scheme,
verification provider, approval, nonce, funds or execution gate. It neither
authenticates an arbitrary caller's claimed rows nor proves real chain execution.
The source host must supply actual original observations and verifier results.

Eight authored regression methods cover same-position role separation,
independent verification, duplicate original binding, incomplete unsigned
records, historical position stability, six locales/privacy, legacy consumers
and long timelines. Author product tests, imports, syntax/type/browser/build
execution are NOT_RUN. Current-head independent integration/CI and original
browser/native evidence remain required; complete T-76 acceptance stays OPEN.
