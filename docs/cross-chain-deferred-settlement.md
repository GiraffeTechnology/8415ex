# Cross-chain collateral-backed deferred settlement

Status: implementation specification; not a runtime acceptance certificate.
Existing UI is reused. Keep V1.5 isolated from V1.4/main even after CI succeeds. Later authorized wiring, runtime testing and deployment must identify the exact approved V1.5 version; no main merge is authorized. No production execution is authorized by this document.

## Product boundary

This is an additional trading mode, not a replacement for prepaid spot trading. The seller explicitly accepts a deferred payment deadline: an agreed T+n or 72 hours before the registration deadline. EX locks collateral and grants a bounded trading allowance. EX does not lend cash, promise funding, or charge an interest spread. The agreed normal settlement fee is collected upfront in ETH; contingent liquidation additionally incurs the agreed collateral-deducted penalty described below. A 50 percent collateral ratio is an example, not an implicit mandatory policy.

Principal is an explicitly selected, NFT0-permitted USD stablecoin. Collateral is BTC or ETH; receipt-collateral selection elsewhere remains intact but is not silently added to this module. Bitcoin custody/verification remains unavailable unless separately implemented and verified. A selection label is never collateral evidence.

The test profile is precisely:
- Sepolia ETH for Sepolia execution gas.
- Sepolia PYUSD for principal and seller payment.
- Hoodi ETH locked on Hoodi as collateral.
Hoodi lock, unlock and liquidation operations require their own Hoodi gas. Hoodi ETH cannot be treated as Sepolia ETH, or as PYUSD. A BTC asset bridge is not a product prerequisite: production collateral may remain on Bitcoin while verified source facts support the Ethereum-side USD trading allowance. Agreed custody/disposal and destination-settlement arrangements can deliver USD proceeds without transporting BTC across chains. Cross-chain fact verification is required but is not an asset bridge. No actual custody, liquidity or execution capability is inferred from this design or a successful local model. Native Bitcoin operations pay BTC fees, not ETH; retain source-native fee accounting separately from the ETH-denominated commercial charge.

## Two independent obligations

For A to B to C, B owes A the agreed principal. B may resell the NFT to C before paying A. C's proceeds enter B's escrow, but money still reserved for a refundable C segment cannot also be irrevocably allocated to A. The original segment responsibility and refund rules remain effective until the corresponding registration cut is complete.

Registration and payment are independent state axes. Registration of AB completes according to the existing authoritative ordered owner/holder cut, not address comparison or equality with the latest owner. Once that cut completes, AB's NFT rollback responsibility is permanently detached. B's unpaid debt to A survives; it cannot revive AB rollback or reverse C's completed ownership.

At the agreed settlement deadline:
1. If AB registration is not complete, the trade is incomplete and enters the existing eligible rollback process. Do not wait indefinitely for registration and do not pay A as though registration succeeded.
2. If registration is complete, pay A from the available correctly denominated B escrow. B may top up before the deadline or settle early when registration permits payment. If insufficient at the deadline, initiate collateral liquidation for the remaining debt.
3. Normal-process gas is funded by the upfront ETH settlement fee. If contingent liquidation is required, 8415EX pays its execution gas first and charges B an additional penalty from the liquidated collateral. Do not wait for a fresh ETH payment from B or for liquidation proceeds before funding that liquidation. This is not permission to admit a new trade without the upfront normal-process gas check.
4. Never cancel a completed registration cut because payment or liquidation execution failed. Failures and unknown outcomes stay visible and reconcilable.

Early manual settlement must not bypass the registration condition. Before registration completion it may reserve additional principal but must not irreversibly release the seller payment. Registration-first completed debt and deadline-first rollback must have explicit, separately tested outcomes.

## Cross-chain trust and accounting

A lock must be bound to source chain, configured vault, asset, depositor, amount, unique lock identity, source transaction/log and finalized canonical evidence. A destination trading allowance must additionally bind the settlement chain, borrower, policy version, valuation denomination, valuation freshness and exact proof identity. RPC reachability, a caller-supplied verified flag or an unauthenticated relay assertion is not proof.

Only a configured trusted proof verifier may admit observations. Its implementation, finality policy and allowlisted addresses are deployment inputs. Missing verifier or missing native-chain evidence blocks that dependent operation; it does not generate simulated acceptance.

Credit is an integer amount in the selected settlement token's minor units. Calculate from verified collateral valuation and explicitly agreed ratio, rounding down. Do not add values across stablecoins, chains or locks without an explicit corresponding allocation. A pledged unit cannot support overlapping limits; reserved obligations reduce available capacity. Price changes do not invent an unapproved margin call or early liquidation threshold.

Each deposit, payment, liquidation receipt, rollback and collateral release has an idempotent operation identity and exact payload commitment. Duplicate evidence cannot increase balance twice. An unknown external outcome prevents redispatch until reconciliation. Persist claims before dispatch, persist confirmed effects before releasing reservations, and retain audit history across restart. Generation checks prevent concurrent overspending.

Liquidation is a workflow, not an immediate accounting conversion. Record the sale request and its bounded purpose separately from source-chain sale evidence and destination receipt. A seller debt is paid only after confirmed Sepolia PYUSD reaches the correct destination. Normal-process gas must already be received and allocated through the upfront ETH fee. Contingent liquidation gas comes from EX, not a prerequisite liquidation-to-gas conversion. Source sale success alone is not destination payment. Use the agreed custody/disposal and destination liquidity arrangement; do not require an asset bridge, fabricate a provider or presume live funding is configured. An unavailable actual provider or execution capability blocks its dependent operation, not the commercial model or independent work.

Principal, upfront settlement fees, their normal-process gas allocations, EX-paid liquidation gas, the additional collateral-deducted liquidation penalty, source-chain native costs, collateral remainder and outstanding debt are distinct ledger amounts. A principal shortage and a gas shortage are not interchangeable. Liquidate only within the authorized collateral/quote bounds; retain residual shortfall if proceeds are insufficient. Release remaining collateral only after all its reserved obligations and unknown operations are resolved. Do not promise full recovery under price gaps or unavailable liquidity.

## Confirmed commercial fee allocation

Collect the agreed settlement fee in ETH when accepting collateral. It includes normal-process gas only. It must not pre-reserve gas for contingent liquidation, because liquidation is a remedy rather than an inevitable stage. Admission verifies sufficient actual receipt and disjoint allocation of this normal-process funding; collateral-backed USD allowance cannot substitute for it. Do not charge the same included gas twice or demand another payment merely because B later has no free ETH.

If liquidation becomes necessary, 8415EX supplies execution gas first. EX then charges B an additional liquidation penalty deducted from the collateral assets being liquidated. Thus liquidation does not depend on B's current ETH balance, and execution cannot be circularly gated on receiving its own sale proceeds. This is an explicitly specified contingent payer arrangement, not permission for arbitrary subsidies in prepaid trading.

Keep evidenced execution costs and the penalty separately reconcilable; do not automatically add a second reimbursement of the same cost. The penalty amount/rate, cap, deduction denomination or conversion, and distribution priority relative to A's debt are not fixed by this revision and must not be invented. Record partial recovery, remaining liabilities and collateral honestly. Actual custody, counterparties, funding and deployment still need their authorized runtime configuration; the PRD does not perform or authorize live transactions.

## Existing UI and handoff contract

Do not create a duplicate collateral UI. Expose backend projections and typed commands for the existing views: eligibility, locked collateral, allowance/reserved capacity, deadline, registration cut, escrow availability, debt shortfall, top-up, early settlement, rollback, upfront normal-fee/gas allocation, EX-funded liquidation, collateral penalty, reconciliation and collateral release. Preserve the existing six-language, identity-excluding frontend boundary. Provider endpoints, credentials and wallet secrets are not frontend state.

The wiring/test/deployment handoff contains the exact approved V1.5 commit/tree, with the no-main-merge hold preserved, API contract, exact CI results, test fixtures and explicit NOT_RUN/NOT_VERIFIED runtime gaps.

## Required acceptance cases

- Prepaid trading remains unchanged; deferred mode requires signed seller consent and explicit parameters.
- Hoodi lock evidence is verified before Sepolia allowance; wrong chain/vault/asset/borrower, replay, stale valuation and unfinalized proof fail closed.
- B cannot double reserve collateral or spend refundable C proceeds twice.
- A-B-C resale, valid top-up and early registered settlement preserve exact currency accounting.
- Deadline before registration selects rollback, not a delayed seller payout.
- Registration before deadline detaches NFT rollback even if B's debt remains unpaid.
- Registered debt shortage at deadline selects debt liquidation. Normal gas is covered by the upfront ETH fee; contingent liquidation gas is not pre-reserved there and is funded by EX, even when B has no current free ETH.
- Source sale without destination USD receipt does not satisfy seller debt. The separately recorded penalty is deducted from liquidated collateral once; no invented rate, distribution priority or duplicate cost recovery.
- Collateral stays on its source chain; verified source facts authorize destination allowance without requiring an asset bridge. Missing genuine evidence or payment cannot be replaced by a model flag.
- Duplicated, late, mismatched or unknown execution results cannot duplicate payment, reversal or capacity release.
- Concurrent requests, process restart and ambiguous persistence acknowledgements retain reservations and reconciliation state.
- Collateral insufficient after liquidation leaves an explicit unresolved balance, never fictitious settlement.
- Live Hoodi lock and Sepolia receipt, actual UI wiring and deployment are separate acceptance evidence, not inferred from model tests or green CI.
