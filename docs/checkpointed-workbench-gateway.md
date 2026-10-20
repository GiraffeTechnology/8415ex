# Original workbench to durable native-operation binding

`CheckpointedWorkbenchGateway` supplies the existing workbench `enquire` and
`dispatch` port for payment enquiry/resume and suffix recovery. It composes the
original `CheckpointedOperationBridge`; it is not a financial writer, native
transaction ABI, wallet permission implementation or new authorization layer.

An installed application resolver maps a new UI command to its actual original
receipt/asset/global-leg/native-operation/journal scope. No mapping is guessed
from a label, account balance or URL. The native action must match the UI action
family, and the original scope validator and pre-effect asset binding remain in
force. Registration continues through an explicitly supplied original fallback
gateway; its absent configuration affects that path only.

The host explicitly initializes a non-secret correlation table on the same
existing durable operation-journal connection. The immutable mapping binds an
instance and UI journal key to receipt, action, exact request digest and original
native scope. No database path is selected and no schema is created on import
or construction. The original FULL/persistent-journal write boundary is checked
before correlation writes. Another owner's transaction is never committed.

After correlation commit, original `invoke_once` still checks native absence,
persists its UNKNOWN claim, and saves the original immutable pre-effect
checkpoint before entering the original checked gate. That gate retains current
wallet grants, funds, ETH, nonces and atomic domain validation. The UI observation
revision and a persisted correlation grant none of these authorities.

Recovery reads the stored correlation without re-resolving a command or reading
mint declarations. Existing local claims or native observations are enquiry-only
and never replay execution. If a crash occurred after mapping commit but before
any claim, only an absent local claim plus authenticated native absence permits
the same request to continue through the original first-claim path. An enquiry
failure is not absence. A mapping commit exception never enters native execution;
an uncertain original claim or effect keeps its original evidence and UNKNOWN.

The host supplies read-only native enquiry and the already installed checked
execution callback. No login, approval, custody migration or overall readiness
step is added. A lookup error cannot fall through to a send. Returned native
observations use the original allowlisted command-result projection; raw scope,
receipt identifiers, account names and private diagnostics are not served by
this adapter. HTTP success still does not reconcile the original durable row or
prove economic finality.

Thirteen synthetic regression definitions cover actual RuntimeBinding command
composition, restart enquiry without declarations, lost acknowledgements on
both correlation and original claim, scope/request conflicts, original asset
checks, unavailable enquiry, native timeout, fallback preservation, durable
write boundaries and corrupted storage. They have not been run. The actual
resolver, native journal/provider binding, application mounting, browser and
live execution acceptance remain separate work with current-source evidence.
