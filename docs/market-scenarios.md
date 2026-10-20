# Read-only market scenario context

Current PRD EX-SCOPE-13, T-69 and D-14 confirm hedging, collateral and arbitrage
scenes involving BTC/ETH and soybean/iron-ore receipts. `market_scenarios`
provides those explicit scene and context choices in the six existing languages.
It selects no default asset, principal currency or economic mechanism.

Receipt choices come exclusively from the original `NftDirectory`. A selected
receipt links to its original `/nft?nft=...&lang=...` detail route. Changing
language preserves the exact scene, labels and opaque original receipt key.
Selection reads no domain/provider state and publishes neither receipt IDs nor
wallet identities. A commodity label does not assert that a selected receipt
contains that commodity. The original detail remains the terms authority.

The context is explicitly simulated. It creates no order, hedge, financing,
arbitrage signal or execution, calculates no valuation, ratio, liquidation or
return, and evaluates no asset mapping or trading eligibility. Missing receipts
remain empty. A future separate trade retains the original receipt, currency,
authority and ETH gas rules. This context is not full scenario acceptance.

Seven synthetic regression definitions cover the full scene/context matrix,
missing receipts, exact original detail links, privacy, six-language context
continuity, forbidden financial inputs and invalid/cross-directory selections.
They have not been run by this source author. HTTP mounting, actual browser
interaction and native business acceptance are separate work; no deployment or
live market connection is claimed by these three files.
