# NFT0 atomic remint candidate

This separate Sepolia test contract extends NFT0 product behavior; it does not
claim that remint is an ERC-8415 standard function. It reads the fixed draft's
original `IRegisterProjection.holderAsOf(uint256,uint64)` ABI. The original
projection address and register identity must be supplied from verified existing
deployment bindings. No address is guessed and no second holder registry is created.

The caller must possess the old ERC721 and equal its authoritative projected
holder. One EVM operation burns the old token, mints the replacement, preserves
the stable bill identity, and records predecessor/successor and operation-result
links. A rejected receiver reverts the entire transaction. The previous terms and
currency declaration remain readable after burning. Replacement terms and allowed
currencies are declared afresh and then have no setters. Currency references must
be bound to the original authenticated currency/network/unit schema at integration.

Ordinary inherited ERC721 transfers do not call the projection or require holder
equality, a closed gap, or finality. Remint adds no cleanup, refund, unfreeze,
issuer approval or migration approval prerequisite. Financial journals remain with
their original writers; this contract neither settles nor refunds principal/gas.

An exact repeated operation ID returns its prior token ID; conflicting reuse is
rejected. This is not authorization to resend an UNKNOWN transaction. Reconcile
the original transaction receipt, operation result, burn/mint logs, bill binding
and authoritative projection before deciding the next action. Chain reorganization
and concurrent registration/trading still require original transaction integration.

Status: SOURCE_ONLY / NOT_COMPILED / NOT_RUN / NOT_DEPLOYED. Thirteen synthetic Forge
cases are authored separately from real acceptance. Use the existing pinned
Solc 0.8.24 and OpenZeppelin 5.0.2 toolchain only on a verified approved CTYun or
Aliyun Linux server after the mandatory execution-target boundary check. Existing
Solc/Forge download failures remain unresolved. No local validation is permitted.
Real Oracle/Wallet cross-operation cases remain
to be added and executed; no business-closure PASS is claimed.
