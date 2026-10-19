"""The stage map: what is developed here, additional integration evidence.

The acceptance matrix already says which case belongs to which stage. What it
does not say is which evidence remains outstanding, and that is the question a stage
map has to answer: for each stage, what this surface develops, what is then
tested with independent evidence, and what real-world integration input
remains outstanding.

Three things keep this honest rather than decorative.

Every deliverable names a path, and the path is checked against the disk. A
deliverable claiming a module that is not there is a finding, not a line of
prose nobody re-reads.

Every stage's case list is cross-checked against the acceptance matrix. If the
two disagree, the disagreement is reported: a stage map that drifts from the
matrix is worse than no stage map, because it reads as authoritative.

A dependency is named with its evidence category, the scope it genuinely blocks and the next
step. A stage is never marked complete because its local half is done, and never
dropped because its real-world evidence is outstanding.

The path check was one-directional and that was not enough. It caught a
deliverable claiming a module that is not there, and said nothing about a module
that is there and claimed by nothing: three shipped modules were missing from the
map, one of them a whole new contract group. A map that reads as "what is
developed here" while omitting part of what is shipped is the same failure as a
map pointing at files that do not exist, so both directions are now checked.
"""
import pathlib

from . import matrix

#: The package this map speaks for. Modules of other surfaces are not this
#: map's to claim.
PACKAGE = "scenarios"

#: Files in this package that are not deliverables, with the reason. An
#: exemption is stated rather than skipped, so it can be argued with.
NOT_A_DELIVERABLE = {
    "scenarios/__init__.py": "the package marker: it states what the package is and "
                             "declares no deliverable of its own",
}

#: What this surface develops per stage, with the path that holds it. The path
#: is checked, so a deliverable cannot claim a module that does not exist.
DEVELOPED_HERE = {
    0: (
        {"deliverable": "the baseline source and run identity a reviewer can re-derive",
         "where": "scenarios/manifest.py"},
        {"deliverable": "the reuse and interface map, with the interfaces still unlocated",
         "where": "scenarios/reuse.py"},
        {"deliverable": "the requirement to case to implementation to run traceability",
         "where": "scenarios/matrix.py"},
        {"deliverable": "the index from requirement through to the artifact it lands in",
         "where": "scenarios/evidence_index.py"},
        {"deliverable": "the open-decision register, with what each one does not block",
         "where": "scenarios/decisions.py"},
        {"deliverable": "the candidate receipt, with the chain and deployment groups NOT_RUN",
         "where": "scenarios/receipt.py"},
        {"deliverable": "the one subcommand list the parser and the usage check both "
                        "read, so neither can drift from the other",
         "where": "scenarios/commands.py"},
        {"deliverable": "this stage map itself, cross-checked against the matrix and "
                        "against the modules on disk in both directions",
         "where": "scenarios/stages.py"},
        {"deliverable": "the measured share of the domain's own public API that this "
                        "delivery enters, with any unexercised method accounted for",
         "where": "scenarios/surface.py"},
        {"deliverable": "the comparison of the finished record with itself, which "
                        "refuses a published copy that contradicts another",
         "where": "scenarios/agreement.py"},
    ),
    1: (
        {"deliverable": "the six scenarios as recorded expectations over the domain",
         "where": "scenarios/demos.py"},
        {"deliverable": "one contract result per registrar route",
         "where": "scenarios/paths.py"},
        {"deliverable": "the scenario runner and its recorded assertions",
         "where": "scenarios/harness.py"},
        {"deliverable": "the logical event contract, checked read-only over the timeline",
         "where": "scenarios/events.py"},
        {"deliverable": "the logical operations, resolved onto the real methods",
         "where": "scenarios/operations.py"},
        {"deliverable": "the domain guarantees the six scenarios never asserted: the "
                        "whole-receipt rule, the wallet grant and its bounds, the "
                        "pairing rule, the single valid head and reproducibility",
         "where": "scenarios/guarantees.py"},
    ),
    2: (
        {"deliverable": "the segmented-funding scenarios, with principal, amount, asset "
                        "units and gas bearer kept distinct",
         "where": "scenarios/demos.py"},
        {"deliverable": "the replay check that repeated consumption settles nothing twice",
         "where": "scenarios/events.py"},
        {"deliverable": "the contract that each segment settles on its own evidence, "
                        "and that a failed or unknown payment is not a registration "
                        "refusal",
         "where": "scenarios/guarantees.py"},
    ),
    3: (
        {"deliverable": "the suffix-rollback and buyer-gas scenarios, including the "
                        "blocked and resumable states",
         "where": "scenarios/demos.py"},
        {"deliverable": "the gas unit separation, so a gas count is never netted against "
                        "a quote-asset principal",
         "where": "scenarios/demos.py"},
        {"deliverable": "the contract that a repeated or re-ordered observation moves "
                        "nothing twice",
         "where": "scenarios/guarantees.py"},
    ),
    4: (
        {"deliverable": "the deadline, exit and voucher scenarios, with the non-atomic "
                        "steps shown as separate instants",
         "where": "scenarios/demos.py"},
    ),
    5: (
        {"deliverable": "the whole local delivery in one reproducible command",
         "where": "scenarios/cli.py"},
        {"deliverable": "the execution records: what ran, how it ended, or NOT_RUN",
         "where": "scenarios/execution.py"},
        {"deliverable": "the configuration and evidence validators",
         "where": "scenarios/validation.py"},
        {"deliverable": "the bounded secret scan and the measured observations",
         "where": "scenarios/observations.py"},
        {"deliverable": "the execution checklist with every real-evidence slot unfilled",
         "where": "scenarios/handoff.py"},
        {"deliverable": "the check that keeps the usage instructions true",
         "where": "scenarios/docs.py"},
        {"deliverable": 'the definition of done, clause by clause, with its evidence dependency',
         "where": "scenarios/completion.py"},
        {"deliverable": 'per requirement section, implementation and evidence dependencies',
         "where": "scenarios/prd.py"},
        {"deliverable": "per scenario, the nine items a demonstration must carry",
         "where": "scenarios/dossier.py"},
        {"deliverable": "the factual storyboard and presentation outline",
         "where": "scenarios/STORYBOARD.md"},
        {"deliverable": "the check that keeps the outline describing the code",
         "where": "scenarios/storyboard.py"},
    ),
}

#: Independent technical acceptance evidence, per stage.
#: Model evidence does not establish integration acceptance.
ACCEPTED_ELSEWHERE = {
    0: ("independent re-derivation of the baseline identity",
        "review of the traceability denominator against the approved requirements"),
    1: ("the domain and ledger implementation behind these scenarios",
        "operable UI acceptance; a rendered status page is not one"),
    2: ("the authoritative settlement binding for a real release",
        "reconciliation against a real payment provider's records"),
    3: ("real asset-return control and the wallet authorization behind it",
        "actual fee accounting against real gas spent"),
    4: ("the voucher hand-over and burn sequence as a real process",
        "the conflict priority and hand-over order where they are still undecided"),
    5: ('deployment to a supported environment and the run on a real test chain',
        "independent security review of the exact head",
        "verification and packaging of the presentation materials"),
}

#: Real-world integration evidence. Each entry names the
#: scope it blocks, so a stage is neither marked complete without it nor
#: abandoned because of it.
REAL_WORLD_DEPENDENCIES = (
    {
        "stage": 1,
        "needs": "an operable UI journey in a real browser",
        "owner": 'browser acceptance evidence',
        "blocks": "only the UI half of this stage's acceptance",
        "doesNotBlock": "the scenarios, the route contracts or their local results",
        "nextStep": "run the journeys against a deployed build and record what was "
                    "asserted on screen",
        "slot": "uiAssertions",
    },
    {
        "stage": 2,
        "needs": "the authoritative settlement binding for a real release",
        "owner": 'domain integration evidence',
        "blocks": "only real per-segment settlement acceptance",
        "doesNotBlock": "the segmented-funding model or its local reconciliation",
        "nextStep": "name the real binding, then bind a release to it instead of to "
                    "a simulated source",
        "slot": "perSegmentReconciliation",
    },
    {
        "stage": 3,
        "needs": "real asset-return control and its wallet authorization",
        "owner": 'asset-control interface and permission evidence',
        "blocks": "only a real on-chain rollback",
        "doesNotBlock": "the rollback model, the fee separation or the recovery paths",
        "nextStep": "name the control interface and the permissions it needs",
        "slot": "transactionHashes",
    },
    {
        "stage": 3,
        "needs": "whether a real fee is deducted from a refunded principal, in which "
                 "asset and by whom",
        "owner": 'fee specification',
        "blocks": "only the fee figure in a real refund",
        "doesNotBlock": "the refund model, which deducts nothing and says so",
        "nextStep": "decide it; until then the obligation stays NOT_RUN",
        "slot": "perSegmentReconciliation",
    },
    {
        "stage": 4,
        "needs": "the confirmation and recovery order for voucher hand-over, stopping "
                 "resale and the burn",
        "owner": 'product specification',
        "blocks": "only the branches whose order is undecided",
        "doesNotBlock": "the deadline, the eligibility checks or the recorded steps",
        "nextStep": "decide the order; the gap is listed rather than guessed",
        "slot": "events",
    },
    {
        "stage": 5,
        "needs": "a supported deployment target, its configuration and the connected chain "
                 "identity",
        "owner": 'deployment evidence',
        "blocks": "every real-chain and deployment obligation",
        "doesNotBlock": "the local delivery, its records or the prepared package",
        "nextStep": "supply the verified target and configuration; nothing here may "
                    "guess them",
        "slot": "deployedHead",
    },
    {
        "stage": 5,
        "needs": "independent security review of the exact head",
        "owner": 'security review evidence',
        "blocks": "general release",
        "doesNotBlock": "functional local development or a functional-testing candidate",
        "nextStep": "review the exact head; local suites are preparation, never an audit",
        "slot": "requiredCiRun",
    },
)

#: The stages this map covers, with the one-line description this repository
#: uses for each. These are engineering phases of this work, not approvals.
STAGE_TITLES = {
    0: "baseline identity, reuse and the evidence entry point",
    1: "domain state, authorized intents and the three route contracts",
    2: "segmented funding and independent per-segment settlement",
    3: "suffix rollback and buyer gas",
    4: "deadline, exit and voucher hand-over",
    5: "integration, delivery and the honest presentation of it",
}


def cases_by_stage():
    """Which cases the acceptance matrix assigns to each stage.

    Read from the matrix rather than restated here, so the two cannot disagree
    without the disagreement being this module's own finding. The keys are
    strings because one stage is "all" rather than a number, and because a
    canonical encoding admits no other kind of key.
    """
    grouped = {}
    for case, stage in sorted(matrix.CASE_STAGE.items()):
        grouped.setdefault(str(stage), []).append(case)
    return {stage: sorted(cases) for stage, cases in sorted(grouped.items())}


def shipped_modules(root="."):
    """Every module this package ships, read from the disk rather than listed.

    Test modules are left out: a test is the check on a deliverable, not a
    deliverable a stage develops. An unreadable package is reported as such,
    because an empty module list would make every claim look accounted for.
    """
    base = pathlib.Path(root)
    folder = base / PACKAGE
    if not folder.is_dir():
        return {"package": PACKAGE, "readable": False, "modules": [],
                "error": "EX_PACKAGE_UNREADABLE"}
    found = []
    for path in sorted(folder.rglob("*.py")):
        parts = path.relative_to(base).parts
        if "tests" in parts or parts[-1].startswith("test_"):
            continue
        found.append(path.relative_to(base).as_posix())
    return {"package": PACKAGE, "readable": True, "modules": found, "error": None}


def _deliverables(stage, root):
    """One stage's deliverables, with each path checked against the disk."""
    checked = []
    for entry in DEVELOPED_HERE[stage]:
        path = pathlib.Path(root) / entry["where"]
        checked.append(dict(entry, whereExists=path.is_file()))
    return checked


def build(root="."):
    """The stage map, cross-checked against the acceptance matrix and the disk."""
    by_stage = cases_by_stage()
    every_stage_case = {case for cases in by_stage.values() for case in cases}
    stages = []
    missing_paths = []
    for stage in sorted(DEVELOPED_HERE):
        deliverables = _deliverables(stage, root)
        missing_paths.extend(entry["where"] for entry in deliverables
                             if not entry["whereExists"])
        dependencies = [dict(entry) for entry in REAL_WORLD_DEPENDENCIES
                        if entry["stage"] == stage]
        stages.append({
            "stage": stage,
            "title": STAGE_TITLES[stage],
            "developedHere": deliverables,
            "developedHereCount": len(deliverables),
            "acceptedElsewhere": list(ACCEPTED_ELSEWHERE[stage]),
            "cases": by_stage.get(str(stage), []),
            "caseCount": len(by_stage.get(str(stage), [])),
            "realWorldDependencies": dependencies,
            "dependencyCount": len(dependencies),
            "localHalfOnly": True,
        })
    unassigned = sorted(set(matrix.CASE_REQUIREMENTS) - every_stage_case)
    invented = sorted(every_stage_case - set(matrix.CASE_REQUIREMENTS))
    # The other direction of the path check: a module that is shipped and that
    # no stage claims is a gap in the map, not in the code.
    shipped = shipped_modules(root)
    claimed = {entry["where"] for entries in DEVELOPED_HERE.values()
               for entry in entries}
    unclaimed = sorted(name for name in shipped["modules"]
                       if name not in claimed and name not in NOT_A_DELIVERABLE)
    all_stage_cases = [case for stage in sorted(DEVELOPED_HERE)
                       for case in by_stage.get(str(stage), [])]
    return {
        "schema": "8415ex-stage-map/1",
        "stages": stages,
        "stageCount": len(stages),
        "casesByStage": by_stage,
        "casesNotAssignedToANumberedStage": sorted(
            case for case, stage in matrix.CASE_STAGE.items()
            if str(stage) not in {str(known) for known in DEVELOPED_HERE}),
        "casesInNoStage": unassigned,
        "casesInNoMatrixRow": invented,
        "duplicatedCases": sorted({case for case in all_stage_cases
                                   if all_stage_cases.count(case) > 1}),
        "missingDeliverablePaths": sorted(set(missing_paths)),
        "shippedModules": shipped["modules"],
        "shippedModuleCount": len(shipped["modules"]),
        "packageReadable": shipped["readable"],
        "packageError": shipped["error"],
        "claimedPaths": sorted(claimed),
        "shippedButClaimedByNoStage": unclaimed,
        "notADeliverable": dict(NOT_A_DELIVERABLE),
        "everyShippedModuleIsClaimed": shipped["readable"] and not unclaimed,
        "agreesWithMatrix": not unassigned and not invented and not missing_paths,
        "slotsDependedOn": sorted({entry["slot"] for entry in REAL_WORLD_DEPENDENCIES}),
        "isNot": [
            "not an approval: these are engineering phases of this work, and a stage "
            "being developed here says nothing about it being accepted",
            "not a completion claim: every stage's local half is all this surface "
            "delivers, and each dependency names the scope it still blocks",
            'dependency labels identify technical evidence categories',
            "not a claim about other surfaces: only this package's own modules are "
            "checked for being claimed, because a stage map here cannot speak for "
            "the domain or the CI surface",
        ],
    }
