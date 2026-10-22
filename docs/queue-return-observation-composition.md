# Queue funds and original return-task observations

The current workbench composition retains two independent queue components:
original ordered segment reconciliation and bounded process-local gateway
observations. Principal stays in each segment's selected original currency and
smallest units; consumed ETH gas stays separate. A displayed status cannot
supply a missing amount, prove native movement or authorize a resend.

The original direct-return task adapter is included with its exact task-status
reader and reserved execute gateway. It preserves the original four execute
fields and forwards the original expected budget revision. Construction and
execute do not insert a task-status or native-absence preflight. The original
client's durable attempt guard and the original server's authorization and CAS
remain authoritative. No credentials, source endpoints, alternative store,
signer, reserve or native financial writer is created.

A returned execute body remains an unknown native outcome. Showing that result
in the queue performs no further Wallet calls. Cache eviction or process restart
does not establish absence from the original durable journal. Domain funds,
gateway reports, registration and native chain results remain separate evidence.

Four new synthetic integration definitions join both HTTP queue components in
six locales, exercise an actual original mock execute result through its public
projection, retain empty-cache uncertainty, and keep per-segment currency/gas
units independent. Existing retained tests remain source-bound. Author product
execution is NOT_RUN; no current runtime, browser, financial or chain acceptance
is inherited or claimed.
