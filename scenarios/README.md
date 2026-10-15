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
| `decisions.py` | the open-decision register: what each one blocks, and what it does not |
| `receipt.py` | the nine-group candidate receipt, assembled from a completed run |
| `reuse.py` | what this package reuses, what is simulated, and what is not located yet |
| `events.py` | the logical event contract, checked read-only over the domain's timeline |
| `stages.py` | per stage: what is developed here, what is accepted elsewhere, what is owed |
| `dossier.py` | per scenario: the nine items a demonstration must carry, and what did not resolve |
| `storyboard.py` | the presentation outline, parsed and checked against the code it describes |
| `evidence_index.py` | one index from requirement to artifact over a run's own artefacts |
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

# the nine-group candidate receipt for a completed run
python3 -B -m scenarios.cli receipt [--execute-suites]

# the open-decision register
python3 -B -m scenarios.cli decisions

# the reuse and interface map, read from the imported modules and this source
python3 -B -m scenarios.cli reuse

# the logical event contract, its conformance, and one timeline's coverage
python3 -B -m scenarios.cli events

# the stage map: developed here, accepted elsewhere, still owed
python3 -B -m scenarios.cli stages

# per scenario: the nine items a demonstration must carry
python3 -B -m scenarios.cli dossier

# whether the presentation outline still describes the code
python3 -B -m scenarios.cli storyboard

# individual parts
python3 -B -m scenarios.cli scenarios
python3 -B -m scenarios.cli paths
python3 -B -m scenarios.cli matrix --json
python3 -B -m scenarios.cli manifest --json
python3 -B -m scenarios.cli handoff --json
python3 -B -m scenarios.cli validate-config
python3 -B -m scenarios.cli observations
python3 -B -m scenarios.cli evidence-index

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

## The candidate receipt

`scenarios.cli receipt` performs a run and then describes it, in the nine groups
a candidate has to account for. Nothing in the receipt is recomputed: it is
assembled from the record that run already produced, so it cannot disagree with
it.

| Group | Covers |
| --- | --- |
| 1 source | repository, branch, full commit and tree, parents, base and the exact diff range |
| 2 requirements | which identifiers this candidate claims, which are recorded as not locally testable, what is unimplemented or unexecuted, and the open decisions |
| 3 environment | platform, runtime, the actual commands, a configuration summary and the run id |
| 4 results | totals, per-command outcome, exit code, instants and the digests identifying the raw output |
| 5 artifacts | each produced file with its byte count, digest, how it was built and where it is stored |
| 6 deployment | target, deployed version, URL and health verification |
| 7 chain | chain id, verified addresses, transaction hashes, receipts, block identity, confirmation policy and events |
| 8 reconciliation | per scenario, the per-segment funds and gas, owner and holder positions, registration prefix and recovery outcome |
| 9 blockers | the blocked action, the missing input, the affected scope, its owner, and the independent work that continued |

Groups 6 and 7 cover work this package does not perform, so every field in them
reads `NOT_RUN`. They are still emitted, because in a hand-written receipt an
omitted group and an unperformed one look identical, and here they cannot.

The private requirements identity belongs to group 2 and is never embedded in
this source. Supply it at call time through `EX_REQUIREMENTS_IDENTITY`, the same
way the scan takes private markers; the receipt reports only whether it was
supplied, so a published artifact never carries it.

Group 1's diff range is the range a reviewer can pass straight to `git diff`.
It is computed from the head's parents and the merge base against the branch
this work is based on, so the diff under review is named rather than guessed.
`manifest.parent_identity()` returns it on its own if that is all you need.

## The open-decision register

`scenarios.cli decisions` prints the open decisions, and each entry names four
things: what is undecided, who confirms it, the narrowest scope that genuinely
waits on it, and the work that proceeds anyway. That last column is the point.
Without it an open decision tends to be read as blocking far more than it does,
and authorized work stops for a question it does not depend on.

The register answers nothing and is not a defect list. Where a question could be
settled by reading an existing interface or configuration rather than by a
product choice, the entry says so, so it is investigated instead of escalated.
Three decisions are reported by a scenario as an observation rather than
resolved, and `decisions.reported_locally()` names which scenario does that.

It also records the defaults that must not be assumed in place of a decision: a
pre-funded test account standing in for a gas policy, a budget deduction
standing in for a fee mechanism, or a device or attestation setting standing in
for an authorization model.

## The reuse and interface map

`scenarios.cli reuse` answers two questions that otherwise get answered from
memory: what does this package actually consume, and what is simulated.

Neither half is a hand-maintained list. The domain half declares the real
attribute names taken from each domain module and checks them against the
imported module, so a rename in the domain shows up as an unresolved name. It
then reads this package's own import statements out of the source and compares
them with the declaration, which catches the opposite drift: a module that is
consumed but never declared. The two findings are kept apart, because they mean
different things — an undeclared module is a gap in the map, a declared module
with no import left is a dependency the code dropped. Imports that only the test
suites make are reported on their own line and are not counted as package
reuse: a suite importing a domain module to assert something about it is not
this package consuming it.

The adapter half is read from a real run rather than from the module's own list,
so a role that stopped being exercised stops appearing. Every adapter role is
simulated. This package connects to no real registrar, payment provider, asset
control, collection desk or wallet, and says so wherever a result is reported.

The last section is the one usually missing: the interfaces that are **not
located yet**. An unlocated interface is neither a defect nor a simulated one —
it is work that cannot start until someone says where the real thing is. Each
names the open decision that tracks it and the owner who can answer it, so it
reads as a dependency with an owner rather than as an unexplained hole.

The subcommand exits non-zero when the map stops accounting for the source.

## The load record, and what it refuses to be

`EX-NFR-08` asks that a recorded test load, execution time, queue backlog and
failure rate exist before any throughput or latency figure is spoken about. The
workload observation is those four, and it is explicit about not being a fifth
thing: one observation on one machine is a load record, never a target.

Two separations carry the weight. A `not-run` obligation is not a failure, so it
has its own rate and is excluded from the failure rate; counting it as one would
make an honest outstanding duty read as a defect. And a backlog is a count, not
a problem: a deferred registration result waiting for its gap is the normal
serial state, and an outstanding leg is work in flight.

Rates are integers in parts per thousand, because no floating point appears in
these records, and a rate over nothing is null rather than zero, because zero
would read as a measurement.

The backlog is read from facts the scenarios already record, so nothing is
instrumented specially for it. The second figure per scenario is the **last
recorded** value, not the end state: a scenario stops recording a fact once it
is no longer what a step is about, so a non-zero last value means it stopped
mentioning the backlog, not that it ended with one. Writing that distinction
down immediately earned its keep: the out-of-order scenario recorded its
deferral building up and never recorded it draining, so the one scenario that
demonstrates a backlog clearing had no record of it clearing. It records it now.

## Keeping the outline from going stale

`STORYBOARD.md` is the part of this delivery most likely to go stale and least
likely to be noticed doing it. A scenario can change route, a case can stop
owing real evidence, a panel can describe a scenario that no longer exists, and
nothing fails: the document just becomes wrong while still reading as
authoritative to the audience it was written for.

So `scenarios.cli storyboard` parses it and checks it. Every panel must name a
scenario that exists and the route that scenario really runs; all six must
appear exactly once; every case a panel says is still owed must be a real case
that genuinely still owes real evidence, so a panel can neither invent an
obligation nor keep claiming a discharged one. The video segments may name only
scenarios that exist and must each require on-screen labelling, and five claims
the outline has to carry - that a local run is labelled as one, that it is not a
public test network result, that a rendered page is not interface acceptance,
that no cooperation is implied, and that the routes are simulated roles - are
checked as present, because dropping one is how a factual outline becomes a
misleading one.

The checks are one-directional about wording on purpose. They verify the
identifiers, the routes and the obligations and say nothing about the prose: a
test that policed the prose would be a test nobody could edit the document past.
Every finding has its own negative control in the suite, so the check is known
to fail when the outline drifts rather than only known to pass today.

## What each scenario has to carry

A scenario report says what was checked. It does not say whether the scenario
carries everything a demonstration has to present, and those are different
questions: a run can pass every expectation while still not recording the prices
it used or the escrow result it reached. `scenarios.cli dossier` declares the
nine items and resolves each one from the scenario record.

Three statuses do the work, and keeping them apart is the point.

A **gap** is an item a local run could record and did not. That is the only
status here that is a finding against this surface, and writing this found three
real ones: the two rollback scenarios and the deadline scenario each reached a
funded state, asserted things about it, and recorded no per-segment escrow
result on any step. They record it now, so the item resolves from the record
rather than from the wording of a check.

**Resolved elsewhere** is an item the scenario does not hold but this delivery
does, named so a reviewer follows it instead of concluding it is missing. The
event trail is the one: it belongs to the domain and is read by `events.py`
rather than restated inside each scenario.

**NOT_RUN** is an item no local run can discharge at all - a transaction hash
with nothing signing, a page state with no browser. It carries the evidence slot
that will hold it and the reason it is empty, the slot is checked against the
handoff checklist, and no local stand-in is offered: the page state stays
NOT_RUN however completely the status pages render, and `renderedBy` names the
renderer precisely so it is on record as not being evidence.

Rules match on structure and on case identifiers, never on the wording of an
expectation, so rephrasing a check cannot silently turn an item into a gap. A
gap names exactly which keys were missing, and an empty report covers nothing
rather than reading as complete.

## The stage map

The acceptance matrix says which case belongs to which stage. It does not say
who does the rest, and that is what `scenarios.cli stages` answers: per stage,
what this surface develops, what is tested and accepted by whoever owns that,
and what genuine real-world input stays with its existing owner.

Three things keep it checkable rather than decorative. Every deliverable names a
path and the path is checked against the disk, so a deliverable claiming a module
that is not there is a finding instead of prose nobody re-reads. Every stage's
case list is read from the matrix rather than restated, so the two cannot
disagree without this module reporting it. And every dependency names its owner,
the scope it genuinely blocks, the scope it does **not** block, and the next
step, pointing at a slot that really exists in the handoff checklist.

That "does not block" column is the one that earns its place. A dependency
stated without it reads as blocking everything, and authorized work stops for a
question it does not depend on: a missing deployment target blocks every
real-chain obligation and blocks none of the local delivery, and an undecided
refund fee blocks the fee figure in a real refund and not the refund model that
deducts nothing and says so.

The map claims nothing about completion. A stage being developed here says
nothing about it being accepted, every stage carries `localHalfOnly`, and the
two cases that belong to every stage rather than one are named as such rather
than dropped.

## The logical event contract

`scenarios.cli events` is the event contract of PRD section 10.2, answered from
where this task actually stands. The recorder and the event shape belong to the
domain and ledger surface, which this task does not own, so the contract is
checked read-only rather than enforced, and what cannot be read is reported as
an interface gap with its owner and the next step rather than fixed in someone
else's file.

**The vocabulary** is a conformance check. The kinds the domain records are read
out of its own source, so a kind it adds or removes is a finding rather than an
invisible change, and two findings are kept apart because they mean different
things: a kind the domain records and the contract does not declare means the
trail carries something unaccounted for, while a kind the contract declares and
the domain does not record means an audit group that cannot be evidenced until
someone records it. Two kinds the domain writes, minting and an observed gas
figure, serve no group and are declared as ancillary, so they are not reported
as undeclared and never count as coverage of something they do not evidence. The
report says plainly that it is not an enforcement point: the recorder still
accepts any string, and this check is the only thing that notices.

**Correlation** is derived from the event as it stands, with every key present
and `carriedByDomain` saying which were really on it. A key the domain does not
carry is null, because an absent key and an unknown value read the same to a
consumer and are not the same thing, and each key names where it comes from. No
run id is invented, and no local event is ever reported as observed on chain.

**Replay** needs nothing but the timeline. Two records that differ only in a
free-form detail are one event, so a re-delivery is a counted duplicate that
changes nothing: replaying the same events twice gives the same digest and the
same movement count. Out-of-order delivery is reported rather than silently
reordered, and an undeclared kind met during a replay is reported rather than
raised, because refusing would make an unaccounted kind look like a crash in the
reader.

An attempt is not a movement. Where an attempt has its own completed counterpart
(a refund records `segment-refunded` on success and `segment-refund-attempt`
only when it fails), counting the attempt too would double-count the success. A
release has no separate completion record, so its own escrow status decides, and
a failed or unknown-outcome release is recorded as an attempt that moved nothing
rather than as money reported paid that the adapter never confirmed.

Each group gets exactly one status, so the buckets cannot overlap and a group
cannot be read two ways at once:

| status | what it means |
| --- | --- |
| `recorded` | every locally recordable kind in the group was observed |
| `partly-recorded` | some were, and the group needs no chain observation |
| `derived` | correctly read off other events, and said to be derived |
| `awaiting-chain-observation` | part of the group needs a real chain |
| `not-observed` | the group simply did not occur in this run |

`awaiting-chain-observation` exists for the case most easily overstated. A
transfer is submitted locally and observed on a chain; calling that group
recorded because its local half is complete would be exactly the conflation this
report prevents, so the group says it is waiting, with `localHalfObserved`
showing that the local part really was recorded. The confirmed prefix advancing
is the opposite case: the domain records no event for it, but every registration
result carries the resulting holder index, so it is reported as derived: a
correct reading of the trail, not an event, which a consumer told it was
recorded would go looking for.

## The evidence index, including the artifact it lands in

`scenarios.cli evidence-index` prints one row per case, and the row is a chain a
reviewer can walk in either direction:

    approved requirement
      -> the assertion that was actually recorded
      -> where it is implemented, and which test covers it
      -> the exact source and run it was observed under
      -> what was observed, with the raw expected and observed values
      -> which artifact carries the row, and where inside it
      -> what real evidence is still owed, and who owns it

The last-but-one leg is new, and it closes the gap that mattered: without it, a
reviewer holding a delivered file cannot tell which rows that file is supposed
to carry, and a row cannot say whether it reached a file at all. Each row names
every declared output, and for the JSON output gives a pointer that resolves
that same row inside the delivered record — the pointer is relative to the
file's own root, because that is where a reviewer opening the file starts.

It is also the leg most easily overstated, so it is deliberately understated.
The index is built before the outputs are written, so at index time every
artifact is **declared, not delivered**: each slot and the index as a whole
report `NOT_CAPTURED_IN_PROCESS` and point at the delivery report that carries
the actual per-path result. The published file says this about itself even
though its own existence proves the write happened, because the record inside it
was serialised before the write was attempted. A run that declared no output
file is reported as `NO_ARTIFACT_DECLARED` — a legitimate run whose rows are
carried by stdout only, not a delivery failure.

The text summary is named as an artifact but carries no row pointer, because it
is a summary and does not contain the row verbatim.

The index is rebuilt when the run is sealed, so the declared plan is carried on
the bundle from the moment it is declared. A rebuild without it would drop the
artifact leg from the only copy a reviewer ever reads, which is why the
guarantee is tested on the published file rather than on the in-memory bundle.

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
