# 8415ex

Continuous trading of one whole warehouse receipt, with owner tracking the trade position and holder tracking the same authoritative Oracle registration record.

## Current product and recovery contract

Read [PRD.md](PRD.md), [AGENTS.md](AGENTS.md) and the exact [machine pin](config/prd-lock.json) before work. Version **1.3** replaces conflicting previous product requirements. The [execution plan](config/execution-plan.json) contains all 21 sections, 91 requirement IDs, 68 acceptance cases, 13 decisions, six stages and six revised demonstrations.

From the repository root on the existing approved Linux executor:

```sh
python3 -B -m scenarios.current_prd plan
python3 -B -m scenarios.current_prd stages
python3 -B -m scenarios.current_prd matrix
python3 -B -m scenarios.current_prd decisions
python3 -B -m scenarios.current_prd handoff
python3 -B -m scenarios.current_prd sections
```

These commands verify the exact PRD/plan bytes, reload repository files on every invocation, and report requirements and missing evidence. They do not sign, broadcast, deploy or grant acceptance. No original chat, credentials, network or installed third-party dependency is needed to recover the product contract.

The existing scenarios CLI routes its matrix, stages, decisions, handoff and sections commands to the same pinned data:

```sh
python3 -B -m scenarios.cli matrix
python3 -B -m scenarios.cli stages
python3 -B -m scenarios.cli decisions
python3 -B -m scenarios.cli handoff
python3 -B -m scenarios.cli sections
```

A successful checklist read is not a passing product case. Every revised case starts NOT_VERIFIED and carries no inherited historical pass.

Version 1.3 fixes one or more allowed currencies at NFT0 mint. Each order selects
one member; EX does not exchange, substitute or combine currency balances. Gas
settles only in ETH and is checked/accounted separately from principal, including
when the selected principal is ETH. Insufficient selected principal or available
ETH gas warns and refuses before signing, execution or broadcast.

A holder who possesses the NFT and equals its owner may atomically burn that NFT
and mint a new one with newly declared terms. Old/new identities and history stay
traceable. This remint rule adds no cleanup or approval prerequisite. Ordinary
continuous transfers do not require holder=owner, a closed gap or current finality.
Physical collection-driven destruction remains retired; atomic remint is distinct.

## Removed requirements are not executable duties

EX transfers the bill of lading; physical collection, transport, warehouse exit and collection-driven NFT destruction are outside delivery. Oracle alone ingests and verifies the off-chain voucher and writes its one authoritative record; holder follows that record. Release already frozen principal without a second buyer payment. Rollback preserves registered/settled prefix and returns owner to effective holder; valid unexpired assets may trade again.

Price priority/FIFO, complete mint data, cutoff and gas cap/P50 policy are confirmed. Before send disclose cap and real median ETH/contemporaneous USD, obtain bound buyer confirmation, freeze the maximum gas separately from principal, debit actual consumption and unfreeze unused balance. Only actual shared-operation allocation remains D-04.

Old six-scenario implementations have not been migrated by this documentation change. The scenarios CLI, direct Scenario.run calls for DEMO-01..06, and exchange.stage5 entry explicitly refuse those old execution paths with PRD_MIGRATION_REQUIRED before old callbacks. This refuses obsolete duties rather than executing and relabelling them. History remains in Git. Migrate and verify each affected scenario with its original implementation owner before removing the targeted guard.

## Development and acceptance

Proceed to the next independent authorized stage after a stage PR without waiting for CI. Missing RPC, issuer, one integration or one deployment target blocks only that action. Build/QA does not need RPC or an existing issuer deployment. Preserve exact base/head and the single writer for each shared path. Existing QA, review, CI/merge and deployment responsibilities remain controlling.

The existing dependency-free Python model uses Python 3.10+ and standard library. Historical model/fixture code and reports remain source-bound development evidence; a rendered page is not browser acceptance. Three sources are direct, electronic and intermediary registration into one backend, with whole-artwork alignment and real frontend acceptance still required. Sepolia 11155111 and the designated verified test PYUSD stay distinct from other projects' test networks.

All product validation, including syntax, type, build, package and browser tests,
uses an existing approved remote non-Windows Linux server with verified CTYun or
Aliyun provider evidence and the current per-action boundary check. This machine,
Windows, WSL, containers and VMs are not fallback test targets. Do not repeat
capabilities probes stopped by the owner; reuse saved evidence and diagnose source.

Product suites and genuine runtime/chain/browser/material acceptance remain separate from the document loader. Current source, package, required exact-head CI, actually served version, real receipts/Oracle/funds/UI evidence and artifact readback must all correspond before full delivery. This update does not make any of them PASS.

## Repository areas

| Area | Purpose |
| --- | --- |
| PRD.md / config/ | Current complete sanitized product specification and machine contract |
| exchange/ | Existing domain, adapters, UI and stage execution code; legacy scenarios require migration |
| scenarios/ | Pinned checklist loader and existing evidence/reporting infrastructure |
| ci/ | Existing bootstrap and source/evidence checks |

Public files are English and sanitized. Private source links, internal topology, operational paths, credentials and full private handoffs stay outside GitHub. Existing approved Linux execution, wallet consent and no mainnet/real-value/new-resource boundaries remain. No Drive timer or automatic server synchronization is introduced.
