# Original receipt-task consumer

This initial read-only consumer projects an original Wallet frozen task into
bounded EX-facing public data. It is deliberately not a command gateway. Import
`project_receipt_task` from `exchange.receipt_task_projection` in the original
host when it has an existing task to display. No network, credential, provider,
file I/O, digest recomputation, signature check or transaction submission occurs.
Lexical shape checks are not original Wallet semantic validation. Never feed
this projection back as a validated or signed task. No caller verified flag is
trusted, and arbitrary input fields are not copied to output.

## Pinned original interfaces

Original repository: GiraffeTechnology/8415Wallet-Code. Inspected full commit:
`19c47cbc9aa1106b7c0663065e9f2c70e2b75e48` (PR92 candidate).

- `src/agent/receiptTask.ts`: `receiptTaskCopy`, `receiptPhaseScope`, frozen
  `policy` plus `digest`, receipt kind `artfi-receipt`, handler
  `artfi:whole-receipt:v1`, phases `funded`, `registered`, `paid`.
  Chain allowlist is **31337 / 560048**, not EX-required Sepolia 11155111.
- `server/receipt-operation-encoding.mjs`: `validateReceiptWire` verifies original
  calldata, fee bounds and typed segment correspondence. Reuse its original
  digest domain; EX must not reimplement it with its local SHA256 binding.
- `server/task-receipt-runtime.mjs`: `connectAuthorization`, held preparation
  and send gates, original one-use journal capability, and separate grant and
  native journal stores. No public HTTP command route is supplied by this module.
- `server/task-journal-capabilities.mjs`: original get/create/update claims,
  full task principal, peer, native operation, request digest, plus independent
  receipt phase/nonce/planDigest/journalBindingHash commitments. These are not
  interchangeable with EX receipt ID, segment binding or a caller-supplied key.

## Exact remaining integration contract

Before command composition, the original host must supply the original frozen
task/grant and validated mapping from each EX operation and receipt/asset/segment
identity to its original supported action and phase. It must supply the existing
native operation/journal identity and original unknown-outcome enquiry path,
including authoritative source and segment correspondence. An approved original
Sepolia-capable implementation is required for EX; do not switch EX to Hoodi,
add a chain to Wallet here, guess token/provider or hash a new task schema.

The existing `RuntimeBinding.gateway.enquire/dispatch` injection contract alone
does not establish this mapping. In particular rollback and exit do not appear
in the inspected receipt phase enum. This consumer reports those concrete gaps
and always leaves canExecute false. Even a Sepolia literal is not proof the
pinned Wallet contract accepts it. No source-map value is READY or authority.

## Verification ownership

Five contract test methods are authored in
`integration/test_receipt_task_projection.py`. Independent QA may run
`python3 -B -m unittest integration.test_receipt_task_projection -v` on the exact
candidate. The development writer did not import, compile or execute this
consumer or its tests. Ordinary tests, submitted fixes, CI, integration and merge
belong to the independent QA owner. No browser, deployment or chain acceptance
is represented by this source batch. Existing domain/producer/harness and earlier
submitted files are untouched.
