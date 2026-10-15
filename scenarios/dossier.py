"""Per scenario: the content a demonstration has to carry, item by item.

A scenario report says what was checked. It does not say whether the scenario
carries everything a demonstration is required to present, and those are
different questions: a run can pass every expectation while still not recording
the prices it used or the holder position it reached.

So this module declares the nine items a demonstration must carry, resolves each
one from the scenario record by a declared rule, and reports what did not
resolve. Three distinctions do the real work.

A **gap** is an item a local run could record and did not. That is a finding
against this surface, and the only kind here that is.

An item **resolved elsewhere** is one the scenario does not hold but something
else in this delivery does, named so a reviewer can follow it rather than
concluding it is missing.

An item that is **NOT_RUN** is one no local run can discharge at all - a
transaction hash with nothing signing, a page state with no browser - and it
carries the evidence slot that will hold it and the reason it is empty. It is
never a gap, and a local stand-in for it is never offered.

Rules require recorded values, never case labels or module paths as substitutes
for evidence. Rephrasing a check does not alter its recorded values.
"""
from .demos import MAIN_PATHS
from .handoff import EVIDENCE_SLOTS, NOT_RUN

#: Funding labels are metadata only; they cannot establish escrow observations.
FUNDING_CASES = ("T-11", "T-12", "T-13", "T-14", "T-15", "T-16", "T-28", "T-31")

#: The nine items a demonstration must carry, with how each is resolved.
#:
#: ``setup`` and ``stepFacts`` name keys on the record; ``require`` says whether
#: all of them or any of them is enough. Case labels never replace values.
#: ``notRun`` marks an item no local run can discharge, with the slot
#: that will hold it. ``resolvedElsewhere`` marks one this delivery holds outside
#: the scenario record.
DOSSIER_ITEMS = (
    {
        "item": "preset receipt and accounts",
        "setup": ("receipt", "accounts"),
        "require": "all",
    },
    {
        "item": "test prices and gas conditions",
        "setup": ("prices", "gasConditions"),
        "require": "all",
    },
    {
        "item": "execution steps",
        "steps": True,
    },
    {
        "item": "owner, holder and the registered prefix reached",
        "stepFacts": ("owner", "holder", "ownerPosition", "holderPosition",
                      "registeredPrefixLegs"),
        "require": "all",
    },
    {
        "item": "per-segment escrow result",
        "stepFacts": ("segmentFunds", "escrowStatus", "fundingStatus", "released",
                      "payee", "principal"),
        "require": "any",

    },
    {
        "item": "recorded events",
        "resolvedElsewhere": "the domain timeline, read by scenarios/events.py",
        "why": "a scenario records the facts it observed after each step; the "
               "event trail itself belongs to the domain and is read from there "
               "rather than restated here",
    },
    {
        "item": "transaction hashes",
        "notRun": "nothing here signs or broadcasts, so no transaction exists",
        "slot": "transactionHashes",
    },
    {
        "item": "page state",
        "notRun": "a text render is not UI evidence, and no browser ran",
        "slot": "uiAssertions",
        "renderedBy": "exchange/views.py, for development and diagnosis only",
    },
    {
        "item": "actual result and failure detail",
        "expectations": True,
    },
)


def _populated(value):
    """Zero and False are observations; empty containers and null are not."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, dict):
        return any(_populated(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return any(_populated(v) for v in value)
    return True


def _resolve(rule, scenario):
    """Resolve only material present in this scenario's actual record."""
    if "notRun" in rule:
        return {"status": NOT_RUN, "resolvedFrom": None, "missingKeys": [],
                "reason": rule["notRun"], "slot": rule["slot"],
                "renderedBy": rule.get("renderedBy")}
    steps = [step for step in scenario.get("steps", ()) if isinstance(step, dict)]
    facts = [(i, step.get("facts", {})) for i, step in enumerate(steps)
             if isinstance(step.get("facts", {}), dict)]
    found, wanted, where, enough = [], [], None, False
    if "resolvedElsewhere" in rule:
        from exchange import audit, audit_projection
        from exchange.errors import DomainError
        receipt = scenario.get("setup", {}).get("receipt")
        receipt_id = receipt.get("receiptId") if isinstance(receipt, dict) else None
        for i, fact in facts:
            timeline = fact.get("auditTimeline")
            if not isinstance(timeline, (list, tuple)) or not timeline or not receipt_id:
                continue
            try:
                replay = audit.replay(timeline)
                view = audit_projection.project(timeline)
                mint = timeline[0]["detail"]
                setup_matches = all(mint.get(key) == receipt.get(key) for key in (
                    "receiptId", "origin", "registrationPath", "tradeStopAt", "commodityQuantity", "tradeableUnits"))
                setup_matches = setup_matches and mint.get("asset") == [
                    receipt.get("chainId"), receipt.get("contract"), receipt.get("tokenId")]
                setup_matches = setup_matches and mint.get("registrationPath") == scenario.get("mainPath")
                positions = [f for _, f in facts if all(k in f for k in (
                    "owner", "ownerPosition", "holder", "holderPosition", "registeredPrefixLegs"))]
                last = positions[-1] if positions else {}
                positions_match = (view["owner"] == {"account": last.get("owner"), "position": last.get("ownerPosition")}
                    and view["holder"] == {"account": last.get("holder"), "position": last.get("holderPosition")}
                    and view["holder"]["position"] == last.get("registeredPrefixLegs"))
                enough = (replay["completeFromMint"] and replay["sequential"]
                    and setup_matches and positions_match and view == fact.get("auditBusinessView")
                    and all(event.get("receiptId") == receipt_id for event in timeline))
            except (DomainError, KeyError, TypeError, ValueError, AttributeError):
                enough = False
            if enough:
                where = f"steps/{i}/facts/auditTimeline; local recorded timeline, inspected by scenarios/events.py"
                break
        wanted = ["auditTimeline"]
    elif rule.get("steps"):
        enough = bool(steps) and all(_populated(step.get("name"))
            and isinstance(step.get("facts"), dict) and _populated(step["facts"])
            for step in steps)
        where, wanted = "the scenario's recorded steps", ["steps"]
    elif rule.get("expectations"):
        expectations = scenario.get("expectations", ())
        enough = bool(expectations) and all(isinstance(e, dict)
            and _populated(e.get("name")) and "expected" in e and "observed" in e
            and not (e["expected"] is None and e["observed"] is None)
            and e.get("outcome") in ("passed", "failed", "blocked", "not-run")
            and (e["outcome"] not in ("blocked", "not-run") or _populated(e.get("detail")))
            for e in expectations)
        where, wanted = "recorded expectations with expected/observed values and outcomes", ["expectations"]
    elif "setup" in rule:
        wanted, where = rule["setup"], "setup"
        setup = scenario.get("setup", {})
        found = [key for key in wanted if _populated(setup.get(key))]
        enough = len(found) == len(wanted)
    elif rule["item"] == "per-segment escrow result":
        wanted = ["segmentFunds or identified escrow result"]
        for i, fact in facts:
            funds = fact.get("segmentFunds")
            segments = list(funds.values()) if isinstance(funds, dict) else funds
            complete_segments = isinstance(segments, (list, tuple)) and bool(segments) and all(
                isinstance(row, dict) and _populated(row.get("escrowStatus"))
                and _populated(row.get("principal")) for row in segments)
            identified = _populated(fact.get("escrowStatus")) and (
                _populated(fact.get("escrowId")) or _populated(fact.get("legIndex")))
            result = all(_populated(fact.get(key)) for key in ("released", "principal", "payee"))
            if complete_segments or identified or result:
                enough, where = True, f"steps/{i}/facts: recorded escrow result"
                break
    else:
        wanted = rule["stepFacts"]
        for i, fact in facts:
            current = [key for key in wanted if _populated(fact.get(key))]
            if len(current) > len(found):
                found, where = current, f"steps/{i}/facts"
            if len(current) == len(wanted):
                enough = True
                break
    return {"status": "recorded" if enough else "gap",
            "resolvedFrom": where if enough else None,
            "missingKeys": [] if enough else sorted(set(wanted) - set(found)),
            "reason": ("local timeline matches independent business view, setup and final positions; not verified chain evidence"
                       if enough and "resolvedElsewhere" in rule else None),
            "slot": None, "renderedBy": None}


def for_scenario(scenario):
    """One scenario's dossier: every item, with how it resolved."""
    items = [dict(rule_result, item=rule["item"])
             for rule, rule_result in ((rule, _resolve(rule, scenario))
                                       for rule in DOSSIER_ITEMS)]
    by_status = {}
    for entry in items:
        by_status.setdefault(entry["status"], []).append(entry["item"])
    return {
        "scenarioId": scenario["scenarioId"],
        "title": scenario["title"],
        "mainPath": scenario["mainPath"],
        "cases": list(scenario.get("cases", ())),
        "items": items,
        "itemCount": len(items),
        "byStatus": {name: sorted(entries) for name, entries in sorted(by_status.items())},
        "gaps": sorted(entry["item"] for entry in items if entry["status"] == "gap"),
        "complete": not any(entry["status"] == "gap" for entry in items),
    }


def build(scenario_report=None):
    """Every scenario's dossier, and whether the declared items are carried.

    An empty report is reported as covering no scenario rather than as complete:
    nothing was read, so nothing is carried.
    """
    scenarios = list((scenario_report or {}).get("scenarios", ()))
    dossiers = [for_scenario(scenario) for scenario in scenarios]
    declared_slots = {name for name, _ in EVIDENCE_SLOTS}
    used_slots = sorted({rule["slot"] for rule in DOSSIER_ITEMS if "slot" in rule})
    ids = [entry["scenarioId"] for entry in dossiers]
    missing = sorted(set(MAIN_PATHS) - set(ids))
    unexpected = sorted(set(ids) - set(MAIN_PATHS))
    duplicates = sorted({scenario_id for scenario_id in ids if ids.count(scenario_id) > 1})
    return {
        "schema": "8415ex-demonstration-dossier/1",
        "items": [dict(rule, setup=list(rule.get("setup", ())),
                       stepFacts=list(rule.get("stepFacts", ())),
                       cases=list(rule.get("cases", ())))
                  for rule in DOSSIER_ITEMS],
        "declaredItemCount": len(DOSSIER_ITEMS),
        "dossiers": dossiers,
        "scenarioCount": len(dossiers),
        "scenariosNotCovered": missing,
        "unexpectedScenarios": unexpected,
        "duplicatedScenarios": duplicates,
        "gapsByScenario": {entry["scenarioId"]: entry["gaps"]
                           for entry in dossiers if entry["gaps"]},
        "allItemsCarried": bool(dossiers) and not missing and not unexpected and not duplicates
        and all(entry["complete"] for entry in dossiers),
        "notRunSlots": used_slots,
        "notRunSlotsAreDeclared": set(used_slots) <= declared_slots,
        "isNot": [
            "not a demonstration: this says a scenario records what a "
            "demonstration must carry, never that one was given",
            "not UI evidence: a page state stays NOT_RUN however completely the "
            "status pages render, because no browser ran",
            "not a chain result: a transaction hash stays NOT_RUN because nothing "
            "here signs or broadcasts",
        ],
    }

