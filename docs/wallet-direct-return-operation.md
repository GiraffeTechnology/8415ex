# Existing Wallet direct-transfer operation binding

An existing Wallet exact-operation can express an ERC-721 transfer directly from
its actor to its recipient. EX can correlate that operation to its existing
rollback interval instead of interpreting a loop of return-hop calls as one
asset-control return.

`bind_wallet_direct_return` accepts the original EX durable scope, original
RollbackAuthority, current-owner observation, exact affected-leg interval and
the existing Wallet operation. It requires Sepolia/receipt/NFT/refused-leg
correlation and the original rollback interval digest. The existing operation
must be exactly `erc721-transfer` with the original owner actor and effective
boundary recipient, identical NFT and canonical string quantities. Extra
calldata, another asset/recipient, a return-hop or another operation kind cannot
be substituted. The returned copies retain the original operation/journal/
intent identities and do not mutate the caller's inputs.

This is one correlation step toward EX-ROLLBACK and T-46 native reuse, not an
execution permission or completed native adapter. It creates no grant, task,
nonce, fee quote, reservation or custody account and sends nothing. The original
trusted composition must supply the actual owner and effective-holder boundary;
constructing a RollbackAuthority object does not authenticate that authority.
The original Wallet still performs existing grant, owner/simulation, fee/funds,
nonce and execution checks. Contract-owned or otherwise unsupported ownership
must use its actual existing control path, without pretending it is this actor
transfer. No new human approval or all-ready condition is introduced.

Refunds of selected-currency principal and ETH gas accounting remain separate
from the single asset return. A prepared operation, successful HTTP response or
this pure mapping is not a confirmed transfer. The original durable operation
journal and authoritative native enquiry remain required to preserve UNKNOWN
and avoid replay. Actual installed callbacks, effective-time Oracle mapping,
direct-control execution and chain acceptance remain OPEN.

Six synthetic correlation definitions cover exact mapping, boundary substitution,
operation/field drift, scope drift, interval identity and detached copies.
Author execution is NOT_RUN; existing integration CI discovers the module.
