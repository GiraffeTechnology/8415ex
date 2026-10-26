# Deployment preparation candidate — not production-ready

This immutable offline service bundle contains the unified lifecycle-route and existing-checkpoint opener increments. It does not replace the earlier service-preparation release or change the V1.5 business-source hold.

- Package: `8415ex-v15-unified-wiring-service-preparation-20261026.tar`
- Bytes: 1853440
- SHA256: `00afa83c3fb253f315eb6f14ce2da1e5e91d64e0debe2cb5487bd1619572c12b`
- Embedded origin: `ec35f24212f432d1df78d12c75a39a8212dcb826`
- Embedded tree: `afba4cd26719ad6a014cc7a6e4fc71c500389c1f` (703 source files)

Verify SHA256 before inspecting the six-member tar. Read the bundled readiness and gap documents. The exact `install.py` verifies the manifest, inventory, source identities and a fresh destination; it refuses overwrites and does not initialize state or start a service. Installation remains the authorized host operator's responsibility.

## Two explicit verification layers

The public package workflow checks the exact outer archive, inner archive, Git content tree, original installer and full public-core test inventory. The following three cross-repository tests are inventoried separately, not executed or counted as passing by that workflow:

- `integration.test_wallet_lifecycle_wiring.WalletLifecycleWiring.test_cancel_unattempted_after_revoke_and_duplicate_refused`
- `integration.test_wallet_lifecycle_wiring.WalletLifecycleWiring.test_revoke_cas_replay_and_execution_after_revoke`
- `integration.test_wallet_lifecycle_wiring.WalletLifecycleWiring.test_route_fields_session_chain_and_foreign_task`

Those exact tests were independently executed against this exact EX source tree and the paired private Wallet runtime: 3 passed, 0 skipped, 61 loopback HTTP requests, 0 external RPC/signing calls and 0 real transactions. Raw-log SHA256: `7d67940b74cc8b9f3effa83bf6e8fe5ee0ea6ea4e09aec09eda5ed7cacf3a38c`. The private source and raw audit manifest are not published. This is a separately reviewed local verification layer, not a GitHub Actions check. Public CI explicitly reports `NOT_EXECUTED_HERE` for this layer; any other test skip, missing inventory or failure is an error.

Both layers must be reviewed for the exact released bytes before publication. Neither layer establishes production acceptance. Real native contract binding, Oracle authority, authenticated durable runtime/store binding, authentication-service recovery and real browser acceptance remain NOT_RUN. Synthetic memory state and offline installation do not satisfy those requirements. No production credentials, Wallet source, deployment action or financial transaction is included.
