# Existing reserved Wallet task gateway

This composition enters the original Wallet `tasks/execute` route for an
already-reserved exact operation. It creates no task, grant, reservation,
credential, store, signer, RPC connection or substitute native journal.

The trusted host supplies the existing immutable EX scope, Wallet task/operation/
child identities and original exact operation. The status reader matches those
identities and the original budget. Only a matching reserved row reaches execute;
the returned budget revision is passed unchanged as the original server CAS
input. Missing, cancelled, outcome-unknown or submitted rows remain read/reconcile
only. The gateway never refreshes a failed CAS and retries, or changes operation
IDs to get around a conflict.

The existing WalletAPIClient remains responsible for its dedicated persistent
execute-attempt guard and session/transport behavior. Reconstructing this gateway
does not clear that guard. No fallback database or new approval/readiness gate
is introduced. The original server still checks the grant, child, actor/chain,
fees, funds, nonce, live operation and execution conditions. The actual installed
source/configuration and trustworthy mapping remain separate runtime evidence.

An execute response is always exposed as outcome unknown here. Even HTTP success
or a submitted transaction hash is not a confirmed asset return, principal
settlement or Oracle registration. The original authoritative effect enquiry
must reconcile the same operation. Read-only task status is not authenticated
native absence, and this gateway never modifies an EX UNKNOWN claim.

Eight synthetic HTTP definitions exercise exact CAS input, non-dispatch states,
transport uncertainty, persistent no-resend on reconstruction, missing-store
refusal, immutable mapping, concurrent entry and read-only recovery. They use the original client
fixture and do not sign or move value. Author execution is NOT_RUN. Existing
integration CI discovers them. This stage depends on the original task-status
reader; actual native/runtime/chain acceptance remains OPEN.
