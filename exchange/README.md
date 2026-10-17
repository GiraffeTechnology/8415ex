# Exchange domain: current v1.2 scope

Use [PRD.md](../PRD.md), [AGENTS.md](../AGENTS.md) and the [pinned execution plan](../config/execution-plan.json) for current requirements. Earlier domain guides and assertions are preserved in Git history; they are not current acceptance instructions.

On the existing approved Linux executor, from the repository root:

```sh
python3 -B -m scenarios.current_prd plan
python3 -B -m scenarios.current_prd stages
python3 -B -m scenarios.current_prd matrix
```

## Required domain behavior

One NFT maps to one complete warehouse receipt. Owner tracks the traded position; holder tracks the contiguous authoritative Oracle registration record. Owner may lead holder during normal continuous resale. The off-chain voucher is itself the receipt: Oracle alone ingests, verifies and writes it. EX consumes that chain record, not raw originals or a second receipt.

Freeze each segment's original-buyer principal before execution; release that same frozen position when the segment is eligible. A later pending segment cannot block an eligible prefix or subsidize its funds. Registration does not start another buyer payment obligation.

Rollback withdraws only the unregistered suffix, preserves registered/settled prefix and returns owner to effective holder without issuer reset. Recovery and duplicate/unknown execution must not repeat funds or gas. An otherwise valid unexpired NFT may trade again after recovery; expired assets cannot bypass the cutoff.

Stage 4 is cutoff, bill-of-lading transfer and restored-trading eligibility. Physical collection, transport, warehouse exit, voucher handover and collection-driven burn are removed from EX implementation and delivery. No VoucherAndBurn assertion or unknown-burn gate is part of current T-25/T-32/T-33. Terms remain readable; no physical fulfillment is claimed.

Implement price priority/equal-price FIFO/best executable price, complete mint fields/formats/deadlines and three source routes sharing one backend. Before send disclose cap/P50 ETH and contemporaneous USD, obtain bounded buyer confirmation, freeze maximum gas separately from principal, debit real consumption and unfreeze unused amount; failed-tx gas stays charged. D-04 leaves only genuine shared-operation allocation undecided.

## Existing code is not automatic v1.2 evidence

Domain files retain original implementation history and still require actual migration in affected areas. The pre-v1.2 Stage5 scenarios are refused before execution by the current migration guard. Do not use old local scenario commands, physical-exit fixtures or historical unit-suite green as revised acceptance. The original implementation and QA owners must migrate/assert the actual behaviors under exact source, retaining failures and missing evidence.

The read-only current checklist is independent of legacy scenario execution. Its successful output reports requirements, not product PASS. Old diagnostic/model entrypoints supplement development only and cannot establish wallet authority, chain finality, actual principal freeze or operable UI.

## Acceptance remains separate

T-01..51 in the current plan are obligations. Actual source/schema/wallet/Oracle/journal/segment and authorization bindings are verified from original components, never invented. EX Sepolia 11155111 and designated verified test PYUSD remain separate from other projects' networks/assets.

Ordinary QA, submitted repairs, independent review, exact-head CI/merge and deployment follow existing single-writer responsibilities. Continue independent stage work after a PR without waiting for CI. A missing real interface affects only its dependent action. No new credentials, permission expansion, mainnet or real-value operations follow from this document.

Full delivery also requires real Linux/served-version, chain/Oracle/funds, source-specific UI and demo/PPT/playable-film evidence. Keep private operational paths, original handoffs, secrets and credentials out of the public repository.
