"""The logical operations of PRD section 10.1, mapped onto real code.

The PRD names ten logical operations. Logical names are not an ABI and not a
published standard, and the PRD says so, but they still have to land somewhere:
a logical operation with no implementation behind it is a requirement nobody is
carrying, and nothing notices until someone goes looking.

So each one is resolved to the domain methods that implement it, and the
resolution is checked rather than asserted in prose. A method that is renamed or
removed is a finding. One operation maps to two methods and says so, because
pretending it maps to one would hide where the work actually happens.

Two of the section's rules are also checked, each in the only way it honestly
can be.

A read must not move money or an asset. That is a behaviour, so it is exercised:
every read-only operation is called against a funded exchange and the payment
and asset-control counters are compared before and after. A read that moved
something would fail here.

Whether a state-changing operation has idempotency and precondition checks is
answered by the acceptance cases that exercise them, not by inspecting a
signature. Each operation names its cases, the cases are checked against the
matrix, and that is stated as the route rather than dressed up as an assertion
about the code.

What is deliberately not claimed: that a method's return carries everything the
PRD's result column asks for. That is a review judgement over real output, and
a signature cannot settle it.
"""
import inspect

from exchange.ledger import Exchange

from . import matrix

#: The ten logical operations, the domain methods behind each, and the
#: acceptance cases that exercise it. ``readOnly`` marks an operation that must
#: leave no fund or asset movement behind.
OPERATIONS = (
    {
        "logical": "validateIntent",
        "methods": ("validate_intent",),
        "readOnly": True,
        "leaves": "executability, the exact refusal reasons, and the checked "
                  "authorization identity",
        "cases": ("T-06", "T-08", "T-34"),
    },
    {
        "logical": "matchIntents",
        "methods": ("match_intents",),
        "readOnly": False,
        "leaves": "a deterministic pairing or none, with no signed term changed",
        "cases": ("T-09",),
    },
    {
        "logical": "executeTransfer",
        "methods": ("execute_transfer",),
        "readOnly": False,
        "leaves": "one transfer, its execution result and the registration work "
                  "it leaves behind",
        "cases": ("T-03", "T-07"),
    },
    {
        "logical": "submitRegistration",
        "methods": ("submit_registration",),
        "readOnly": False,
        "leaves": "an idempotent request identity, the submission state and the "
                  "commitment window",
        "cases": ("T-04", "T-05", "T-10"),
    },
    {
        "logical": "applyRegistrationResult",
        "methods": ("apply_registration_result",),
        "readOnly": False,
        "leaves": "accepted, deferred, refused or conflicting, and whether the "
                  "final prefix advanced",
        "cases": ("T-04", "T-05", "T-10", "T-29"),
    },
    {
        "logical": "settleEligibleSegments",
        "methods": ("settle_eligible_segments", "release_segment"),
        "readOnly": False,
        "leaves": "independent release evidence per segment, waiting on no "
                  "unfinished suffix",
        "cases": ("T-11", "T-12", "T-13", "T-14", "T-15", "T-16", "T-28", "T-31"),
    },
    {
        "logical": "evaluateDeadline",
        "methods": ("evaluate_deadline",),
        "readOnly": True,
        "leaves": "whether new trades stop, whether a defined recovery may be "
                  "triggered, and why",
        "cases": ("T-24", "T-25"),
    },
    {
        "logical": "rollbackSuffix",
        "methods": ("begin_rollback", "advance_rollback"),
        "readOnly": False,
        "leaves": "the affected interval, each step's result and a safely "
                  "retryable state",
        "cases": ("T-17", "T-18", "T-19", "T-20", "T-21", "T-22", "T-23", "T-30"),
        "note": "opening a rollback and advancing it are separate operations "
                "here, because a rollback is resumable and an advance that "
                "blocks must be retryable without reopening",
    },
    {
        "logical": "requestRedemption",
        "methods": ("request_redemption", "exit_eligibility"),
        "readOnly": False,
        "leaves": "redeemable or the exact refusal, and the execution evidence",
        "cases": ("T-32", "T-33"),
    },
    {
        "logical": "getReceiptTimeline",
        "methods": ("receipt_timeline",),
        "readOnly": True,
        "leaves": "the trade, registration, funding, rollback and chain "
                  "observation records in one consistent order",
        "cases": ("T-26",),
    },
)

#: Further read-only operations this layer relies on. They are not in the
#: section's table, but they are reads, so the no-movement rule covers them too.
ADDITIONAL_READS = ("receipt_view", "reconciliation", "rollback_report",
                    "exit_report", "redemption_readiness", "owner_of",
                    "holder_of", "deferred_legs", "overdue_requests",
                    "segment_release_state", "authorization_state")


def resolve():
    """Each logical operation against the domain class, method by method."""
    resolved = []
    for entry in OPERATIONS:
        methods = []
        for name in entry["methods"]:
            attribute = getattr(Exchange, name, None)
            methods.append({
                "method": name,
                "exists": attribute is not None,
                "callable": callable(attribute),
                "parameters": ([parameter for parameter
                                in inspect.signature(attribute).parameters
                                if parameter != "self"]
                               if callable(attribute) else []),
            })
        resolved.append(dict(entry, methods=methods,
                             methodNames=list(entry["methods"]),
                             cases=list(entry["cases"]),
                             resolved=all(item["callable"] for item in methods),
                             mapsToSeveralMethods=len(methods) > 1))
    return resolved


def _movement_counters(exchange):
    """What this exchange has moved so far: money, assets and recorded events."""
    payments = exchange.payments
    control = exchange.asset_control
    return {
        "paymentMovements": getattr(payments, "movements", None),
        "assetReturns": getattr(control, "returns", None),
        "recordedEvents": len(exchange.receipt_timeline("rcpt-8415-0001")),
        "ownerOf": exchange.owner_of("rcpt-8415-0001"),
        "holderIndex": exchange.holder_index("rcpt-8415-0001"),
    }


def read_only_moves_nothing():
    """Exercise every read against a funded exchange and compare the counters.

    This is the one rule in the section that can be demonstrated rather than
    declared, so it is: a read that moved money, moved the asset, or appended to
    the audit trail shows up as a difference.
    """
    from exchange import fixtures as F

    # A funded chain that also holds asset control, so every counter a read
    # could disturb is really present and really readable.
    exchange, _ = F.rollback_chain_to_d()
    receipt_id = "rcpt-8415-0001"
    reads = [entry for entry in OPERATIONS if entry["readOnly"]]
    results = []
    for entry in reads:
        for name in entry["methods"]:
            before = _movement_counters(exchange)
            called, error = True, None
            try:
                _call_read(exchange, name, receipt_id)
            except Exception as problem:            # noqa: BLE001 - reported, not raised
                called, error = False, "%s: %s" % (type(problem).__name__, problem)
            after = _movement_counters(exchange)
            results.append({
                "logical": entry["logical"], "method": name, "called": called,
                "error": error, "before": before, "after": after,
                "movedNothing": before == after,
            })
    for name in ADDITIONAL_READS:
        before = _movement_counters(exchange)
        called, error = True, None
        try:
            _call_read(exchange, name, receipt_id)
        except Exception as problem:                # noqa: BLE001 - reported, not raised
            called, error = False, "%s: %s" % (type(problem).__name__, problem)
        after = _movement_counters(exchange)
        results.append({
            "logical": None, "method": name, "called": called, "error": error,
            "before": before, "after": after, "movedNothing": before == after,
        })
    return {
        "schema": "8415ex-read-only-check/1",
        "reads": results,
        "readCount": len(results),
        "calledCount": sum(1 for entry in results if entry["called"]),
        "notCalled": [{"method": entry["method"], "error": entry["error"]}
                      for entry in results if not entry["called"]],
        "movedSomething": [entry["method"] for entry in results
                           if not entry["movedNothing"]],
        "allReadsMovedNothing": all(entry["movedNothing"] for entry in results),
        "counters": ["paymentMovements", "assetReturns", "recordedEvents",
                     "ownerOf", "holderIndex"],
        "note": ("a read that moved money, moved the asset or appended to the "
                 "audit trail would show as a difference in one of these"),
    }


def _call_read(exchange, name, receipt_id):
    """Call one read with arguments it accepts, without changing any state."""
    arguments = {
        "validate_intent": ("sell-ab",),
        "evaluate_deadline": (receipt_id,),
        "receipt_timeline": (receipt_id,),
        "receipt_view": (receipt_id,),
        "reconciliation": (receipt_id,),
        "rollback_report": (receipt_id,),
        "exit_report": (receipt_id,),
        "redemption_readiness": (receipt_id, exchange.owner_of(receipt_id)),
        "owner_of": (receipt_id,),
        "holder_of": (receipt_id,),
        "deferred_legs": (receipt_id,),
        "overdue_requests": (receipt_id,),
        "segment_release_state": (receipt_id, 0),
        "authorization_state": ("auth-sell-ab",),
    }[name]
    return getattr(exchange, name)(*arguments)


def build(root="."):
    """The operation map, its resolution and the read-only demonstration."""
    resolved = resolve()
    unresolved = [entry["logical"] for entry in resolved if not entry["resolved"]]
    unknown_cases = sorted({case for entry in OPERATIONS for case in entry["cases"]
                            if case not in matrix.CASE_REQUIREMENTS})
    reads = read_only_moves_nothing()
    covered = sorted({case for entry in OPERATIONS for case in entry["cases"]})
    return {
        "schema": "8415ex-operation-map/1",
        "operations": resolved,
        "operationCount": len(resolved),
        "unresolvedOperations": unresolved,
        "casesNamed": covered,
        "casesNamedThatDoNotExist": unknown_cases,
        "readOnlyCheck": reads,
        "consistent": (not unresolved and not unknown_cases
                       and reads["allReadsMovedNothing"]
                       and not reads["notCalled"]),
        "resultColumnCheckedBy": ("the acceptance cases each operation names; a "
                                  "method signature cannot settle whether its "
                                  "return carries what the result column asks for"),
        "isNot": [
            "not an ABI and not a published standard: these are logical names "
            "mapped onto what the domain already implements",
            "not a claim about return content: that a method exists says nothing "
            "about its result carrying every required field",
            "not an idempotency proof: whether a state-changing operation checks "
            "its preconditions is answered by the cases listed, not by this map",
        ],
    }
