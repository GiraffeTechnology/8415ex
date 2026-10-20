# 8415ex Product Requirements

Version: 1.5 (complete product iteration 2026-10-20 UTC)
Edition: complete English product and acceptance contract
Status: OPEN; requirements are not implementation or acceptance evidence.

This English edition carries the complete product and acceptance scope of v1.5: 123 EX requirements, 96 acceptance cases, six stages and six core demonstrations. Publication does not imply implementation or acceptance. It supersedes conflicting earlier requirement editions and execution checklists. All prior product stages, requirement IDs, acceptance cases and decisions remain represented. The added deferred mode is not evidence of deployed capability.

## 1. Execution conclusion

Build a commodity spot-intermediary Web3 infrastructure DEMO with a cryptocurrency/commodity-market frontend, BTC/ETH and soybean/iron-ore scenarios, two collateral asset classes, live public reference data and simulated NFT orders kept distinct. The optional cross-chain collateral-backed deferred mode is specified in section 7.1; EX grants a trading allowance without lending cash or charging an interest spread. Undefined provider, valuation, ratio and fee parameters block only dependent mechanisms, never independent confirmed delivery.

Implement the confirmed whole-receipt trading, Oracle registration, segment settlement and suffix rollback model, then Linux integration and Sepolia demonstrations. Commercial pricing, legal advice and real-asset admission remain local later decisions. Six stages define development and acceptance scopes. CI and exact-head acceptance are verified separately before merge. A source file, HTTP 200 or CI success alone is not delivery.

Execution boundary: GitHub Actions is permitted for CI and its automated checks. Runtime and integration acceptance use the project-supported Linux configuration. Sepolia remains the EX demonstration network. CI results do not establish deployment or live-chain acceptance.

## 2. Requirement states and change control

Confirmed requirements are product constraints. Engineering contracts implement them without inventing a standard ABI or expanding product scope. Parked items have not been decided and cannot become defaults or block unrelated work. Execution gates are the actual permission/runtime conditions for a particular external action. EX-* and T-* identifiers are local traceability identifiers, not ERC-8415 interface or event names. Every change identifies its source, requirement, affected cases/stages and authorization consequences. Later business discussion does not reopen independently accepted unchanged work.

## 3. Product goals and boundaries

Provide an ordered chain of whole-receipt trades while off-chain registration may lag. Protect conditional funds and agreed return control until registration; independently finalize eligible prefix segments and unwind only the eligible unregistered suffix. Agent execution is bounded by the human wallet grant, without platform wallet-key custody. Demonstrate properties with reproducible Linux and actual authorized test-chain evidence.

| ID | Requirement |
| --- | --- |
| EX-SCOPE-01 | A Web3 infrastructure DEMO simulating an ordinary commodity spot intermediary, with cryptocurrency and commodity-market presentation; do not claim to operate a licensed centralized exchange or real financial service. |
| EX-SCOPE-02 | One NFT equals one whole warehouse receipt; no fractions. |
| EX-SCOPE-03 | Allow continuous A to B to C to D trading while registration catches up. Ordinary transfers cannot require holder equal to owner, a closed projection gap or current finality; the holder-equals-owner remint predicate is separate. |
| EX-SCOPE-04 | Support 8415Wallet V3 or any wallet satisfying the same authorization and control semantics; no exclusive wallet binding. |
| EX-SCOPE-05 | Every Agent operation comes from verifiable bounded human wallet authority. |
| EX-SCOPE-06 | The buyer pays its transaction gas and assigned rollback gas in ETH only. Warn and refuse a new trade when ETH is absent or insufficient. Agent service fees remain a separate later decision. |
| EX-SCOPE-07 | No arbitrary compulsory custody or instant liquidation. Normal conditional funds escrow and agreed asset-return control remain. Only the explicitly consented deferred-mode debt and recovery-gas liquidation in section 7.1 is added. |
| EX-SCOPE-08 | Transfer the mapped bill of lading only; physical collection belongs to the parties named in its terms. |
| EX-SCOPE-09 | The off-chain change voucher is itself the registration receipt; Oracle alone ingests, verifies and records it on chain. |
| EX-SCOPE-10 | Align ArtFi whole artwork and EX backend; direct, electronic and intermediary registration are transaction sources with middleware and frontend paths. |

Non-goals: operating a CEX, customer-funds general ledger or platform custody account, guaranteed returns or unconfirmed financing/leverage/liquidation, receipt fragmentation, arbitrary cross-chain routes or new real-asset commercial admission. The explicitly agreed deferred mode in section 7.1 is included; it is not an EX loan. Reuse and alignment of existing whole-artwork, wallet, Oracle, journal and settlement components remain required. Charity shares are excluded. Collection terms remain in the bill; EX does not perform collection, transport, warehouse exit or collection-driven burn. No license, institutional cooperation, legal effect, fee rate or revenue distribution is presumed.

| ID | Requirement |
| --- | --- |
| EX-SCOPE-11 | For prepaid mode: NFT0 fixes one or more allowed price currencies at mint. Each order explicitly selects one member; insufficient selected-currency funds warn and refuse. EX does not exchange, auto-select, combine currency balances or substitute assets for principal or ETH gas. Holder remint creates a new NFT and never edits the old allowed set. For explicitly selected deferred mode, section 7.1 substitutes verified reserved collateral allowance for principal prefunding, not for gas or currency identity. |
| EX-SCOPE-12 | A holder possessing the original NFT may atomically burn it and mint a replacement under the remint conditions. New terms may be added, removed or changed before the new mint; retain bidirectional identity and complete history. |
| EX-SCOPE-13 | Demonstrate hedging, collateral and arbitrage scenarios involving BTC/ETH and whole soybean/iron-ore receipts; labels do not authorize financing, futures or guaranteed returns. |
| EX-SCOPE-14 | Both cryptocurrency and commodity warehouse-receipt NFTs are confirmed collateral choices; do not restrict the scenario to crypto collateral only. Deferred crypto-collateral terms are specified in section 7.1; other economic and execution parameters remain D-14. |
| EX-SCOPE-15 | Continuously read and refresh real public commodity spot reference prices with traceable source values/times and fetch times. NFT quotes/trades may be simulated but must not impersonate external references. |
| EX-SCOPE-16 | Market makers may submit ordinary quotes under the same currency, price-priority, FIFO and authorization rules; no privileged priority, AMM, incentives or return promise is implied. |
| EX-SCOPE-17 | EX frontend covers markets, NFTs, trades and evidence. Exclude wallet asset overview, account, security, validator and Agent-permission-management pages while retaining transaction authorization and balance/fee checks. |
| EX-SCOPE-18 | Align six UI languages with 8415wallet.com. Source candidates are en, zh-Hans, zh-Hant, fr, es and ja; verify live alignment separately. Cover every new state/error/explanation and preserve protocol identifiers. |

BTC scenarios do not authorize a Bitcoin bridge, wrapped asset, custody service or additional network. A collateral selection is not permission to pay principal in that asset or replace ETH gas. NFT0 still determines the permitted principal assets. Show undefined valuation, LTV, loan amount, interest, liquidation, maturity or revenue-sharing terms honestly, without invented defaults. Source freshness or financing uncertainty cannot become a universal spot-trading gate.

## 4. Baseline and factual limits

Resolve current full source commit/tree and actual repository content before work or acceptance. Historical dependency-free bootstrap tests and old PR/CI records are source-bound history, not current product capability. Stage 0 must independently resolve current main, branch ancestry and exact diff. T-35 through T-38 require actual current-round deployment and chain evidence; this edition supplies requirements, never a passing certificate. Document publication does not establish deployment or runtime acceptance.

## 5. Participants and trust boundaries

Humans choose assets and sign allowed intent terms; Agent cannot fill in an unsigned intent. Wallets control assets, validate authority and execute permitted operations without disclosing private keys. Agent discovers/matches executable orders, submits permitted actions and follows outcomes without changing bounds or fabricating registration.

EX validates conditions, records the chain, coordinates frozen-principal release/rollback and derives business projections from Oracle chain authority. EX does not ingest raw off-chain vouchers, invent another business receipt or treat its database as authoritative. Registrars form the mint-declared voucher; Oracle adapters alone ingest/verify/bind it and write the authoritative chain record. Holder follows that record, never an independent asynchronous write. Contracts enforce agreed escrow/control without arbitrary confiscation or finalized-prefix rewrite. Operators investigate and retry through the same permissions, never by manually marking success.

Run receipts are engineering evidence and not new registration receipts.

## 6. Domain model and complete mint contract

Owner is the actual current ERC-721 token owner: ownerOf(tokenId) returns an address, not a timeline position. EX maps that authority to ownerPosition using real trade/transfer records. Holder is the verified remote-register holder represented by Oracle chain evidence, mapped to a registration position. Initial owner0=holder0. Owner D with holder A/B is normal; compare positions in the same ordered chain, not numeric address values. Holder and its registration receipt represent one authoritative fact, whereas chain observation, indexing and funds execution can have recoverable technical states.

A finalized prefix contains contiguous registered/settled segments. Principal was frozen before trade; registration releases that existing position without a second buyer payment. A registered segment undergoing technical release recovery is not a refundable unregistered suffix. Rollback changes owner to current effective holder, never revokes holder, resets issuer or changes settled prefix. The recovered equality is a new-chain starting point, not a prerequisite for all normal resale.

The fixed ERC-8415 Draft has no standard holderOf getter; that name may only be a verified application/adapter label. currentEntry(tokenId).holder is the latest admitted entry, whereas holderAsOf(tokenId,t) is a historical effective-time query. Preserve effectiveAt, query time and observation block; never present a future-effective admission as currently effective. Registration version, transfer count and holderPosition are distinct. The protocol permits same-holder confirmation registrations and does not require one admission per ERC-721 transfer; EX's sequential segment registration is its application contract.

The UI currentPosition, ownerPosition and holderPosition are three independent markers on the same actual timeline. Do not merge them or derive one by a fixed offset; 8/7/1, 3/3/3 and 20/19/2 are fixtures only. Missing records remain unknown. Per-position signature state binds the position/transfer, signing role, original payload, applicable version/domain/nonce or equivalent scheme binding and verification result. Distinguish transaction signatures, order grants, registration/proof signatures, admission and funds. Alignment or proof success does not imply a signature; historical signers cannot be reassigned to the current owner.

Keep protocol gap state, latest admission, historical finality, EX registration/refusal, funds and execution separate. GapStatus is NONE, OPEN, ADMITTED, CANCELLED or SUPERSEDED, with no protocol REJECTED state. Oracle application refusal cannot be inferred from absence, failed proof submission or gap closure. Historical finality holds for first.effectiveAt <= t < latest.effectiveAt; at or beyond latest.effectiveAt it remains provisional. Before the first entry, holderAsOf/entryAsOf revert and isFinalAsOf is false. Cancellation changes neither admitted history nor historical finality. EX's finalized prefix is a business term, not an alias for isFinalAsOf.

Logical records must preserve or trace:

| Record | Required correlations |
| --- | --- |
| Receipt | Unique receipt, chain/NFT identity, full goods/bill terms and nonsecret mappings, owner/holder, validity, mint-spec version, both cutoffs and format |
| Transfer | Unique transfer/receipt, sequence/predecessor, seller/buyer, terms, authority, registration, settlement and rollback states |
| TradeIntent | Signer, whole asset, direction, price/quote asset, quantity one, nonce, expiry and permission boundaries |
| EscrowPosition | Original buyer/seller, transfer, wallet freeze reference, exact asset/amount, release/refund state and unique action |
| RegistrationRequest | Transfer, declared source/adapter, native request, predecessor, submission/deadline and technical attempt count |
| RegistrationEvidence | Same Oracle voucher/format/digest, asset/transfer/journal, chain/token contract/tokenId/registerId/verificationProfile/authority, remote finalized source record, old/new holder, independent registration version, effectiveAt/query time/observation block and chain/tx/block/log identity |
| GasEstimate | Quote/version, action/scope, estimated gas/rate, cap/P50 ETH/USD, same-time FX provenance, sample algorithm/population/count/window/blocks, validity, grant and buyer confirmation |
| GasPrepayment | Confirmed quote/scope, native freeze reference, cap/frozen ETH, real consumption, unused amount, debit/unfreeze and transaction/action identities |
| AuthorizationReference | Wallet, capability object, original signed grant reference, validity, revocation and permitted actions |
| ExecutionEvidence | Exact source/config/run/network, actual addresses/tx or failure, timestamps and artifact/log digests |

Additional records preserve:
- RemintOperation: one operation ID, original/new NFT links, effective holder/possession/equality/authority evidence, original/new terms and currency-set differences, atomic result, concurrency preconditions and idempotency.
- CommodityReferencePrice: provider/source URL and fixed series identity, commodity/specification/grade/market/location/priceType, price/currency/unit, sourceAsOf with original precision, fetchedAt, sourceDelay, freshness/status and fetch evidence.
- NftQuoteView: individual NFT/quote identity, full-receipt terms, simulated/real provenance, quote currency/value, individual eligibility/registration/gap and correct detail route.
- TransferTimelineView: real ordered transfers, the three independent positions, per-position signature evidence, registered prefix, unknown/loading/error state and identity-free frontend projection.
- CollateralScenario: linked crypto/warehouse-NFT collateral class, commodity/receipt association, known/unknown mechanism parameters and simulation labels.

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

Equality and possession are the confirmed EX remint business predicate, not an ERC proof that no gap, escrow or task exists. Same-holder admissions and round-trip ownership can yield equal addresses. Preserve the predicate without adding cleanup/migration approvals. Atomic old burn/new mint and history continuity are EX responsibilities, not automatic ERC features. Remint gas remains ETH within the separately authorized scope; no invented fee payer or borrowing another trade's principal/frozen gas.

## 7. Continuous trading, registration and cutoff

A starts as owner/holder. Independent A/B orders match by price/FIFO/best executable price with valid signed terms, receipt/deadline checks and buyer-confirmed gas disclosure. In prepaid mode, B's principal and maximum gas amount are independently frozen before transfer/registration admission. In the separately selected deferred mode, section 7.1 replaces only the principal-prefunding obligation with verified reserved collateral-backed allowance; the original new-trade gas gate remains. Owner advances to B; B may resell to C, then C to D under the same conditions without waiting for holder. Each hop retains its own transfer, grant, freeze and registration task.

Oracle verifies the mint-format voucher and writes the one chain record; holder advances A/B/C/D contiguously. EX rebuilds missing/reordered index observations from authority instead of local arrival order. Release a segment when both ordered owner and holder have reached its buyer or beyond and registration is timely. Owner D/holder B makes AB eligible, not BC/CD. No second buyer payment in prepaid mode; deferred payment remains governed by section 7.1.

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
| EX-SETTLE-01 | In prepaid mode fully freeze each buyer's selected NFT0-allowed principal and confirmed maximum ETH gas separately before trading. Deferred mode instead requires the section 7.1 verified collateral allowance for principal; it still requires separate new-trade gas. Never double-use principal, collateral capacity or a confirmed freeze. |
| EX-SETTLE-02 | At the authoritative registered buyer cut, permanently remove that segment's NFT rollback control without waiting for the suffix. Release its prepaid funds; in deferred mode retain B's separate payment obligation until actual settlement, without reviving the completed NFT rollback. |
| EX-SETTLE-03 | Keep seller, buyer, price, asset, registration sequence, principal, fees and rollback per segment. Prepaid mode cannot use later-funds subsidy. Explicit deferred mode may allocate B's resale proceeds to its escrow under section 7.1, preserving refundable suffix obligations and preventing double allocation. |
| EX-SETTLE-04 | Bind release to genuine authorized Oracle chain source, asset, transfer and journal; historical registration and current holder observations remain distinguishable. |
| EX-SETTLE-05 | Prepaid mode releases already frozen principal without a second buyer payment. Deferred mode permits the explicitly agreed later payment, top-up and deadline liquidation in section 7.1. Technical recovery never duplicates debit, payment, release or gas. |
| EX-TIME-01 | Record both deadlines at mint; stop new trading at the declared cutoff. |
| EX-TIME-02 | Registration beyond trading cutoff fails the unregistered suffix and returns owner to effective holder; registration must also satisfy its own mint deadline. |
| EX-TIME-03 | Use mint rules and authoritative Oracle ordering for deadline decisions; protect registered/settled prefix; no late-voucher grace or second-receipt wait. |
| EX-EXIT-01 | EX completion is bill-of-lading transfer with full terms and Oracle-confirmed holder, without physical collection. |
| EX-EXIT-02 | Off-chain parties handle collection, transport and warehouse exit; these are not EX completion/acceptance conditions. |
| EX-EXIT-03 | Do not introduce physical-collection-driven burn. Authorized holder remint atomically burns the old NFT; retain old/new receipt, registration, trade and funds history and prevent duplicate valid asset mappings. |

Before mint cutoffs, show genuine pending status; absent local notification is neither success nor refusal. Deadline, registration and rollback races need atomic preconditions against one ordered authority. Technical log replay does not create a holder-first/receipt-later business state. Same identity/same content is idempotent; same identity/different content conflicts. Old messages cannot revive failed segments. Registered holder stays effective during technical recovery. After recovery an otherwise valid, unexpired and authorized NFT may begin a new chain; expiry cannot be bypassed by recovery. Actual off-chain collection rights are unaffected by test cutoff, and no forced disposal follows expiry.

One or more allowed price currencies are declared immutably by NFT0 at mint; each order explicitly selects one member and carries that selection through the signed order, each principal freeze, release and refund. Ordinary prepaid trading never selects a fallback currency, performs exchange, automatically buys ETH or converts principal to cover gas. The deferred collateral liquidation routes in section 7.1 are separately authorized, explicitly denominated recovery actions, not principal substitution. Principal balance is checked in its own asset and smallest unit; gas is checked independently in ETH wei. If the designated price currency is ETH, the two liabilities remain separately reserved so one balance is not counted twice. Native execution rechecks original funds/reservations/nonce/UNKNOWN atomically. In prepaid mode, missing or insufficient funds on either side warns and refuses; deferred mode verifies its reserved collateral allowance instead of cash principal. No balance or denomination is inferred from a label.

| ID | Requirement |
| --- | --- |
| EX-SETTLE-06 | Keep each leg denominated in its explicitly selected immutable NFT0 currency through quote and payment/refund. Prepaid mode freezes that principal before transfer; deferred mode reserves section 7.1 collateral allowance and records later same-currency escrow allocations. Keep gas separate; liquidation destination receipts cannot be treated as principal or gas until actually received in the required asset. Never double-count or substitute balances. |
| EX-SETTLE-07 | For prepaid mode: If available selected-currency funds cannot fully freeze the price, warn and stop before signing, execution and broadcast. Adequate ETH gas or other allowed currencies cannot replace this order principal. For explicitly selected deferred mode, section 7.1 substitutes verified reserved collateral allowance for principal prefunding, not for gas or currency identity. |
| EX-INV-13 | For prepaid mode: One or more allowed currencies are immutable per minted NFT and each order binds one through its whole principal lifecycle. Principal or ETH gas shortage forms no new trade. No currency conversion, aggregate currency payment or third-party subsidy bypass; old and replacement identities remain distinct. For explicitly selected deferred mode, section 7.1 substitutes verified reserved collateral allowance for principal prefunding, not for gas or currency identity. |
| EX-INV-14 | Remint never leaves both old and new valid or loses the valid asset through a one-sided burn. Existing history, funds and registration obligations survive the replacement. |

### 7.1 Optional cross-chain collateral-backed deferred mode

This scoped mode supersedes prepaid-only and no-liquidation language only for explicitly selected deferred trades. All other authorization, Oracle, NFT0, audit, privacy and registered-prefix rules remain. No production deployment or financial execution is authorized by publication.

| ID | Requirement |
| --- | --- |
| EX-DEFER-01 | Deferred mode is optional and seller-consented, with an exact T+n deadline or 72 hours before the registration deadline; retain prepaid mode. Only NFT0-allowed USD stablecoins may be principal. EX grants secured trading allowance, not a cash loan, and charges no interest spread. |
| EX-DEFER-02 | Accept BTC/ETH as product collateral; test only Hoodi ETH collateral with Sepolia PYUSD principal and Sepolia ETH gas. Hoodi operations need separately accounted Hoodi gas. No unimplemented Bitcoin custody or cross-chain bridge is inferred. |
| EX-DEFER-03 | Verify canonical finalized collateral lock evidence and its chain, vault, asset, borrower, amount and unique identity before granting destination allowance. Authenticated proof validation, valuation freshness/denomination and explicit ratio policy are required; 50 percent is only an example. |
| EX-DEFER-04 | Reserve collateral-backed allowance per obligation atomically and durably; reject duplicate pledges, replay, conflicting observations and concurrent over-allocation. A UI balance or caller verified flag is not authority. |
| EX-DEFER-05 | For A-B-C, B may resell before paying A. C's principal enters B's escrow, with original refundable segment encumbrances preserved and no double allocation. B may deposit the correctly denominated difference before the agreed deadline. |
| EX-DEFER-06 | If the settlement deadline arrives before AB registration completes, treat AB as incomplete and initiate the existing eligible rollback, preserving registered prefix. Do not extend the payment wait or pay A as if registration succeeded. |
| EX-DEFER-07 | If AB registration completes first, its NFT rollback responsibility permanently detaches under the original ordered-cut rule even if A is unpaid. B independently owes A; later debt, liquidation or payment failure cannot reverse that completed cut or make C responsible. |
| EX-DEFER-08 | Allow early manual settlement only with the original registration and authorization conditions. At registered-debt maturity, settle from available B escrow; liquidate pledged collateral for a remaining shortfall. No automatic unapproved margin-call threshold or guaranteed recovery is added. |
| EX-DEFER-09 | When B cannot fund gas needed for eligible rollback, allow collateral liquidation to cover that verified gas shortfall. Keep debt principal, fee, Sepolia recovery gas, Hoodi execution gas and residual collateral separate; do not treat Hoodi ETH as Sepolia gas. |
| EX-DEFER-10 | Liquidation request, source execution and destination receipt are distinct. Only verified destination PYUSD satisfies seller-payment funds; only verified destination ETH satisfies recovery-gas funding. Missing liquidity/provider, partial proceeds or unknown outcome remain unresolved, never fabricated conversion. |
| EX-DEFER-11 | Persist operation identity, exact payload and reservation before dispatch; reconcile ambiguous outcomes without blind replay. Confirm actual payment/refund/release once, preserve restart/concurrency safety and prohibit collateral unlock while secured obligations or unknown effects remain. |
| EX-DEFER-12 | Reuse existing UI rather than create a duplicate. Bind implementation, exact-head CI and main merge to the module contract before downstream wiring/testing/deployment acceptance. Report simulation, CI, actual cross-chain and served acceptance separately. |

The complete module specification is [cross-chain deferred settlement](docs/cross-chain-deferred-settlement.md). It preserves deadline-first rollback versus registration-first independent debt, and the separately authorized rollback-gas liquidation exception. No new UI is requested.

## 8. Conditional funds, suffix rollback and gas

AB, BC and CD have separate prices and original-buyer funds; do not assume equal prices. If owner D/holder A and registration of B is refused, unwind unregistered AB/BC/CD, refund B/C/D their own unreleased principal and return owner to A. If AB is registered and settled and registration of C is refused, keep AB and holder B, unwind BC/CD only and return owner to B. Never return to issuer A or require A to participate again. When holder successively reaches B, C and D, independently release AB, BC and CD.

| ID | Requirement |
| --- | --- |
| EX-ROLLBACK-01 | If registration of B is refused while holder remains A, withdraw all unregistered segments and return owner to A without changing holder. |
| EX-ROLLBACK-02 | After AB registration, if registration of C is refused, withdraw only the unregistered suffix and return owner to B; preserve holder and settled prefix. |
| EX-ROLLBACK-03 | Refund each segment to its original buyer in its original selected NFT0-allowed price currency. Display original principal, actual ETH gas and net receipts separately by currency; never subtract ETH wei from non-ETH principal through a display exchange rate. |
| EX-ROLLBACK-04 | Rollback does not require the NFT to visit intermediate ordinary wallets or their current unfrozen ETH. Sufficient original ETH prepayment for the approved obligation remains usable, without a second prepayment, premature unfreeze or cancellation of rollback. |
| EX-ROLLBACK-05 | Rollback does not burn the NFT; valid unexpired authorized assets may start a new chain from recovered owner equal to effective holder. |
| EX-GAS-01 | Each leg buyer pays the actual gas assigned to its trade, refund and NFT return in ETH, without shifting liability merely because another party refused registration. |
| EX-GAS-02 | Do not charge one shared actual operation in full to multiple segments; allocation method remains D-04. |
| EX-GAS-03 | ETH is the sole gas settlement asset. Refuse a new trade if ETH is absent or insufficient after reservations; principal and gas balances cannot substitute for one another. Deferred-mode rollback may liquidate the borrower's collateral to cover a verified recovery-gas shortfall, without waiving the original new-trade gate or inventing a custody/redemption deadline. |
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

Protocol boundary: rollbackSuffix and refund use the existing authorized asset-control and funds paths. ERC-8415 cancelSettlement is not owner return, refund or registration reversal. Only the recorded initiator may cancel strictly after the protocol deadline; EX trade/registration deadlines and protocol gap deadline remain separate. Business failure does not authorize early cancellation or forced gap closure. Opening a gap follows protocol authority; valid proofs may be relayed by any account. A caller allowlist cannot replace cryptographic verification. Proofs establish inclusion under the accepted verification profile's remote finalized state, not source honesty, legal title, goods existence, payment or performance. expectedHolder and initiator are not proof of the admitted holder. Mutations atomically recheck existing authority and preconditions at execution, without adding business approvals.

Integration acceptance retains direct boundary return through one asset-control operation, without ordinary intermediate-wallet traversal. This does not require every refund and gas reconciliation step to share one atomic transaction; resumable technical recovery remains required. The merged Wallet returnHop implementation currently transfers one cursor leg to the previous account per call. A loop of per-hop calls or separately green model tests is not evidence of this EX return requirement. Require a verified production adapter/control path and joined evidence; do not weaken the requirement to fit an unverified integration.

## 9. Wallet, Agent and matching

| ID | Requirement |
| --- | --- |
| EX-AUTH-01 | Trace each Agent action to valid human wallet authority. |
| EX-AUTH-02 | Check asset, action, eligibility constraints, principal/fee bounds, expiry, nonce and chain domain without modifying signed terms or using counterparty restrictions as priority. |
| EX-AUTH-03 | Support the actual semantic wallet contract; at least one genuine integrated path plus the same conformance checks for alternatives. |
| EX-AUTH-04 | Revocation or expiry rejects new restricted actions with deterministic concurrent behavior. |
| EX-AUTH-05 | Wallet manages Agent authorization; no extra platform approval layer or repeated manual step for an already permitted action. |
| EX-MATCH-01 | Both orders must select the same member of the NFT0 mint-time allowed set. Price priority, FIFO and best executable price operate within one currency book only. No named-counterparty priority jump, FX conversion or numeric price ranking across currencies. |
| EX-MATCH-02 | Reference CME spot matching and asset-specific receipt specifications only; do not import futures margin, CCP, leverage liquidation, proprietary trading or business fees. Market makers participate under the same ordinary order rules without AMM, incentives or preferential queueing. |
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

## 11. Commodity-market UI and operator console

An operable UI is required; CLI supplements development/diagnostics and cannot replace interface acceptance.

| View | Required content and interaction |
| --- | --- |
| Receipt | Complete goods/bill and terms, owner/holder, head, Oracle prefix, both deadlines and eligibility |
| Trade confirmation | Verified authorization result without wallet identity, whole asset, price/order priority, network and signed terms; cap/P50 ETH/USD, samples/source/time, confirmation/reconfirmation, separate principal/gas freeze and actual debit/unfreeze |
| Timeline | Every A/B/C/D hop with registration/funds state and cutoff; submitted is not delivered |
| Rollback | Protected prefix, eligible suffix, refunds/releases, owner restoration, remaining steps and failures |
| Queue | Oracle chain pending/refused, deadline failures, index replay, technical retry, unknown outcome and alerts; no EX raw-voucher upload or manual success |
| Demonstration/evidence | Scenario/run/exact source/network, actual hashes and assertions; no relabelled old or simulated evidence |
| Source entries | Direct/electronic/intermediary operable paths, source description, mint voucher format, task/Oracle record; shared trade/fees/funds/history |

Do not hide partial states, infer unlimited approval from connection, fabricate zero fees, silently raise cap, refund consumed gas, request a second payment or imply physical fulfillment. Retry/recovery uses identical authority/state checks; no privileged funds bypass.

### 11.1 Public reference prices and simulated orders

| ID | Requirement |
| --- | --- |
| EX-PRICE-01 | Continuously read real public spot references and refresh the frontend when new source records are read. Timestamp successful and failed fetches; a screenshot, hand-entered price or static design is not a live feed. |
| EX-PRICE-02 | Retain provider/source, sourceAsOf, fetchedAt, currency, unit, specification/grade, market/location, priceType, sourceDelay and freshness. Preserve date-only source precision rather than inventing seconds. |
| EX-PRICE-03 | Stale source, failed network/parse, conflicting units/specifications or absent data yields stale/unavailable/unknown and last-success time; retain identifiable old values without fake zero or false live labels. Record configured thresholds against actual supply cadence, not an invented SLA. |
| EX-PRICE-04 | Keep references and simulated NFT quotes/trades distinct in data types, labels, timestamps and rendering. Never silently substitute futures, FX conversions, wet/dry tonnes, grades or markets. |

Real-time means continuous reading and timely reflection of newly read records, not a claim that the provider publishes every second. Verify the permitted supply method, display/storage rights, endpoints, cadence, caching/backoff and access limits; do not guess endpoints or bypass limits. Fix the series, specification, market and price type rather than extracting the last number on a page. A per-tonne reference is not a whole-NFT executable quote and cannot rewrite signed orders, select currencies or move funds. Missing reference data blocks only dependent views/mechanisms.

Public candidate sources are https://bean.100ppi.com/, https://ironore.100ppi.com/ and https://www.100ppi.com/product/service.html. Their existence does not prove API access, permission, feed integration or SLA; D-15 remains local. No observed research price becomes a constant.

### 11.2 Per-NFT status, complete terms and timeline

| ID | Requirement |
| --- | --- |
| EX-UI-01 | Every NFT quote has its own status and correct keyboard/click detail route with preserved return context. A verified open gap displays literal openGapOF=YES in red; verified absence displays openGapOF=NO in green. Unknown/loading/error/unsupported never becomes NO or green. |
| EX-UI-02 | Display independent currentPosition, ownerPosition and holderPosition from real records; distinguish ownerOf address, registration version and transfer position. Bind each signature to its role, position/transfer, original payload, applicable version/domain/nonce or equivalent and verification result. Unknown remains unknown; alignment/admission cannot imply signing. |
| EX-UI-03 | Frontend ownership/signature views show positions and statuses only, never wallet names, full/truncated addresses, hover/title/accessible identity labels or recoverable identity displays. Backend authority bindings remain intact. |
| EX-UI-04 | Display every applicable business condition completely as an identity-excluding projection of signed terms. Do not summarize or alter obligations or directly render identity-bearing raw documents/JSON/metadata. Keep original signed files complete, private and unchanged for hash/signature verification. The projection is not byte-identical to the original; translations are informative, placeholders cannot pass completeness. |
| EX-UI-05 | An open gap, owner different from holder or current non-finality cannot automatically prohibit ordinary transfers. Existing deadline, funds and authority rules still apply; remint equality is evaluated separately. |
| EX-UI-06 | Do not build wallet assets, account, security, validator or Agent-permission-management pages. Retain necessary EX eligibility/fee disclosure without disclosing wallet identities. |

The exact six-language UI literals are openGapOF=YES and openGapOF=NO. The actual method is openGapOf(uint256), returning bytes32 settlementId, not bool. Independently verify ERC-165 registration interface 0x6309e170 and optional settlement interface 0xf4a7d71b. Only a supported successful settlement query maps nonzero to YES/red and zero to NO/green. Unsupported, missing, loading, failed or unverifiable values remain explicit and do not universally disable ordinary trading. Preserve readable text as well as color. This display rule does not rename protocol methods, ABI, events or backend fields. NO/green proves neither registration, equality, finality, payment nor legal validity.

Organize complete terms into commodity specifications, whole quantity, storage/delivery, immutable NFT0 currencies, trade/registration deadlines, additional terms, complete signed-business-terms view and revision history. These are display areas, not invented default clauses. Hash and signature verification always use the unchanged private original; exclude identity fields from every frontend embedding, download/copy, metadata, tooltip and accessibility path while retaining every business obligation. Do not add identity permission prompts or product gates. Long timelines expand/scroll without losing records or the three markers.

### 11.3 Six languages and responsive interaction

| ID | Requirement |
| --- | --- |
| EX-I18N-01 | Align with 8415wallet.com's six languages; current source candidates are English en, Simplified Chinese zh-Hans, Traditional Chinese zh-Hant, French fr, Spanish es and Japanese ja. Verify live behavior separately through safe access, never by bypassing a certificate warning. |
| EX-I18N-02 | Reviewed fixed resources cover every market, NFT, gap explanation, terms heading, position/signature, missing-data, principal/gas, pending/failure/recovery message. No runtime automatic-translation dependency; verify key completeness, locale formatting and desktop/mobile layout without mixing or clipping. |
| EX-I18N-03 | Preserve openGapOF=YES/NO exact spelling and YES/red NO/green across locales, along with NFT0, verified ownerOf/currentEntry/holderAsOf/openGapOf names and all chain/asset/transaction/protocol identifiers. Original signed terms retain language/version; explanations are informative and cannot change amounts, order, identity or status. |

Do not add an EX About page or copy wallet marketing claims. Existing authored EX copy receives the same six-language consistency. Live language-set verification is not a global gate on candidate-language implementation. Market, cards, details, full terms, collateral selections, confirmation, recovery, queue, sources and evidence must be operable and responsive with loading/empty/error/unknown/long-chain states. CLI is diagnostic, not UI acceptance.

### 11.4 Design versus implementation

Use the existing approved independent EX design, not a wallet design. Its six-language desktop/mobile screens, state gallery and prototype routes are design evidence only. Static NFT/position examples and placeholder terms do not prove a live feed, actual routing/data/authority, complete original terms, browser execution or chain acceptance. Bind design and implementation evidence separately.

## 12. Non-functional and security requirements

| ID | Requirement |
| --- | --- |
| EX-NFR-01 | CI and its applicable automated unit/model/fixture/integration/UI/API/EVM simulation, syntax/type, build and package checks may run in GitHub Actions. Runtime and integration acceptance use the project-supported Linux configuration. Record exact source, configuration and run evidence. Deployment and live-chain acceptance require separate execution evidence. |
| EX-NFR-02 | Prevent funds/asset reentry and replay with authority and state preconditions. |
| EX-NFR-03 | Safely recover reorg, duplicate logs, RPC timeout and unknown results. |
| EX-NFR-04 | Restart and duplicate queue consumption preserve correlations and never duplicate settlement. |
| EX-NFR-05 | Associate errors with asset, transfer, request and run; publish sanitized error codes. |
| EX-NFR-06 | Keep secrets out of code, public artifacts, logs, chain and metadata; encrypted receipt-access storage is separate from wallet-key custody. |
| EX-NFR-07 | Explicit network, chain, contracts, units, confirmation and timeout parameters enter configuration digest. |
| EX-NFR-08 | Measure load, duration, backlog and failure rate; do not invent throughput/latency SLAs. |
| EX-NFR-09 | Product documentation is in English. |
| EX-NFR-11 | Trace reference-source timing and UI projections; do not expose wallet identities, private records, signing secrets or raw authorization material. Data failure and locale changes cannot rewrite signed content. |
| EX-NFR-10 | Upgrade, pause and recovery cannot bypass ownership or finalized-prefix boundaries. |

Choose reproducible confirmation/reorg windows, retry intervals and resource limits from the project-supported environment and record them as test configuration, not production SLA.

## 13. Reuse, dependencies and whole-artwork alignment

Inspect actual existing whole-artwork receipt, signed order, wallet, task journal, Oracle schema/projection and settlement coordinator contracts before adding an adapter. Reuse equivalent functionality; do not build a second Oracle, settlement architecture or general custody ledger. Whole-artwork intermediary and registrar names are business roles, not proof of any deployed API or institutional cooperation.

Only authoritative permitted Oracle chain evidence bound to asset/segment/journal can drive release. A signature, VALID string, public JSON, bare settlement ID or off-chain file alone is insufficient. Historical registered C and current D can coexist without denying C eligibility or separating holder from receipt. Keep funds frozen before trade and release only that original position.

| ID | Requirement |
| --- | --- |
| EX-ARCH-01 | Align whole-artwork backend receipt, wallet, Oracle, journal, freeze/release, rollback and audit semantics with actual contracts/schema/events/errors and evidence. Reuse first; no implied new deployment instance or migration permission. |
| EX-ARCH-02 | Route REG-DIRECT, REG-ELECTRONIC and REG-INTERMEDIARY sources to the same trade/settlement backend; Oracle remains sole raw-voucher authority. |
| EX-ARCH-03 | Implement usable frontend flows for all three source paths with source explanation, declared mint voucher format, task state and original Oracle records. Share immutable allowed-currency selection, matching, wallet authorization, ETH maximum/median disclosure and confirmation, shortage warnings/refusal, owner/holder, funds and history. No conversion or multi-currency sum. Placeholder buttons do not satisfy this requirement. |
| EX-ARCH-04 | Alignment covers whole artwork/receipt only, excluding charity fractions, shares and invented market modes. |

Missing CI route affects that candidate's CI/merge, not independent models. Missing wallet support, Oracle authority, asset-return control, gas interface, verified test-token address or target affects the respective real path only. Continue contracts, fixtures, implementation and packages independent of it. First search existing source/config/evidence; escalate only a precise genuine product/permission decision. The confirmed commodity-market UI and both collateral choices are required; undefined economic mechanisms alone remain local open items.

Additional dependencies remain local: feed access/method/specification/unit/cadence affects actual reference integration; unsupplied collateral valuation/provider/fee parameters affect only dependent mechanisms; unverified live locale behavior affects only live-alignment claims. Implement independent contracts, honest unavailable states, both collateral choices, market UI and fixed candidate language resources without waiting.

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

### DEMO-03: Registration of B is refused

Main source fixture: REG-INTERMEDIARY (source coverage must be independently verified).

Owner D, holder A; B registration refused. Unwind only unregistered AB/BC/CD, owner returns to A, original buyers refunded, actual fees separate and charged once.

Cases: T-17, T-19, T-21, T-44.

### DEMO-04: Refused registration of C preserves AB

Main source fixture: REG-DIRECT (source coverage must be independently verified).

AB registered and settled; owner D, holder B; registration of C is refused. Unwind BC/CD, owner returns to B; preserve AB registration and released principal; no issuer reset.

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
| EX-DEMO-01 | The settlement demonstration uses Ethereum Sepolia 11155111 and test ETH gas, with verified designated test PYUSD permitted by fixture NFT0 and explicitly selected by orders. Deferred cross-chain tests additionally lock Hoodi ETH on Hoodi 560048; Hoodi does not replace Sepolia settlement, its gas or principal. Do not copy unrelated Wallet configuration. |
| EX-DEMO-02 | Deliver all six revised scenarios with actual steps, state assertions and execution evidence. |
| EX-DEMO-03 | Deliver an operable trading demo, editable PPT proposal and playable film, clearly labelling real test-chain activity, simulated registrars and animation. |

Each scenario records whole receipt/account setup, mint fields/format, order sequence/prices, cap/P50 ETH/USD statistical evidence and buyer confirmation, separate cap-gas/principal freezes, actual gas/unfreeze, steps, Oracle chain records, owner/holder/prefix, every segment's funds, events/tx, UI assertions and actual failures. Include positive unexpired resumed trading and negative expired reopening. Test prices are reproducible fixtures, not commercial quotes. Read designated PYUSD from existing approved configuration; do not guess or substitute its address, claim issuer approval or imply redeemability.

## 16. Stages 0 through 5

### Stage 0: Baseline and evidence alignment

Entry: Verify current source, CI evidence and Linux execution configuration; separate bootstrap, fixtures, application and deployment.

- Resolve full branch/commit/tree and actual diff.
- Inventory existing wallet, orders, Oracle, journal, settlement and UI reuse interfaces and precise missing bindings.
- Map ArtFi whole-artwork contracts, the three source middleware routes and their actual frontend entrypoints.
- Trace requirement to test to exact source to run to artifact.

Deliverables: Baseline identity, interface map, requirement/test map and current PRD pin.

Acceptance: Independent source/evidence identity; no assertion that CI means product acceptance.

An exit condition defines the evidence required for stage acceptance.

### Stage 1: Domain state and basic interaction

Entry: Use verified source and supported Linux configuration; label fixtures wherever a real integration is absent.

- Implement complete mint declaration, whole NFT, encrypted off-chain mapping, both deadlines and voucher format; ordered owner/holder positions.
- Independent bids/asks; price/FIFO/best-price matching and replayable trusted book sequence.
- Disclose cap/P50 ETH/USD with statistical evidence and buyer confirmation. Prepaid mode freezes principal and maximum gas separately; deferred mode reserves verified collateral allowance for principal and separately freezes new-trade gas.
- Read actual wallet grant and show switch/disconnect/revocation/session loss without extra Agent approval.
- Three Oracle sources share a contract; holder follows the same authoritative record; ordered index rebuild and duplicate handling.
- Operable basic UI and whole-artwork backend alignment; separate actual, simulated and disconnected states.

Deliverables: Domain model, samples, adapter contracts, operable UI and Linux unit/state evidence.

Acceptance: All applicable Stage 1 cases including T-41..43,45..51; real freeze is never inferred from model.

An exit condition defines the evidence required for stage acceptance.

### Stage 2: Segment principal and independent settlement

Entry: Reproducible chain and registration sequence; real paths additionally require actual authority.

- For prepaid mode, freeze each buyer's own segment principal and confirmed maximum gas separately. For deferred mode, bind reserved allowance, selected-currency debt and actual escrow allocations under section 7.1. Both bind parties, asset, amount and Oracle reference.
- Never use unreleased later funds to support earlier settlement or resale.
- Release original frozen funds once owner/holder positions and timely Oracle registration make the segment eligible; eliminate its return control.
- Demonstrate AB release while BC/CD remain pending; bind original Oracle/journal/settlement coordinator.
- Recover unknown release, RPC failure, repeat events and restart by lookup before retry. Prepaid recovery creates no second buyer payment; deferred unpaid debt and recovery use section 7.1.

Deliverables: Segment escrow/settlement implementation, real/simulated binding list, reconciliation and Linux unit/integration evidence.

Acceptance: T-11..16,28,31 and applicable T-51; per-segment reconciliation; historical C/current D interpreted correctly.

An exit condition defines the evidence required for stage acceptance.

### Stage 3: Suffix rollback and buyer gas

Entry: Segment model is verified; genuine rollback needs existing authorized control and test gas path.

- If registration of B is refused with holder A, unwind the unregistered suffix; after registered AB, if registration of C is refused, unwind BC/CD only and return owner to holder B.
- Keep registered segments even while technical release is recovering; never revoke holder or reset issuer.
- Refund original buyers; actual gas and net amounts use separate explicit assets and units.
- Return NFT without intermediate-wallet traversal or reliance on ordinary wallet ETH; no duplicate full shared-operation charging.
- Recover interruption, retries, obsolete/duplicate events, insufficient budget and unknown results; do not invent late-receipt waits.
- Re-trade valid unexpired assets from recovered owner=holder; ordinary resale still permits owner ahead of holder.
- Integrate gas statistical disclosure, confirmation/cap, maximum prefreeze, actual debit, unused unfreeze and reconfirmed top-up; D-04 allocation only remains pending.
- Outside section 7.1, no gas-shortage forced sale or liquidation is executable. Gas-shortage custody and invented redemption deadlines remain excluded in all modes. The explicit deferred rollback-gas exception does not waive new-trade gas admission.

Deliverables: Rollback, fee/reconciliation records, recovery flow and Linux fault-injection evidence.

Acceptance: Applicable T-17..23,29,30,43,44,49..51; model evidence and real control/fee evidence remain distinct.

An exit condition defines the evidence required for stage acceptance.

### Stage 4: Deadline, bill transfer, restored trading and holder remint

Entry: Reproducible trading, Oracle and rollback; verifiable mint cutoffs/formats. No physical-collection or collection-driven-burn gate; authorized holder remint remains required.

- Reject new trades at cutoff and verify mint units, timezone, precision and serialized boundary semantics.
- Overdue unregistered suffix fails; return only owner to current holder; preserve registration, issuer and settled prefix.
- Resolve registration/deadline races against one authoritative ordered state; no holder-first/receipt-later, second receipt or grace stage.
- Valid unexpired unburned NFT may begin a new chain when authorized; expiry cannot be bypassed by recovery.
- Allow ordinary owner-ahead-of-holder continuous resale.
- Show full bill terms, off-chain collection obligations and Oracle/transfer history without implementing physical fulfillment or collection-driven destruction.
- Reject duplicate mapping and transfer replay; preserve history and idempotent technical recovery.

Deliverables: Deadline and suffix recovery model, bill-transfer/scope UI, boundary fixtures and resumed-trading evidence.

Acceptance: T-24,25,32,33,44,45; only applicable branch evidence; no out-of-scope fulfillment in completion.

An exit condition defines the evidence required for stage acceptance.

### Stage 5: Sepolia integration and final delivery

Entry: Affected model/integration checks and exact runtime configuration, permissions, asset control and designated test asset are verified for each real path.

- Deploy exact candidate using project-supported Linux process; absent target blocks that deployment only while packaging proceeds.
- Execute six revised scenarios on Sepolia 11155111 with actual chain records and explicitly simulated registrars, never Hoodi settlement substitution; use Hoodi only as the explicit deferred collateral source.
- Cover all three source/Oracle contracts and record each scenario's chosen main source.
- Verify whole-artwork backend alignment, each middleware route and frontend; join actual Oracle, funds and UI evidence.
- Generate demo, editable PPT and playable film from final verified demo; distinguish real chain, simulated institutional roles and animation.
- Independently verify exact head CI, same-version artifact and actually served version; package identity is not deployment evidence.

Deliverables: Accessible demo, deployment receipt, six scenario results, three-source coverage, tests/security results, PPT, film and remaining issues.

Acceptance: All six scenarios and complete evidence chain; deployment/runtime/chain/product verdicts separate; NOT_RUN for absent operations.

An exit condition defines the evidence required for stage acceptance.

Stage 4 also includes authorized holder replacement mint: possession plus holder=owner, atomic old burn/new mint, editable new terms, retained old/new history and UNKNOWN/concurrency recovery. No extra cleanup/refund/unfreeze/migration approval gate is introduced. Ordinary transfer remains independent of holder equality, gap closure and current finality. Stage 5 integrates T-52 through T-68 with all source paths and real evidence.

Stage 0 also verifies v1.5 document identity, current design and exact base, protects valid concurrent increments, and identifies feed/locale/parameter gaps without making global gates. Historical v1.3 loaders/locks cannot certify v1.5 or inherit acceptance.

Stage 1 additionally implements the full commodity/crypto market, individual quote cards and gap details, complete identity-free signed-business-terms projections, actual independent positions and per-position signature evidence, long-chain interactions, six candidate languages, real reference adapter/freshness states, both collateral choices and ordinary market-maker participation. T-69..84 apply where relevant; actual feed/browser evidence stays NOT_RUN/NOT_VERIFIED until genuinely obtained. A missing feed cannot stop independent trading or registration work.

Stage 5 additionally supplies real UI/data evidence for T-69..84: continuous source reading/refresh/failure recovery, simulation separation, individual gap/terms/positions/signatures/privacy, six-language responsive navigation, market-maker ordering and both collateral scenarios. Only the section 7.1 deferred mechanism is confirmed; unsupplied execution/provider/fee parameters remain explicitly open. A model, design or historical loader pass cannot replace these results.

## 17. Acceptance matrix

The complete matrix retains T-01 through T-68 with revised semantics and extends through T-96, including the scoped deferred-mode cases T-85..96. A row is an obligation, not a passing result. Parameterized/property cases may cover multiple rows. First stage is the latest initial inclusion point, not a prohibition on earlier work. Preserve exact source/run/evidence; never inherit historical green into revised assertions.

| Case | Assertion | Requirements | First stage / later integration |
| --- | --- | --- | --- |
| T-01 | One NFT is one whole receipt; preserve full receipt and underlying goods quantity; reject fractions and duplicate mappings. | EX-SCOPE-02 / EX-INV-02 / EX-MINT-01 | 1 |
| T-02 | Initial equality and subsequent independent positions are accurate. ownerOf is an address, not a position; currentEntry latest admission and holderAsOf historical effective holder are distinct; future effectiveAt is not current effectiveness. | EX-SCOPE-03 | 1 |
| T-03 | Record A to B to C to D in order, with a separate registration request for every hop. | EX-INV-01 / EX-INV-05 | 1 |
| T-04 | Sequential EX/Oracle registration remains contiguous and replayable without skipping or a second receipt. Protocol versions are contiguous and effectiveAt strictly increases; same-holder confirmation is valid. Version, transfer count and holderPosition never substitute for one another. | EX-INV-03 / EX-INV-05 / EX-INV-11 | 1 |
| T-05 | Consume the same Oracle record idempotently; reject different content under the same identity; no second business receipt. | EX-INV-04 / EX-INV-05 / EX-INV-11 | 1 |
| T-06 | Reject absent, expired, revoked or altered asset, amount or chain-domain authorization. | EX-AUTH-01 / EX-AUTH-02 / EX-AUTH-04 | 1 |
| T-07 | Reject nonce replay; concurrent transfers to two buyers advance only one valid head. | EX-INV-01 / EX-INV-06 | 1 |
| T-08 | Account switching, disconnect or lost session must not reuse the previous account's authorization. | EX-AUTH-01 / EX-AUTH-03 | 1 |
| T-09 | Independently submitted bids and asks follow price priority, equal-price FIFO and best executable price; no queue jumping, altered limits or specified-counterparty substitution. | EX-MATCH-01 / EX-INV-12 | 1 |
| T-10 | All three Oracle adapters satisfy one registration contract using mint-declared formats; holder follows the same receipt; simulated roles are labelled. | EX-INV-05 / EX-SCOPE-09 / EX-MINT-05 | 1 |
| T-11 | Prepaid-mode regression: Principal uses the explicit selected member of the immutable NFT0 set through freeze/release/refund. Refuse missing/changed currency, conversion/substitution and insufficient/unknown selected-currency balance even with sufficient ETH gas. Freeze each liability separately before trade; no second principal debit after registration. | EX-SETTLE-01 / EX-SETTLE-05 | 2 |
| T-12 | Release eligible AB without waiting for C or D. | EX-SETTLE-02 / EX-INV-03 | 2 |
| T-13 | Prepaid-mode regression: Keep every segment's price and funds separate; pending later funds cannot subsidize an earlier release. | EX-SETTLE-01 / EX-SETTLE-03 | 2 |
| T-14 | Reject wrong asset/segment/journal/network/source and bind chain/token contract/tokenId/registerId/verificationProfile/authority to the remote finalized record. Any account may relay valid proof; caller allowlists and ordinary signatures do not replace proof verification. | EX-INV-05 / EX-SETTLE-04 | 2 |
| T-15 | Historical C and current D coexist correctly. Historical finality holds first.effectiveAt <= t < latest.effectiveAt; latest and later remain provisional. Earlier-than-first holderAsOf/entryAsOf revert and isFinalAsOf is false. Cancellation adds no finality; EX prefix completion is distinct. | EX-SETTLE-04 | 2 |
| T-16 | Recover unknown RPC or execution results for release of already frozen funds idempotently; no new buyer-payment business failure, duplicate debit or gas charge. | EX-SETTLE-05 / EX-INV-04 / EX-NFR-04 | 2 |
| T-17 | When registration of B is refused and holder is A, refund the unregistered suffix and return owner to A; holder stays A and the NFT is not burned. | EX-ROLLBACK-01 / EX-ROLLBACK-05 | 3 |
| T-18 | When AB is registered and registration of C is refused, withdraw BC/CD only and return owner to effective holder B; keep registration and settled AB; never reset to issuer. | EX-ROLLBACK-02 / EX-INV-03 / EX-INV-08 | 3 |
| T-19 | Return each segment's unreleased principal to its original buyer; show actual gas and net proceeds with explicit units. | EX-GAS-01 / EX-ROLLBACK-03 / EX-SETTLE-06 | 3 |
| T-20 | Intermediate wallets with zero ordinary ETH do not change recovery duties or require serial wallet-by-wallet NFT return. | EX-ROLLBACK-04 / EX-GAS-07 / EX-GAS-10 | 3 |
| T-21 | One shared operation must not be charged in full to multiple segments. | EX-GAS-02 | 3 |
| T-22 | Prepaid-mode freeze/shortage regression; deferred-mode allowance and recovery follow section 7.1, while currency identity and separate new-trade ETH gas checks remain unchanged. ETH is the sole gas asset. Zero/insufficient/unverified applicable ETH warns and refuses new trading even if price funds suffice; selected-currency shortage also refuses. Original sufficient frozen gas remains usable for its approved recovery without second prepayment or double counting. | EX-GAS-03 | 3 |
| T-23 | Resume crashed rollback without duplicate refunds/gas or revival of failed segments. cancelSettlement is not refund/owner return/registration reversal; enforce recorded initiator and strict protocol deadline independently. Gap closure cannot fabricate refusal or completion. | EX-INV-04 / EX-INV-07 / EX-TIME-03 | 3 |
| T-24 | Honor mint time units and boundaries; refuse new trades after cutoff; overdue unregistered suffix fails and owner returns to effective holder; preserve registered and settled prefix. | EX-TIME-01 / EX-TIME-02 / EX-TIME-03 | 4 |
| T-25 | EX transfers the bill of lading without physical collection, transport, warehouse exit or collection-driven burn. Terms remain readable; owner ahead of holder may resell. Authorized atomic holder remint is separately covered by T63-68. | EX-SCOPE-08 / EX-EXIT-01 / EX-INV-08 / EX-SCOPE-12 | 4 |
| T-26 | Separate simulated/real, pending/complete, owner/holder, NONE/OPEN/ADMITTED/CANCELLED/SUPERSEDED, historical provisional/final, Oracle application refusal, admission and funds. No protocol REJECTED or overall-complete inference from NO/green. | EX-NFR-05 | 1 |
| T-27 | Record exact source/config/run/commands/fixtures for GitHub Actions CI or the project-supported Linux configuration, as applicable. CI validates only checks actually run; it does not prove deployment or live-chain acceptance. | EX-NFR-01 / EX-NFR-07 | 1 |
| T-28 | On duplicate consumption, restart or unknown freeze/release/refund, query before retry; never duplicate funds or gas actions. | EX-NFR-03 / EX-NFR-04 / EX-SETTLE-05 | 2 |
| T-29 | Reject rollback without sufficient authority; no arbitrary confiscation or rewriting a finalized prefix. | EX-SCOPE-07 / EX-NFR-10 | 3 |
| T-30 | Recover reorg, duplicate logs, RPC timeout and reordered events without early or repeated release. | EX-INV-10 / EX-NFR-03 | 3 |
| T-31 | Release and refund are mutually exclusive; reconcile segment principal, fees and final balances. | EX-INV-04 / EX-SETTLE-03 | 2 |
| T-32 | Trace bill-of-lading terms, original Oracle registration, holder and funds. Physical collection or collection-driven destruction is not completion; authorized remint separately preserves old/new NFT links and existing evidence. | EX-EXIT-02 / EX-EXIT-03 / EX-SCOPE-09 / EX-REMINT-04 | 4 / 5 |
| T-33 | Reject duplicate valid mappings, transfer replay and repeated funds actions; failed old segments stay dead, valid NFTs can start a new chain, history remains. | EX-EXIT-03 / EX-ROLLBACK-05 | 4 |
| T-34 | Agent actions already authorized in the wallet need no extra platform step approval; refuse out-of-scope actions. | EX-AUTH-01 / EX-AUTH-05 | 1 |
| T-35 | Sepolia remains the execution/principal chain with verified NFT0-permitted selected PYUSD and test ETH gas. Reject accidental chain/asset substitution; allow Hoodi only for the separately specified deferred collateral source, never as settlement or gas replacement. | EX-DEMO-01 / EX-SCOPE-11 / EX-GAS-09 | 5 |
| T-36 | All six scenarios have matching actual transactions, simulated registration evidence, UI states and final assertions. | EX-DEMO-02 | 5 |
| T-37 | Demo, PPT and playable film consistently label real test-chain actions, simulated roles and animation; no implied institutional cooperation. | EX-DEMO-03 | 5 |
| T-38 | Required CI belongs to exact head; actual deployed commit matches; read back artifact bytes and hashes. | EX-NFR-07 | 5 |
| T-39 | Verify that receipt-access secrets and wallet private keys are absent from product outputs, logs, chain data and NFT metadata; product documentation is in English. | EX-NFR-06 / EX-NFR-09 | 0 |
| T-40 | Record real resource and performance baselines and diagnosable errors; no invented production SLA. | EX-NFR-05 / EX-NFR-08 | 0 |
| T-41 | Mint complete asset-specific receipt data, terms, both cutoffs and time semantics; reject missing required fields; do not copy unrelated commodity rules. | EX-MINT-01 / EX-MINT-02 / EX-MINT-04 / EX-MINT-06 | 1 |
| T-42 | Encrypt receipt-access secrets only in controlled off-chain storage; NFT has only opaque nonsecret mapping; no wallet private keys held by EX. | EX-MINT-03 / EX-NFR-06 | 1 |
| T-43 | Before trade show both cap and median in ETH and contemporaneous USD with source, time, scope and buyer confirmation; unavailable quote, FX or confirmation blocks submission; no fake zero. | EX-GAS-04 / EX-GAS-05 / EX-GAS-06 | 1 / 3 |
| T-44 | Rollback aligns owner only to effective holder; unexpired valid NFT may trade again, expired NFT stays closed; ordinary owner-ahead-of-holder resale remains allowed. | EX-ROLLBACK-05 / EX-INV-08 / EX-TIME-01 | 3 / 4 |
| T-45 | The voucher is the one receipt; Oracle alone ingests/verifies/writes it and holder follows it. No EX raw intake, independent holder writer, second receipt or late wait. Proof validates the accepted profile's remote finalized record, not legal title/source honesty/goods/payment; expectedHolder/initiator do not prove admitted holder. | EX-SCOPE-09 / EX-MINT-05 / EX-INV-11 / EX-TIME-03 | 1 / 4 |
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
| T-56 | Sufficient original frozen ETH for the same approved rollback obligation remains usable with zero unfrozen cash. No second prepayment, early unfreeze or cancelled rollback. A remaining shortage uses the original confirmed replenishment flow in prepaid mode; deferred rollback may use the explicitly authorized collateral gas-recovery route in section 7.1. | EX-ROLLBACK-04 / EX-GAS-05 / EX-GAS-07 / EX-GAS-08 | 3 / 5 |
| T-57 | Prepaid-mode freeze/shortage regression; deferred-mode allowance and recovery follow section 7.1, while currency identity and separate new-trade ETH gas checks remain unchanged. Each order selects one immutable NFT0-allowed currency; both intents and leg freeze/release/refund match it. Wrong currency refuses consistently across three sources and UI/API/Agent, without conversion or substitution. | EX-SCOPE-11 / EX-MINT-07 / EX-MATCH-01 / EX-SETTLE-06 / EX-INV-13 | 1 / 2 / 3 / 5 |
| T-58 | Absent, conflicting, changed or unverifiable NFT0 currencies or an order without explicit selection refuse. No ETH/PYUSD default or balance-based automatic choice. PYUSD fixtures require mint-time membership and explicit selection. | EX-MINT-07 / EX-SCOPE-11 / EX-DEMO-01 | 1 / 5 |
| T-59 | When selected principal is ETH, independently cover and account for principal and maximum gas. Refuse coverage of only one or counting the same balance/freeze twice. Reconcile principal refund and unused gas separately without restoring consumed gas. | EX-SETTLE-06 / EX-SETTLE-07 / EX-GAS-07 / EX-GAS-08 / EX-INV-13 | 1 / 2 / 3 |
| T-60 | Mint-time one-currency and multiple-currency sets are recorded/read correctly. No later UI/API/Agent/contract/admin path can add, remove or replace the same NFT set. Valid remint creates a new NFT while atomically burning the old one. | EX-MINT-07 / EX-SCOPE-11 / EX-INV-13 / EX-REMINT-03 | 1 / 4 / 5 |
| T-61 | Prepaid-mode regression: Warn and refuse selected-currency principal at zero or one smallest unit short before signing/broadcast, despite sufficient other currencies/gas. Exact sufficiency may proceed under other conditions. Exclude concurrent reservations; reuse only this operation own effective freeze. | EX-SETTLE-07 / EX-SETTLE-06 / EX-GAS-07 / EX-INV-13 | 1 / 2 / 3 / 5 |
| T-62 | For multiple allowed currencies, both orders select the same currency; verify price priority/FIFO/best executable price independently inside each currency. No raw cross-currency numeric comparison, FX ranking, mixed principal sum or automatic conversion. | EX-MATCH-01 / EX-SCOPE-11 / EX-SETTLE-06 / EX-INV-12 | 1 / 5 |
| T-63 | A holder possessing the original NFT with holder equal to owner may remint under valid existing wallet authority. Refuse non-holder, no possession, unequal owner, admin-only identity and invalid/revoked/replayed authority. | EX-REMINT-01 / EX-AUTH-01 / EX-AUTH-04 | 4 / 5 |
| T-64 | Successful remint atomically burns the old NFT and validly mints the new one. Failure of either leaves no one-sided asset loss or two simultaneously valid bills; retain same-operation evidence. | EX-REMINT-02 / EX-INV-14 | 4 / 5 |
| T-65 | Before new mint holder may add/remove/change new terms including allowed currencies; preserve old terms/history. New minted currencies become immutable. New terms cannot bypass ETH gas, no-conversion, Oracle or authority boundaries. | EX-REMINT-03 / EX-MINT-07 / EX-GAS-09 | 4 / 5 |
| T-66 | Remint concurrent with trade/registration atomically rechecks possession and holder equal to owner, yielding one valid result. Duplicate/RPC-timeout/failed/UNKNOWN requests reconcile and recover idempotently, never repeating burn/mint/debit. | EX-REMINT-05 / EX-INV-04 / EX-INV-14 | 4 / 5 |
| T-67 | Read old/new NFT links both ways, term differences and original registration/trade/funds evidence. A burned predecessor cannot trade/remint again. New terms cannot delete or rewrite completed history. | EX-REMINT-04 / EX-SCOPE-12 / EX-INV-14 | 4 / 5 |
| T-68 | Possession and holder equality establish the confirmed EX remint business predicate with existing authority; no cleanup/refund/unfreeze/migration approval. Address equality is not an ERC proof of no gap/escrow/tasks and cannot block ordinary owner-ahead-of-holder resale. | EX-REMINT-01 / EX-INV-08 / EX-SCOPE-03 | 4 / 5 |
| T-69 | Market is an ordinary commodity spot-intermediary infrastructure DEMO with crypto/commodity styling, BTC/ETH and soybean/iron-ore scenes and simulation labels; no real financial or institutional endorsement. | EX-SCOPE-01 / EX-SCOPE-13 | 1 / 5 |
| T-70 | Both crypto and warehouse NFTs are selectable collateral. Do not invent valuation/LTV/financing/liquidation/returns; undefined mechanisms affect only dependent actions while core spot work continues. | EX-SCOPE-14 / D-14 | 1 / 5 |
| T-71 | Continuously read/update actual external spot sources with traceable successful reads and source changes. Separate source/fetch times faithfully, preserving precision; static designs/manual values cannot pass actual integration. | EX-SCOPE-15 / EX-PRICE-01 / EX-PRICE-02 | 1 / 5 |
| T-72 | Show provider/currency/unit/specification/market/priceType/as-of/fetch/delay. Reproduce stale/unavailable/parse failure/recovery honestly without fake zero, per-second-source claims or silent futures/unit substitution. | EX-PRICE-02 / EX-PRICE-03 / EX-PRICE-04 | 1 / 5 |
| T-73 | Each NFT has independent quote/status and correct click/keyboard/back/switch detail navigation. Only supported successful openGapOf nonzero/zero bytes32 maps to openGapOF=YES red/NO green. Unsupported/unknown/loading/error never maps to NO/green, another NFT's state or inferred positions. | EX-UI-01 | 1 / 5 |
| T-74 | Show all business conditions completely in an identity-excluding projection without summary or changed obligations. Keep unchanged complete private originals for hash/signature checks; never render identity-bearing originals or claim projection byte identity. Missing/placeholders fail completeness; locale explanation is informative. | EX-UI-04 / EX-MINT-01 / EX-EXIT-01 | 1 / 5 |
| T-75 | Bind current/owner/holder independently to actual records on one timeline; 8/7/1 is a fixture. Cover equality, divergence, long chains and unknown values without hardcoded offsets or merged markers. | EX-UI-02 | 1 / 5 |
| T-76 | Every signature status binds its position/transfer, role, payload, applicable scheme version/domain/nonce or equivalent and verification. Distinguish unknown/unsigned/pending/signed and transaction/order/registration-proof/admission; never infer signing from alignment, chain length or proof success or move historic signatures to current owner. | EX-UI-02 / EX-NFR-11 | 1 / 5 |
| T-77 | No wallet names or full/truncated addresses across cards/details/terms/embeddings/popups/hover/title/accessibility/download/copy. Raw documents/JSON/metadata cannot leak identities. Backend originals/hash/signature/authority stay intact; add no identity permission prompt. | EX-UI-03 / EX-SCOPE-17 | 1 / 5 |
| T-78 | openGapOF=YES red and owner!=holder do not automatically block ordinary transfers. Independent deadline/principal/gas/authority reasons remain accurate; remint qualification remains separate. | EX-UI-05 / EX-SCOPE-03 / EX-REMINT-01 | 1 / 5 |
| T-79 | Market makers and ordinary participants follow same-currency price/FIFO without identity priority, selected-counterparty bypass or default AMM/rebate/incentive/return promises. | EX-SCOPE-16 / EX-MATCH-01 / EX-MATCH-02 | 1 / 5 |
| T-80 | All six candidate languages cover markets/cards/terms/timeline/unknown/errors/principal/gas without mixed language or clipping. Preserve protocol identifiers and exact openGapOF=YES/NO with YES red/NO green; unknown stays unknown and original signed language remains unchanged. | EX-SCOPE-18 / EX-I18N-01 / EX-I18N-02 / EX-I18N-03 | 1 / 5 |
| T-81 | No wallet asset/account/security/validator/Agent-permission-management routes; per-trade authority, balance/freeze and gas confirmation remain enforced. | EX-UI-06 / EX-AUTH-01 / EX-GAS-10 | 1 / 5 |
| T-82 | Separate external references, simulated NFT quotes/trades and real chain evidence. A per-tonne reference cannot replace whole-receipt price or trigger FX-based cross-currency matching/payment/gas conversion. | EX-PRICE-04 / EX-MATCH-01 / EX-SCOPE-11 | 1 / 5 |
| T-83 | Documents/design/code/runtime have independent identities. v1.5 cannot inherit a historical loader pass or clickable design as runtime acceptance; preserve T-01..68, six stages/demos and the current product edition. | EX-NFR-09 / Section 18 | 0 / all |
| T-84 | Responsive market/details navigation and loading/error/empty/long-chain states recover; all three sources share real states and six-language rules. Missing feed/original terms stays explicit, never overall-complete. | EX-ARCH-03 / EX-UI-01 / EX-UI-04 / EX-PRICE-03 / EX-I18N-02 | 1 / 5 |
| T-85 | Deferred mode is optional and seller-consented, with an exact T+n deadline or 72 hours before the registration deadline; retain prepaid mode. Only NFT0-allowed USD stablecoins may be principal. EX grants secured trading allowance, not a cash loan, and charges no interest spread. | EX-DEFER-01 | 1 / 5 |
| T-86 | Accept BTC/ETH as product collateral; test only Hoodi ETH collateral with Sepolia PYUSD principal and Sepolia ETH gas. Hoodi operations need separately accounted Hoodi gas. No unimplemented Bitcoin custody or cross-chain bridge is inferred. | EX-DEFER-02 | 1 / 5 |
| T-87 | Verify canonical finalized collateral lock evidence and its chain, vault, asset, borrower, amount and unique identity before granting destination allowance. Authenticated proof validation, valuation freshness/denomination and explicit ratio policy are required; 50 percent is only an example. | EX-DEFER-03 | 1 / 5 |
| T-88 | Reserve collateral-backed allowance per obligation atomically and durably; reject duplicate pledges, replay, conflicting observations and concurrent over-allocation. A UI balance or caller verified flag is not authority. | EX-DEFER-04 | 1 / 5 |
| T-89 | For A-B-C, B may resell before paying A. C's principal enters B's escrow, with original refundable segment encumbrances preserved and no double allocation. B may deposit the correctly denominated difference before the agreed deadline. | EX-DEFER-05 | 1 / 5 |
| T-90 | If the settlement deadline arrives before AB registration completes, treat AB as incomplete and initiate the existing eligible rollback, preserving registered prefix. Do not extend the payment wait or pay A as if registration succeeded. | EX-DEFER-06 | 1 / 5 |
| T-91 | If AB registration completes first, its NFT rollback responsibility permanently detaches under the original ordered-cut rule even if A is unpaid. B independently owes A; later debt, liquidation or payment failure cannot reverse that completed cut or make C responsible. | EX-DEFER-07 | 1 / 5 |
| T-92 | Allow early manual settlement only with the original registration and authorization conditions. At registered-debt maturity, settle from available B escrow; liquidate pledged collateral for a remaining shortfall. No automatic unapproved margin-call threshold or guaranteed recovery is added. | EX-DEFER-08 | 1 / 5 |
| T-93 | When B cannot fund gas needed for eligible rollback, allow collateral liquidation to cover that verified gas shortfall. Keep debt principal, fee, Sepolia recovery gas, Hoodi execution gas and residual collateral separate; do not treat Hoodi ETH as Sepolia gas. | EX-DEFER-09 | 1 / 5 |
| T-94 | Liquidation request, source execution and destination receipt are distinct. Only verified destination PYUSD satisfies seller-payment funds; only verified destination ETH satisfies recovery-gas funding. Missing liquidity/provider, partial proceeds or unknown outcome remain unresolved, never fabricated conversion. | EX-DEFER-10 | 1 / 5 |
| T-95 | Persist operation identity, exact payload and reservation before dispatch; reconcile ambiguous outcomes without blind replay. Confirm actual payment/refund/release once, preserve restart/concurrency safety and prohibit collateral unlock while secured obligations or unknown effects remain. | EX-DEFER-11 | 1 / 5 |
| T-96 | Reuse existing UI rather than create a duplicate. Bind implementation, exact-head CI and main merge to the module contract before downstream wiring/testing/deployment acceptance. Report simulation, CI, actual cross-chain and served acceptance separately. | EX-DEFER-12 | 1 / 5 |


## 18. Engineering delivery and exact-source acceptance

Each candidate records repository/branch/full commit/tree/parent/base and exact diff; PRD edition/digest and requirements; missing implementation and NOT_RUN operations; actual Linux runtime/path/commands/config/run/timestamps/exits; test counts/results and complete logs; artifact bytes/SHA/source/storage; deployment target/served version/URL/start/health/recovery or explicit not-deployed; actual chain/addresses/tx/EVM receipts/blocks/confirmation/Oracle events; and per-segment principal/gas/owner/holder/recovery reconciliation.

Gas evidence includes original cap/P50 ETH/USD with samples and FX, buyer confirmation/reconfirmation, maximum prefreeze, actual costs and unused unfreeze. Record NFT validity and resumed-trading eligibility. Record whole-artwork backend contract alignment and source-route/Oracle/UI coverage. A candidate's own success is not independent acceptance; preserve trusted controller, exact identity, expiry and artifact/log verification.

Required checks and relevant acceptance must match the exact current head. A changed head needs fresh exact-head verification; historical green, short SHA and screenshots cannot substitute.

This edition is the English product and acceptance contract.

## 19. Decisions and local gates

Confirmed or removed requirements cannot remain open-choice blockers. Only the stated affected path waits.

| ID | Status | Current rule | Narrow dependency |
| --- | --- | --- | --- |
| D-01 | CONFIRMED | Price priority, equal-price FIFO and best executable price; no specified-counterparty queue priority. | No product decision remains; validate the matching implementation. |
| D-02 | ENGINEERING_VERIFICATION | Complete asset-specific receipt/mint data, encrypted off-chain secret mapping, both cutoffs and declared registration format are fixed. | Only unresolved actual schema, serialization or controlled-store bindings. |
| D-03 | CONFIRMED | Overdue unregistered suffix fails at cutoff; return owner to effective holder and preserve prefix; no late-receipt grace. | Verify actual time, Oracle ordering and concurrency boundaries; not a new product choice. |
| D-04 | PARTIALLY_PENDING | Cap/P50 ETH and contemporaneous USD, confirmation, cap-sized freeze, actual debit and unused unfreeze are fixed. | Only allocation of one genuinely shared operation remains a product decision; actual send/payment interfaces require engineering verification. |
| D-05 | ENGINEERING_VERIFICATION | Real owner return uses existing authorized asset control and wallet grant. | Only actual rollback lacking verified authority or interface; models and settled business rules proceed. |
| D-06 | CONFIRMED | Prepaid mode freezes principal before trade and registration releases that position without a second payment. The separately selected deferred mode follows section 7.1: collateral allowance, registration-independent B debt, exact deadline and recovery rules. | Implementation and exact-version acceptance remain; no EX lending obligation is added. |
| D-07 | CONFIRMED | Physical fulfillment remains outside EX; holder possession/equality, authorized atomic remint and new terms are in scope without additional cleanup/migration decisions. | No physical-delivery gate; implement confirmed remint. |
| D-08 | ENGINEERING_VERIFICATION | Bind original Oracle source, journal, asset, segment and actual deployment interfaces. | Only the concrete missing integration path; other paths proceed. |
| D-09 | ENGINEERING_VERIFICATION | Verify wallet compatibility from real semantics and interfaces. | Only unverified wallet execution; supported paths and contract checks proceed. |
| D-10 | PARKED | Agent service-fee mechanism, rate, timing, bearer and refunds. | Commercial charging only; all core stages and fee-free demo proceed. |
| D-11 | PARKED | Real commercial asset classes, cooperation, registrars and admission. | Later real business expansion only; three simulated sources proceed. |
| D-12 | PARKED | Commercial pricing, revenue, funding, operations and legal path. | Later commercial or outward commitments only; authorized test development proceeds. |
| D-13 | RESERVED | No product decision is assigned to this identifier. | No product dependency. |

A funded account is not a gas-policy decision; a token/provider interface is not wallet semantic acceptance. No new device lock, remote-attestation or pre-funded account is presumed. Later valid authorization is retained with its actual scope; a version change alone does not revoke it.

| ID | Status | Current rule | Narrow dependency |
| --- | --- | --- | --- |
| D-14 | PARTLY_CONFIRMED | Crypto and warehouse-NFT choices remain. Section 7.1 confirms optional BTC/ETH-backed deferred stablecoin settlement, deadline debt liquidation and rollback-gas recovery, without EX lending. Exact ratio, valuation/finality/provider and fee parameters must be explicitly configured; no invented defaults or returns. | Only unsupplied dependent mechanisms; do not block independent spot/UI work. |
| D-15 | ENGINEERING_OPEN | Continuous references are confirmed; verify actual permitted feed method/endpoints/display rights/cadence. Public pages do not prove integration. | Actual provider integration/acceptance only; contracts and unavailable-state UI continue. |
| D-16 | ENGINEERING_VERIFICATION | Verify live six-language alignment safely; source candidates en/zh-Hans/zh-Hant/fr/es/ja remain implementable. | Unverified live-alignment claim only, not independent delivery. |

## 20. Source and decision traceability

This edition preserves the complete v1.4 baseline and adds the 2026-10-20 deferred cross-chain collateral requirements, including deadline-first rollback and recovery-gas liquidation. GitHub Actions is permitted for CI.

| Source group | Preserved product scope |
| --- | --- |
| SRC-01 / SRC-01B | Original whole-receipt, owner/holder, registration, segment escrow, suffix rollback, gas, deadlines and six demonstrations; the two source formats are not different product versions. |
| SRC-02 / SRC-04 / SRC-09 | Infrastructure, compatible-wallet, whole-artwork reuse, authority/journal/segment binding and role boundaries. |
| SRC-03 / SRC-05 / SRC-06 | Historical baseline and source-bound CI evidence only, never current acceptance. |
| SRC-07 / SRC-10 | Complete staged delivery; matching, mint, deadlines, gas, original freezes, bill-transfer scope, return to effective holder and Oracle-only receipt. |
| SRC-08 / SRC-10P | Historical document delivery provenance. |
| SRC-10B | Whole-artwork backend alignment and direct/electronic/intermediary transaction sources, not new trading modes. |
| SRC-10C / SRC-10D | Buyer-confirmed cap/P50, maximum prefreeze, actual consumption/unused refund and ETH-only gas with zero/insufficient-ETH refusal. |
| SRC-10E | Non-Windows execution and GitHub Actions CI. |
| SRC-10F / SRC-10G / SRC-10H | Immutable one/multiple NFT0 currencies, explicit per-order selection, selected-currency shortage refusal and no conversion. |
| SRC-10I | Independent QA/CI acceptance and exact-source required checks. |
| SRC-10J / SRC-10K / SRC-10L | Authorized holder possession/equality remint, atomic old burn/new mint, editable new terms, no added cleanup/migration/product approval. |
| SRC-10M | Commodity spot-intermediary DEMO, crypto/commodity styling, BTC/ETH/soybean/iron-ore scenes, both collateral classes and ordinary market makers. |
| SRC-10N / SRC-10O | Individual NFT states/full terms/independent positions/signatures/privacy, continuous public references, six languages and excluded wallet-management UI. |
| SRC-10Q | Exact openGapOF=YES red / openGapOF=NO green display, with unknown preserved. |
| SRC-10R | Correct protocol getters, timing/finality/gap/admission/proof/signature boundaries without new business gates. |
| SRC-11 / SRC-12 | [CME spot rules](https://www.cmegroup.com/rulebook/CME/I/12.pdf) and [Direct Auction FIFO reference](https://www.cmegroup.com/content/dam/cmegroup/education/files/cme-direct-auction-dairy-user-manual.pdf); only already confirmed spot principles and applicable receipt specifications, not imported commercial rules. |
| SRC-13 / SRC-13B / SRC-13C | Complete historical v1.0/v1.2/v1.3 lineage; v1.4 preserves nonconflicting requirements and extends T-68 to T-84. Historical hashes do not certify this edition. |
| SRC-14 | [ERC-8415 fixed Draft](https://github.com/GiraffeTechnology/ERCs/blob/12e68aee54c6f94f6910d4db42f1d5677b506de1/ERCS/erc-8415.md). It is a Draft, not a claim of final adoption or implemented compliance. |
| SRC-15 | Public commodity source/service references in section 11.1; access rights and actual integration remain separately verified. |
| SRC-16 / SRC-17 | Existing design and document/source revision provenance, not code/runtime acceptance; exact current candidates must be independently verified. |

Outside the expressly scoped section 7.1 deferred mode, conflicting old minimum-console-only, no-market-maker, agriculture-later, collateral-placeholder-only, physical-collection/burn, second-payment, second-receipt, late-grace and forced-sale mechanisms are retired. Wallet-only ALL ON or generalized multichain defaults are not silently imported into EX.

## 21. Definition of done

Complete only when all six revised scenarios, all three explicitly simulated Oracle sources, complete whole-receipt mint, price/FIFO matching, per-segment original-funds release, bounded suffix rollback, cutoff/bill-transfer boundary and eligible resumed trading have reproducible evidence. Verify real cap/P50 ETH/USD, samples, buyer confirmation/reconfirmation, maximum gas freeze, actual debit and unused unfreeze within confirmed cap and separate from principal. Match demo/PPT/playable film, exact code/config, actual Linux deployment, Sepolia observations and execution records. Whole-artwork alignment, operable middleware/frontend for all sources and T-46..48 must pass. Missing applicable evidence keeps delivery OPEN.

Physical collection, transport, warehouse exit and collection-driven NFT destruction are not completion conditions. Authorized atomic holder remint, immutable allowed-currency selection and separate ETH gas/price coverage remain required by T-52 through T-68. Completion does not imply real warehouses/institutions admitted, cooperation, licenses, commercial fees, mainnet deployment or acceptance of new human financial/legal obligations. Parked items affect only genuinely dependent later work.

The v1.4 completion scope additionally requires all applicable T-69..84: operable crypto/commodity and both collateral scenes, ordinary market-maker ordering, continuous actual public references with traceable freshness isolated from simulated orders, independent NFT gap/detail navigation, complete identity-free business terms verified against unchanged private originals, actual independent positions and role-bound signatures, no frontend wallet identities, and complete responsive six-language interaction. Undefined financing/valuation/liquidation/revenue parameters stay local and cannot be fabricated into completion. No document edit or CI-only result proves these outcomes.

The deferred module additionally requires T-85..96, exact cross-chain lock and destination-receipt evidence, independent registered-cut/debt behavior, gas-shortfall recovery, durable reconciliation and existing UI wiring. Code and CI alone do not establish these runtime outcomes.

## Appendix A: migration coverage

Coverage preserves sections 1..21, all six stages/demonstrations, all 111 prior requirement IDs plus EX-DEFER-01..12, T-01..96 and D-01..16. Conflicting old assertions are replaced in their applicable requirements and acceptance cases. Historical machine plans/locks must be reconciled separately and cannot certify this revision; no historical run inherits a revised-case PASS.

This v1.5 edition contains 123 EX-* requirement rows and T-01 through T-96, preserving the prior 111 requirements and T-01 through T-84, all D-01 through D-16, sections 1 through 21, Stage 0 through Stage 5 and DEMO-01 through DEMO-06. No product runtime test, deployment or on-chain action is evidenced by this publication.
