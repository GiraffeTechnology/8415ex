# Complete replacement terms and change history

`exchange.remint_terms.prepare_remint_terms` prepares old and replacement
declarations through the existing `MintSpecification.metadata` verifier. This
reuses NFT0 currency/schema, commodity template, controlled document mapping and
privacy validation. A replacement must identify a distinct Sepolia NFT. Its
allowed currencies and editable terms may differ from the old NFT; the old
declaration remains available in the returned detached history.

The installed application's original bill resolver must authenticate the stable
bill identity and return the exact old/new asset, receipt and declaration-digest
binding. This is an original data-source port, not an extra holder approval,
cleanup, refund or settlement gate. A callback returning a matching dictionary
is only sufficient in the synthetic tests; it is not runtime source evidence.

The result retains complete declarations, a deterministic history digest and
explicit added, removed and changed values. NFT identity changes are marked
separately from terms. Output is a preparation result: it does not authorize,
sign, burn, mint, write Oracle state, transfer money or persist an operation.
An installed controller still needs to bind this result to the contract's
atomic remint operation and durable reconciliation, preserve existing financial
and registration history, and read back the actual on-chain result. UNKNOWN
must be reconciled before another execution attempt. Ordinary ERC-721 transfers
do not call this preparation function or gain new holder/finality/gap gates.

Eight Python case definitions cover replacement terms/currencies, optional
attribute changes, detached deterministic history, required verification,
distinct same-chain identity, exact original bill binding, callback mutation
and rejection of numerically equal float substitutions for integer asset IDs.
They are **NOT_RUN** and must run on an approved CTYun/Aliyun Linux target with
the exact complete source manifest. The thirteen Solidity cases remain
**NOT_COMPILED / NOT_RUN**. No existing remote result is inherited by these files.

`remint_execution.invoke_remint` now composes this preparation with the V3
`DurableEXOperationJournal.invoke_once` implementation. It requires the original
operation to bind the precise old asset and history digest. Original enquiry
precedes a durable UNKNOWN claim; only a new claim enters the installed checked
gateway with detached complete history. Existing operations, lost replies and
restart recovery only enquire. EX persists complete history through the explicit
`RemintHistoryStore` before entering the gateway. The original gateway retains
its native operation journal and enforces session, authorization, holder/owner and ETH gas
checks before the atomic call. This code does not supply a deployed gateway,
original bill resolver or independent financial journal. Transport success
remains explicitly insufficient for business acceptance. Fifteen additional
composition case definitions are **NOT_RUN**. Their dependency is the exact V3
durable operation source recorded in its separate manifest.

`observe_remint` uses the original operation binding without re-running old
mint/schema validation or fetching destroyed NFT declarations. It invokes only
`DurableEXOperationJournal.observe`: no new claim, revision advance, dispatch,
refund, quota release or automatic terminal reconciliation. Existing local
claims must match the exact operation identity before the original read. An
absent local claim still permits an authenticated original-source enquiry;
it never permits a send. Actual source authentication remains an installed port.

Complete old/new declarations and differences are stored as canonical JSON in
an explicitly created `ex_remint_histories` table on a caller-owned file-backed
EX connection with FULL/EXTRA synchronization. The native operation ID uniquely
binds the exact scope and history digest; subsequent changed history is refused.
Readback verifies both scope and full history bytes against that digest. The
store can share the dedicated EX operation connection, but creates no table on
import and never overwrites or automatically migrates an existing schema.
An uncertain history commit cannot enter execution; the existing operation
remains UNKNOWN for original-source enquiry. The stored record is preparation
history, not proof the atomic burn/mint happened. No live store has been created
or upgraded by this source-only stage, and no local product tests have run.
Both complete declarations must also match their independently bound original
declaration digests and exact old/new asset/receipt identities. Rehashing an
incomplete or changed history cannot substitute for those original bindings.

The observation entry can also return the detached stored declarations with
explicit FOUND / ABSENT / NOT_CONFIGURED / UNAVAILABLE history status. Missing
or corrupt local history never hides a successful original operation enquiry,
never serves partial terms and never implies failure/success of the native
operation. An original-source enquiry error still propagates; local history
cannot replace it. Authentication/session and actual UI routing remain the
installed application's responsibility; this source does not mount a route.
