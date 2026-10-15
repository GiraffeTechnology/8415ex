"""The logical event contract: a declared vocabulary, correlation, and replay.

Three things are needed of an audit trail before it is worth keeping, and this
module supplies them.

First, a **declared vocabulary**. A free-form event kind means a typo silently
becomes a new kind, and nobody notices that a group of events stopped being
recorded. Every kind here is declared, grouped by the audit coverage it serves,
and an undeclared kind is refused at the point of recording.

Second, **correlation**. An event that cannot be tied to the asset, transfer,
request and run it belongs to cannot be used to investigate anything. Every
event carries the full set of correlation keys, and a key that is genuinely not
known for that event is present and null rather than absent - an absent key and
an unknown value read the same to a consumer, and they are not the same thing.
The chain keys are the same: null means not observed, never zero or empty.

Third, **replay**. Rebuilding the index from the recorded events must produce
the same view, and consuming the same event twice must not move an asset or any
money twice. Both are checkable here, over the events the domain really wrote.

What this module does not do is manufacture coverage. Two groups - a transfer
observed on chain, and a chain reorganisation - cannot be evidenced without a
real chain, and the coverage report says so with a reason instead of counting a
simulated record as an observation.
"""
import re

from .errors import require
from .ids import canonical_json, digest

HEX32 = re.compile(r"\A0x[0-9a-f]{64}\Z")

#: The audit groups of PRD section 10.2, each with the event kinds that serve
#: it. A group with no declared kind would be a coverage claim with nothing
#: behind it, so every group names at least one.
AUDIT_GROUPS = (
    {
        "group": "intent-decision",
        "requires": "an intent accepted, and an intent refused with its reasons",
        "kinds": ("intent-accepted", "intent-refused"),
        "locallyEvidenced": True,
    },
    {
        "group": "transfer",
        "requires": "a transfer submitted, and the same transfer observed on chain",
        "kinds": ("transfer-executed", "transfer-observed"),
        "locallyEvidenced": False,
        "whyNotLocal": "the observation half needs a real transaction on a real "
                       "chain; a simulated record is not an observation",
    },
    {
        "group": "registration",
        "requires": "a registration request, and its result in every disposition",
        "kinds": ("registration-submitted", "registration-result",
                  "registration-result-idempotent", "registration-result-drained"),
        "locallyEvidenced": True,
    },
    {
        "group": "final-prefix",
        "requires": "the confirmed final prefix advancing",
        "kinds": ("final-prefix-advanced",),
        "locallyEvidenced": True,
    },
    {
        "group": "funding",
        "requires": "funds locked, released and refunded, each on its own record",
        "kinds": ("escrow-locked", "payment-attempt-started", "payment-enquiry",
                  "segment-release-attempt", "segment-refund-attempt",
                  "segment-refunded"),
        "locallyEvidenced": True,
    },
    {
        "group": "rollback",
        "requires": "a rollback opened, progressing, blocked and finished",
        "kinds": ("rollback-opened", "rollback-advanced", "rollback-step-blocked",
                  "asset-return-attempt", "asset-returned"),
        "locallyEvidenced": True,
    },
    {
        "group": "redemption",
        "requires": "a redemption requested, and each exit step's result",
        "kinds": ("redemption-requested", "exit-step-done", "exit-step-blocked",
                  "receipt-burned"),
        "locallyEvidenced": True,
    },
    {
        "group": "reorg-recovery",
        "requires": "an event reorganisation, and recovery from one",
        "kinds": ("late-result-conflict", "chain-reorg-observed"),
        "locallyEvidenced": False,
        "whyNotLocal": "a reorganisation is a chain observation; the late-result "
                       "conflict is the local half and is not a reorg",
    },
)

#: Kinds the domain records that serve no section 10.2 group. They are declared
#: so recording them is allowed, and kept out of the groups so they never count
#: as coverage of something they do not evidence.
ANCILLARY_KINDS = (
    {"kind": "receipt-minted", "why": "a technical record of one receipt as one "
                                      "token; it asserts no right"},
    {"kind": "gas-recorded", "why": "an observed gas-unit figure, not a funding "
                                    "movement"},
)

#: Every declared kind.
EVENT_KINDS = tuple(sorted(
    [kind for group in AUDIT_GROUPS for kind in group["kinds"]]
    + [entry["kind"] for entry in ANCILLARY_KINDS]))

#: The kinds that record a movement that definitely happened. Replay counts
#: these separately, because the rule that matters is that repeated consumption
#: must not move an asset or money twice.
#:
#: An attempt is not a movement. Where an attempt has its own completed
#: counterpart - a refund records ``segment-refunded`` when it succeeds and
#: ``segment-refund-attempt`` only when it does not - counting the attempt as
#: well would double-count the success.
MOVEMENT_KINDS = {
    "transfer-executed": "asset",
    "asset-returned": "asset",
    "receipt-burned": "asset",
    "escrow-locked": "fund",
    "segment-refunded": "fund",
}

#: The one kind that has no completed counterpart: a release records its
#: attempt whether the money moved or not, and the escrow status in its own
#: detail is what says which happened. A failed or unknown-outcome release is
#: not a movement, and treating it as one would report money as paid that the
#: adapter never confirmed.
CONDITIONAL_MOVEMENT_KINDS = {
    "segment-release-attempt": {"moves": "fund", "key": "escrowStatus",
                                "movedWhen": "released"},
}

#: Correlation keys every event carries. A key that is not known for an event is
#: present and null: absent and unknown must not read the same.
CORRELATION_KEYS = ("receiptId", "assetKey", "transferId", "requestId", "runId")

#: Chain correlation keys. Null means not observed - never zero, never empty.
CHAIN_KEYS = ("chainId", "txHash", "blockHash", "logIndex")


def declared_kind(kind, code="EX_EVENT_KIND_REFUSED"):
    """The kind, or a refusal. An undeclared kind is never recorded."""
    require(isinstance(kind, str) and kind in EVENT_KINDS, code, kind)
    return kind


def _hash32(value, code):
    require(isinstance(value, str) and HEX32.match(value) is not None, code, value)
    return value


def _index(value, code):
    # bool is an int in Python and is not an acceptable log index.
    require(isinstance(value, int) and not isinstance(value, bool) and value >= 0,
            code, value)
    return value


def correlation(receipt_id=None, asset_key=None, transfer_id=None, request_id=None,
                run_id=None, chain=None):
    """One event's correlation block, with every key present.

    ``chain`` is a caller-reported position, not independently verified evidence.
    Each of its keys is syntax-validated if given; anything not supplied stays
    null, which is the honest answer for a record this layer produced without
    touching a chain.
    """
    observed = dict(chain or {})
    unknown = sorted(set(observed) - set(CHAIN_KEYS))
    require(not unknown, "EX_EVENT_CHAIN_KEY_REFUSED", ", ".join(unknown))
    block = {
        "receiptId": receipt_id,
        "assetKey": list(asset_key) if asset_key is not None else None,
        "transferId": transfer_id,
        "requestId": request_id,
        "runId": run_id,
        "chainId": None,
        "txHash": None,
        "blockHash": None,
        "logIndex": None,
    }
    if "chainId" in observed:
        block["chainId"] = _index(observed["chainId"], "EX_EVENT_CHAIN_ID_REFUSED")
    if "txHash" in observed:
        block["txHash"] = _hash32(observed["txHash"], "EX_EVENT_TX_HASH_REFUSED")
    if "blockHash" in observed:
        block["blockHash"] = _hash32(observed["blockHash"], "EX_EVENT_BLOCK_HASH_REFUSED")
    if "logIndex" in observed:
        block["logIndex"] = _index(observed["logIndex"], "EX_EVENT_LOG_INDEX_REFUSED")
    observed_on_chain = all(block[key] is not None for key in CHAIN_KEYS)
    block["chainPositionComplete"] = observed_on_chain
    block["observedOnChain"] = False
    block["chainEvidenceStatus"] = "NOT_RUN"
    block["chainProvenance"] = "caller-reported-unverified" if observed else "not-supplied"
    block["chainPosition"] = ("%s/%s/%s" % (block["blockHash"], block["txHash"],
                                            block["logIndex"])
                              if observed_on_chain else None)
    return block


def event_identity(event):
    """What makes two records the same event rather than two events.

    Taken from the kind, the sequence and the correlation, not from the detail:
    differing payloads under the same identity are conflicts, not extra movements.
    Replay rejects those conflicts rather than silently choosing one payload.
    """
    return digest({"kind": event["kind"], "sequence": event["sequence"],
                   "correlation": event.get("correlation")})


def coverage(timeline):
    """Which audit groups this timeline evidenced, and which it did not.

    A group whose evidence needs a real chain is reported as not locally
    evidenceable with the reason, separately from a group that simply did not
    occur in this run. Collapsing the two would turn a missing observation into
    a passing one.
    """
    observed = {}
    for event in timeline:
        observed.setdefault(event["kind"], 0)
        observed[event["kind"]] += 1
    groups = []
    for group in AUDIT_GROUPS:
        seen = {kind: observed.get(kind, 0) for kind in group["kinds"]}
        groups.append({
            "group": group["group"],
            "requires": group["requires"],
            "declaredKinds": list(group["kinds"]),
            "observedCounts": seen,
            "observedKinds": sorted(kind for kind, count in seen.items() if count),
            "anyObserved": any(seen.values()),
            "allObserved": all(seen.values()),
            "locallyEvidenced": group["locallyEvidenced"],
            "whyNotLocal": group.get("whyNotLocal"),
        })
    undeclared = sorted(set(observed) - set(EVENT_KINDS))
    return {
        "schema": "8415ex-audit-coverage/1",
        "groups": groups,
        "groupCount": len(groups),
        "fullyObserved": sorted(entry["group"] for entry in groups
                                if entry["allObserved"] and entry["locallyEvidenced"]),
        "partlyObserved": sorted(entry["group"] for entry in groups
                                 if entry["anyObserved"] and not entry["allObserved"]),
        "notObserved": sorted(entry["group"] for entry in groups
                              if not entry["anyObserved"]),
        "notLocallyEvidenceable": sorted(entry["group"] for entry in groups
                                         if not entry["locallyEvidenced"]),
        "undeclaredKindsObserved": undeclared,
        "eventCount": len(timeline),
        "chainEvidenceStatus": "NOT_RUN",
        "isNot": [
            "not a chain observation: a locally produced record is not evidence "
            "that a transaction or a reorganisation was seen on a chain",
            "not an acceptance result: coverage says an audit group was recorded, "
            "never that the behaviour it records is correct",
        ],
    }


def replay(timeline):
    """Build a pure local index, without executing asset or payment operations.

    Every event is consumed in recorded order. A repeat of an event already
    consumed is counted as a duplicate and changes nothing, which is the rule
    that matters: re-consuming an event must not move an asset or money again.
    """
    state = {
        "schema": "8415ex-audit-replay/1",
        "consumed": 0,
        "duplicatesIgnored": 0,
        "kindCounts": {},
        "assetMovements": [],
        "fundMovements": [],
        "attemptsThatMovedNothing": [],
        "finalPrefix": None,
        "byTransfer": {},
        "byRequest": {},
        "correlationGaps": {},
        "outOfOrder": [],
    }
    seen = {}
    stream_key = None
    slots = {}
    operations = set()
    payloads = []
    highest = -1
    for event in timeline:
        kind = declared_kind(event["kind"])
        identity = event_identity(event)
        _index(event["sequence"], "EX_EVENT_SEQUENCE_REFUSED")
        payload = digest(event)
        link = event.get("correlation") or {}
        require(link.get("receiptId") == event.get("receiptId"),
                "EX_EVENT_STREAM_REFUSED", "receipt correlation mismatch")
        current_stream = (link.get("receiptId", event.get("receiptId")), link.get("runId"))
        if stream_key is None:
            stream_key = current_stream
        require(current_stream == stream_key, "EX_EVENT_STREAM_REFUSED", str(current_stream))
        slot = (current_stream[0], event["sequence"])
        require(slot not in slots or slots[slot] == payload, "EX_EVENT_CONFLICT", str(slot))
        slots[slot] = payload
        if identity in seen:
            require(seen[identity] == payload, "EX_EVENT_CONFLICT", identity)
            state["duplicatesIgnored"] += 1
            continue
        seen[identity] = payload
        payloads.append(payload)
        if event["sequence"] < highest:
            state["outOfOrder"].append(event["sequence"])
        highest = max(highest, event["sequence"])
        state["consumed"] += 1
        state["kindCounts"][kind] = state["kindCounts"].get(kind, 0) + 1
        moves = MOVEMENT_KINDS.get(kind)
        conditional = CONDITIONAL_MOVEMENT_KINDS.get(kind)
        if conditional is not None:
            observed = (event.get("detail") or {}).get(conditional["key"])
            if observed == conditional["movedWhen"]:
                moves = conditional["moves"]
            else:
                state["attemptsThatMovedNothing"].append({
                    "kind": kind, "sequence": event["sequence"],
                    conditional["key"]: observed})
        detail = event.get("detail") or {}
        if kind == "asset-returned" and detail.get("operations") == 0:
            moves = None
        if kind == "payment-enquiry" and detail.get("paymentStatus") == "settled":
            moves = "fund"
        operation = (kind, identity)
        if moves == "fund" and kind != "escrow-locked":
            intent = detail.get("paymentIntent") or ("refund" if kind == "segment-refunded" else "release")
            operation = (intent, detail.get("escrowId"))
        if moves == "asset" and kind == "asset-returned":
            operation = (kind, detail.get("stepId", identity))
        if moves is not None and operation not in operations:
            operations.add(operation)
            state["%sMovements" % moves].append({"kind": kind,
                                                 "sequence": event["sequence"],
                                                 "identity": identity})
        if kind == "receipt-minted":
            state["finalPrefix"] = 0
        if kind == "final-prefix-advanced":
            state["finalPrefix"] = event["detail"].get("to")
        link = event.get("correlation") or {}
        for key, bucket in (("transferId", "byTransfer"), ("requestId", "byRequest")):
            if link.get(key) is not None:
                state[bucket].setdefault(link[key], []).append(event["sequence"])
        for key in CORRELATION_KEYS:
            if link.get(key) is None:
                state["correlationGaps"][key] = state["correlationGaps"].get(key, 0) + 1
    state["attemptsThatMovedNothingCount"] = len(state["attemptsThatMovedNothing"])
    state["assetMovementCount"] = len(state["assetMovements"])
    state["fundMovementCount"] = len(state["fundMovements"])
    state["sequential"] = state["outOfOrder"] == []
    sequences = sorted(slot[1] for slot in slots)
    state["completeFromMint"] = bool(sequences) and sequences == list(range(len(sequences))) and bool(payloads) and timeline[0]["kind"] == "receipt-minted"
    state["projectionOnly"] = True
    state["chainEvidenceStatus"] = "NOT_RUN"
    state["attemptOutcomeMeaning"] = "unconfirmed attempts are not proof that no external movement occurred"
    state["digest"] = digest({
        "payloadDigests": payloads,
        "kindCounts": state["kindCounts"],
        "assetMovements": state["assetMovements"],
        "fundMovements": state["fundMovements"],
        "finalPrefix": state["finalPrefix"],
        "byTransfer": state["byTransfer"],
        "byRequest": state["byRequest"],
        "attemptsThatMovedNothing": state["attemptsThatMovedNothing"],
    })
    return state


def rebuilt_identically(timeline):
    """Whether a replay, and a replay of the same events consumed twice, agree.

    The second replay feeds every event in a second time. A sound index answers
    the same thing both times; one that double-counts does not.
    """
    once = replay(timeline)
    twice = replay(list(timeline) + list(timeline))
    return {
        "schema": "8415ex-audit-rebuild/1",
        "digest": once["digest"],
        "repeatedDigest": twice["digest"],
        "identical": once["digest"] == twice["digest"],
        "consumed": once["consumed"],
        "duplicatesIgnoredOnRepeat": twice["duplicatesIgnored"],
        "assetMovementsOnce": once["assetMovementCount"],
        "assetMovementsOnRepeat": twice["assetMovementCount"],
        "fundMovementsOnce": once["fundMovementCount"],
        "fundMovementsOnRepeat": twice["fundMovementCount"],
        "meaning": ("pure local projection; identical duplicate records do not duplicate "
                    "projected effects; no external asset or payment operation is executed"),
    }


def contract():
    """The declared event contract, for a reviewer reading it without a run."""
    return {
        "schema": "8415ex-audit-contract/1",
        "groups": [dict(group, kinds=list(group["kinds"])) for group in AUDIT_GROUPS],
        "ancillaryKinds": [dict(entry) for entry in ANCILLARY_KINDS],
        "declaredKinds": list(EVENT_KINDS),
        "declaredKindCount": len(EVENT_KINDS),
        "movementKinds": dict(MOVEMENT_KINDS),
        "conditionalMovementKinds": {kind: dict(rule) for kind, rule
                                     in CONDITIONAL_MOVEMENT_KINDS.items()},
        "correlationKeys": list(CORRELATION_KEYS),
        "chainKeys": list(CHAIN_KEYS),
        "nullMeans": ("not known for this event; an absent key and an unknown "
                      "value must not read the same"),
        "isNot": [
            "not a standard event signature: these are logical names mapped onto "
            "what the domain already records, not an ABI or a published standard",
        ],
        "contractDigest": digest({"groups": [list(group["kinds"]) for group in AUDIT_GROUPS],
                                  "kinds": list(EVENT_KINDS),
                                  "movement": MOVEMENT_KINDS,
                                  "conditional": CONDITIONAL_MOVEMENT_KINDS,
                                  "correlation": list(CORRELATION_KEYS),
                                  "chain": list(CHAIN_KEYS)}),
    }


def canonical(timeline):
    """The timeline in its canonical encoding, for a stable comparison."""
    return canonical_json(list(timeline))
