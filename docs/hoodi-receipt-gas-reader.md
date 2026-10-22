# Hoodi native receipt gas observation

Status: source-only implementation increment. Automated checks, runtime and live
chain acceptance are NOT_RUN. The deferred Fact adapter and runtime binding are
UNBOUND. This document is not acceptance evidence.

## Scope and API

PRD v1.5 EX-DEFER-02, EX-DEFER-09, EX-DEFER-10 and EX-GAS-09, and acceptance
cases T-86, T-93 and T-94, require source-native Hoodi gas to remain separate
from Sepolia ETH execution gas, Sepolia PYUSD debt and collateral penalties.
This increment supplies only a read-only receipt observation seam.

The existing `OriginalGasReceiptReader(original_rpc, verify_original_attempt)`
and `ReceiptGasObserver(verify)` remain Sepolia-only (11155111). Their public
read/observe signatures and original Sepolia behavior remain unchanged for
outputs produced by that path. They do not start accepting Hoodi.

`HoodiOriginalGasReceiptReader(original_rpc, verify_original_attempt)` is the
explicit source-chain counterpart, fixed to Hoodi 560048. Its
`read(attempt_id=..., transaction_hash=..., proof_reference=...)` uses the
original injected read transport. It selects no endpoint, configures no keys,
adds no store and performs no signing, sending, retry or accounting mutation.
There is no constructor option for an arbitrary chain.

`HoodiReceiptGasObserver(verify).observe(raw_receipt, chain_id=560048,
attempt_id=..., transaction_hash=..., proof_reference=...)` reuses the existing
strict receipt parser and cost derivation. It rejects Sepolia, all other
chain IDs and boolean/string chain contexts. A standalone observer requires
the injected verifier to authenticate canonical finality as well as original
attempt association; parsing alone does not establish either.

The result is `HoodiReceiptGasObservation`, retaining chain 560048, original
attempt/transaction/proof, receipt block identity, transaction gas used,
effective gas price, actual native wei, SUCCESS/FAILED and the raw receipt
SHA-256. `actual_wei` is `gasUsed * effectiveGasPrice`, not the cumulative gas,
gas limit, penalty or principal amount. A failed mined transaction still
consumes its actual gas.

`GasConsumption` is a legacy chainless value, not a chain verifier. The Hoodi
result refuses `consumption()`. The base observation conversion also rejects
non-Sepolia context, including an explicit base-method call on a Hoodi result,
so this seam cannot silently discard the verified source-chain identity into
a destination gas-budget application. Existing Sepolia conversions still work.

## Read and verification contract

Each RPC result must be original result bytes, not a JSON-RPC envelope, with
length 1..262144. Duplicate JSON keys, malformed UTF-8/JSON, noncanonical
quantities and hashes are rejected. Quantities are canonical lowercase hex
bounded to 256 bits; hashes are lowercase 32-byte hex. Supported transaction
types remain 0/1/2 and statuses 0/1. Zero mined gas, blob fee fields and the
existing additional-fee models remain refused instead of undercounted.

A mined receipt uses seven bounded reads:
1. `eth_chainId` must be Hoodi 560048 before receipt lookup.
2. Read the exact original transaction receipt.
3. Read the finalized head and require receipt height not to exceed it.
4. Read the canonical block at the receipt height and match height/hash.
5. Read the same receipt again and require byte-for-byte equality.
6. Read the canonical receipt block again and match height/hash.
7. `eth_chainId` must still be Hoodi 560048 before verification/output.

The original verifier receives exactly the existing evidence structure, now
bound to Hoodi: original attempt, transaction and proof reference; chain ID;
finalized block number/hash; parsed receipt evidence including exact raw bytes
and their hash; and the ordered seven raw RPC reads with methods/parameters.
Only the singleton `True` accepts. False, truthy non-booleans, unavailable
verification or transport errors refuse; private exception text is not echoed.
The configured verifier is still the trust boundary. A synthetic callback
returning True is not authenticated chain evidence.

A null Hoodi receipt performs a third read to recheck chain identity, then
returns `None` without invoking the verifier. It is unknown, never zero-cost,
terminal nonexecution or retry authority. The existing Sepolia null contract
remains two reads with zero verifier calls. No evidence or accounting mutation
is produced by either unknown result.

## Unimplemented deferred EvidenceVerifier boundary

No `Fact` is constructed and no deferred settlement method is called. A mined
receipt does not authenticate that EX paid for the issued liquidation, that
the payment belongs to its reserved funding budget, or that its costs may be
assigned to a specific deferred operation/profile.

Before this observation can support `observe_liquidation_cost`, the existing
configured `EvidenceVerifier.verify(evidence, kind="liquidation-cost", now=...)`
must authenticate and return the canonical `Fact` under the original trust
policy, including all of the following:

- Unique original native evidence identity and canonical observation time,
  with a profile commitment equal to the exact configured profile digest.
- Source chain 560048 and gas asset ETH, never destination Sepolia ETH/PYUSD.
- `reference` equal to the issued operation's exact commitment.
- `account` equal to the approved EX `gasPayer`, and `location` equal to its
  original `gasBudget`, supported by authenticated payer/funding evidence.
- `units` equal to the evidenced native `actual_wei`, within `gasCapUnits`.
- Association with the original issued debt-liquidation operation and its
  existing funding record, not a caller-asserted replacement budget or payer.

The aggregate must continue enforcing original operation status, profile,
funding, uniqueness/conflict and cap checks. Persisting it through the existing
same-aggregate checkpoint/CAS boundary is a separate unresolved integration,
not supplied here. No new proof API, endpoint, provider, custody capability,
valuation, penalty rate, financing term or persistent store is inferred.

A verified receipt cost, including status SUCCESS, proves neither collateral
sale, penalty deduction, destination PYUSD receipt nor seller-debt repayment.
Those remain separate evidence-backed operations. No failed transaction cost
is refunded or transformed into an automatic new borrower debt by this seam.

## Authored checks and handoff

`integration/test_hoodi_receipt_gas.py` contains 22 authored test methods with
synthetic fixtures. They cover successful and failed Hoodi costs; strict
chain separation; unchanged Sepolia conversion and pending behavior; exact
verifier/transcript binding; null/unknown; reorg, finality and changed receipt;
original attempt/proof mismatch; bool/noncanonical values; bounded JSON;
unsupported fees; and refusal of chain-erasing conversion.

These test sources have not been imported, executed, compiled or typechecked.
No historical green is inherited. The existing authorized CI route must
establish results for the exact integrated candidate. Deployment, live source
and destination evidence and served acceptance remain separately NOT_RUN.
