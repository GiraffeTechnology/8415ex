# Stage 5 local delivery and independent acceptance

This supplement binds the independent local scenario and recovery checks to a
portable source/evidence archive. The separate `scenarios/` package in PR #10
contains the broader requirement matrix, six-panel storyboard and presentation
framework. Review and reuse that package after its producer resolves review
findings; this supplement does not replace or modify it.

## Exact batch boundaries

| Batch | Source | Actual local verification |
| --- | --- | --- |
| 1 | PR #11, c5c558646466edb5448d7f61a48ea8537dda0c3c, tree 1ba0d35033246dfa0fb41211fa4ecde0de0e3a5b | six scenarios; nine focused checks |
| 2 | PR #12, 3cbb4fdc13d6954291c5fcd2f4d2cb26dfda5984, tree f740f0c5bcd85b202d35e0bd4004af178abb7bca | five checks, each on all three routes |
| 3 | candidate commit/tree recorded in the external manifest | archive integrity checks and actual source/log readback |

Existing Stage 4 baseline is 9af92133f8746f06ce8bbc92cf8b571fd0f5ed46.
Its previously reported 252 domain and 29 bootstrap tests are baseline evidence;
they were not rerun or relabelled as new results.

## Coverage and recovery matrix

All routes are simulated: REG_DIRECT, REG_ELECTRONIC, REG_INTERMEDIARY.
The fixture APIs report route identity independently. No result establishes a
real registrar integration.

| Contract | Local evidence | Requirement references | Real evidence still owed |
| --- | --- | --- | --- |
| Whole receipt, independent release, separate exit steps/history | DEMO-01 | T-02, T-11, T-25, T-32, T-33 | actual UI/provider/receipt journey |
| Serial registration and release before final holder | DEMO-02 | T-03, T-04, T-12, T-13 | actual ordered registrar results |
| First refusal refunds original buyers | DEMO-03 | T-17, T-19, T-21 | real payment and asset authority |
| Later refusal preserves finalized prefix | DEMO-04 | T-18, T-19, T-29 | actual suffix-return reconciliation |
| Gas shortfall blocks and resumes without custody | DEMO-05 | T-20 to T-23 | actual gas funding and return mechanism |
| Cutoff rejects new trade, preserves in-flight completion/exit | DEMO-06 | T-24, T-25, T-32, T-33 | real deadline and collection journey |
| Unknown refund/return cannot be resent blindly | cross-route acceptance | T-23, T-29, T-30 | durable restart and provider enquiry |
| Failed refund resumes only the missing payment | cross-route acceptance | T-19, T-23 | durable adapter/journal proof |
| Nonzero gas remains separately recorded | cross-route acceptance | T-19, T-21 | approved units, conversion and deduction |
| Complete source, raw-log hashes, archive refusal cases | delivery integrity tests | T-38 | final merged-source and deployed-artifact identity |

## Reproducible Linux execution

Use an existing approved Linux source checkout and approved artifact destination.
Do not install another environment or write project files to a server system
disk. Standard library only; disable bytecode writes.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest exchange.tests.test_stage5 -v
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest exchange.tests.test_stage5_routes -v
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest exchange.tests.test_delivery -v
PYTHONDONTWRITEBYTECODE=1 python3 -B -m exchange.stage5
```

These are reproduction instructions. The original constrained Linux run used
`unittest.TextTestRunner` and an in-memory source importer; its exact commands
and actual start/end times are in the external run evidence. Source-tree
verification preceded commit creation; subsequent published trees matched it.
No command is recorded as executed merely because this guide lists it.

`exchange.delivery.build_bundle(source_bytes, evidence, raw_logs)` returns ZIP
bytes without filesystem writes. `verify_bundle(zip_bytes)` checks every listed
member, duplicate/unsafe paths, full regular-file source tree and evidence/log
binding in memory. It refuses source drift, missing logs and non-string source
identities. The caller supplies actual run records and chooses the approved
archive destination. The manifest cannot include its own hash; record the outer
ZIP SHA-256 separately and verify it after object-storage readback. Repeated
builds over identical inputs produce identical ZIP bytes.

A verifier proves internal consistency and source bytes, not that a producer's
command claim is true. Independent reviewers must compare raw execution logs,
the original host record and the exact published commit/tree.

## Execution evidence and acceptance

Every item below starts NOT_RUN unless independent, version-bound evidence is
attached. A local model pass cannot close it.

1. Select the reviewed merged commit and verify its tree, package hash and
   object-storage readback; preserve existing state and rollback references.
2. Bind the existing authorized Linux execution area and production target.
   Record actual runtime, output/cache mappings and deployed artifact identity.
3. Resolve network, token, contract, provider and journal bindings from approved
   records. Refuse missing/guessed bindings before any send.
4. Reconcile unknown outcomes before retry; distinguish same-object model resume
   from fresh-process persistence and recovery.
5. Exercise six real journeys and all three actual route contracts. Record
   source identity, commands, times, UI observations, transaction/receipt/block
   identities and actual gas responsibility, with human signing at its boundary.
6. Verify owner/holder order, immutable prefix, original-buyer refund and
   owner=holder plus all other exit checks. Physical handover and burn need
   separate evidence; do not collapse them into an atomic operation.
7. Independently verify required hosted CI and findings against the exact source;
   local passing tests or package publication do not establish final acceptance.
8. Reconcile final real evidence before replacing local-model labels in the
   demonstration, deck and video. Clearly label animation and unresolved items.

Unresolved decisions remain explicit: fee deduction/apportionment, real asset
return authority, registration-confirmed/payment-failed policy, late-result vs
deadline precedence, and physical voucher/burn recovery ordering. None receives
a business default from these fixtures. No deployment, signing, transaction,
new credential, runner or resource is performed by this package.
