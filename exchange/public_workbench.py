"""Explicit HTTP projections; private reports remain the execution source.

Do not recursively redact reports: unknown fields, party labels, session IDs,
journal keys and arbitrary error text must never become public by default.
Amounts are exact base-unit integers; missing/invalid input is unknown, not zero.
"""
import re

STATES = frozenset(("pending", "unknown", "settled", "failed", "refused", "blocked",
    "not-funded", "locked", "released", "refunded", "not-modelled", "release-failed",
    "release-outcome-unknown", "not-submitted", "confirmed", "rejected", "none",
    "available", "detached", "in-progress", "returned", "complete", "done"))


def integer(value):
    return value if type(value) is int and 0 <= value < 2**256 else None


def amount(value):
    if isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]{0,77}", value):
        return value if int(value) < 2**256 else None
    return None


def state(value):
    return value if isinstance(value, str) and value in STATES else "unknown"


def currency(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Z][A-Z0-9]{0,15}", value) else None


def funds(report):
    rows = []
    for item in report.get("segments", ()):
        index = integer(item.get("legIndex"))
        buyer = item.get("buyer")
        bearer_matches = isinstance(buyer, str) and bool(buyer) and item.get("gasBorneBy") == buyer
        gas = []
        for entry in item.get("gasEntries", ()):
            gas.append({"amount": amount(str(entry.get("amount"))) if type(entry.get("amount")) is int else None,
                        "asset": "ETH" if entry.get("asset") == "ETH" else None,
                        "unit": "wei" if entry.get("unit") == "wei" else None,
                        "sharedWith": [value for value in entry.get("sharedWith", ()) if integer(value) is not None],
                        "sharedOperation": entry.get("sharedOperation") is True,
                        "apportionment": entry.get("apportionment") if entry.get("apportionment") in ("undecided", "single-leg") else "unknown"})
        rows.append({"legIndex": index, "buyerPosition": index + 1 if index is not None else None,
                     "sellerPosition": index,
                     "principal": amount(item.get("principal")),
                     "principalAsset": currency(item.get("principalAsset")),
                     "principalUnit": "base-units" if item.get("principalUnit") == "base-units" else None,
                     "escrowStatus": state(item.get("escrowStatus")),
                     "paymentStatus": state(item.get("paymentStatus")),
                     "registrationStatus": state(item.get("registrationStatus")),
                     "fundingStatus": state(item.get("fundingStatus")),
                     "rollbackStatus": state(item.get("rollbackStatus")),
                     "released": item.get("released") is True, "refunded": item.get("refunded") is True,
                     "netToSeller": amount(item.get("netToPayee")), "netToBuyer": amount(item.get("netToPayer")),
                     "gasBearerRole": "this-leg-buyer" if bearer_matches else "unknown",
                     "gasBearerPosition": index + 1 if bearer_matches and index is not None else None,
                     "gasAsset": "ETH" if item.get("gasAsset") == "ETH" else None,
                     "gasUnit": "wei" if item.get("gasUnit") == "wei" else None,
                     "gasTotal": amount(item.get("gasTotal")), "gasEntries": gas})
    return {"segments": rows, "sharedGasAllocation": "undecided; original operation recorded once"}


def snapshot(private):
    raw = private["state"]
    receipt = raw["receipt"]
    rollback = raw["rollback"]
    source = private.get("source", {})
    # Only immutable source identities, never arbitrary deployment/run metadata.
    public_source = {key: value for key in ("commit", "tree")
                     if isinstance((value := source.get(key)), str) and re.fullmatch(r"[0-9a-f]{40}", value)}
    return {"schema": "8415ex-public-workbench/2", "source": public_source,
            "revision": private["revision"], "commandGateway": private["commandGateway"],
            "state": {"positions": {role: integer(receipt.get(role, {}).get("position")) for role in ("owner", "holder")},
                      "funds": funds(raw["funds"]),
                      "rollback": {"open": rollback.get("open") is True, "state": state(rollback.get("state")),
                                   "complete": rollback.get("complete") is True,
                                   "lastFinalizedPosition": integer(rollback.get("lastFinalizedPosition")),
                                   "affectedLegs": [i for i in rollback.get("affectedLegs", ()) if integer(i) is not None],
                                   "outstandingSteps": [{"legIndex": integer(step.get("legIndex")),
                                                         "status": state(step.get("status"))}
                                                        for step in rollback.get("outstandingSteps", ())]},
                      "overdue": [{"legIndex": integer(item.get("legIndex")),
                                   "commitmentDeadlineAt": integer(item.get("commitmentDeadlineAt"))}
                                  for item in raw["overdue"]]},
            "meaning": "Identity-excluding domain observation; not chain or complete delivery acceptance"}


def command_result(value):
    if not isinstance(value, dict):
        return {"status": "unknown"}
    result = {"status": state(value.get("status"))}
    transaction = value.get("transactionHash")
    if isinstance(transaction, str) and re.fullmatch(r"0x[0-9a-fA-F]{64}", transaction):
        result["transactionHash"] = transaction
    return result
