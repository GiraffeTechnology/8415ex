# Cross-chain collateral-backed deferred settlement

Status: implementation specification; not a runtime acceptance certificate.
Existing UI is reused. Wiring, runtime testing and deployment use the exact CI-verified main version. No production execution is authorized by this document.

## Product boundary

This is an additional trading mode, not a replacement for prepaid spot trading. The seller explicitly accepts a deferred payment deadline: an agreed T+n or 72 hours before the registration deadline. EX locks collateral and grants a bounded trading allowance. EX does not lend cash, promise funding, or charge an interest spread. Only the separately agreed settlement fee applies. A 50 percent collateral ratio is an example, not an implicit mandatory policy.

Principal is an explicitly selected, NFT0-permitted USD stablecoin. Collateral is BTC or ETH; receipt-collateral selection elsewhere remains intact but is not silently added to this module. Bitcoin custody/verification remains unavailable unless separately implemented and verified. A selection label is never collateral evidence.

The test profile is precisely:
- Sepolia ETH for Sepolia execution gas.
- Sepolia PYUSD for principal and seller payment.
- Hoodi ETH locked on Hoodi as collateral.
Hoodi lock, unlock and liquidation operations require their own Hoodi gas. Hoodi ETH cannot be treated as Sepolia ETH, or as PYUSD. No bridge, exchange liquidity or cross-chain execution capability is inferred from a balance or a successful local model.

## Two independent obligations

For A to B to C, B owes A the agreed principal. B may resell the NFT to C before paying A. C's proceeds enter B's escrow, but money still reserved for a refundable C segment cannot also be irrevocably allocated to A. The original segment responsibility and refund rules remain effective until the corresponding registration cut is complete.

Registration and payment are independent state axes. Registration of AB completes according to the existing authoritative ordered owner/holder cut, not address comparison or equality with the latest owner. Once that cut completes, AB's NFT rollback responsibility is permanently detached. B's unpaid debt to A survives; it cannot revive AB rollback or reverse C's completed ownership.

At the agreed settlement deadline:
1. If AB registration is not complete, the trade is incomplete and enters the existing eligible rollback process. Do not wait indefinitely for registration and do not pay A as though registration succeeded.
2. If registration is complete, pay A from the available correctly denominated B escrow. B may top up before the deadline or settle early when registration permits payment. If insufficient at the deadline, initiate collateral liquidation for the remaining debt.
3. If B lacks the gas necessary for rollback, collateral liquidation may cover that gas shortfall. This is the specifically authorized recovery exception, not permission to admit a new trade without the original gas checks.
4. Never cancel a completed registration cut because payment or gas recovery failed. Failures and unknown outcomes stay visible and reconcilable.

Early manual settlement must not bypass the registration condition. Before registration completion it may reserve additional principal but must not irreversibly release the seller payment. Registration-first completed debt and deadline-first rollback must have explicit, separately tested outcomes.

## Cross-chain trust and accounting

A lock must be bound to source chain, configured vault, asset, depositor, amount, unique lock identity, source transaction/log and finalized canonical evidence. A destination trading allowance must additionally bind the settlement chain, borrower, policy version, valuation denomination, valuation freshness and exact proof identity. RPC reachability, a caller-supplied verified flag or an unauthenticated relay assertion is not proof.

Only a configured trusted proof verifier may admit observations. Its implementation, finality policy and allowlisted addresses are deployment inputs. Missing verifier or missing native-chain evidence blocks that dependent operation; it does not generate simulated acceptance.

Credit is an integer amount in the selected settlement token's minor units. Calculate from verified collateral valuation and explicitly agreed ratio, rounding down. Do not add values across stablecoins, chains or locks without an explicit corresponding allocation. A pledged unit cannot support overlapping limits; reserved obligations reduce available capacity. Price changes do not invent an unapproved margin call or early liquidation threshold.

Each deposit, payment, liquidation receipt, rollback and collateral release has an idempotent operation identity and exact payload commitment. Duplicate evidence cannot increase balance twice. An unknown external outcome prevents redispatch until reconciliation. Persist claims before dispatch, persist confirmed effects before releasing reservations, and retain audit history across restart. Generation checks prevent concurrent overspending.

Liquidation is a workflow, not an immediate accounting conversion. Record the sale request and its bounded purpose separately from source-chain sale evidence and destination receipt. A seller debt is paid only after confirmed Sepolia PYUSD reaches the correct destination. Rollback gas is available only after confirmed Sepolia ETH reaches the correct recovery payer/reservation. Hoodi sale success alone satisfies neither condition. Do not fabricate a cross-chain swap provider or silently use an operator's funds. Missing executable route is a specific runtime blocker.

Principal, settlement fees, recovery gas, source-chain gas, collateral remainder and outstanding debt are distinct ledger amounts. A principal shortage and a gas shortage are not interchangeable. Liquidate only within the authorized collateral/quote bounds; retain residual shortfall if proceeds are insufficient. Release remaining collateral only after all its reserved obligations and unknown operations are resolved. Do not promise full recovery under price gaps or unavailable liquidity.

## Existing UI and handoff contract

Do not create a duplicate collateral UI. Expose backend projections and typed commands for the existing views: eligibility, locked collateral, allowance/reserved capacity, deadline, registration cut, escrow availability, debt shortfall, top-up, early settlement, rollback, gas-recovery liquidation, debt liquidation, reconciliation and collateral release. Preserve the existing six-language, identity-excluding frontend boundary. Provider endpoints, credentials and wallet secrets are not frontend state.

The wiring/test/deployment handoff contains the merged commit/tree, API contract, exact CI results, test fixtures and explicit NOT_RUN/NOT_VERIFIED runtime gaps.

## Required acceptance cases

- Prepaid trading remains unchanged; deferred mode requires signed seller consent and explicit parameters.
- Hoodi lock evidence is verified before Sepolia allowance; wrong chain/vault/asset/borrower, replay, stale valuation and unfinalized proof fail closed.
- B cannot double reserve collateral or spend refundable C proceeds twice.
- A-B-C resale, valid top-up and early registered settlement preserve exact currency accounting.
- Deadline before registration selects rollback, not a delayed seller payout.
- Registration before deadline detaches NFT rollback even if B's debt remains unpaid.
- Registered debt shortage at deadline selects debt liquidation; rollback gas shortage selects gas-recovery liquidation with separate amounts and assets.
- Source sale without destination receipt does not satisfy either debt or gas.
- Duplicated, late, mismatched or unknown execution results cannot duplicate payment, reversal or capacity release.
- Concurrent requests, process restart and ambiguous persistence acknowledgements retain reservations and reconciliation state.
- Collateral insufficient after liquidation leaves an explicit unresolved balance, never fictitious settlement.
- Live Hoodi lock and Sepolia receipt, actual UI wiring and deployment are separate acceptance evidence, not inferred from model tests or green CI.
