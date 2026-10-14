# Local Stage 5 preparation

This package prepares the Stage 5 deliverables that do not require a deployment
or any chain execution. It drives the existing `exchange` domain through
labelled synthetic fixtures, records what actually happened, and states what is
still owed.

It does not modify the domain implementation, and it keeps its own files
separate from it.

## What is here

| Module | Role |
| --- | --- |
| `harness.py` | scenario definition, execution and recorded expectations |
| `demos.py` | the six confirmed scenarios, DEMO-01 to DEMO-06 |
| `paths.py` | one contract result per registrar route, plus the coverage map |
| `matrix.py` | the requirement, source and acceptance matrix |
| `validation.py` | configuration and evidence validators |
| `manifest.py` | source and package manifest |
| `handoff.py` | the execution checklist with NOT_RUN evidence slots |
| `observations.py` | the secret scan (T-39) and measured observations (T-40) |
| `cli.py` | one reproducible entry point |
| `STORYBOARD.md` | the factual storyboard and presentation outline |

## Commands

Linux, Python 3.10 or newer, standard library only.

```sh
# the whole local delivery; exit 0 only when every expectation passed
PYTHONDONTWRITEBYTECODE=1 python3 -B -m scenarios.cli run-all

# individual parts
python3 -B -m scenarios.cli scenarios
python3 -B -m scenarios.cli paths
python3 -B -m scenarios.cli matrix --json
python3 -B -m scenarios.cli manifest --json
python3 -B -m scenarios.cli handoff --json
python3 -B -m scenarios.cli validate-config
python3 -B -m scenarios.cli observations

# this package's own tests
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s scenarios/tests -t . -v
```

## How a result is recorded

A scenario records rather than asserts. Each expectation keeps the expected and
observed value next to the cases it serves, so a mismatch survives as a genuine
failure in the report instead of raising out of the run. An outcome is one of
`passed`, `failed`, `blocked` or `not-run`:

- `failed` is a real disagreement between the scenario and the implementation.
  It is reported with both values, never relaxed away.
- `blocked` means the check could not run, with the reason.
- `not-run` is a real Stage 5 obligation this local run is not entitled to
  discharge. It is reported and never counted as a pass.

The report carries a deterministic digest over everything except wall-clock
fields, so two runs of the same source over the same fixtures compare equal.

## Route coverage

All three routes go through the same state machine and the same adapter
contract, and each gets its own contract result in `paths.py`. The six scenarios
each name one main route, covering all three across the set, rather than
multiplying six scenarios by three routes. Success on one route never
establishes another.

| Route | Contract result | Scenarios using it as the main route |
| --- | --- | --- |
| `REG_DIRECT` | `PATH-REG_DIRECT` | DEMO-01, DEMO-04 |
| `REG_ELECTRONIC` | `PATH-REG_ELECTRONIC` | DEMO-02, DEMO-05 |
| `REG_INTERMEDIARY` | `PATH-REG_INTERMEDIARY` | DEMO-03, DEMO-06 |

## What stays unresolved

The designated test token address, the deployment target, the endpoint and the
wallet permissions are **not** set here and are not guessed. `UNRESOLVED` is the
only value the configuration validator accepts for them, and a concrete value
is refused as unverified. The validator checks shape and non-invention only; it
never means a configuration is approved or an address verified.

Real deployment and authorized test-network execution belong to the party that
owns them. Their evidence slots in `handoff.py` start at `NOT_RUN`, and a
fabricated hash or a placeholder success is refused by `validation.py`.

T-35 to T-38 stay real acceptance obligations. A local model result never
substitutes for them, and a rendered status page is not interface acceptance.
