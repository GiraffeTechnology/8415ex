"""Completion evidence, clause by clause.

Local signals and additional integration evidence are tracked separately.
Model results do not establish deployment, chain, browser or security
acceptance. Non-claims checked against a run are distinguished from declarations.
The legacy owner fields carry technical evidence categories."""
from . import matrix, stages

#: What the clauses need, as paths into a run's bundle. ``stages`` resolves
#: through the acceptance matrix instead: every case belonging to those stages
#: must have a local outcome that really stands for local coverage.
LOCAL_OUTCOMES_THAT_STAND = ("passed", "unit-suite-only")

#: The clauses of the definition of done, each with the signals that evidence
#: it here and the additional integration evidence still required.
CLAUSES = (
    {
        "clause": "the six confirmed scenarios have reproducible evidence inside "
                  "the controlled test scope",
        "signals": (("scenarioReport", "allPassed"),
                    ("dossier", "allItemsCarried")),
        "stages": (),
        "awaits": ({"needs": "the same six scenarios on a real test chain",
                    "owner": 'deployment evidence',
                    "slot": "transactionHashes"},),
    },
    {
        "clause": "the three registration routes are covered and clearly labelled "
                  "as simulated roles",
        "signals": (("pathReport", "allPassed"),
                    ("reuse", "allAdaptersSimulated")),
        "stages": (),
        "awaits": ({"needs": "a real registrar interface behind any route",
                    "owner": 'domain integration evidence',
                    "slot": "events"},),
    },
    {
        "clause": "segmented funding and bounded rollback behave as specified",
        "signals": (),
        "stages": (2, 3),
        "awaits": ({"needs": "the authoritative settlement binding, and real "
                             "asset-return control for an on-chain rollback",
                    "owner": 'asset-control interface and permission evidence',
                    "slot": "perSegmentReconciliation"},),
    },
    {
        "clause": "the deadline and exit path behaves as specified",
        "signals": (),
        "stages": (4,),
        "awaits": ({"needs": "the voucher hand-over and burn sequence as a real "
                             "process, in a decided order",
                    "owner": 'product specification',
                    "slot": "events"},),
    },
    {
        "clause": "the demonstration, deck and video show these capabilities "
                  "accurately",
        "signals": (("storyboard", "consistent"),),
        "stages": (),
        "awaits": ({"needs": "a demonstration, deck and video actually produced "
                             "from verified execution evidence",
                    "owner": 'presentation evidence',
                    "slot": "uiAssertions"},),
    },
    {
        "clause": "the code, configuration, deployment, chain results and artifact receipts "
                  "cross-check against one another",
        "signals": (("manifest", "consistent"),
                    ("sourceReconciliation", "consistent"),
                    ("usage", "consistent")),
        "stages": (),
        "awaits": ({"needs": "a deployment receipt and a chain result to "
                             "cross-check the source against",
                    "owner": 'deployment evidence',
                    "slot": "deployedHead"},
                   {"needs": 'artifact byte counts and digests verified by readback',
                    "owner": 'artifact provenance',
                    "slot": "artifactHashes"}),
    },
)

#: What this round's completion explicitly does not mean. A non-claim that is
#: only ever restated drifts; the four marked ``checkedBy`` are verified against
#: the run, because those are the ones a reader could mistake for the real
#: thing. The rest are declared, and say so.
NOT_MEANT = (
    {"notTheCase": "no real warehouse receipt has been connected",
     "checkedBy": None},
    {"notTheCase": "no cooperation exists with any of the simulated roles",
     "checkedBy": "every adapter in the run reports itself simulated"},
    {"notTheCase": "no business licence has been obtained",
     "checkedBy": None},
    {"notTheCase": "no commercial charging is enabled",
     "checkedBy": "the prices and gas figures in the run are declared fixtures, "
                  "and the quote asset is a local test label"},
    {"notTheCase": "the project has not moved to a public main network",
     "checkedBy": "every asset in the run names a test chain"},
    {"notTheCase": "no new financial or legal obligation has been accepted",
     "checkedBy": None},
)

#: The chain id a main network uses. Nothing here may run against it.
MAINNET_CHAIN_ID = 1

#: The label a local test quote asset must carry.
TEST_QUOTE_ASSET = "local-test-quote"


def _signal(bundle, key, flag):
    """One signal's value, or None when the report it reads is absent."""
    report = bundle.get(key)
    return report.get(flag) if isinstance(report, dict) else None


def _stage_coverage(bundle, wanted):
    """Whether every case of these stages has a local outcome that stands."""
    rows = (bundle.get("matrix") or {}).get("rows") or []
    outcomes = {row["case"]: row["localOutcome"] for row in rows}
    by_stage = stages.cases_by_stage()
    cases = [case for stage in wanted for case in by_stage.get(str(stage), [])]
    observed = {case: outcomes.get(case) for case in sorted(cases)}
    unmet = sorted(case for case, outcome in observed.items()
                   if outcome not in LOCAL_OUTCOMES_THAT_STAND)
    return {"stages": list(wanted), "cases": sorted(cases),
            "outcomes": observed, "casesNotStanding": unmet,
            "met": bool(cases) and not unmet}


def _checked_non_claims(bundle):
    """The four non-claims that can be verified against the run, verified."""
    # Every executed group participates, including guarantee contracts. Reading
    # only the demonstration and route groups would let a guarantee violate a
    # non-claim while the combined run still reports that it holds.
    scenarios = [scenario
                 for key in ("scenarioReport", "pathReport", "guaranteeReport")
                 for scenario in (bundle.get(key) or {}).get("scenarios") or []]
    chain_ids, quote_assets, adapters = set(), set(), []
    fixture_notes = []
    for scenario in scenarios:
        setup = scenario.get("setup") or {}
        receipt = setup.get("receipt") or {}
        if "chainId" in receipt:
            chain_ids.add(receipt["chainId"])
        if "quoteAsset" in setup:
            quote_assets.add(setup["quoteAsset"])
        adapters.extend(label for label in (setup.get("simulatedAdapters") or {}).values()
                        if label is not None)
        conditions = setup.get("gasConditions") or {}
        if isinstance(conditions, dict) and conditions.get("note"):
            fixture_notes.append(conditions["note"])
    simulated = _signal(bundle, "reuse", "allAdaptersSimulated")
    return {
        "chainIdsObserved": sorted(chain_ids),
        "noMainnet": bool(chain_ids) and MAINNET_CHAIN_ID not in chain_ids,
        "quoteAssetsObserved": sorted(quote_assets),
        "quoteAssetIsATestLabel": quote_assets == {TEST_QUOTE_ASSET},
        "adapterLabelsObserved": sorted(set(adapters)),
        "everyAdapterSimulated": simulated is True and bool(adapters)
        and all("simulated" in label.lower() or "Simulated" in label
                for label in adapters),
        "fixtureNotesObserved": sorted(set(fixture_notes)),
        "scenariosRead": len(scenarios),
    }


def build(bundle=None):
    """The definition of done, resolved against one run.

    With no run this is the clause list and the non-claims only: a reviewer
    reading the definition does not need a run to see what it requires, and the
    report says plainly that nothing was resolved.
    """
    bundle = bundle or {}
    read = bool(bundle)
    clauses = []
    for entry in CLAUSES:
        signals = [{"report": key, "flag": flag,
                    "value": _signal(bundle, key, flag)}
                   for key, flag in entry["signals"]]
        coverage = _stage_coverage(bundle, entry["stages"]) if entry["stages"] else None
        met = ([signal["value"] is True for signal in signals]
               + ([coverage["met"]] if coverage else []))
        status = ("not-resolved" if not read
                  else "evidenced-locally" if met and all(met)
                  else "partly-evidenced" if any(met)
                  else "not-evidenced")
        clauses.append({
            "clause": entry["clause"],
            "signals": signals,
            "stageCoverage": coverage,
            "localStatus": status,
            "awaits": [dict(owed) for owed in entry["awaits"]],
            "awaitsCount": len(entry["awaits"]),
            "completeHere": False,
        })
    checked = _checked_non_claims(bundle) if read else None
    non_claims = []
    for entry in NOT_MEANT:
        verified = None
        if read and entry["checkedBy"]:
            verified = {
                "every adapter in the run reports itself simulated":
                    checked["everyAdapterSimulated"],
                "the prices and gas figures in the run are declared fixtures, "
                "and the quote asset is a local test label":
                    checked["quoteAssetIsATestLabel"]
                    and bool(checked["fixtureNotesObserved"]),
                "every asset in the run names a test chain": checked["noMainnet"],
            }.get(entry["checkedBy"])
        non_claims.append(dict(entry, confirmedByThisRun=verified,
                               declaredOnly=entry["checkedBy"] is None))
    owed = [dict(owed, clause=clause["clause"])
            for clause, entry in zip(clauses, CLAUSES) for owed in entry["awaits"]]
    return {
        "schema": "8415ex-completion-ledger/1",
        "runRead": read,
        "clauses": clauses,
        "clauseCount": len(clauses),
        "clausesEvidencedLocally": sorted(
            entry["clause"] for entry in clauses
            if entry["localStatus"] == "evidenced-locally"),
        "clausesNotFullyEvidencedLocally": sorted(
            entry["clause"] for entry in clauses
            if entry["localStatus"] != "evidenced-locally"),
        "outstanding": owed,
        "outstandingCount": len(owed),
        "owners": sorted({entry["owner"] for entry in owed}),
        "slotsOwed": sorted({entry["slot"] for entry in owed}),
        "notMeant": non_claims,
        "notMeantChecked": checked,
        "notMeantConfirmedByThisRun": sorted(
            entry["notTheCase"] for entry in non_claims
            if entry["confirmedByThisRun"] is True),
        "notMeantDeclaredOnly": sorted(entry["notTheCase"] for entry in non_claims
                                       if entry["declaredOnly"]),
        # The one verdict here a run must act on. The clauses cannot be
        # satisfied locally by design, but a violated non-claim is different:
        # a run against a main network, against a real adapter, or against a
        # live quote asset is not a reportable observation, it is a stop.
        "notMeantHolds": (None if not read else all(
            entry["confirmedByThisRun"] is True for entry in non_claims
            if not entry["declaredOnly"])),
        "completionEstablished": False,
        "whyNot": ("every clause also needs additional integration evidence, so no run of "
                   "this surface can establish completion; the outstanding list names the "
                   "required evidence"),
        "isNot": [
            "not an acceptance decision: this resolves the clauses against one local run; "
            "independent acceptance evidence remains required",
            "not a percentage: a clause evidenced locally is one clause, not a "
            "fraction of a product",
            "not a claim that every non-claim was verified: three are confirmed "
            "against this run and the rest say they are declared only",
        ],
    }
