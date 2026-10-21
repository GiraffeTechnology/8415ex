# Existing reserved Wallet task gateway

This composition enters the original Wallet `tasks/execute` route for an
existing exact-operation request. It creates no task, grant, reservation,
credential, store, signer, RPC connection or substitute native journal.

The trusted host supplies the existing immutable EX scope, Wallet task/operation/
child identities and original exact operation. Execution passes the caller's
ORIGINAL expectedBudgetRevision unchanged to the original client/server. The
server's existing reservation/child/CAS and execution checks decide whether that
request can proceed. No extra status fetch, readiness test or human approval is
added as an execution prerequisite, and no failed request is refreshed and retried.
The independent `read()` port can inspect the same task for observation/recovery;
its return value never dispatches anything or grants execution authority.

The existing WalletAPIClient remains responsible for its dedicated persistent
execute-attempt guard and session/transport behavior. Reconstructing this gateway
does not clear that guard. No fallback database or new all-ready gate exists.
The original server still checks the grant, child, actor/chain, fees, funds,
nonce and live execution conditions. Actual installed source/configuration and
the trustworthy original mapping remain separate runtime evidence.

An execute response is always exposed as outcome unknown here. Even HTTP success
or a submitted transaction hash is not a confirmed asset return, principal
settlement or Oracle registration. The original authoritative effect enquiry
must reconcile the same operation. Read-only task status is not authenticated
native absence, and this gateway never modifies an EX UNKNOWN claim.

Eight synthetic HTTP definitions exercise exact original CAS input, absence of a
new mandatory status query, transport uncertainty, persistent no-resend on
reconstruction, missing-store refusal, immutable mapping, concurrent entry and
independent read recovery. They use the original client fixture and do not sign
or move value. Author execution is NOT_RUN. Existing integration CI discovers
them. This stage depends on the original task-status reader; actual native/
runtime/chain acceptance remains OPEN.
