# Original remint declaration to EVM argument binding

bind_remint_evm_arguments connects complete original EX remint history to the
argument encoder for the existing same-contract EXNFT0Remint ABI. It reuses
RemintHistoryStore's complete-history validation without opening a database or
writing a row. Original scope, history digest, both declaration digests, old
asset and receipt must remain correlated.

The trusted installed original resolver receives a detached exact request and
complete replacement declaration. It supplies its authenticated EVM operation
ID, replacement declaration words, original ordered currency references and
source reference, bound back to that same request. The bill key must remain
the original history bill key. Exact canonical JSON comparison keeps integer
and float identity types distinct. A typed response or matching hashes alone
are not source authentication; the original resolver remains the trust boundary.

This code does not turn an EX native-operation string, history SHA-256, document
text or currency label into an EVM identifier or declaration hash. Those values
must already exist in the original semantic mapping. It neither predicts the
new token ID nor treats replacement metadata as a confirmed mint result. This
specific ABI remints inside the original contract; an unrelated replacement
contract requires a compatible original adapter, never an automatic reroute.

The result contains argument bytes and the unchanged private correlation, not
a selector, Wallet operation, transaction or authority proof. No wallet/RPC,
signer, authorization, nonce, balance, cleanup, refund, gap/finality check or
persistence is added. Existing original contract and native execution checks
remain in their own path. Missing semantic input blocks only this encoding;
observe_remint and original-operation reconciliation remain independent and do
not need old/new declaration availability.

Eight authored synthetic definitions cover exact semantic correlation, digest
and type mismatches, changed declarations, stable bill/word constraints,
distinct native/EVM IDs, detached inputs, unavailable private source errors and
same-contract adapter limits. They have not been run by the author. Actual
resolver source, Wallet encoder/selector, deployed contract and native
financial/chain acceptance remain open.
