# Mounted workbench component validation

The validation owner can run:

    python3 -B -m unittest integration.test_integrated_workbench_http -v

The ten new methods construct the actual IntegratedWorkbenchServer and send real
HTTP requests to its loopback ephemeral port. Existing GasConfirmationPage and
RegistrationSourceWorkbench implementations handle those requests. Tests cover
quote disclosure, trusted controller bindings, invalid CSRF/origin, quote changes,
edited/duplicate forms, duplicate Content-Length, unknown acknowledgement without
automatic retry, all three source views, receipt/source query isolation, and
confirmation route query rejection.

Wallet confirmation and original journal data are explicitly fixtures. They
prove no installed authenticated session, financial freeze/debit/release/refund,
Oracle record, deployment, real account, signature or chain outcome. Existing
source fixture tests are reused for setup only, not inherited into this suite.
A successful HTTP303 is not principal freeze or a transaction receipt.

At author submission all ten tests are AUTHORED_NOT_RUN. The original validation
owner must retain exact candidate head/tree, command, UTC, exit, test names and
raw log identities. Reuse unaffected exact-version green tests; do not inherit
prior-head results for changed code. Actual session/CSRF and native principal/gas
integration remain separate real acceptance requirements, including responsible
accounts, principal token/base units, ETH gas/wei and UNKNOWN reconciliation.
