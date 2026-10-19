"""Deterministic local scenario orchestration; never deploys or sends transactions."""
import argparse
import json
from . import fixtures as F
from .errors import DomainError

RECEIPT = "rcpt-8415-0001"
PATHS = ("REG_DIRECT", "REG_ELECTRONIC", "REG_INTERMEDIARY")
SCENARIOS = ("DEMO-01", "DEMO-02", "DEMO-03", "DEMO-04", "DEMO-05", "DEMO-06")
DEFAULT_PATH = dict(zip(SCENARIOS, PATHS * 2))
CASES = {
    "DEMO-01": ("T-02", "T-11", "T-25", "T-32", "T-33"),
    "DEMO-02": ("T-03", "T-04", "T-12", "T-13"),
    "DEMO-03": ("T-17", "T-19", "T-21"),
    "DEMO-04": ("T-18", "T-19", "T-29"),
    "DEMO-05": ("T-20", "T-21", "T-22", "T-23"),
    "DEMO-06": ("T-24", "T-25", "T-32", "T-33"),
}

def check(value, label):
    if not value:
        raise AssertionError(label)

def snapshot(ex):
    return {"receipt": ex.receipt_view(RECEIPT), "funds": ex.reconciliation(RECEIPT),
            "rollback": ex.rollback_report(RECEIPT), "exit": ex.exit_report(RECEIPT),
            "timeline": ex.receipt_timeline(RECEIPT)}

def release(ex, index):
    return ex.release_segment(RECEIPT, index, F.release_authority(ex, index, "scenario-release-" + str(index)))

def make_chain(path, **kwargs):
    ex, clock = F.rollback_exchange(registration_path=path, **kwargs)
    for seller, buyer, nonce, suffix, price in (
        (F.A, F.B, 1, "ab", F.PRICE_AB),
        (F.B, F.C, 2, "bc", F.PRICE_BC),
        (F.C, F.D, 3, "cd", F.PRICE_CD)):
        F.funded_hop(ex, seller, buyer, nonce, "transfer-" + suffix,
                     "session-" + seller[-1], "session-" + buyer[-1], price=price)
    return ex, clock

def _execute(scenario, path):
    checkpoints = []
    if scenario == "DEMO-01":
        ex, clock = F.rollback_exchange(registration_path=path)
        F.funded_hop(ex, F.A, F.B, 1, "transfer-ab", "session-a", "session-b", price=F.PRICE_AB)
        request = F.submit_all(ex)[0]
        F.confirm(ex, request, "result-ab")
        release(ex, 0)
        check(ex.owner_of(RECEIPT) == ex.holder_of(RECEIPT) == F.B, "owner/holder B")
        checkpoints.append(snapshot(ex))
        expected_owner, expected_holder, released, refunded = F.B, F.B, (0,), ()
    elif scenario == "DEMO-02":
        ex, clock = make_chain(path)
        reqs = F.submit_all(ex)
        F.confirm(ex, reqs[2], "result-cd")
        F.confirm(ex, reqs[1], "result-bc")
        check(ex.holder_index(RECEIPT) == 0, "later results cannot skip B")
        F.confirm(ex, reqs[0], "result-ab")
        # A separate fresh chain demonstrates release while holder is only B.
        prefix, _ = make_chain(path)
        first = F.submit_all(prefix)[0]
        F.confirm(prefix, first, "prefix-result")
        release(prefix, 0)
        check(prefix.holder_index(RECEIPT) == 1, "AB released before holder D")
        check(prefix.escrow_for_leg(RECEIPT, 1).status == "locked", "BC remains independently locked")
        checkpoints.append(snapshot(prefix))
        for index in range(3):
            release(ex, index)
        expected_owner, expected_holder, released, refunded = F.D, F.D, (0, 1, 2), ()
    elif scenario in ("DEMO-03", "DEMO-04", "DEMO-05"):
        budgets = {F.D: 0} if scenario == "DEMO-05" else None
        ex, clock = make_chain(path, gas_budgets=budgets)
        reqs = F.submit_all(ex)
        refused = 0
        if scenario == "DEMO-04":
            F.confirm(ex, reqs[0], "result-ab")
            release(ex, 0)
            prefix_before = ex.reconciliation(RECEIPT)["segments"][0]
            refused = 1
        F.refuse(ex, reqs[refused], "refused-result")
        ex.begin_rollback(RECEIPT, refused, F.rollback_authority(ex, refused, "scenario-rollback"))
        report = ex.advance_rollback(RECEIPT)
        if scenario == "DEMO-05":
            check(report["state"] == "blocked" and not report["complete"], "shortfall is blocked")
            check(ex.asset_control.returns == 0, "no asset movement while budget insufficient")
            checkpoints.append(snapshot(ex))
            # Explicit fixture budget adjustment; no ordinary wallet is funded.
            ex._budgets[F.D] = 100000
            report = ex.advance_rollback(RECEIPT)
        check(report["complete"], "rollback complete")
        expected_owner = expected_holder = F.B if refused else F.A
        released = (0,) if refused else ()
        refunded = (1, 2) if refused else (0, 1, 2)
        check(ex.asset_control.returns == len(refunded), "one evidenced return per original reverse hop")
        check(ex.payments.movements == 3, "one payment per independently settled/refunded segment")
        before = ex.payments.movements
        ex.advance_rollback(RECEIPT)
        check(ex.payments.movements == before, "rollback repeats no refund")
        if refused:
            check(prefix_before == ex.reconciliation(RECEIPT)["segments"][0], "AB prefix unchanged")
        if scenario == "DEMO-05":
            blocked = [e for e in ex.receipt_timeline(RECEIPT) if e["kind"] == "rollback-step-blocked"]
            check(blocked and all(not e["detail"]["custodyTaken"] and not e["detail"]["forcedSale"]
                                  and not e["detail"]["liquidation"] for e in blocked), "withdrawn mechanisms absent")
    elif scenario == "DEMO-06":
        ex, clock = make_chain(path)
        requests = F.submit_all(ex)
        F.confirm(ex, requests[0], "confirmed-prefix")
        release(ex, 0)
        prefix = ex.reconciliation(RECEIPT)["segments"][0]
        clock.now = ex.receipt(RECEIPT).trade_stop_at
        before = snapshot(ex)
        try:
            F.funded_hop(ex, F.D, F.A, 4, "transfer-late", "session-d", "session-a",
                         now=clock(), expires_at=clock() + 600)
        except DomainError as error:
            check(error.code in ("EX_MATCH_UNEXECUTABLE", "EX_TRADE_WINDOW_CLOSED"), "named cutoff refusal")
        else:
            raise AssertionError("trade at cutoff must fail")
        check(ex.recorded_legs(RECEIPT) == 3, "cutoff forms no new leg")
        authority = F.rollback_authority(ex, 1, "deadline-rollback", now=clock())
        ex.begin_rollback(RECEIPT, 1, authority, trigger="deadline")
        report = ex.advance_rollback(RECEIPT)
        check(report["complete"], "unfinished suffix returned to current holder")
        check(ex.reconciliation(RECEIPT)["segments"][0] == prefix, "registered prefix retained")
        check(not ex.exit_report(RECEIPT)["burned"], "deadline does not burn the NFT")
        checkpoints.append({"beforeCutoffRefusal": before, "afterRecovery": snapshot(ex)})
        expected_owner, expected_holder, released, refunded = F.B, F.B, (0,), (1, 2)

    else:
        raise ValueError("unknown scenario")
    check(ex.owner_of(RECEIPT) == expected_owner, "final owner")
    check(ex.holder_of(RECEIPT) == expected_holder, "final holder")
    funds = ex.reconciliation(RECEIPT)["segments"]
    check(tuple(s["legIndex"] for s in funds if s["released"]) == released, "released segment set")
    check(tuple(s["legIndex"] for s in funds if s["refunded"]) == refunded, "refunded segment set")
    for segment in funds:
        check(not (segment["released"] and segment["refunded"]), "release/refund mutually exclusive")
        check(segment["gasBorneBy"] == segment["buyer"], "buyer gas responsibility")
        if segment["refunded"]:
            check(segment["netToPayer"] == segment["principal"], "original buyer principal refund")
    check(ex.registrars[path].simulated, "registrar is explicitly simulated")
    return {"expected": {"owner": expected_owner, "holder": expected_holder,
                          "releasedLegs": released, "refundedLegs": refunded},
            "observed": snapshot(ex), "checkpoints": checkpoints,
            "fixtureConditions": {"ordinaryWalletETH": "not queried; no real wallet adapter",
                                 "gasUnit": "synthetic", "commercialFees": "none",
                                 "gasDeductionPolicy": "NOT_RUN: D-04 unresolved"},
            "realEvidence": dict.fromkeys(("deployment", "providerUI", "signatures", "chain", "realFees"), "NOT_RUN")}

def run_scenario(scenario, path=None):
    if scenario not in SCENARIOS:
        raise ValueError("unknown scenario")
    path = path or DEFAULT_PATH[scenario]
    if path not in PATHS:
        raise ValueError("unknown registration path")
    from scenarios.current_prd import require_current_scenario
    require_current_scenario(scenario, revision="1.4")
    try:
        result = _execute(scenario, path)
        return dict(result, scenario=scenario, path=path, simulated=True, status="passed", cases=CASES[scenario])
    except (AssertionError, DomainError) as error:
        return {"scenario": scenario, "path": path, "simulated": True, "status": "failed",
                "cases": CASES[scenario], "failure": {"type": type(error).__name__, "detail": str(error)}}

def main(argv=None):
    parser = argparse.ArgumentParser(description="Run local-only exchange scenarios.")
    parser.add_argument("--scenario", choices=SCENARIOS)
    parser.add_argument("--path", choices=PATHS)
    args = parser.parse_args(argv)
    results = [run_scenario(name, args.path) for name in ((args.scenario,) if args.scenario else SCENARIOS)]
    print(json.dumps({"schemaVersion": 1, "evidenceKind": "LOCAL_SIMULATION",
                      "results": results}, sort_keys=True))
    return 1 if any(r["status"] != "passed" for r in results) else 0

if __name__ == "__main__":
    raise SystemExit(main())