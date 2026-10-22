# Deferred module runtime contract

This source candidate retains the original deferred accounting, aggregate checkpoint and two-chain Wallet ports. It does not deploy a vault, select credentials, create liquidity or establish runtime acceptance. V1.5 remains isolated from V1.4/main even after successful CI. The complete PRD remains unchanged.

## Evidence and denomination

Only the configured trusted EvidenceVerifier can produce canonical Fact records. It must authenticate original source, finality, exact profile, asset, parties, operation, location and native identity. HTTP flags, symbols, RPC reachability and ordinary relay signatures are not proof. The caller cannot rename one native event into multiple receipts.

Principal alone consumes the stablecoin-denominated allowance and determines seller debt. The upfront settlement fee is ETH wei, not PYUSD principal. Source-native execution costs, destination proceeds, penalties and residual collateral remain separate. The test profile is Sepolia PYUSD principal, Sepolia ETH gas and Hoodi ETH collateral with independent Hoodi gas. No asset bridge or production Bitcoin capability is inferred.

## Upfront fee and normal funding

Reservation requires five authenticated facts bound to complete terms: seller consent, borrower admission, actual ETH fee receipt, original Sepolia normal-gas allocation and independent original Hoodi normal-gas allocation. The profile explicitly names the fee receiver. Each native funding descriptor binds its payer, budget, quote, canonical scope, grant, location, cap and observation validity.

The verifier must establish that both original allocations are actually funded, exclusively assigned, not already spent or unfrozen, authorized for their normal action scope and covered by the agreed commercial fee. A historical allocation alone is insufficient. Sepolia ETH is not Hoodi ETH; this module neither sums the two balances nor performs a conversion. Actual original source-native funding is required independently.

All checks precede obligation, evidence and principal-reservation mutation. Exact replay of recorded terms and the same evidence returns the existing obligation. Changed evidence under the same identity is refused. Lost save acknowledgement is reconciled through the original identity and generation, never a new request ID.

The candidate accepts one exclusive receipt/allocation set per obligation. It does not fabricate shared-receipt splits or another payment request. Shared fees require the corresponding original-journal allocation contract; unsupported sharing is an integration gap, not an instruction to charge B twice. No second custody ledger, collection or gas freeze is created.

Rollback observes current available and required gas in the original budget, preserving the canonical fact. Older observations and old duplicates cannot replace current funding. A prepared, unissued rollback may refresh the same budget without changing its identity. UNKNOWN operations cannot refresh their way into another send. Dispatch checks validity; the original Wallet still atomically checks actual authority, funds and budget revision. Original sufficient prepaid funding can cover normal recovery without fresh free ETH.

## Registration, debt and recovery

Registration-first completion permanently detaches NFT rollback while preserving unpaid debt. Deadline-first failure follows the original eligible suffix rollback. Missing local registration is not refusal: an authenticated original Oracle cut as of the deadline is required, otherwise REGISTRATION_RECONCILIATION_REQUIRED is returned. A late-arriving timely cut cancels only an unissued rollback; conflicting issued effects remain reconciliation problems.

Same-currency top-ups, early registered payment, partial recovery, excess refunds and final collateral release retain distinct states. Refundable downstream proceeds cannot also pay an earlier seller. Multiple obligations reserve disjoint integer allocations under one fresh lock valuation. Unknown source exposure blocks additional borrowing; stale valuation grants no new capacity. Existing receipt transfer, rollback and remint authority is not replaced.

## Contingent liquidation

New gas-liquidation operations are prohibited. Normal gas uses its already paid allocation. Debt liquidation binds explicit original EX payer, source-native asset, budget, cap and validity, plus agreed penalty, conversion and priority policies. No rate, priority or provider is invented. Missing liquidation terms do not block unrelated prepaid trading, valid principal payment or normal rollback.

Original liquidation authority binds the operation, quote, source collateral cap and commercial terms. A separate liquidation-ex-funding observation is required before durable dispatch. Prepared operations may refresh a later observation of the same funding. Contingent budgets cannot alias prepaid source-normal budgets in either direction. Sharing a treasury is not proof of distinct usable suballocations.

The native resolver must verify the actual EX-funded task and budget, not an EX label. Execution does not require B to replenish ETH or wait for the liquidation's own proceeds. This candidate supports Hoodi ETH native execution funding; other source-native adapters remain unimplemented.

Four evidence paths remain separate:
- liquidation-source records gross source consumption within the approved collateral cap and retains its complete canonical fact.
- terminal-operation-receipt records the original route's final aggregate net destination effect. It is not the first transfer or a pending fragment. Terminal partial recovery can be below target; verified excess above target remains refundable. This interface does not accept multiple incremental fragments as separate final outcomes.
- liquidation-cost records actual EX-paid native cost within the original budget. It does not increase seller principal or automatically create a second borrower reimbursement.
- liquidation-penalty records the agreed collateral deduction as a component of gross consumption, never a second collateral debit. Unknown is not silently zero.

Source success is not destination payment. Destination funds do not release unknown source exposure. Principal settlement alone cannot unlock collateral while source, cost or penalty remains unreconciled. Duplicates are idempotent; conflicting observations fail closed.

## Original durable execution

DeferredCheckpoint uses the original AggregateCheckpointStore, scope and synchronous journal. All other components remain byte-for-byte unchanged. No new store, database path, signer, account or route is created.

The opt-in [existing-row snapshot composition](composite-exchange-checkpoint.md)
allows the original EX snapshot loader to share a declared aggregate row with
this module. Both writers retain the same generation CAS and untouched companion
bytes. This does not initialize/migrate an aggregate or complete the separate
native-command pre-effect, runtime, business-transition or UI integration paths.

dispatch_once first resolves the original task read-only, then persists UNKNOWN under the exact generation before execute. Stale writers, failed saves and lost save acknowledgement never dispatch. Transport errors after possible execution remain UNKNOWN. Terminal nonexecution requires authenticated proof the exact operation cannot execute later, not a timeout or missing RPC record.

DeferredWalletPorts keeps original Sepolia and Hoodi clients separate. Every normal operation carries its original chain-specific prepaid funding, including Hoodi collateral unlock. Debt liquidation uses its separate EX-funded binding. The callback rereads the original task and funding before execute and rejects changes. The original Wallet performs its own atomic checks. The resolver is trusted application composition, never HTTP-supplied binding data.

## Checkpoint and projection

Checkpoint and public projection use version 2. Version 1 yields LEGACY_FEE_ACCOUNTING_RECONCILIATION_REQUIRED; its bytes, commitments and UNKNOWN effects must remain intact. There is no automatic migration from old PYUSD fee to ETH, empty replacement store, deletion or permission to send old prepared gas-liquidation operations. Legacy reconciliation observes originally issued commitments through their original journals only.

Restore validates reference structure before cross-record sums, principal-only reservations, canonical funding/source facts, native caps, original quote and authority, operation commitments and cost/penalty consistency. Private storage remains trusted; arbitrary client snapshots are not a proof interface.

The identity-free public view distinguishes principal, ETH fee, each chain's gas cap, native liquidation cost, penalty and collateral reconciliation. It exposes no wallet identity, budget reference, grant or credential. Existing UI wiring remains required; no duplicate UI is introduced.

## Verification and unfinished work

Tests use explicitly synthetic facts, original-port fixtures and the existing file-backed aggregate. Until exact-candidate GitHub CI runs, these are test sources, not PASS results. Historical green does not certify the candidate. No local product execution is claimed.

Production proof verifiers, original native resolver composition, actual vault/disposal/destination-liquidity routes, full same-store runtime/business-transition bindings beyond the explicit existing-row adapter, existing UI wiring and real Hoodi/Sepolia evidence remain unfinished integration work. This candidate is not complete V1.5 delivery or production readiness.
