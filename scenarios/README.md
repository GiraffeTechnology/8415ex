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
| `observations.py` | tracked-file enumeration, the secret scan (T-39) and measured observations (T-40) |
| `execution.py` | real command records: what ran, how it ended, or NOT_RUN |
| `cli.py` | one reproducible entry point |
| `STORYBOARD.md` | the factual storyboard and presentation outline |

## Commands

Linux, Python 3.10 or newer, standard library only.

```sh
# the whole local delivery; exit 0 only when every expectation passed over a
# confirmed, clean source tree with a complete file inventory
PYTHONDONTWRITEBYTECODE=1 python3 -B -m scenarios.cli run-all

# both outputs of one single execution, under one run id
python3 -B -m scenarios.cli run-all --json-out /tmp/ex-run.json --text-out /tmp/ex-run.txt

# also really execute the two unit suites and record their true status
python3 -B -m scenarios.cli run-all --execute-suites

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

A scenario that raises does not leave the assertions it managed to record
standing as acceptance: the matrix marks every case that scenario serves, and
`allCasesSound` is false. Partial progress before an exception is progress, not
a result.

The report carries a deterministic digest over everything except wall-clock
fields, so two runs of the same source over the same fixtures compare equal.

## Command records

A command record comes from an execution that happened, or it says it did not
happen. There is no third shape and no pre-filled success:

- the run's self record covers the completed calculation only, before publication;
  final process exit is known only to an external observer;
- the two unit suites are `not-run`, with no exit code and no timing, unless
  `--execute-suites` is given, in which case their real status, UTC timing, exit
  code and stdout/stderr digests are recorded;
- `failed`, `error`, `timeout` and `signalled` stay distinct, so "the suite
  failed" is never confused with "the suite never started";
- `--execute-suites` inside a suite this run started records `not-run` rather
  than re-entering the run.

## Source binding

The run reports observed source origins and on-disk file hashes. These do not
attest every executed byte, already loaded code object, bytecode cache, import
hook or monkey patch. The reported root must match the loaded project origins, the worktree must be clean, and the file inventory must cover
every enumerated path. A failed Git call, a root that is not this repository, an
empty enumeration, a tracked path missing from the worktree and an unreadable
file are each reported as an error; none of them is read as clean, empty or
consistent, and each one blocks a local pass.

Enumeration is NUL-delimited (`git ls-files -z`), so a path containing spaces
survives intact. The scan reports its own coverage — enumerated, scanned,
skipped with reasons, unreadable — and is clean only when enumeration succeeded,
at least one file was read, nothing was unreadable and no pattern matched. There
is no exemption for the scanner's own source.

## One run, one identity

A run id is unique per execution. `--json-out` and `--text-out` write both
renderings of the same single execution under that one id. Two invocations are
two runs, and their observations are never presented as one.

## Units

Principal and gas are separate obligations in separate units: a principal is an
amount in the quote asset, gas is a count of gas units borne by a named party.
They are recorded side by side and never subtracted from one another. Whether a
real fee is deducted from a refunded principal, in which asset and by whom, is
open decision D-04 and is reported `NOT_RUN`.

The domain's own rollback report still carries `netToOriginalBuyer`, a figure
derived by subtracting a gas-unit count from a quote-asset principal. That
projection lives in `exchange/ledger.py`, which this package does not own and
does not change. It is recorded as an existing-owner dependency in
`scenarios/handoff.py` and is never read here as real net proceeds.

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


## Publication and final evidence boundaries

Outputs must be outside both the requested source repository and the actually
imported repository. Symlink destinations and source aliases through symlink
parents are rejected. This protects source files, including untracked inputs
and Git metadata, from output replacement after reconciliation.

All outputs are staged before publication. If a later replacement fails, earlier
publications are rolled back to their old bytes, or removed if newly created.
Restoration and cleanup errors are failures and carry explicit recovery paths.
An unrestorable backup is retained; a published file with cleanup failure is
reported as published but not successful. This is recoverable publication, not
a cross-file atomic transaction: intermediate visibility, concurrent writers,
process termination and power loss are not covered. Consumers must wait for
and check the external receipt, not infer success from file existence.

The published JSON and text describe the same sealed calculation. Their delivery
status is explicitly `NOT_CAPTURED_IN_PROCESS`. The final stdout record adds
observed delivery and post-delivery source reconciliation; its calculation-only
self record remains unchanged even when output fails. The process's actual final
exit and complete raw logs are captured outside that process by
`execution.capture_cli(..., raw_log_dir=...)`. The directory must already exist;
log-write failures raise rather than invent a successful log reference.

CI retains `stage5-process.json`, both full command stream logs, the published
calculation files when present, and `stage5-evidence-index.json`. The latter adds
the actual external observation for T-39/T-40 and pointers to saved raw logs.
The in-process index has no invented future raw-log path: inline tails and
digests are explicitly distinguished from full logs. Suite command references
are aggregate evidence, never individual case verdicts. T-35 through T-38 and
all 13 real-evidence slots remain NOT_RUN.

Loaded-module details include the `__main__` entry point for `python -m`, its
project module name, resolved origin, byte count and current disk hash. The
before/pre-publication/final snapshots expose their complete measurements and
state their limits; they do not claim import-time execution-byte attestation.

## Historical citations and conservative matrix outcomes

Current commands must fit the current run window. Historical evidence belongs
in separate `historicalCitations`, with historical run ID, full source commit
and tree, an evidence locator, `scope: historical-citation` and
`verification: unverified`. These are structurally checked citations, not
verified historical source or current-run pass evidence. Merely supplying a
nonblank foreign `observedInRun` in a current command cannot bypass timing.

Each case retains its own recorded assertions. A failed or blocked scenario
conservatively taints the cases it serves; mixed failed/blocked assertions keep
both counts, while failed scenario propagation takes precedence over a case
that only recorded blocked assertions. This deliberately conservative choice
is not a claim that the blocked assertion itself executed and failed.
An exception or incomplete scenario remains unsound for every served case.
Neither conservative propagation nor a unit-suite-only row is a false pass.
