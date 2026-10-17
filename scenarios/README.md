# Current scenario and acceptance instructions

The current contract is [PRD v1.2](../PRD.md), [AGENTS](../AGENTS.md) and the byte-pinned [execution plan](../config/execution-plan.json). Earlier scenario guidance is retained in Git history only. It is not a live execution or acceptance checklist.

## Restore the current contract

On the existing approved Linux executor, from the repository root:

```sh
python3 -B -m scenarios.current_prd plan
python3 -B -m scenarios.current_prd matrix
python3 -B -m scenarios.current_prd stages
python3 -B -m scenarios.current_prd decisions
python3 -B -m scenarios.current_prd handoff
python3 -B -m scenarios.current_prd sections
```

Every invocation reads and verifies PRD.md and config/execution-plan.json against config/prd-lock.json. The data includes all 21 sections, 77 requirement IDs, T-01..51, D-01..13, Stage 0..5 and six revised demos. No original chat is required. Existing scenarios CLI matrix/stages/decisions/handoff/sections routes use this same data.

These are requirement reports. Revised cases remain NOT_VERIFIED and product status remains OPEN; a successful read does not mean scenario or product acceptance.

## Migrate actual scenarios before executing them

The shipped pre-v1.2 scenario bodies are historical implementation inputs. They have not become compliant by changing this guide. Current scenario-producing CLI, direct DEMO-01..06 callbacks and the exchange Stage5 entry reject their old path with PRD_MIGRATION_REQUIRED before obsolete callbacks. Do not run old guide commands as current acceptance, remove the guard merely to restore old green, or report an old model result as a revised-case pass.

The implementation owner must actually migrate matching, mint data, Oracle authority, original-funds release, cutoff/suffix recovery and buyer gas before the corresponding scenario is admitted under the exact new source. Existing QA/review owners then verify that source and record genuine evidence. The migration guard blocks only affected old paths; independent work and current checklist reads continue.

## Current business assertions

EX transfers the whole bill of lading. There is no collection, transport, warehouse-outbound or destruction step. Terms remain visible and history survives. Oracle alone ingests/verifies the voucher and records it; holder follows that same chain record. No second receipt, independent holder write or late-registration grace.

Principal is frozen before trade and released from that original position, without a second buyer payment. Rollback protects registration/settled prefix and returns owner to effective holder; valid unexpired NFTs may start a new chain, while ordinary continuous resale permits owner ahead of holder.

Price/FIFO/best-price matching, mint/deadline semantics and cap/P50 gas policy are fixed. Disclose cap and real median ETH/contemporaneous USD, bind buyer confirmation, prefreeze maximum gas separately from principal, debit actual consumption and unfreeze unused balance. Only shared-operation allocation remains partially pending in D-04.

## Evidence and delivery

Six revised demos and each of the direct, electronic and intermediary sources require their own source/route/Oracle/funds/UI evidence. Linux model/fixture results do not establish actual Sepolia, wallet, served UI or browser/material acceptance. Preserve full source/config/run identity, raw results and actual missing evidence. Do not fabricate transaction hashes or promote NOT_RUN.

After a stage PR continue the next independent authorized stage without waiting for CI. Required exact-head checks and acceptance still gate merge. Source, package, CI and HTTP success alone never close delivery. Private operational references and secrets stay outside public files.
