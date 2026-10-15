# 8415ex

8415ex is an application-layer model for one whole warehouse receipt traded in a
continuous chain, where registration lags behind the trade on purpose. It is
developed in small, verifiable increments. Wallet integration will use ERC-8415,
supporting 8415wallet and compatible wallets.

Python 3.10 or newer and the standard library are the only requirements. There
is no third-party dependency anywhere in the repository.

## The two positions, which are never merged

The owner is the on-chain trade position. The holder is the
registration-confirmed position. They move at different speeds, and the whole
model exists because of that gap: a receipt can change hands several times while
the register is still recording the first hop. Nothing here presents the two as
one, and a deferred registration result is never shown as a refusal.

## What is here

| Directory | What it holds |
| --- | --- |
| [`exchange/`](exchange/README.md) | the domain: receipt state, the owner/holder dual track, serial registration with three simulated registrar adapters, segmented escrow and independent settlement, suffix rollback with buyer gas, the deadline and exit path, and a read-only status console |
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

From the repository root. The bootstrap checks need `APPROVED_TEST_ROOT` set to
an existing, canonical directory chosen explicitly for them.

```sh
BOOTSTRAP_TEST_ROOT="$APPROVED_TEST_ROOT" python3 -B -m unittest discover -s ci/tests -v
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s exchange/tests -t . -v
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s scenarios/tests -t . -v
```

The whole local delivery in one command, which exits non-zero unless every
expectation passed over a confirmed, clean source tree:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m scenarios.cli run-all
```

## The reports, and what each one answers

Each is a subcommand of `python3 -B -m scenarios.cli`.

| Command | The question it answers |
| --- | --- |
| `run-all` | did every local expectation pass, over which exact source |
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
