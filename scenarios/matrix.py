"""The requirement, source and acceptance matrix.

One row per acceptance case: the requirement it serves, the stage it belongs to,
where it is implemented, which local scenario or test records it, and what real
evidence is still owed. The matrix never marks an unexecuted chain assertion as
passed: a Stage 5 obligation stays an obligation.
"""
from exchange.model import REGISTRATION_PATHS

from .demos import MAIN_PATHS

#: Case to requirement identifiers, from the private requirements test matrix.
#: Identifiers only; no requirement text is reproduced here.
CASE_REQUIREMENTS = {
    "T-01": ("EX-SCOPE-02", "EX-INV-02"), "T-02": ("EX-SCOPE-03",),
    "T-03": ("EX-INV-01", "EX-INV-05"), "T-04": ("EX-INV-03", "EX-INV-05", "EX-INV-09"),
    "T-05": ("EX-INV-04", "EX-INV-05"),
    "T-06": ("EX-AUTH-01", "EX-AUTH-02", "EX-AUTH-04", "EX-SCOPE-05"),
    "T-07": ("EX-INV-01", "EX-INV-06"), "T-08": ("EX-AUTH-01", "EX-AUTH-03"),
    "T-09": ("EX-MATCH-01", "EX-MATCH-02", "EX-MATCH-03"), "T-10": ("EX-INV-05",),
    "T-11": ("EX-SETTLE-01",), "T-12": ("EX-SETTLE-02", "EX-INV-03"),
    "T-13": ("EX-SETTLE-01", "EX-SETTLE-03"), "T-14": ("EX-INV-05", "EX-SETTLE-04"),
    "T-15": ("EX-SETTLE-04",), "T-16": ("EX-INV-04", "EX-NFR-04"),
    "T-17": ("EX-ROLLBACK-01",), "T-18": ("EX-ROLLBACK-02", "EX-INV-03"),
    "T-19": ("EX-GAS-01", "EX-ROLLBACK-03", "EX-SCOPE-06"), "T-20": ("EX-ROLLBACK-04",),
    "T-21": ("EX-GAS-02",), "T-22": ("EX-GAS-03",),
    "T-23": ("EX-INV-04", "EX-INV-07"), "T-24": ("EX-TIME-01", "EX-TIME-02"),
    "T-25": ("EX-SCOPE-08", "EX-EXIT-01", "EX-INV-08"), "T-26": ("EX-NFR-05",),
    "T-27": ("EX-NFR-01", "EX-NFR-07"), "T-28": ("EX-NFR-03", "EX-NFR-04"),
    "T-29": ("EX-SCOPE-07", "EX-NFR-10"), "T-30": ("EX-INV-10", "EX-NFR-03", "EX-NFR-02"),
    "T-31": ("EX-INV-04", "EX-SETTLE-03"), "T-32": ("EX-EXIT-02", "EX-EXIT-03"),
    "T-33": ("EX-EXIT-03",), "T-34": ("EX-AUTH-01", "EX-AUTH-05"),
    "T-35": ("EX-DEMO-01",), "T-36": ("EX-DEMO-02",), "T-37": ("EX-DEMO-03",),
    "T-38": ("EX-NFR-07",), "T-39": ("EX-NFR-06", "EX-NFR-09"),
    "T-40": ("EX-NFR-05", "EX-NFR-08"),
}

#: Every approved requirement identifier, so a requirement that no case claims
#: is found by a test rather than noticed by eye. Identifiers only: no
#: requirement text, private locator or document identity appears here.
DECLARED_REQUIREMENTS = (
    "EX-AUTH-01", "EX-AUTH-02", "EX-AUTH-03", "EX-AUTH-04", "EX-AUTH-05",
    "EX-DEMO-01", "EX-DEMO-02", "EX-DEMO-03",
    "EX-EXIT-01", "EX-EXIT-02", "EX-EXIT-03",
    "EX-GAS-01", "EX-GAS-02", "EX-GAS-03",
    "EX-INV-01", "EX-INV-02", "EX-INV-03", "EX-INV-04", "EX-INV-05",
    "EX-INV-06", "EX-INV-07", "EX-INV-08", "EX-INV-09", "EX-INV-10",
    "EX-MATCH-01", "EX-MATCH-02", "EX-MATCH-03",
    "EX-NFR-01", "EX-NFR-02", "EX-NFR-03", "EX-NFR-04", "EX-NFR-05",
    "EX-NFR-06", "EX-NFR-07", "EX-NFR-08", "EX-NFR-09", "EX-NFR-10",
    "EX-ROLLBACK-01", "EX-ROLLBACK-02", "EX-ROLLBACK-03", "EX-ROLLBACK-04",
    "EX-SCOPE-01", "EX-SCOPE-02", "EX-SCOPE-03", "EX-SCOPE-04", "EX-SCOPE-05",
    "EX-SCOPE-06", "EX-SCOPE-07", "EX-SCOPE-08",
    "EX-SETTLE-01", "EX-SETTLE-02", "EX-SETTLE-03", "EX-SETTLE-04",
    "EX-TIME-01", "EX-TIME-02",
)

#: Requirements with no local test surface, and why. Stating this keeps an
#: omission from hiding: the requirement is accounted for, as something this
#: package cannot settle rather than as something it has shown.
NOT_LOCALLY_TESTABLE = {
    "EX-SCOPE-01": {
        "reason": "a positioning statement about what the product is and is not; "
                  "nothing in a local model run can confirm or refute it",
        "owner": "the product owner",
    },
    "EX-SCOPE-04": {
        "reason": "wallet compatibility across conforming wallets; this package "
                  "has no wallet adapter and uses simulated authorization, so "
                  "compatibility can only be shown against real wallets",
        "owner": "the party that owns wallet integration acceptance",
    },
}


def requirement_coverage():
    """Which approved requirements are claimed by a case, and which are not.

    ``unclaimed`` is the real answer to "is anything missing": a requirement in
    neither a case nor the not-locally-testable record is coverage nobody has
    accounted for.
    """
    claimed = {}
    for case, requirements in CASE_REQUIREMENTS.items():
        for requirement in requirements:
            claimed.setdefault(requirement, []).append(case)
    declared = set(DECLARED_REQUIREMENTS)
    unclaimed = sorted(declared - set(claimed) - set(NOT_LOCALLY_TESTABLE))
    unknown = sorted(set(claimed) - declared)
    return {
        "declared": len(declared),
        "claimedByCases": {name: sorted(cases) for name, cases in sorted(claimed.items())},
        "claimedCount": len(claimed),
        "notLocallyTestable": NOT_LOCALLY_TESTABLE,
        "unclaimed": unclaimed,
        "unknown": unknown,
        "complete": unclaimed == [] and unknown == [],
    }


#: Which stage each case is first accepted in.
CASE_STAGE = {**{case: 1 for case in ("T-01", "T-02", "T-03", "T-04", "T-05", "T-06", "T-07",
                                      "T-08", "T-09", "T-10", "T-26", "T-27", "T-34")},
              **{case: 2 for case in ("T-11", "T-12", "T-13", "T-14", "T-15", "T-16", "T-28",
                                      "T-31")},
              **{case: 3 for case in ("T-17", "T-18", "T-19", "T-20", "T-21", "T-22", "T-23",
                                      "T-29", "T-30")},
              **{case: 4 for case in ("T-24", "T-25", "T-32", "T-33")},
              **{case: 5 for case in ("T-35", "T-36", "T-37", "T-38")},
              "T-39": "all", "T-40": "all"}

#: Where each case is implemented and covered. Unit suites are the existing
#: `exchange/tests` files; scenario coverage is this package's runners.
CASE_IMPLEMENTATION = {
    "T-01": ("exchange/model.py, exchange/ledger.py", "exchange/tests/test_receipt_state.py"),
    "T-02": ("exchange/ledger.py", "exchange/tests/test_receipt_state.py"),
    "T-03": ("exchange/ledger.py", "exchange/tests/test_trade_chain.py"),
    "T-04": ("exchange/ledger.py, exchange/registration.py", "exchange/tests/test_registration.py"),
    "T-05": ("exchange/registration.py", "exchange/tests/test_registration.py"),
    "T-06": ("exchange/ledger.py, exchange/model.py", "exchange/tests/test_authorization.py"),
    "T-07": ("exchange/ledger.py", "exchange/tests/test_trade_chain.py"),
    "T-08": ("exchange/ledger.py", "exchange/tests/test_authorization.py"),
    "T-09": ("exchange/ledger.py", "exchange/tests/test_matching.py"),
    "T-10": ("exchange/registration.py", "exchange/tests/test_registration.py"),
    "T-11": ("exchange/settlement.py, exchange/ledger.py", "exchange/tests/test_settlement.py"),
    "T-12": ("exchange/ledger.py", "exchange/tests/test_settlement.py"),
    "T-13": ("exchange/settlement.py", "exchange/tests/test_settlement.py"),
    "T-14": ("exchange/settlement.py, exchange/ledger.py", "exchange/tests/test_settlement.py"),
    "T-15": ("exchange/ledger.py", "exchange/tests/test_settlement.py"),
    "T-16": ("exchange/settlement.py", "exchange/tests/test_settlement.py"),
    "T-17": ("exchange/rollback.py, exchange/ledger.py", "exchange/tests/test_rollback.py"),
    "T-18": ("exchange/ledger.py", "exchange/tests/test_rollback.py"),
    "T-19": ("exchange/ledger.py", "exchange/tests/test_rollback.py"),
    "T-20": ("exchange/rollback.py", "exchange/tests/test_rollback.py"),
    "T-21": ("exchange/ledger.py", "exchange/tests/test_rollback.py"),
    "T-22": ("exchange/ledger.py, exchange/rollback.py", "exchange/tests/test_rollback.py"),
    "T-23": ("exchange/ledger.py", "exchange/tests/test_rollback.py"),
    "T-24": ("exchange/ledger.py", "exchange/tests/test_exit.py"),
    "T-25": ("exchange/exit.py, exchange/ledger.py", "exchange/tests/test_exit.py"),
    "T-26": ("exchange/views.py, exchange/ledger.py", "exchange/tests/test_views.py"),
    "T-27": ("exchange/ids.py, exchange/fixtures.py", "exchange/tests/test_reproducibility.py"),
    "T-28": ("exchange/settlement.py, exchange/ledger.py",
             "exchange/tests/test_settlement.py, exchange/tests/test_payment_binding.py"),
    "T-29": ("exchange/ledger.py", "exchange/tests/test_rollback.py"),
    "T-30": ("exchange/ledger.py, exchange/audit.py, exchange/audit_projection.py, scenarios/events.py",
             "exchange/tests/test_rollback.py, exchange/tests/test_audit_boundaries.py, "
             "exchange/tests/test_audit_projection.py, scenarios/tests/test_events.py"),
    "T-31": ("exchange/settlement.py, exchange/ledger.py", "exchange/tests/test_settlement.py"),
    "T-32": ("exchange/exit.py, exchange/ledger.py",
             "exchange/tests/test_exit.py, exchange/tests/test_voucher_recovery.py"),
    "T-33": ("exchange/exit.py", "exchange/tests/test_exit.py"),
    "T-34": ("exchange/ledger.py", "exchange/tests/test_authorization.py"),
    "T-35": ("not implemented locally", "scenarios/handoff.py evidence slots"),
    "T-36": ("not implemented locally", "scenarios/handoff.py evidence slots"),
    "T-37": ("scenarios/STORYBOARD.md outline only", "scenarios/handoff.py evidence slots"),
    "T-38": ("not implemented locally", "scenarios/manifest.py, scenarios/handoff.py"),
    "T-39": ("scenarios/observations.py", "scenarios/tests/test_observations.py"),
    "T-40": ("scenarios/observations.py", "scenarios/tests/test_observations.py"),
}

#: What real evidence each case still owes after a local run.
REMAINING_EVIDENCE = {
    "T-35": "Sepolia execution with the verified designated test token address, by Codex",
    "T-36": "six scenarios executed on the public test network with real transactions, "
            "receipts and a real UI journey, by Codex",
    "T-37": "demonstration, deck and video built from verified execution evidence",
    "T-38": "exact deployed head aligned with required CI and artifact hash read-back",
}

#: Cases whose acceptance is only partly local, with the reason.
PARTIAL_LOCAL = {
    "T-16": "the recovery detail for a confirmed registration with a failed payment is an "
            "open decision; the enquiry path is modelled, the product choice is not made here",
    "T-19": "gas figures are labelled fixtures; the actual fee deduction mechanism is open",
    "T-21": "a shared operation is recorded once; the apportionment rule is open",
    "T-22": "the shortfall path uses a fixture budget ceiling, not an approved fee mechanism",
    "T-24": "the precedence of a timeout, the cutoff and a late result is open and reported",
    "T-25": "the other eligibility checks arrive as verified facts, not established here",
    "T-32": "the voucher hand-over and burn confirmation order is open and reported",
}


def _scenario_cases():
    """Case to scenario identifiers, from the runners themselves."""
    from .paths import PATH_CONTRACTS

    mapping = {}
    for scenario in list(_demos()) + list(PATH_CONTRACTS):
        for case in scenario.cases:
            mapping.setdefault(case, []).append(scenario.scenario_id)
    return {case: sorted(ids) for case, ids in mapping.items()}


def _demos():
    from .demos import DEMOS

    return DEMOS


def build(source_identity, run_identity, scenario_report=None, path_report=None):
    """One matrix row per case, bound to the exact source and run.

    ``scenario_report`` and ``path_report`` are the harness reports; when given,
    each row carries the recorded local outcome for its scenarios.
    """
    scenario_cases = _scenario_cases()
    # A scenario may assert against a case it does not list in its own header,
    # as DEMO-05 does for T-19. The coverage column has to follow the
    # assertions that were actually recorded, or it under-reports which runners
    # exercise a case and a reviewer cannot find the evidence from the row.
    observed_cases = {}
    recorded, problems = {}, {}
    for report in (scenario_report, path_report):
        for scenario in (report or {}).get("scenarios", []):
            touched = set(scenario.get("cases", ()))
            for expectation in scenario["expectations"]:
                touched.update(expectation["cases"])
                for case in expectation["cases"]:
                    observed_cases.setdefault(case, set()).add(scenario["scenarioId"])
                    bucket = recorded.setdefault(case, {"passed": 0, "failed": 0,
                                                        "blocked": 0, "not-run": 0})
                    bucket[expectation["outcome"]] += 1
            # A scenario that raised, or that did not pass as a whole, reaches
            # every case it serves. Assertions that happened to pass before the
            # exception are not an acceptance result for those cases: the
            # scenario did not complete, so the case is not passed.
            # Why it did not pass matters: a scenario that raised is an
            # error, one with a failed assertion is a failure, one that only
            # could not run a check is blocked, and one that recorded nothing
            # conclusive is incomplete. Collapsing these into "failed" loses
            # the difference between a wrong answer and no answer.
            status = None
            if scenario.get("error"):
                status = "error"
            elif scenario.get("passed") is False:
                scenario_counts = scenario.get("counts") or {}
                if scenario_counts.get("failed"):
                    status = "failed"
                elif scenario_counts.get("blocked"):
                    status = "blocked"
                else:
                    status = "incomplete"
            if status is not None:
                for case in sorted(touched):
                    problems.setdefault(case, []).append(
                        {"scenarioId": scenario.get("scenarioId"), "status": status,
                         "error": scenario.get("error"),
                         "counts": scenario.get("counts")})

    rows = []
    for case in sorted(CASE_REQUIREMENTS, key=lambda name: int(name.split("-")[1])):
        implementation, unit_cover = CASE_IMPLEMENTATION[case]
        counts = recorded.get(case)
        raised = problems.get(case, [])
        statuses = {entry["status"] for entry in raised}
        # A case is judged on its own recorded assertions first, then on what
        # happened to the scenarios carrying it. Each state keeps its own name.
        if "error" in statuses:
            local = "error"
        elif counts and counts["failed"]:
            local = "failed"
        elif "failed" in statuses:
            local = "failed"
        elif counts and counts["blocked"]:
            local = "blocked"
        elif "blocked" in statuses:
            local = "blocked"
        elif "incomplete" in statuses:
            # Assertions may have passed, but the scenario did not complete, so
            # this is not acceptance for the case either.
            local = "incomplete"
        elif case in REMAINING_EVIDENCE:
            local = "not-run"
        elif counts and counts["not-run"] and not counts["passed"]:
            # The scenarios covering this case recorded only obligations.
            local = "not-run"
        elif counts and counts["passed"]:
            local = "passed"
        else:
            local = "unit-suite-only"
        rows.append({
            "case": case,
            "requirements": list(CASE_REQUIREMENTS[case]),
            "stage": CASE_STAGE[case],
            "implementation": implementation,
            "unitCoverage": unit_cover,
            "scenarios": sorted(set(scenario_cases.get(case, []))
                                | observed_cases.get(case, set())),
            "declaredScenarios": scenario_cases.get(case, []),
            "scenarioAssertionCounts": counts or {},
            "localOutcome": local,
            "scenarioProblems": raised,
            "partiallyLocal": PARTIAL_LOCAL.get(case),
            "remainingRealEvidence": REMAINING_EVIDENCE.get(case),
        })
    unsound = [row["case"] for row in rows
               if row["localOutcome"] in ("error", "failed", "blocked", "incomplete")]
    return {
        "schema": "8415ex-acceptance-matrix/3",
        "sourceIdentity": source_identity,
        "runIdentity": run_identity,
        "rows": rows,
        "paths": list(REGISTRATION_PATHS),
        "mainPathPerScenario": dict(sorted(MAIN_PATHS.items())),
        "localOutcomeCounts": _tally(rows),
        "requirementCoverage": requirement_coverage(),
        "unsoundCases": unsound,
        "allCasesSound": unsound == [],
        "note": ("a local outcome is evidence about the model only; the cases with remaining "
                 "real evidence are Stage 5 obligations and are never marked passed here. A "
                 "scenario that raised or did not pass marks every case it serves, whatever "
                 "its individual assertions recorded first"),
    }


def _tally(rows):
    counts = {}
    for row in rows:
        counts[row["localOutcome"]] = counts.get(row["localOutcome"], 0) + 1
    return dict(sorted(counts.items()))
