# Bound original remint operation-result read

`RemintOperationResultReadPort` connects the existing two-word operation-result
decoder to a single original `eth_call` for `operationResult(bytes32)`.
The host supplies the original Sepolia contract, Keccak implementation,
canonical-read policy, raw transport and exact-response verifier. No endpoint,
credential, account, signer or contract is discovered or selected.

The request binds the original operation ID and complete observed block, using
the original block hash and explicit EIP-1898 canonical policy. Its fresh
JSON-RPC ID correlates one read only; it is not a task ID, transaction nonce or
replacement operation. There is no effect method, value, sender or fallback.

Before decoding, the verifier receives exact raw response bytes, exact request,
original chain/contract/block binding and original expected contract digest.
Only an actual true verifier result continues. Request echoes and shape checks
alone do not authenticate provider or contract code. The original port retains
its private provider evidence, credentials, timeout and no-retry handling.

The response must be bounded complete bytes and one exact successful JSON-RPC
object with the matching ID. Errors, duplicate fields, batches, missing results,
malformed ABI and conflicting original digests remain unavailable. They never
become an empty result. A valid zero tuple remains only not-recorded-at-read:
pending absence, receipt finality, financial release and replay permission are
not established. Even a matching recorded result does not establish them.

Eight synthetic integration definitions cover exact request/decoder joining,
zero-result uncertainty, scope refusal before transport, authentication before
decoding, response correlation, malformed/conflicting ABI, private failure
handling, bounds and detached RPC identities. Author product execution is
NOT_RUN. Installing the class is not installing an original provider binding
or completing a live read, receipt, native business or chain acceptance.
