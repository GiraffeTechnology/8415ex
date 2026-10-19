# 8415ex

8415ex is an application-layer model for one whole warehouse receipt traded in a
continuous chain, where registration lags behind the trade on purpose. It is
developed in small, verifiable increments. Wallet integration will use ERC-8415,
supporting 8415wallet and compatible wallets.

## Current requirements

[PRD.md](PRD.md) v1.4 is the current complete product and acceptance contract: 111 EX requirements, T-01..84, six stages and six demonstrations. Read [AGENTS.md](AGENTS.md) before implementation. Earlier v1.3 loaders/locks/plans and conflicting subdirectory guides are historical, not authority or v1.4 acceptance. This publication does not claim implementation, runtime, deployment or chain completion.

The scope is a commodity spot-intermediary Web3 infrastructure DEMO: whole receipts, BTC/ETH and soybean/iron-ore scenes, both crypto and receipt-NFT collateral, ordinary market-maker quotes, continuous real public spot references isolated from simulated NFT orders, full terms, independent current/owner/holder markers, role-bound per-position signatures and six-language responsive UI. Undefined financing/valuation/liquidation/returns remain local open items, not invented defaults or a global stop.

Python 3.10 or newer and the standard library are the only requirements. There
is no third-party dependency anywhere in the repository.

## The two positions, which are never merged

The owner is the actual ERC-721 token owner; ownerOf returns an address mapped
separately to an actual transfer position. Holder is the Oracle-confirmed
registration projection. Latest admission and effective-time history are distinct. They move at different speeds, and the whole
model exists because of that gap: a receipt can change hands several times while
the register is still recording the first hop. Nothing here presents the two as
one, and a deferred registration result is never shown as a refusal.

## Product invariants and current gaps

- Oracle alone ingests/verifies the single registration voucher. Owner may lead holder; ordinary transfer requires neither equality, gap closure nor current finality.
- Release a segment's original frozen principal when ordered owner and holder reach its buyer or beyond; remove completed-segment rollback independently, without a second buyer payment.
- Refund only eligible unregistered suffix in original currencies and directly restore owner to effective holder without ordinary intermediate-wallet traversal. Preserve registration and settled prefix. Current Wallet returnHop transfers one previous leg per call; a production adapter and joined evidence remain needed for EX's one-control-operation requirement. Model tests do not close this gap.
- Valid unexpired NFTs can trade again after rollback. Holder possession/equality permits authorized atomic old burn/new mint with editable new terms. Physical collection and collection-driven destruction remain outside EX.
- NFT0 principal currencies are immutable after mint. Orders explicitly choose one, match same-currency price/FIFO and refuse shortage; no conversion, substitution or balance aggregation.
- ETH alone pays gas: confirmed cap/real P50 ETH and informative USD, full maximum freeze separate from principal, actual debit/unused unfreeze and no zero/insufficient-ETH new trade. Existing adequate approved freezes still fund their recovery.
- Each NFT has its own exact openGapOF=YES red / openGapOF=NO green from supported successful bytes32 openGapOf reads; unknown/loading/error/unsupported stays explicit. This display does not prove registration/payment/legal title.
- Three positions and signing evidence stay independent. Frontend excludes wallet names/addresses everywhere and shows complete identity-free business conditions; unchanged signed originals remain private. Candidate locales are en, zh-Hans, zh-Hant, fr, es, ja. Exclude wallet-management pages, retaining EX authorization/balance/fees.

## What is here

| Directory | What it holds |
| --- | --- |
| [`exchange/`](exchange/README.md) | the domain: receipt state, the owner/holder dual track, serial registration with three simulated registrar adapters, segmented escrow and independent settlement, suffix rollback with buyer gas, historical deadline/exit paths requiring reconciliation with current bill-transfer/remint requirements, and a read-only status console |
| [`scenarios/`](scenarios/README.md) | the six scenarios and three route contracts, the acceptance matrix and evidence index, and the records a reviewer needs: source identity, open decisions, the event contract, the stage map and the candidate receipt |
| [`ci/`](ci/README.md) | a dependency-free bootstrap, its smoke command and its output manifest |

## What this is not

Nothing in this repository signs, pays, broadcasts, deploys or moves value. The
three registration routes are simulated business roles, not real registration
institutions. A rendered status page is development and diagnostic output, not
interface acceptance. Every obligation that needs a real chain, a real browser
or an independent review is reported as `NOT_RUN` rather than approximated, and
the reports below say so about themselves.

## Running the checks

GitHub Actions is permitted for CI. Runtime and integration acceptance use the project-supported Linux configuration. Deployment and live-chain acceptance require separate evidence. EX remains Sepolia 11155111, not Wallet Hoodi.

Commands below are documentation, not permission to execute them here. Historical outputs do not validate current code. GitHub Actions is valid evidence for its actual CI checks, not for unexecuted deployment or live-chain acceptance. Record exact head/base and the tested commit; synthetic merge identity differs from head. Missing checks are not green.

The bootstrap checks need `APPROVED_TEST_ROOT` set to
an existing, canonical directory chosen explicitly for them.

```sh
BOOTSTRAP_TEST_ROOT="$APPROVED_TEST_ROOT" python3 -B -m unittest discover -s ci/tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s exchange/tests -t . -v
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s scenarios/tests -t . -v
```

The existing model evidence bundle in one command on the supported Linux runtime, which exits non-zero unless every
expectation passed over a confirmed, clean source tree:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m scenarios.cli run-all
```

## The reports, and what each one answers

Each is a subcommand of `python3 -B -m scenarios.cli`.

| Command | The question it answers |
| --- | --- |
| `run-all` | did every model expectation pass, over which exact source |
| `scenarios`, `paths` | what did the six scenarios and the three route contracts record |
| `matrix` | which requirement does each case serve, and what is its local outcome |
| `evidence-index` | from a requirement, through the assertion and the run, to the artifact it lands in |
| `receipt` | the nine-group candidate receipt, with the chain and deployment groups `NOT_RUN` |
| `manifest` | the exact source, the file inventory and the diff under review |
| `handoff` | which real-evidence slots are unfilled, and who owns them |
| `stages` | per stage, what is developed here, what is accepted elsewhere, what is owed |
| `dossier` | per scenario, the nine items a demonstration must carry |
| `storyboard` | does the presentation outline still describe the code |
| `operations` | do the logical operations land on real methods, and do reads move nothing |
| `events` | which audit groups are recorded, derived, or waiting on a chain |
| `reuse` | what this package consumes, what is simulated, what is not located yet |
| `decisions` | which decisions are open, and what each one does **not** block |
| `observations` | the bounded secret scan, and the recorded load, backlog and rates |
| `validate-config` | would this configuration be accepted, and why a bad one is refused |
| `usage` | do these instructions still match the commands that exist |
| `completion` | per clause of the definition of done: its evidence here, or the owner who owes the rest |
| `sections` | per requirement section: what addresses it here, or the owner it belongs to |

The domain has its own diagnostic command line, which supplements the console
and does not replace it:

```sh
python3 -B -m exchange.cli view
python3 -B -m exchange.cli timeline
python3 -B -m exchange.cli queue
```

## Keeping these instructions true

The commands above are checked against the commands that actually exist, in both
directions: a documented command that does not exist is a broken instruction,
and a command no guide mentions is a report nobody will find. Both are findings,
and the suite fails on either.

## Evidence and continued work

Reuse existing CI and check exact-source outcomes, without historical PASS inheritance. Missing implementation/evidence remains NOT_RUN/NOT_VERIFIED.

Published product baseline file integrity: PRD.md SHA-256 `b3989a91f1d3f7a1de6812fa05777d0dfdf84a4eee4a7909bdda77d1196032ce`. This identifies document bytes, not a runtime acceptance result.
