"""Identity-excluding simulation presentation, not the canonical run evidence.

The original expected/observed record stays unchanged in the private run store.
Only typed business observations are public. Hidden identity comparisons and
free-form diagnostics are explicitly marked private, never represented as a new
verification or a complete copy of the underlying record.
"""
import re

OUTCOMES = frozenset(("passed", "failed", "blocked", "not-run"))
VALUES = frozenset(("unknown", "pending", "settled", "failed", "blocked", "done", "complete",
    "not-submitted", "confirmed", "rejected", "locked", "released", "refunded", "not-funded",
    "not-modelled", "release-outcome-unknown", "release-failed", "available", "detached", "returned",
    "in-progress", "none", "open", "closed", "ETH", "wei", "base-units", "gas-units",
    "local-test-quote", "undecided", "single-leg", "NOT_RUN"))
FIELDS = frozenset(("ownerPosition", "holderPosition", "currentPosition", "registeredPrefixLegs",
    "outstandingLegs", "legIndex", "principal", "quoteAsset", "principalAsset", "principalUnit",
    "gasAsset", "gasUnit", "gasTotal", "amount", "escrowStatus", "paymentStatus", "fundingStatus",
    "registrationStatus", "rollbackStatus", "released", "refunded", "netToPayee", "netToPayer",
    "segments", "funds", "prices", "gasConditions", "trade", "refund", "shared-return", "AB", "BC", "CD",
    "status", "state", "complete", "open", "affectedLegs", "finalizedPrefixLegs", "lastFinalizedPosition",
    "ownerEqualsHolder", "tradingOpen", "tradeStopAt", "eligible", "burned", "stepCount", "allDone",
    "distinctInstants", "atomic", "instantsDiffer", "completedAt", "observedAt"))
PRIVATE = {"visibility": "private-evidence-only"}


def business(value):
    if isinstance(value, dict):
        return {key: business(item) for key, item in value.items()
                if key in FIELDS or isinstance(key, str) and re.fullmatch(r"[0-9]{1,10}", key)}
    if isinstance(value, (tuple, list)):
        return [business(item) for item in value]
    if type(value) is bool or value is None:
        return value
    if type(value) is int and abs(value) < 2**256:
        return value
    if isinstance(value, str) and (value in VALUES or re.fullmatch(r"-?(0|[1-9][0-9]{0,77})", value)):
        return value
    return dict(PRIVATE)


def counts(value):
    return {name: item if type(item := value.get(name)) is int and item >= 0 else None for name in OUTCOMES}


def run_record(original):
    report = original["report"]
    results = []
    for row in report["scenarios"]:
        identifier = row.get("scenarioId")
        if not isinstance(identifier, str) or re.fullmatch(r"DEMO-0[1-6]", identifier) is None:
            raise ValueError("known simulation identifier required")
        results.append({"scenarioId": identifier, "title": identifier + " simulation",
            "mainPath": row.get("mainPath") if row.get("mainPath") in ("REG_DIRECT", "REG_ELECTRONIC", "REG_INTERMEDIARY") else "unknown",
            "setup": business(row.get("setup", {})),
            "steps": [{"index": index, "name": "Observation " + str(index + 1), "facts": business(step.get("facts", {}))}
                      for index, step in enumerate(row.get("steps", ()))],
            "expectations": [{"name": "Assertion " + str(index + 1),
                "cases": [case for case in item.get("cases", ()) if isinstance(case, str) and re.fullmatch(r"T-[0-9]{2}", case)],
                "outcome": item.get("outcome") if item.get("outcome") in OUTCOMES else "unknown",
                "expected": business(item.get("expected")), "observed": business(item.get("observed")),
                "detail": "Identity fields and free-form diagnostics remain in the private original"}
                for index, item in enumerate(row.get("expectations", ()))],
            "counts": counts(row.get("counts", {})), "passed": row.get("passed") is True,
            "error": "Original run error retained privately" if row.get("error") is not None else None,
            "notes": ["Public business projection; not a complete copy of original evidence"]})
    key = original.get("runId")
    if not isinstance(key, str) or re.fullmatch(r"demo-[0-9a-f]{32}", key) is None:
        raise ValueError("server-owned simulation run identifier required")
    source = original.get("source", {})
    return {"schema": "8415ex-public-demo/2", "runId": key, "evidenceKind": "SIMULATION_PUBLIC_PROJECTION",
        "source": {name: value for name in ("commit", "tree")
                   if isinstance((value := source.get(name)), str) and re.fullmatch(r"[0-9a-f]{40}", value)},
        "report": {"scenarios": results, "totals": counts(report.get("totals", {})),
                   "allPassed": report.get("allPassed") is True},
        "realEvidence": {name: "NOT_RUN" for name in ("deployment", "provider", "signatures", "chain", "transactions")},
        "projection": "Identity-excluding subset; private original retains complete expected/observed and failure detail"}
