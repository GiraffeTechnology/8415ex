# Record actual intent submission decisions

The existing submit_intent action now records its current domain scope decision
for a known receipt, with the original intent digest, authorization reference,
selected currency, reason codes and observation time. A conflicting repeat is
recorded as refused while preserving the original terms. An identical repeat is
idempotent and appends no new decision. validate_intent and page reads remain
read-only and do not turn refreshed displays into new acceptance events.

An accepted intent record is explicitly not trade formation, financial effect,
permission to sign or native execution authorization. It precedes priority-store
admission, which can still fail or have an unknown commit. Execution must still
perform all original current-state, funds, gas, nonce and cutoff checks.

Malformed or unknown-asset submissions cannot be attached to an invented receipt.
Their authenticated intake audit remains an explicit separate gap. Currency/ETH
admission and original atomic remint timeline joins also remain open. The event
contract and its explicit expected source vocabulary now account for the actual
intent calls without manufacturing events for those other missing integrations.

Four new regression definitions cover the real synthetic-domain submission path,
read/idempotency behavior, refusal/conflict evidence and unbound asset handling.
They are NOT_RUN pending established approved remote Linux QA. No local tests,
production signatures, native funds, deployment or chain/UI acceptance are implied.
