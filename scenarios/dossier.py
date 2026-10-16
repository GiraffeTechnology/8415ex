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

Rules match on structure and on case identifiers, never on the wording of an
expectation, so rephrasing a check cannot silently turn an item into a gap.
"""
from .demos import MAIN_PATHS
from .handoff import EVIDENCE_SLOTS, NOT_RUN

#: The funding cases. A scenario asserting one of these has per-segment escrow
#: evidence even where its step facts do not name an escrow field.
FUNDING_CASES = ("T-11", "T-12", "T-13", "T-14", "T-15", "T-16", "T-28", "T-31")

#: The nine items a demonstration must carry, with how each is resolved.
#:
#: ``setup`` and ``stepFacts`` name keys on the record; ``require`` says whether
#: all of them or any of them is enough. ``cases`` is an alternative route: a
#: scenario that asserts one of those cases carries the item whatever its facts
#: are named. ``notRun`` marks an item no local run can discharge, with the slot
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
        "cases": FUNDING_CASES,
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


def _step_fact_keys(scenario):
    keys = set()
    for step in scenario.get("steps", ()):
        keys.update(step.get("facts", {}))
    return keys


def _asserted_cases(scenario):
    asserted = set()
    for expectation in scenario.get("expectations", ()):
        asserted.update(expectation.get("cases", ()))
    return asserted


def _resolve(rule, scenario):
    """One item against one scenario record, with where it resolved from."""
    if "notRun" in rule:
        return {"status": NOT_RUN, "resolvedFrom": None, "missingKeys": [],
                "reason": rule["notRun"], "slot": rule["slot"],
                "renderedBy": rule.get("renderedBy")}
    if "resolvedElsewhere" in rule:
        return {"status": "resolved-elsewhere",
                "resolvedFrom": rule["resolvedElsewhere"], "missingKeys": [],
                "reason": rule["why"], "slot": None, "renderedBy": None}
    if rule.get("steps"):
        present = bool(scenario.get("steps"))
        return {"status": "recorded" if present else "gap",
                "resolvedFrom": "the scenario's recorded steps" if present else None,
                "missingKeys": [] if present else ["steps"],
                "reason": None, "slot": None, "renderedBy": None}
    if rule.get("expectations"):
        present = bool(scenario.get("expectations"))
        return {"status": "recorded" if present else "gap",
                "resolvedFrom": ("the scenario's recorded expectations, each with "
                                 "its expected and observed value") if present else None,
                "missingKeys": [] if present else ["expectations"],
                "reason": None, "slot": None, "renderedBy": None}
    if "setup" in rule:
        available, wanted, where = set(scenario.get("setup", {})), rule["setup"], "setup"
    else:
        available, wanted, where = _step_fact_keys(scenario), rule["stepFacts"], "step facts"
    found = sorted(key for key in wanted if key in available)
    enough = (len(found) == len(wanted) if rule.get("require") != "any" else bool(found))
    if not enough and rule.get("cases"):
        asserted = sorted(set(rule["cases"]) & _asserted_cases(scenario))
        if asserted:
            return {"status": "recorded",
                    "resolvedFrom": "the cases this scenario asserts: "
                                    + ", ".join(asserted),
                    "missingKeys": [], "reason": None, "slot": None,
                    "renderedBy": None}
    return {
        "status": "recorded" if enough else "gap",
        "resolvedFrom": ("%s: %s" % (where, ", ".join(found))) if found else None,
        "missingKeys": sorted(set(wanted) - set(found)) if not enough else [],
        "reason": None, "slot": None, "renderedBy": None,
    }


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
    missing = sorted(set(MAIN_PATHS) - {entry["scenarioId"] for entry in dossiers})
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
        "gapsByScenario": {entry["scenarioId"]: entry["gaps"]
                           for entry in dossiers if entry["gaps"]},
        "allItemsCarried": bool(dossiers) and not missing
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
