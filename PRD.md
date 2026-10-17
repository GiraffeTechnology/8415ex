# 8415ex Product Requirements

Version: 1.3 (complete revision 2026-10-18, Asia/Hong_Kong)
Edition: complete sanitized English product and acceptance contract
Status: OPEN; requirements are not implementation or acceptance evidence.

This sanitized successor represents the current complete product requirements; its prepared source does not imply publication or acceptance. It supersedes conflicting earlier requirement editions and execution checklists. Private operational details are excluded; all product stages, requirement IDs, acceptance cases and decisions remain represented.

## 1. Execution conclusion

Implement the confirmed whole-receipt trading, Oracle registration, segment settlement and suffix rollback model, then Linux integration and Sepolia demonstrations. Commercial pricing, legal advice and real-asset admission remain local later decisions. Six stages are development and acceptance scopes, not a serial CI waiting queue. After a stage PR, continue the next independent authorized stage immediately. CI and exact-head acceptance are verified separately before merge. Existing approved environments and grants remain controlling; this document creates no new infrastructure, credentials or funds authority. A source file, HTTP 200 or CI success alone is not delivery.

## 2. Requirement states and change control

Confirmed requirements are product constraints. Engineering contracts implement them without inventing a standard ABI or expanding product scope. Parked items have not been decided and cannot become defaults or block unrelated work. Execution gates are the actual permission/runtime conditions for a particular external action. EX-* and T-* identifiers are local traceability identifiers, not ERC-8415 interface or event names. Every change identifies its source, requirement, affected cases/stages and authorization consequences. Later business discussion does not reopen independently accepted unchanged work.

## 3. Product goals and boundaries

Provide an ordered chain of whole-receipt trades while off-chain registration may lag. Protect conditional funds and agreed return control until registration; independently finalize eligible prefix segments and unwind only the eligible unregistered suffix. Agent execution is bounded by the human wallet grant, without platform wallet-key custody. Demonstrate properties with reproducible Linux and actual authorized test-chain evidence.

| ID | Requirement |
| --- | --- |
| EX-SCOPE-01 | Infrastructure, without operating a centralized exchange business. |
| EX-SCOPE-02 | One NFT equals one whole warehouse receipt; no fractions. |
| EX-SCOPE-03 | Allow continuous A to B to C to D trading while registration catches up. Ordinary transfers cannot require holder equal to owner, a closed projection gap or current finality; the holder-equals-owner remint predicate is separate. |
| EX-SCOPE-04 | Support 8415Wallet V3 or any wallet satisfying the same authorization and control semantics; no exclusive wallet binding. |
| EX-SCOPE-05 | Every Agent operation comes from verifiable bounded human wallet authority. |
| EX-SCOPE-06 | The buyer pays its transaction gas and assigned rollback gas in ETH only. Warn and refuse a new trade when ETH is absent or insufficient. Agent service fees remain a separate later decision. |
| EX-SCOPE-07 | No arbitrary compulsory custody or instant liquidation; normal conditional funds escrow and agreed asset-return control remain. |
| EX-SCOPE-08 | Transfer the mapped bill of lading only; physical collection belongs to the parties named in its terms. |
| EX-SCOPE-09 | The off-chain change voucher is itself the registration receipt; Oracle alone ingests, verifies and records it on chain. |
| EX-SCOPE-10 | Align ArtFi whole artwork and EX backend; direct, electronic and intermediary registration are transaction sources with middleware and frontend paths. |

Non-goals: operating a CEX, customer-funds general ledger or platform custody account, market-making/guaranteed returns, leverage/liquidation, receipt fragmentation, cross-chain or new real-asset commercial admission. Reuse and alignment of existing whole-artwork, wallet, Oracle, journal and settlement components remain required. Charity shares are excluded. Collection terms remain in the bill; EX does not perform collection, transport, warehouse exit or collection-driven burn. No license, institutional cooperation, legal effect, fee rate or revenue distribution is presumed.

| ID | Requirement |
| --- | --- |
| EX-SCOPE-11 | NFT0 fixes one or more allowed price currencies at mint. Each order explicitly selects one member; insufficient selected-currency funds warn and refuse. EX does not exchange, auto-select, combine currency balances or substitute assets for principal or ETH gas. Holder remint creates a new NFT and never edits the old allowed set. |
| EX-SCOPE-12 | A holder possessing the original NFT may atomically burn it and mint a replacement under the remint conditions. New terms may be added, removed or changed before the new mint; retain bidirectional identity and complete history. |

## 4. Baseline and factual limits

Resolve current full source commit/tree and actual repository content before work or acceptance. Historical dependency-free bootstrap tests and old PR/CI records are source-bound history, not current product capability. Historical cancelled license publication or explicitly refused operations remain cancelled. Stage 0 must independently resolve current main, branch ancestry and exact diff. T-35 through T-38 require actual current-round deployment and chain evidence; this edition supplies requirements, never a passing certificate. Document publication is separate from a deployment, merge, schedule or private-server synchronization.

## 5. Participants and trust boundaries

Humans choose assets and sign allowed intent terms; Agent cannot fill in an unsigned intent. Wallets control assets, validate authority and execute permitted operations without disclosing private keys. Agent discovers/matches executable orders, submits permitted actions and follows outcomes without changing bounds or fabricating registration.

EX validates conditions, records the chain, coordinates frozen-principal release/rollback and derives business projections from Oracle chain authority. EX does not ingest raw off-chain vouchers, invent another business receipt or treat its database as authoritative. Registrars form the mint-declared voucher; Oracle adapters alone ingest/verify/bind it and write the authoritative chain record. Holder follows that record, never an independent asynchronous write. Contracts enforce agreed escrow/control without arbitrary confiscation or finalized-prefix rewrite. Operators investigate and retry through the same permissions, never by manually marking success.

Development continues across stage PRs. Existing review, QA, integration and merge owners retain their exact responsibilities; this product edition does not delegate permissions between projects. Run receipts are engineering evidence and not new registration receipts.

## 6. Domain model and complete mint contract

Owner is the current on-chain trade position; holder is the last contiguous position confirmed by Oracle registration. Initial owner0=holder0. Owner D with holder A/B is normal; compare positions in the same ordered chain, not numeric address values. Holder and its registration receipt represent one authoritative fact, whereas chain observation, indexing and funds execution can have recoverable technical states.

A finalized prefix contains contiguous registered/settled segments. Principal was frozen before trade; registration releases that existing position without a second buyer payment. A registered segment undergoing technical release recovery is not a refundable unregistered suffix. Rollback changes owner to current effective holder, never revokes holder, resets issuer or changes settled prefix. The recovered equality is a new-chain starting point, not a prerequisite for all normal resale.

Logical records must preserve or trace:

| Record | Required correlations |
| --- | --- |
| Receipt | Unique receipt, chain/NFT identity, full goods/bill terms and nonsecret mappings, owner/holder, validity, mint-spec version, both cutoffs and format |
| Transfer | Unique transfer/receipt, sequence/predecessor, seller/buyer, terms, authority, registration, settlement and rollback states |
| TradeIntent | Signer, whole asset, direction, price/quote asset, quantity one, nonce, expiry and permission boundaries |
| EscrowPosition | Original buyer/seller, transfer, wallet freeze reference, exact asset/amount, release/refund state and unique action |
| RegistrationRequest | Transfer, declared source/adapter, native request, predecessor, submission/deadline and technical attempt count |
| RegistrationEvidence | Same Oracle voucher/format/digest, asset/transfer/journal, old/new holder, order/time, chain/tx/block/log identity |
| GasEstimate | Quote/version, action/scope, estimated gas/rate, cap/P50 ETH/USD, same-time FX provenance, sample algorithm/population/count/window/blocks, validity, grant and buyer confirmation |
| GasPrepayment | Confirmed quote/scope, native freeze reference, cap/frozen ETH, real consumption, unused amount, debit/unfreeze and transaction/action identities |
| AuthorizationReference | Wallet, capability object, original signed grant reference, validity, revocation and permitted actions |
| ExecutionEvidence | Exact source/config/run/network, actual addresses/tx or failure, timestamps and artifact/log digests |

Use integer/fixed-point smallest units and check amount, asset and chain together. Registration, funds and execution statuses remain separate: authorized, submitted, observed/confirmed, pending/refused/registered, release, rollback in progress/complete and investigation are not collapsed into success.

| ID | Requirement |
| --- | --- |
| EX-MINT-01 | Record full receipt, underlying commodity name, applicable specification/grade, quantity/unit, receipt/bill number, issuer, registrar/source, location, supporting records and bill terms; trade exactly one NFT. |
| EX-MINT-02 | Record asset-appropriate specification/template/version, required fields and nonsecret original-document mapping; no invented legal effect or institutional endorsement. |
| EX-MINT-03 | Receipt-access secrets remain encrypted in controlled off-chain storage; NFT holds opaque nonsecret mappings. Never hold user wallet private keys. |
| EX-MINT-04 | Declare trade and registration deadlines at mint, including unit, timezone, precision and comparison/serialization semantics; no silent later change. |
| EX-MINT-05 | Declare voucher format, required fields and source path at mint; Oracle verifies it as the one business receipt. |
| EX-MINT-06 | Retain collection terms for inspection without EX physical collection, transport or warehouse-exit work. Authorized holder remint is separate from retired collection-driven burn. |

Use the corresponding commodity/receipt specification; non-CME assets need an explicit equivalent template without implied CME recognition. Complete data does not permit publishing secrets; opaque mappings do not permit omitting required receipt data. Validate existing encryption, controlled-store and schema interfaces before integration, without inventing credentials.

### 6.4 Holder replacement mint

| ID | Requirement |
| --- | --- |
| EX-MINT-07 | At mint NFT0 records one or more allowed price currencies with verifiable asset, network and smallest-unit mappings. No caller or administrator can edit the existing NFT currency set after mint. A valid remint may set new terms, which become immutable on the new NFT. |
| EX-REMINT-01 | A holder possessing the original NFT with holder equal to owner may remint under the existing wallet/contract authorization. This predicate represents no unfinished trades under the confirmed mechanism; add no clearing, refund, unfreeze, migration or extra approval prerequisite. |
| EX-REMINT-02 | Burning the old NFT and validly minting the replacement are one atomic consistency operation. No outcome may destroy the sole valid asset or leave both tokens valid for the same bill of lading. |
| EX-REMINT-03 | Before replacement mint the holder may add, remove or change the new terms, including allowed currencies. Preserve old terms and explicit differences; freeze the new NFT currency set after mint. |
| EX-REMINT-04 | Make old/new NFT links readable in both directions. A burned predecessor cannot trade or remint again. Preserve original registration, trade and funds evidence without rewriting or deletion. |
| EX-REMINT-05 | Immediately before execution atomically recheck possession and holder equal to owner against original authority. Serialize competing trade/registration/remint; duplicate, failed or UNKNOWN outcomes reconcile the same operation before further decisions, never repeating burn, mint or debit blindly. |

## 7. Continuous trading, registration and cutoff

A starts as owner/holder. Independent A/B orders match by price/FIFO/best executable price with valid signed terms, receipt/deadline checks and buyer-confirmed gas disclosure. B's principal and maximum gas amount are independently frozen before transfer/registration admission. Owner advances to B; B may resell to C, then C to D under the same conditions without waiting for holder. Each hop retains its own transfer, grant, freeze and registration task.

Oracle verifies the mint-format voucher and writes the one chain record; holder advances A/B/C/D contiguously. EX rebuilds missing/reordered index observations from authority instead of local arrival order. Release a segment when both ordered owner and holder have reached its buyer or beyond and registration is timely. Owner D/holder B makes AB eligible, not BC/CD. No second buyer payment.

| ID | Requirement |
| --- | --- |
| EX-INV-01 | Only one valid ordered transfer head per receipt. |
| EX-INV-02 | Reject partial quantities and duplicate valid asset mappings. |
| EX-INV-03 | Finalized registration/settlement prefix moves forward only and survives suffix failure. |
| EX-INV-04 | Release and refund exclude each other; exactly-once funds actions. |
| EX-INV-05 | Only authorized Oracle chain records bound to correct asset, transfer, sequence, chain, registrar and journal advance business state. |
| EX-INV-06 | Reject missing, expired, revoked or replayed authority. |
| EX-INV-07 | Rollback affects only eligible unfinalized suffix and resumes after interruption. |
| EX-INV-08 | The recorded owner may resell before holder catches up. Neither holder-owner equality, gap closure nor current finality is a prerequisite to an ordinary continuous transfer. Remint uses its separate possession and holder-equals-owner predicate. |
| EX-INV-09 | Missing local registration observation is not rejection or immediate liquidation authority. |
| EX-INV-10 | Record business finality separately from chain observation; reorg or duplicate events never create a second funds action. |
| EX-INV-11 | Holder changes with the same Oracle registration record, never as a separate asynchronous business fact or second receipt. |
| EX-INV-12 | Matching respects price priority, equal-price FIFO and best executable price; eligibility cannot grant queue priority. |
| EX-SETTLE-01 | Before a trade, fully freeze its own buyer principal in the one explicitly selected NFT0-allowed currency and the buyer-confirmed maximum ETH gas separately. No conversion, currency substitution or duplicate use of funds. Original effective freezes are reconciled, never debited again after registration. |
| EX-SETTLE-02 | Release each eligible segment by ordered owner/holder positions and remove its rollback control without waiting for the entire chain. |
| EX-SETTLE-03 | Keep seller, buyer, price, asset, registration sequence, principal, fees and rollback per segment; no later-funds subsidy. |
| EX-SETTLE-04 | Bind release to genuine authorized Oracle chain source, asset, transfer and journal; historical registration and current holder observations remain distinguishable. |
| EX-SETTLE-05 | Release already frozen principal; no second buyer payment or business-payment failure branch. Technical recovery cannot duplicate debit, release or gas. |
| EX-TIME-01 | Record both deadlines at mint; stop new trading at the declared cutoff. |
| EX-TIME-02 | Registration beyond trading cutoff fails the unregistered suffix and returns owner to effective holder; registration must also satisfy its own mint deadline. |
| EX-TIME-03 | Use mint rules and authoritative Oracle ordering for deadline decisions; protect registered/settled prefix; no late-voucher grace or second-receipt wait. |
| EX-EXIT-01 | EX completion is bill-of-lading transfer with full terms and Oracle-confirmed holder, without physical collection. |
| EX-EXIT-02 | Off-chain parties handle collection, transport and warehouse exit; these are not EX completion/acceptance conditions. |
| EX-EXIT-03 | Do not introduce physical-collection-driven burn. Authorized holder remint atomically burns the old NFT; retain old/new receipt, registration, trade and funds history and prevent duplicate valid asset mappings. |

Before mint cutoffs, show genuine pending status; absent local notification is neither success nor refusal. Deadline, registration and rollback races need atomic preconditions against one ordered authority. Technical log replay does not create a holder-first/receipt-later business state. Same identity/same content is idempotent; same identity/different content conflicts. Old messages cannot revive failed segments. Registered holder stays effective during technical recovery. After recovery an otherwise valid, unexpired and authorized NFT may begin a new chain; expiry cannot be bypassed by recovery. Actual off-chain collection rights are unaffected by test cutoff, and no forced disposal follows expiry.

One or more allowed price currencies are declared immutably by NFT0 at mint; each order explicitly selects one member and carries that selection through the signed order, each principal freeze, release and refund. EX never selects a fallback currency, performs exchange, automatically buys ETH or converts principal to cover gas. Principal balance is checked in its own asset and smallest unit; gas is checked independently in ETH wei. If the designated price currency is ETH, the two liabilities remain separately reserved so one balance is not counted twice. Native execution rechecks original funds/reservations/nonce/UNKNOWN atomically. Missing or insufficient funds on either side warns and refuses; no balance or denomination is inferred from a label.

| ID | Requirement |
| --- | --- |
| EX-SETTLE-06 | Quote, freeze, release and refund each leg in the one currency explicitly selected from its immutable NFT0 allowed set. Keep principal and ETH gas accounts separate; no conversion, substitution or summed multi-currency payment. ETH-priced principal and gas cannot consume the same funds twice. |
| EX-SETTLE-07 | If available selected-currency funds cannot fully freeze the price, warn and stop before signing, execution and broadcast. Adequate ETH gas or other allowed currencies cannot replace this order principal. |
| EX-INV-13 | One or more allowed currencies are immutable per minted NFT and each order binds one through its whole principal lifecycle. Principal or ETH gas shortage forms no new trade. No currency conversion, aggregate currency payment or third-party subsidy bypass; old and replacement identities remain distinct. |
| EX-INV-14 | Remint never leaves both old and new valid or loses the valid asset through a one-sided burn. Existing history, funds and registration obligations survive the replacement. |

## 8. Conditional funds, suffix rollback and gas

AB, BC and CD have separate prices and original-buyer funds; do not assume equal prices. If owner D/holder A and B refuses, unwind unregistered AB/BC/CD, refund B/C/D their own unreleased principal and return owner to A. If AB is registered and settled and C refuses, keep AB and holder B, unwind BC/CD only and return owner to B. Never return to issuer A or require A to participate again. When holder successively reaches B, C and D, independently release AB, BC and CD.

| ID | Requirement |
| --- | --- |
| EX-ROLLBACK-01 | B refusal while holder remains A withdraws all unregistered segments and returns owner to A without changing holder. |
| EX-ROLLBACK-02 | After AB registration, C refusal withdraws only unregistered suffix and returns owner to B; preserve holder and settled prefix. |
| EX-ROLLBACK-03 | Refund each segment to its original buyer in its original selected NFT0-allowed price currency. Display original principal, actual ETH gas and net receipts separately by currency; never subtract ETH wei from non-ETH principal through a display exchange rate. |
| EX-ROLLBACK-04 | Rollback does not require the NFT to visit intermediate ordinary wallets or their current unfrozen ETH. Sufficient original ETH prepayment for the approved obligation remains usable, without a second prepayment, premature unfreeze or cancellation of rollback. |
| EX-ROLLBACK-05 | Rollback does not burn the NFT; valid unexpired authorized assets may start a new chain from recovered owner equal to effective holder. |
| EX-GAS-01 | Each leg buyer pays the actual gas assigned to its trade, refund and NFT return in ETH, without shifting liability merely because another party refused registration. |
| EX-GAS-02 | Do not charge one shared actual operation in full to multiple segments; allocation method remains D-04. |
| EX-GAS-03 | ETH is the sole gas settlement asset. Warn and refuse a new trade if ETH is absent or insufficient after reservations. Validate and account for NFT0 price-currency funds separately; neither balance substitutes for the other. No gas-shortage temporary custody, redemption deadline, forced sale or instant liquidation. |
| EX-GAS-04 | Before trading disclose both the maximum gas amount and median estimate in ETH and contemporaneous ETH/USD display values for buyer confirmation. USD is display only. An estimate disclaimer does not replace numeric amounts. |
| EX-GAS-05 | Confirmed cap constrains the approved action scope together with the wallet grant; stop and obtain a new confirmation before exceeding it; no invented percentage or unlimited authority. |
| EX-GAS-06 | Use real applicable verifiable median samples with algorithm, population, count, window, observation time, network, action and source; no fabricated sample, fake zero or single prediction as P50. |
| EX-GAS-07 | Freeze the buyer-confirmed maximum in ETH separately from selected-currency principal before sending. Count available ETH and disjoint effective original approved prepayment only; never reuse other reservations or principal. Insufficient or incomplete freezing prevents send. |
| EX-GAS-08 | Debit verifiable actual ETH gas and unfreeze only unused ETH prepayment. Failed transactions still pay consumed gas. Duplicate events and retries cannot charge or unfreeze twice. |

Every freeze, registration task, release, refund/unfreeze and asset-return action has stable native identity. Unknown result requires actual lookup before retry; restart cannot turn unknown into failed or a new buyer debit. A rollback report includes trigger, suffix, effective holder, protected prefix, each funds/owner result, remaining technical steps and safe retry conditions. Never claim complete before all required evidence.

Before confirmation disclose two total-fee amounts: approved cap and real sample median/P50, each ETH and same-quote-time USD. Label units, actions, conditional refund/return coverage, aggregate/per-action scope, validity, FX source/time and estimation time. Median is informative, not a guarantee or authorization. Fee-rate samples need an explicit gas-to-total-fee derivation; no unrelated chain/action/window, single-point forecast, cap average, fake sample or missing-as-zero.

Record algorithm, population, sample count, window start/end, collection time, chain/action and reproducible raw sample references/digests. Confirmation binds quote ID/version, action, scope, cap, displayed USD, validity and original grant. Recheck current fee parameters and guarantee the approved scope remains within cap before sending. A broad wallet grant never raises a lower buyer cap. In-scope automation does not need an extra platform approval step.

After confirmation freeze maximum gas ETH separately from principal; insufficient/failed/unknown freeze means no send. If cap is exceeded or cannot be guaranteed, stop the affected step, disclose a fresh quote and obtain new confirmation and sufficient approved top-up. Splits, retries and replacement quotes cannot erase incurred costs, pending exposure or reset aggregate cap. Actual evidenced gas debits remain charged on failed transactions. Unfreeze only unused balance no longer needed; unknown outcome retains possible exposure. Distinct retries can incur new evidenced gas within the same cap; one actual cost is never charged twice. USD is disclosure, not authority to exchange principal for gas. Only genuine shared-operation allocation remains D-04; normal freeze/debit/unfreeze is fixed.

| ID | Requirement |
| --- | --- |
| EX-GAS-09 | ETH is the sole gas settlement asset. USD is disclosure only; PYUSD, WETH or other assets cannot pay gas. No automatic exchange, non-ETH-principal gas deduction or platform/third-party subsidy bypass. |
| EX-GAS-10 | Zero ETH warns and refuses new trading before signing, execution and broadcast. Available ETH below the confirmed maximum freeze also refuses. UI, API, Agent and retry paths cannot bypass this check. |

## 9. Wallet, Agent and matching

| ID | Requirement |
| --- | --- |
| EX-AUTH-01 | Trace each Agent action to valid human wallet authority. |
| EX-AUTH-02 | Check asset, action, eligibility constraints, principal/fee bounds, expiry, nonce and chain domain without modifying signed terms or using counterparty restrictions as priority. |
| EX-AUTH-03 | Support the actual semantic wallet contract; at least one genuine integrated path plus the same conformance checks for alternatives. |
| EX-AUTH-04 | Revocation or expiry rejects new restricted actions with deterministic concurrent behavior. |
| EX-AUTH-05 | Wallet manages Agent authorization; no extra platform approval layer or repeated manual step for an already permitted action. |
| EX-MATCH-01 | Both orders must select the same member of the NFT0 mint-time allowed set. Price priority, FIFO and best executable price operate within one currency book only. No named-counterparty priority jump, FX conversion or numeric price ranking across currencies. |
| EX-MATCH-02 | Reference only CME spot matching and relevant receipt specifications; no futures margin, CCP, leverage liquidation, platform dealing or unapproved commercial fees. |
| EX-MATCH-03 | Matching is not registration or settlement completion. |

Validate whole asset, side, grant, limit/quote asset, one-unit quantity, nonce, expiry and current head before matching. Higher executable bids and lower executable asks have priority; equal prices use trusted server admission order with replayable evidence, never client timestamps. Execute at the best allowed price inside both signed limits. Eligibility constraints can exclude an order but cannot promote a counterparty. Reject noncrossing limits, partial fills, changed intent and head races; retain input order, trusted sequence, exclusion reason and fill price.

CME spot and FIFO references inform only confirmed matching and asset-specific documentation; they do not import futures margin, clearing/CCP, hours, commodity quantities or commercial terms. Authority revocation does not invent control rights or erase previously agreed settlement/recovery duties; verify that interaction. Agent service-fee mechanism/rates/timing/refunds remain parked; an optional extension point is not permission to charge.

## 10. Logical operations and events

Logical names are required capabilities, not asserted standard ABIs. Map them to actual existing interfaces and validate permissions, identities and state.

| Operation | Inputs and required result |
| --- | --- |
| getReceipt | Receipt identity; complete bill, owner/holder, head/prefix, validity/cutoffs and traceable history |
| validateIntent | Signed terms, wallet grant, whole asset, price/chain/nonce/validity; executable or precise reason |
| matchIntents | Executable orders, comparable terms and trusted admission sequence; price/FIFO/best-price result with reasons |
| executeTransfer | Match, predecessor/head and funds/control preconditions; unique transfer, actual result and native registration task |
| submitRegistration | Transfer, predecessor and mint-declared source/original Oracle task; idempotent task and deadline, no raw voucher |
| applyRegistrationResult | Authorized Oracle chain record with asset/transfer/journal/order; holder and eligibility from that same record |
| settleEligibleSegments | Ordered registration/owner/holder conditions and original freeze; independent releases, no second payment |
| evaluateDeadline | Trusted time/block and mint source rules; stopped trading, allowed recovery and reasons |
| rollbackSuffix | Valid trigger, eligible boundary and state; incremental recovery and safe retry |
| getTransferEligibility | Validity, owner/holder, cutoffs, grants and recovery; precise continued-transfer eligibility |
| estimateTransactionGas | Action/chain/current fees, samples, FX and grant; quote/version, cap/P50 ETH/USD and confirmation evidence or unavailability |
| freezeGasPrepayment | Confirmation/scope, native wallet grant/balance and idempotency key; actual separate freeze reference and amount |
| settleGasPrepayment | Original freeze, approved scope and each evidenced actual cost; exactly-once debit and unused unfreeze |
| getReceiptTimeline | Receipt identity; ordered trade, registration, funds, rollback and chain observations |

All mutations require idempotency and atomic/equivalent preconditions; never accept client-declared final state. Reads move no asset or funds. Audit intent accept/refuse, transfer submitted/observed, registration request/result, prefix advance, freeze/release/refund, rollback start/progress/complete, restored eligibility and reorg/recovery. Bind asset/transfer/request/run and actual chain/tx/block/log when applicable. Replay reconstructs the same state without repeated movement. Attempts and observations are not completed business actions.

## 11. Minimum UI and operator console

An operable UI is required; CLI supplements development/diagnostics and cannot replace interface acceptance.

| View | Required content and interaction |
| --- | --- |
| Receipt | Complete goods/bill and terms, owner/holder, head, Oracle prefix, both deadlines and eligibility |
| Wallet/authorization/trade | Actual wallet/grant, whole asset, price/order priority, network and signed terms; cap/P50 ETH/USD, samples/source/time, confirmation/reconfirmation, separate principal/gas freeze and actual debit/unfreeze |
| Timeline | Every A/B/C/D hop with registration/funds state and cutoff; submitted is not delivered |
| Rollback | Protected prefix, eligible suffix, refunds/releases, owner restoration, remaining steps and failures |
| Queue | Oracle chain pending/refused, deadline failures, index replay, technical retry, unknown outcome and alerts; no EX raw-voucher upload or manual success |
| Demonstration/evidence | Scenario/run/exact source/network, actual hashes and assertions; no relabelled old or simulated evidence |
| Source entries | Direct/electronic/intermediary operable paths, source description, mint voucher format, task/Oracle record; shared trade/fees/funds/history |

Do not hide partial states, infer unlimited approval from connection, fabricate zero fees, silently raise cap, refund consumed gas, request a second payment or imply physical fulfillment. Retry/recovery uses identical authority/state checks; no privileged funds bypass.

## 12. Non-functional and security requirements

| ID | Requirement |
| --- | --- |
| EX-NFR-01 | Run all product, unit, integration, API, browser, EVM, syntax, type, build and package tests only on existing approved remote non-Windows Linux with verified ctyun or aliyun provider binding. No local/Windows/WSL/container or unknown hosted-runner fallback. Read the rule on reconnect and bind source, command, environment and evidence; retaining a script alone is not enforcement. |
| EX-NFR-02 | Prevent funds/asset reentry and replay with authority and state preconditions. |
| EX-NFR-03 | Safely recover reorg, duplicate logs, RPC timeout and unknown results. |
| EX-NFR-04 | Restart and duplicate queue consumption preserve correlations and never duplicate settlement. |
| EX-NFR-05 | Associate errors with asset, transfer, request and run; publish sanitized error codes. |
| EX-NFR-06 | Keep secrets out of code, public artifacts, logs, chain and metadata; encrypted receipt-access storage is separate from wallet-key custody. |
| EX-NFR-07 | Explicit network, chain, contracts, units, confirmation and timeout parameters enter configuration digest. |
| EX-NFR-08 | Measure load, duration, backlog and failure rate; do not invent throughput/latency SLAs. |
| EX-NFR-09 | Public repository text is English and sanitized; private links, operational topology and secrets stay private. |
| EX-NFR-10 | Upgrade, pause and recovery cannot bypass ownership or finalized-prefix boundaries. |

Choose reproducible confirmation/reorg windows, retry intervals and resource limits from the existing approved environment and record them as test configuration, not production SLA. Permission/security changes require their existing approval. Keep raw operational records private while public artifacts contain sanitized traceable results.

## 13. Reuse, dependencies and whole-artwork alignment

Inspect actual existing whole-artwork receipt, signed order, wallet, task journal, Oracle schema/projection and settlement coordinator contracts before adding an adapter. Reuse equivalent functionality; do not build a second Oracle, settlement architecture or general custody ledger. Whole-artwork intermediary and registrar names are business roles, not proof of any deployed API or institutional cooperation.

Only authoritative permitted Oracle chain evidence bound to asset/segment/journal can drive release. A signature, VALID string, public JSON, bare settlement ID or off-chain file alone is insufficient. Historical registered C and current D can coexist without denying C eligibility or separating holder from receipt. Keep funds frozen before trade and release only that original position.

| ID | Requirement |
| --- | --- |
| EX-ARCH-01 | Align whole-artwork backend receipt, wallet, Oracle, journal, freeze/release, rollback and audit semantics with actual contracts/schema/events/errors and evidence. Reuse first; no implied new deployment instance or migration permission. |
| EX-ARCH-02 | Route REG-DIRECT, REG-ELECTRONIC and REG-INTERMEDIARY sources to the same trade/settlement backend; Oracle remains sole raw-voucher authority. |
| EX-ARCH-03 | Implement usable frontend flows for all three source paths with source explanation, declared mint voucher format, task state and original Oracle records. Share immutable allowed-currency selection, matching, wallet authorization, ETH maximum/median disclosure and confirmation, shortage warnings/refusal, owner/holder, funds and history. No conversion or multi-currency sum. Placeholder buttons do not satisfy this requirement. |
| EX-ARCH-04 | Alignment covers whole artwork/receipt only, excluding charity fractions, shares and invented market modes. |

Missing CI route affects that candidate's CI/merge, not independent models. Missing wallet support, Oracle authority, asset-return control, gas interface, verified test-token address or target affects the respective real path only. Continue contracts, fixtures, implementation and packages independent of it. First search existing source/config/evidence; escalate only a precise genuine product/permission decision. No visual redesign prerequisite; optional staking hooks do not authorize undecided staking rules.

## 14. Three simulated registration sources

REG-DIRECT simulates a direct registrar producing the mint-format voucher. REG-ELECTRONIC simulates a registrar accepting electronic data. REG-INTERMEDIARY simulates an intermediary arranging registration. Geographical/institutional examples in source material are illustrative only; public demos must label simulation and cannot imply cooperation, API access or permission.

Oracle alone ingests/verifies each voucher and records it. Each source routes into the same backend order, authorization, owner/holder, cutoff, segment-funds and rollback contracts. Verify format, authority, sequential receipt/holder and cutoff per source. Do not copy three Oracles or settlement state machines. At least one contract/UI check per source, with each demo's main source stated separately; one source passing does not prove the other two.

## 15. Six core demonstrations

### DEMO-01: Single bill-of-lading transfer

Main source fixture: REG-DIRECT (source coverage must be independently verified).

A to B; Oracle writes the verified registration voucher and holder reaches B. Release original frozen AB funds; owner=holder=B; readable bill and registration history; no physical collection or collection-driven burn.

Cases: T-02, T-11, T-25, T-32, T-33.

### DEMO-02: Continuous trading and prefix release

Main source fixture: REG-ELECTRONIC (source coverage must be independently verified).

A to B to C to D, holder advances contiguously. Release AB first without waiting for D; then independently BC and CD.

Cases: T-03, T-04, T-12, T-13.

### DEMO-03: B refusal

Main source fixture: REG-INTERMEDIARY (source coverage must be independently verified).

Owner D, holder A; B registration refused. Unwind only unregistered AB/BC/CD, owner returns to A, original buyers refunded, actual fees separate and charged once.

Cases: T-17, T-19, T-21, T-44.

### DEMO-04: C refusal protects AB

Main source fixture: REG-DIRECT (source coverage must be independently verified).

AB registered and settled; owner D, holder B; C refused. Unwind BC/CD, owner returns to B; preserve AB registration and released principal; no issuer reset.

Cases: T-18, T-19, T-29, T-44.

### DEMO-05: Intermediate ordinary-wallet ETH shortage

Main source fixture: REG-ELECTRONIC (source coverage must be independently verified).

Intermediate ordinary wallets lack ETH and recovery is needed. Prearranged authorized return remains possible; each buyer bears applicable gas; no temporary custody or forced sale.

Cases: T-20, T-21, T-22, T-23.

### DEMO-06: Cutoff failure and recovery boundary

Main source fixture: REG-INTERMEDIARY (source coverage must be independently verified).

At trade cutoff attempt a new transfer with unregistered segments outstanding. Reject new trade; overdue unregistered suffix fails and owner returns to effective holder; keep registered/settled prefix; no expired reopening or collection-driven burn.

Cases: T-24, T-25, T-32, T-33, T-44.

| ID | Requirement |
| --- | --- |
| EX-DEMO-01 | Use the original approved Ethereum Sepolia chain11155111 test path. The designated Sepolia PYUSD fixture must be a member of fixture NFT0 mint-time currencies and explicitly selected by scenario orders; gas is test ETH. Do not borrow the separate Wallet Hoodi configuration or make PYUSD a universal product currency. |
| EX-DEMO-02 | Deliver all six revised scenarios with actual steps, state assertions and execution evidence. |
| EX-DEMO-03 | Deliver an operable trading demo, editable PPT proposal and playable film, clearly labelling real test-chain activity, simulated registrars and animation. |

Each scenario records whole receipt/account setup, mint fields/format, order sequence/prices, cap/P50 ETH/USD statistical evidence and buyer confirmation, separate cap-gas/principal freezes, actual gas/unfreeze, steps, Oracle chain records, owner/holder/prefix, every segment's funds, events/tx, UI assertions and actual failures. Include positive unexpired resumed trading and negative expired reopening. Test prices are reproducible fixtures, not commercial quotes. Read designated PYUSD from existing approved configuration; do not guess or substitute its address, claim issuer approval or imply redeemability.

## 16. Stages 0 through 5

### Stage 0: Baseline and evidence alignment

Entry: Read current instructions, source, CI handoff and approved Linux execution references; separate bootstrap, fixtures, application and deployment.

- Resolve full branch/commit/tree and actual diff; do not recover cancelled actions from history.
- Inventory existing wallet, orders, Oracle, journal, settlement and UI reuse interfaces and precise missing bindings.
- Map ArtFi whole-artwork contracts, the three source middleware routes and their actual frontend entrypoints.
- Trace requirement to test to exact source to run to artifact; preserve private operational records separately.

Deliverables: Baseline identity, interface map, requirement/test map and current PRD pin.

Acceptance: Independent source/evidence identity; no assertion that CI means product acceptance.

Develop next independent stage after this stage PR without waiting for CI. An exit condition defines acceptance, not a global development stop.

### Stage 1: Domain state and basic interaction

Entry: Use verified source and approved Linux path; label fixtures wherever a real integration is absent.

- Implement complete mint declaration, whole NFT, encrypted off-chain mapping, both deadlines and voucher format; ordered owner/holder positions.
- Independent bids/asks; price/FIFO/best-price matching and replayable trusted book sequence.
- Disclose cap/P50 ETH/USD with statistical evidence; buyer confirmation; separate principal and maximum gas freezes before send.
- Read actual wallet grant and show switch/disconnect/revocation/session loss without extra Agent approval.
- Three Oracle sources share a contract; holder follows the same authoritative record; ordered index rebuild and duplicate handling.
- Operable basic UI and whole-artwork backend alignment; separate actual, simulated and disconnected states.

Deliverables: Domain model, samples, adapter contracts, operable UI and Linux unit/state evidence.

Acceptance: All applicable Stage 1 cases including T-41..43,45..51; real freeze is never inferred from model.

Develop next independent stage after this stage PR without waiting for CI. An exit condition defines acceptance, not a global development stop.

### Stage 2: Segment principal and independent settlement

Entry: Reproducible chain and registration sequence; real paths additionally require actual authority.

- Freeze each buyer's own segment principal and confirmed maximum gas separately in wallet; bind parties, asset, amount and Oracle reference.
- Never use unreleased later funds to support earlier settlement or resale.
- Release original frozen funds once owner/holder positions and timely Oracle registration make the segment eligible; eliminate its return control.
- Demonstrate AB release while BC/CD remain pending; bind original Oracle/journal/settlement coordinator.
- Recover unknown release, RPC failure, repeat events and restart by lookup before retry; no new buyer payment or business-payment failure.

Deliverables: Segment escrow/settlement implementation, real/simulated binding list, reconciliation and Linux unit/integration evidence.

Acceptance: T-11..16,28,31 and applicable T-51; per-segment reconciliation; historical C/current D interpreted correctly.

Develop next independent stage after this stage PR without waiting for CI. An exit condition defines acceptance, not a global development stop.

### Stage 3: Suffix rollback and buyer gas

Entry: Segment model is verified; genuine rollback needs existing authorized control and test gas path.

- B refusal with holder A unwinds all unregistered suffix; after registered AB, C refusal unwinds BC/CD only and returns owner to holder B.
- Keep registered segments even while technical release is recovering; never revoke holder or reset issuer.
- Refund original buyers; actual gas and net amounts use separate explicit assets and units.
- Return NFT without intermediate-wallet traversal or reliance on ordinary wallet ETH; no duplicate full shared-operation charging.
- Recover interruption, retries, obsolete/duplicate events, insufficient budget and unknown results; do not invent late-receipt waits.
- Re-trade valid unexpired assets from recovered owner=holder; ordinary resale still permits owner ahead of holder.
- Integrate gas statistical disclosure, confirmation/cap, maximum prefreeze, actual debit, unused unfreeze and reconfirmed top-up; D-04 allocation only remains pending.
- No gas-shortage custody, redemption deadline, forced sale or liquidation.

Deliverables: Rollback, fee/reconciliation records, recovery flow and Linux fault-injection evidence.

Acceptance: Applicable T-17..23,29,30,43,44,49..51; model evidence and real control/fee evidence remain distinct.

Develop next independent stage after this stage PR without waiting for CI. An exit condition defines acceptance, not a global development stop.

### Stage 4: Deadline, bill transfer and restored trading

Entry: Reproducible trading, Oracle and rollback; verifiable mint cutoffs/formats. No collection or burn gate.

- Reject new trades at cutoff and verify mint units, timezone, precision and serialized boundary semantics.
- Overdue unregistered suffix fails; return only owner to current holder; preserve registration, issuer and settled prefix.
- Resolve registration/deadline races against one authoritative ordered state; no holder-first/receipt-later, second receipt or grace stage.
- Valid unexpired unburned NFT may begin a new chain when authorized; expiry cannot be bypassed by recovery.
- Allow ordinary owner-ahead-of-holder continuous resale.
- Show full bill terms, off-chain collection obligations and Oracle/transfer history without implementing physical fulfillment or collection-driven destruction.
- Reject duplicate mapping and transfer replay; preserve history and idempotent technical recovery.

Deliverables: Deadline and suffix recovery model, bill-transfer/scope UI, boundary fixtures and resumed-trading evidence.

Acceptance: T-24,25,32,33,44,45; only applicable branch evidence; no out-of-scope fulfillment in completion.

Develop next independent stage after this stage PR without waiting for CI. An exit condition defines acceptance, not a global development stop.

### Stage 5: Sepolia integration and final delivery

Entry: Affected model/integration checks and exact runtime configuration, permissions, asset control and designated test asset are verified for each real path.

- Deploy exact candidate using existing approved Linux process; absent target blocks that deployment only while packaging proceeds.
- Execute six revised scenarios on Sepolia 11155111 with actual chain records and explicitly simulated registrars, never Hoodi substitution.
- Cover all three source/Oracle contracts and record each scenario's chosen main source.
- Verify whole-artwork backend alignment, each middleware route and frontend; join actual Oracle, funds and UI evidence.
- Generate demo, editable PPT and playable film from final verified demo; distinguish real chain, simulated institutional roles and animation.
- Independently verify exact head CI, same-version artifact and actually served version; package identity is not deployment evidence.

Deliverables: Accessible demo, deployment receipt, six scenario results, three-source coverage, tests/security results, PPT, film and remaining issues.

Acceptance: All six scenarios and complete evidence chain; deployment/runtime/chain/product verdicts separate; NOT_RUN for absent operations.

Develop next independent stage after this stage PR without waiting for CI. An exit condition defines acceptance, not a global development stop.

Stage 4 also includes authorized holder replacement mint: possession plus holder=owner, atomic old burn/new mint, editable new terms, retained old/new history and UNKNOWN/concurrency recovery. No extra cleanup/refund/unfreeze/migration approval gate is introduced. Ordinary transfer remains independent of holder equality, gap closure and current finality. Stage 5 integrates T-52 through T-68 with all source paths and real evidence.

## 17. Acceptance matrix

The complete matrix retains T-01 through T-51 with applicable revised semantics and extends through T-68. A row is an obligation, not a passing result. Parameterized/property cases may cover multiple rows. First stage is the latest initial inclusion point, not a prohibition on earlier work. Preserve exact source/run/evidence; never inherit historical green into revised assertions.

| Case | Assertion | Requirements | First stage / later integration |
| --- | --- | --- | --- |
| T-01 | One NFT is one whole receipt; preserve full receipt and underlying goods quantity; reject fractions and duplicate mappings. | EX-SCOPE-02 / EX-INV-02 / EX-MINT-01 | 1 |
| T-02 | Initial owner0 equals holder0; keep accurate independent trade and registered positions after transfer. | EX-SCOPE-03 | 1 |
| T-03 | Record A to B to C to D in order, with a separate registration request for every hop. | EX-INV-01 / EX-INV-05 | 1 |
| T-04 | Oracle registration is contiguous; rebuild out-of-order chain indexes without skipping B, changing holder without its record or inventing a waiting-for-receipt business state. | EX-INV-03 / EX-INV-05 / EX-INV-11 | 1 |
| T-05 | Consume the same Oracle record idempotently; reject different content under the same identity; no second business receipt. | EX-INV-04 / EX-INV-05 / EX-INV-11 | 1 |
| T-06 | Reject absent, expired, revoked or altered asset, amount or chain-domain authorization. | EX-AUTH-01 / EX-AUTH-02 / EX-AUTH-04 | 1 |
| T-07 | Reject nonce replay; concurrent transfers to two buyers advance only one valid head. | EX-INV-01 / EX-INV-06 | 1 |
| T-08 | Account switching, disconnect or lost session must not reuse the previous account's authorization. | EX-AUTH-01 / EX-AUTH-03 | 1 |
| T-09 | Independently submitted bids and asks follow price priority, equal-price FIFO and best executable price; no queue jumping, altered limits or specified-counterparty substitution. | EX-MATCH-01 / EX-INV-12 | 1 |
| T-10 | All three Oracle adapters satisfy one registration contract using mint-declared formats; holder follows the same receipt; simulated roles are labelled. | EX-INV-05 / EX-SCOPE-09 / EX-MINT-05 | 1 |
| T-11 | Principal uses the explicit selected member of the immutable NFT0 set through freeze/release/refund. Refuse missing/changed currency, conversion/substitution and insufficient/unknown selected-currency balance even with sufficient ETH gas. Freeze each liability separately before trade; no second principal debit after registration. | EX-SETTLE-01 / EX-SETTLE-05 | 2 |
| T-12 | Release eligible AB without waiting for C or D. | EX-SETTLE-02 / EX-INV-03 | 2 |
| T-13 | Keep every segment's price and funds separate; pending later funds cannot subsidize an earlier release. | EX-SETTLE-01 / EX-SETTLE-03 | 2 |
| T-14 | Reject wrong asset, segment, journal, network or unauthorized evidence source. | EX-INV-05 / EX-SETTLE-04 | 2 |
| T-15 | Historical registration at C may coexist with a current D observation; settle each segment from its own authority. | EX-SETTLE-04 | 2 |
| T-16 | Recover unknown RPC or execution results for release of already frozen funds idempotently; no new buyer-payment business failure, duplicate debit or gas charge. | EX-SETTLE-05 / EX-INV-04 / EX-NFR-04 | 2 |
| T-17 | When B refuses and holder is A, refund the unregistered suffix and return owner to A; holder stays A and the NFT is not burned. | EX-ROLLBACK-01 / EX-ROLLBACK-05 | 3 |
| T-18 | When AB is registered and C refuses, withdraw BC/CD only and return owner to effective holder B; keep registration and settled AB; never reset to issuer. | EX-ROLLBACK-02 / EX-INV-03 / EX-INV-08 | 3 |
| T-19 | Return each segment's unreleased principal to its original buyer; show actual gas and net proceeds with explicit units. | EX-GAS-01 / EX-ROLLBACK-03 / EX-SETTLE-06 | 3 |
| T-20 | Intermediate wallets with zero ordinary ETH do not change recovery duties or require serial wallet-by-wallet NFT return. | EX-ROLLBACK-04 / EX-GAS-07 / EX-GAS-10 | 3 |
| T-21 | One shared operation must not be charged in full to multiple segments. | EX-GAS-02 | 3 |
| T-22 | ETH is the sole gas asset. Zero/insufficient/unverified applicable ETH warns and refuses new trading even if price funds suffice; selected-currency shortage also refuses. Original sufficient frozen gas remains usable for its approved recovery without second prepayment or double counting. | EX-GAS-03 | 3 |
| T-23 | Resume crashed rollback idempotently without repeat refunds or charges; duplicate or obsolete messages cannot revive withdrawn segments; no late-receipt grace path. | EX-INV-04 / EX-INV-07 / EX-TIME-03 | 3 |
| T-24 | Honor mint time units and boundaries; refuse new trades after cutoff; overdue unregistered suffix fails and owner returns to effective holder; preserve registered and settled prefix. | EX-TIME-01 / EX-TIME-02 / EX-TIME-03 | 4 |
| T-25 | EX transfers the bill of lading without physical collection, transport, warehouse exit or collection-driven burn. Terms remain readable; owner ahead of holder may resell. Authorized atomic holder remint is separately covered by T63-68. | EX-SCOPE-08 / EX-EXIT-01 / EX-INV-08 / EX-SCOPE-12 | 4 |
| T-26 | Distinguish simulated and real, pending and complete, owner and holder. | EX-NFR-05 | 1 |
| T-27 | Reproduce Linux commands and fixtures with exact source, configuration and run identity. | EX-NFR-01 / EX-NFR-07 | 1 |
| T-28 | On duplicate consumption, restart or unknown freeze/release/refund, query before retry; never duplicate funds or gas actions. | EX-NFR-03 / EX-NFR-04 / EX-SETTLE-05 | 2 |
| T-29 | Reject rollback without sufficient authority; no arbitrary confiscation or rewriting a finalized prefix. | EX-SCOPE-07 / EX-NFR-10 | 3 |
| T-30 | Recover reorg, duplicate logs, RPC timeout and reordered events without early or repeated release. | EX-INV-10 / EX-NFR-03 | 3 |
| T-31 | Release and refund are mutually exclusive; reconcile segment principal, fees and final balances. | EX-INV-04 / EX-SETTLE-03 | 2 |
| T-32 | Trace bill-of-lading terms, original Oracle registration, holder and funds. Physical collection or collection-driven destruction is not completion; authorized remint separately preserves old/new NFT links and existing evidence. | EX-EXIT-02 / EX-EXIT-03 / EX-SCOPE-09 / EX-REMINT-04 | 4 / 5 |
| T-33 | Reject duplicate valid mappings, transfer replay and repeated funds actions; failed old segments stay dead, valid NFTs can start a new chain, history remains. | EX-EXIT-03 / EX-ROLLBACK-05 | 4 |
| T-34 | Agent actions already authorized in the wallet need no extra platform step approval; refuse out-of-scope actions. | EX-AUTH-01 / EX-AUTH-05 | 1 |
| T-35 | Use only approved Sepolia 11155111 and designated test PYUSD; reject wrong chain or asset before sending; no Hoodi substitution. | EX-DEMO-01 / EX-SCOPE-11 / EX-GAS-09 | 5 |
| T-36 | All six scenarios have matching actual transactions, simulated registration evidence, UI states and final assertions. | EX-DEMO-02 | 5 |
| T-37 | Demo, PPT and playable film consistently label real test-chain actions, simulated roles and animation; no implied institutional cooperation. | EX-DEMO-03 | 5 |
| T-38 | Required CI belongs to exact head; actual deployed commit matches; read back artifact bytes and hashes. | EX-NFR-07 | 5 |
| T-39 | No secrets, private source documents or internal operational material in code, logs, artifacts or public diffs. | EX-NFR-06 / EX-NFR-09 | 0 |
| T-40 | Record real resource and performance baselines and diagnosable errors; no invented production SLA. | EX-NFR-05 / EX-NFR-08 | 0 |
| T-41 | Mint complete asset-specific receipt data, terms, both cutoffs and time semantics; reject missing required fields; do not copy unrelated commodity rules. | EX-MINT-01 / EX-MINT-02 / EX-MINT-04 / EX-MINT-06 | 1 |
| T-42 | Encrypt receipt-access secrets only in controlled off-chain storage; NFT has only opaque nonsecret mapping; no wallet private keys held by EX. | EX-MINT-03 / EX-NFR-06 | 1 |
| T-43 | Before trade show both cap and median in ETH and contemporaneous USD with source, time, scope and buyer confirmation; unavailable quote, FX or confirmation blocks submission; no fake zero. | EX-GAS-04 / EX-GAS-05 / EX-GAS-06 | 1 / 3 |
| T-44 | Rollback aligns owner only to effective holder; unexpired valid NFT may trade again, expired NFT stays closed; ordinary owner-ahead-of-holder resale remains allowed. | EX-ROLLBACK-05 / EX-INV-08 / EX-TIME-01 | 3 / 4 |
| T-45 | The off-chain voucher itself is the receipt; Oracle alone ingests, verifies and writes it; holder follows that record; no EX raw-voucher intake, independent holder writer, second receipt or late wait. | EX-SCOPE-09 / EX-MINT-05 / EX-INV-11 / EX-TIME-03 | 1 / 4 |
| T-46 | Align ArtFi whole-artwork and EX backend receipt, authorization, Oracle, journal, freeze/release, rollback and audit contracts; provide difference map and shared regression evidence. | EX-ARCH-01 | 1 / 5 |
| T-47 | Direct, electronic and intermediary registration each has an operable UI and source route into one trading/settlement backend; verify route, Oracle, chain and UI together; placeholder buttons do not pass. | EX-ARCH-02 / EX-ARCH-03 | 1 / 5 |
| T-48 | Backend and all sources retain whole artwork/receipt semantics; no charity fractions, shares or newly invented spot/futures/leverage modes. | EX-ARCH-04 / EX-SCOPE-02 / EX-MATCH-02 | 1 / 5 |
| T-49 | Recompute P50 from real applicable algorithm, sample population/count/window/time and source; refuse fabricated or unrelated samples and single-point or cap-average substitutes; estimate is not a guarantee. | EX-GAS-06 / EX-GAS-04 | 1 / 3 |
| T-50 | Buyer confirmation binds quote version, scope and cap; send/retry stays within it and wallet grant; exceeding or unprovable cap stops for fresh confirmation; splitting, retry or quote replacement cannot reset aggregate cap. | EX-GAS-05 / EX-INV-04 | 1 / 3 |
| T-51 | Freeze the confirmed maximum gas amount separately from principal before sending; insufficient or unknown freeze stops; debit actual consumption, unfreeze unused balance, keep failed-tx gas charged and process duplicates once. | EX-GAS-07 / EX-GAS-08 / EX-GAS-10 / EX-INV-04 | 1 / 2 / 3 |

| T-52 | Zero ETH warns and refuses a new trade despite sufficient NFT0 principal or other tokens; no transaction signing/broadcast, valid trade/registration task or owner advance. UI/API/Agent agree. | EX-GAS-09 / EX-GAS-10 / EX-INV-13 | 1 / 3 / 5 |

| T-53 | Check available ETH at zero, one wei below the maximum, exactly the maximum and above it, after other reservations. Sufficient P50 but insufficient cap refuses; sufficient funds proceed only when all other conditions hold. | EX-GAS-05 / EX-GAS-07 / EX-GAS-10 | 1 / 3 / 5 |

| T-54 | Gas quote confirmation, freeze, debit and unused unfreeze settle in ETH; USD is display only. Refuse PYUSD/WETH/other gas assets, conversion, non-ETH-principal gas deductions and subsidy bypass. Preserve cap/median and consumption idempotence. | EX-GAS-04 / EX-GAS-07 / EX-GAS-08 / EX-GAS-09 / EX-SCOPE-11 | 1 / 2 / 3 / 5 |

| T-55 | Recheck changed account/chain, concurrent ETH use, invalid freeze, old-signature replay and retries before signing/broadcast. Direct backend calls cannot bypass; prebroadcast refusal cannot invent consumed gas. | EX-GAS-10 / EX-AUTH-02 / EX-AUTH-04 / EX-INV-04 | 1 / 3 / 5 |

| T-56 | Sufficient original frozen ETH for the same approved rollback obligation remains usable with zero unfrozen cash. No second prepayment, early unfreeze or cancelled rollback. A remaining shortage uses the original confirmed replenishment flow; no automatic exchange/subsidy. | EX-ROLLBACK-04 / EX-GAS-05 / EX-GAS-07 / EX-GAS-08 | 3 / 5 |

| T-57 | Each order selects one immutable NFT0-allowed currency; both intents and leg freeze/release/refund match it. Wrong currency refuses consistently across three sources and UI/API/Agent, without conversion or substitution. | EX-SCOPE-11 / EX-MINT-07 / EX-MATCH-01 / EX-SETTLE-06 / EX-INV-13 | 1 / 2 / 3 / 5 |

| T-58 | Absent, conflicting, changed or unverifiable NFT0 currencies or an order without explicit selection refuse. No ETH/PYUSD default or balance-based automatic choice. PYUSD fixtures require mint-time membership and explicit selection. | EX-MINT-07 / EX-SCOPE-11 / EX-DEMO-01 | 1 / 5 |

| T-59 | When selected principal is ETH, independently cover and account for principal and maximum gas. Refuse coverage of only one or counting the same balance/freeze twice. Reconcile principal refund and unused gas separately without restoring consumed gas. | EX-SETTLE-06 / EX-SETTLE-07 / EX-GAS-07 / EX-GAS-08 / EX-INV-13 | 1 / 2 / 3 |

| T-60 | Mint-time one-currency and multiple-currency sets are recorded/read correctly. No later UI/API/Agent/contract/admin path can add, remove or replace the same NFT set. Valid remint creates a new NFT while atomically burning the old one. | EX-MINT-07 / EX-SCOPE-11 / EX-INV-13 / EX-REMINT-03 | 1 / 4 / 5 |

| T-61 | Warn and refuse selected-currency principal at zero or one smallest unit short before signing/broadcast, despite sufficient other currencies/gas. Exact sufficiency may proceed under other conditions. Exclude concurrent reservations; reuse only this operation own effective freeze. | EX-SETTLE-07 / EX-SETTLE-06 / EX-GAS-07 / EX-INV-13 | 1 / 2 / 3 / 5 |

| T-62 | For multiple allowed currencies, both orders select the same currency; verify price priority/FIFO/best executable price independently inside each currency. No raw cross-currency numeric comparison, FX ranking, mixed principal sum or automatic conversion. | EX-MATCH-01 / EX-SCOPE-11 / EX-SETTLE-06 / EX-INV-12 | 1 / 5 |

| T-63 | A holder possessing the original NFT with holder equal to owner may remint under valid existing wallet authority. Refuse non-holder, no possession, unequal owner, admin-only identity and invalid/revoked/replayed authority. | EX-REMINT-01 / EX-AUTH-01 / EX-AUTH-04 | 4 / 5 |

| T-64 | Successful remint atomically burns the old NFT and validly mints the new one. Failure of either leaves no one-sided asset loss or two simultaneously valid bills; retain same-operation evidence. | EX-REMINT-02 / EX-INV-14 | 4 / 5 |

| T-65 | Before new mint holder may add/remove/change new terms including allowed currencies; preserve old terms/history. New minted currencies become immutable. New terms cannot bypass ETH gas, no-conversion, Oracle or authority boundaries. | EX-REMINT-03 / EX-MINT-07 / EX-GAS-09 | 4 / 5 |

| T-66 | Remint concurrent with trade/registration atomically rechecks possession and holder equal to owner, yielding one valid result. Duplicate/RPC-timeout/failed/UNKNOWN requests reconcile and recover idempotently, never repeating burn/mint/debit. | EX-REMINT-05 / EX-INV-04 / EX-INV-14 | 4 / 5 |

| T-67 | Read old/new NFT links both ways, term differences and original registration/trade/funds evidence. A burned predecessor cannot trade/remint again. New terms cannot delete or rewrite completed history. | EX-REMINT-04 / EX-SCOPE-12 / EX-INV-14 | 4 / 5 |

| T-68 | Possession and holder equal to owner are the confirmed no-unfinished-trade mechanism for remint, subject to existing authority. No extra clearing/refund/unfreeze/migration approval. This predicate cannot block ordinary resale with owner ahead of holder. | EX-REMINT-01 / EX-INV-08 / EX-SCOPE-03 | 4 / 5 |

## 18. Engineering delivery and exact-source acceptance

Each candidate records repository/branch/full commit/tree/parent/base and exact diff; PRD edition/digest and requirements; missing implementation and NOT_RUN operations; actual Linux runtime/path/commands/config/run/timestamps/exits; test counts/results and complete private logs; artifact bytes/SHA/source/storage; deployment target/served version/URL/start/health/recovery or explicit not-deployed; actual chain/addresses/tx/EVM receipts/blocks/confirmation/Oracle events; and per-segment principal/gas/owner/holder/recovery reconciliation.

Gas evidence includes original cap/P50 ETH/USD with samples and FX, buyer confirmation/reconfirmation, maximum prefreeze, actual costs and unused unfreeze. Record NFT validity and resumed-trading eligibility. Record whole-artwork backend contract alignment and source-route/Oracle/UI coverage. A candidate's own success is not independent acceptance; preserve trusted controller, exact identity, expiry and artifact/log verification.

After a stage PR continue independent authorized work. Only merge when required checks on exact current head and relevant acceptance meet existing authorization. A changed head needs fresh exact-head verification; historical green, short SHA and screenshots cannot substitute. Preserve cancelled/refused operations; no mainnet, real value, new credentials/resources or expanded security settings from this document. Gate only the affected operation.

This public edition is English and product-only, published under the later explicit publication instruction. Original private records, source locators, internal paths, topology, credentials and operational handoffs remain private. Any separately required private server synchronization uses its existing approved location and complete byte readback before claimed complete; it is not an automatic new schedule, deployment or prerequisite for independent development.

## 19. Decisions and local gates

Confirmed or removed requirements cannot remain open-choice blockers. Only the stated affected path waits.

| ID | Status | Current rule | Narrow dependency |
| --- | --- | --- | --- |
| D-01 | CONFIRMED | Price priority, equal-price FIFO and best executable price; no specified-counterparty queue priority. | No product decision remains; validate the matching implementation. |
| D-02 | ENGINEERING_VERIFICATION | Complete asset-specific receipt/mint data, encrypted off-chain secret mapping, both cutoffs and declared registration format are fixed. | Only unresolved actual schema, serialization or controlled-store bindings. |
| D-03 | CONFIRMED | Overdue unregistered suffix fails at cutoff; return owner to effective holder and preserve prefix; no late-receipt grace. | Verify actual time, Oracle ordering and concurrency boundaries; not a new product choice. |
| D-04 | PARTIALLY_PENDING | Cap/P50 ETH and contemporaneous USD, confirmation, cap-sized freeze, actual debit and unused unfreeze are fixed. | Only allocation of one genuinely shared operation remains a product decision; actual send/payment interfaces require engineering verification. |
| D-05 | ENGINEERING_VERIFICATION | Real owner return uses existing authorized asset control and wallet grant. | Only actual rollback lacking verified authority or interface; models and settled business rules proceed. |
| D-06 | CLOSED | Principal is frozen before trade; registration releases that original position; no second buyer payment business branch. | Only technical unknown-result and idempotent recovery remain. |
| D-07 | OUT_OF_SCOPE | Physical collection, transport, warehouse exit and collection-driven NFT burn are removed; retain terms, transfer and history. | No Stage 4/5 physical delivery or burn gate. |
| D-08 | ENGINEERING_VERIFICATION | Bind original Oracle source, journal, asset, segment and actual deployment interfaces. | Only the concrete missing integration path; other paths proceed. |
| D-09 | ENGINEERING_VERIFICATION | Verify wallet compatibility from real semantics and interfaces. | Only unverified wallet execution; supported paths and contract checks proceed. |
| D-10 | PARKED | Agent service-fee mechanism, rate, timing, bearer and refunds. | Commercial charging only; all core stages and fee-free demo proceed. |
| D-11 | PARKED | Real commercial asset classes, cooperation, registrars and admission. | Later real business expansion only; three simulated sources proceed. |
| D-12 | PARKED | Commercial pricing, revenue, funding, operations and legal path. | Later commercial or outward commitments only; authorized test development proceeds. |
| D-13 | EXECUTION_VERIFICATION | Any separately required private server document synchronization needs its approved destination and actual byte readback. | That document synchronization only; never block independent development. |

A funded account is not a gas-policy decision; a token/provider interface is not wallet semantic acceptance. No new device lock, remote-attestation or pre-funded account is presumed. Later valid authorization is retained with its actual scope; a version change alone does not revoke it.

## 20. Source and change traceability

Source identifiers are retained without private locators or quoted private operational records:

| Source | Contribution |
| --- | --- |
| SRC-01 / SRC-01B | Original product explanation and equivalent office-format copy: owner/holder, whole receipt, registration, segment escrow, suffix rollback and demos |
| SRC-02 / SRC-03 | Original project and CI handoff: reuse, Linux execution and existing responsibilities; historical cancelled dispatch remains cancelled |
| SRC-04 | Existing whole-artwork authority/journal/segment/settlement alignment |
| SRC-05 / SRC-06 | Historical repository/bootstrap evidence, source-bound and never current acceptance |
| SRC-07 / SRC-09 | Full staged PRD and infrastructure/execution scope |
| SRC-08 | Historical sanitized-publication provenance; every new public upload remains subject to current authorization and actual review |
| SRC-10 | Current confirmed matching, mint, cutoff, bill transfer, prefix protection, single Oracle receipt and stage-PR continuation |
| SRC-10B | Whole-artwork backend alignment and three transaction sources, explicitly not market modes |
| SRC-10C | Cap/P50 ETH/USD, buyer confirmation, cap-sized prefreeze, actual debit and unused unfreeze |
| SRC-11 | CME spot-market chapter 12 reference, limited to corresponding confirmed principles/specifications |
| SRC-12 | CME Direct Auction FIFO reference, without importing unrelated market terms |
| SRC-13 | Original full edition as revision baseline, not a replacement for current requirements |
| SRC-14 | Full v1.3: immutable one/multiple NFT0 currencies, ETH-only gas and separate funds, atomic authorized holder remint, ordinary continuous-transfer boundary and T52-68 |

Matching references: [CME spot rules](https://www.cmegroup.com/rulebook/CME/I/12.pdf), [CME Direct Auction manual](https://www.cmegroup.com/content/dam/cmegroup/education/files/cme-direct-auction-dairy-user-manual.pdf). These are references within confirmed scope, not a claim of certification or implementation.

Migration rules: no 72-hour/previous-working-day forced custody scheme; no physical-collection-driven burn acceptance; owner returns to effective holder without prefix/issuer reset; Oracle's one voucher/record controls holder; no EX raw-original or second receipt; no late grace; no second buyer payment; no open matching/mint/cutoff/cap decision where already confirmed. Preserve all nonconflicting original requirements and IDs. Git history retains superseded text, which is not a live checklist.

## 21. Definition of done

Complete only when all six revised scenarios, all three explicitly simulated Oracle sources, complete whole-receipt mint, price/FIFO matching, per-segment original-funds release, bounded suffix rollback, cutoff/bill-transfer boundary and eligible resumed trading have reproducible evidence. Verify real cap/P50 ETH/USD, samples, buyer confirmation/reconfirmation, maximum gas freeze, actual debit and unused unfreeze within confirmed cap and separate from principal. Match demo/PPT/playable film, exact code/config, actual Linux deployment, Sepolia observations and private execution records. Whole-artwork alignment, operable middleware/frontend for all sources and T-46..48 must pass. Missing applicable evidence keeps delivery OPEN.

Physical collection, transport, warehouse exit and collection-driven NFT destruction are not completion conditions. Authorized atomic holder remint, immutable allowed-currency selection and separate ETH gas/price coverage remain required by T-52 through T-68. Completion does not imply real warehouses/institutions admitted, cooperation, licenses, commercial fees, mainnet deployment or acceptance of new human financial/legal obligations. Parked items affect only genuinely dependent later work.

## Appendix A: migration coverage

This edition retains sections 1..21, stages 0..5, DEMO-01..06, T-01..51, D-01..13 and all 77 requirement identifiers. Revised T-16/25/32/33 and DEMO-01/06 replace conflicting old assertions. T-41/42 cover mint, T-43/49..51 gas, T-44 recovery, T-45 Oracle, T-46..48 backend/source/UI alignment. The machine plan explicitly sets retired requirements non-executable and gives no historical result a revised-case PASS.
