"""The logical event contract, checked over the timeline the domain exposes.

PRD section 10.2 asks three things of the audit trail, and all three can be
answered without touching the recorder:

* a **declared vocabulary**, so a group of events that stopped being recorded is
  visible rather than silently missing;
* **correlation** to the asset, transfer, request and run an investigation
  starts from, and to a chain position where one exists;
* **replay**, so rebuilding the index gives the same business view and
  consuming the same event twice moves no asset and no money twice.

This module is read-only by design. Enforcing the vocabulary inside the
recorder, and carrying a correlation block on the event itself, belong to the
domain and ledger surface, which this task does not own. So the vocabulary is a
conformance check over the kinds the domain really records, read from its own
source; correlation is derived from the event and reports exactly which keys the
domain does not carry; and replay needs nothing but the timeline.

The result is the honest one. Where the contract needs an event the domain does
not record, that is reported as a named interface gap with its owner and the
next step, not papered over and not quietly fixed in someone else's file.
"""
import pathlib
import re

from exchange.ids import digest

#: Where the domain records its events, and the call shape that does it. Read
#: from the source rather than from a list here, so a kind the domain adds or
#: removes shows up as a conformance finding instead of staying invisible.
LEDGER_SOURCE = "exchange/ledger.py"
RECORD_CALL = re.compile(r'self\._record\(\s*[A-Za-z_.\[\]"\' ]+,\s*"([a-z][a-z-]*)"')

#: The audit groups of PRD section 10.2, each with the kinds that serve it.
AUDIT_GROUPS = (
    {
        "group": "intent-decision",
        "requires": "an intent accepted, and an intent refused with its reasons",
        "kinds": ("intent-accepted", "intent-refused"),
        "evidence": "recorded",
    },
    {
        "group": "transfer",
        "requires": "a transfer submitted, and the same transfer observed on chain",
        "kinds": ("transfer-executed", "transfer-observed"),
        "evidence": "recorded",
    },
    {
        "group": "registration",
        "requires": "a registration request, and its result in every disposition",
        "kinds": ("registration-submitted", "registration-result",
                  "registration-result-idempotent", "registration-result-drained"),
        "evidence": "recorded",
    },
    {
        "group": "final-prefix",
        "requires": "the confirmed final prefix advancing",
        "kinds": (),
        # The domain records no event for the prefix moving, but every
        # registration result carries the resulting holder index, so the
        # advance is derivable from the trail as it stands. Derived is kept
        # apart from recorded: it is a correct reading of the events, not an
        # event, and a consumer told it was recorded would look for one.
        "evidence": "derived",
        "derivedFrom": ("registration-result", "registration-result-drained"),
        "derivedBy": "the holderIndex each result carries, read in order",
    },
    {
        "group": "funding",
        "requires": "funds locked, released and refunded, each on its own record",
        "kinds": ("escrow-locked", "payment-attempt-started", "payment-enquiry",
                  "segment-release-attempt", "segment-refund-attempt",
                  "segment-refunded"),
        "evidence": "recorded",
    },
    {
        "group": "rollback",
        "requires": "a rollback opened, progressing, blocked and finished",
        "kinds": ("rollback-opened", "rollback-advanced", "rollback-step-blocked",
                  "asset-return-attempt", "asset-returned"),
        "evidence": "recorded",
    },
    {
        "group": "trading-recovery",
        "requires": "trading eligibility after rollback, preserving withdrawn history",
        "kinds": ("trading-resumed",),
        "evidence": "recorded",
    },
    {
        "group": "currency-admission",
        "requires": "NFT0 missing, mismatched or insufficient selected-currency refusal",
        "kinds": (),
        "evidence": "interface-gap",
        "whyNotLocal": "original currency refusal decisions are not yet carried by this timeline",
    },
    {
        "group": "eth-gas-admission",
        "requires": "zero or insufficient ETH warning and refusal before execution",
        "kinds": (),
        "evidence": "interface-gap",
        "whyNotLocal": "original ETH admission decisions are not yet carried by this timeline",
    },
    {
        "group": "remint",
        "requires": "holder remint request/refusal, old/new links and atomic burn/mint result",
        "kinds": (),
        "evidence": "interface-gap",
        "whyNotLocal": "original remint journal and chain evidence are not yet joined to this timeline",
    },
    {
        "group": "reorg-recovery",
        "requires": "an event reorganisation, and recovery from one",
        "kinds": ("late-result-conflict", "chain-reorg-observed"),
        "evidence": "recorded",
    },
)

#: Kinds the domain records that serve no section 10.2 group. Declared so they
#: are not reported as undeclared, and kept out of the groups so they never
#: count as coverage of something they do not evidence.
ANCILLARY_KINDS = (
    {"kind": "receipt-minted",
     "why": "a technical record of one receipt as one token; it asserts no right"},
    {"kind": "gas-recorded",
     "why": "an observed gas-unit figure, not a funding movement"},
)

#: Kinds no local run can produce, because they are chain observations. They are
#: declared so the contract is complete, and never counted as locally observed.
CHAIN_ONLY_KINDS = (
    {"kind": "transfer-observed",
     "why": "a transaction seen on a real chain; a simulated record is not an "
            "observation"},
    {"kind": "chain-reorg-observed",
     "why": "a reorganisation is a chain observation; the local late-result "
            "conflict is a different fact"},
)

# Known historical physical-operation evidence remains readable. These are not
# required active events, and recording one in current domain source is a gap.
RETIRED_PHYSICAL_KINDS = ("exit-step-blocked", "exit-step-done",
                          "receipt-burned", "redemption-requested")

#: Every kind this contract names.
DECLARED_KINDS = tuple(sorted(
    [kind for group in AUDIT_GROUPS for kind in group["kinds"]]
    + [entry["kind"] for entry in ANCILLARY_KINDS]))

#: Kinds whose record is a movement that definitely happened. An attempt is not
#: a movement: where an attempt has its own completed counterpart - a refund
#: records ``segment-refunded`` on success and ``segment-refund-attempt`` only
#: when it does not - counting the attempt as well would double-count it.
MOVEMENT_KINDS = {
    "transfer-executed": "asset",
    "asset-returned": "asset",
    "escrow-locked": "fund",
    "segment-refunded": "fund",
}
HISTORICAL_MOVEMENT_KINDS = {"receipt-burned": "asset"}

#: The one kind with no completed counterpart: a release records its attempt
#: whether the money moved or not, and its own escrow status says which. A
#: failed or unknown-outcome release is not a movement, and counting it as one
#: would report money as paid that the adapter never confirmed.
CONDITIONAL_MOVEMENT_KINDS = {
    "segment-release-attempt": {"moves": "fund", "key": "escrowStatus",
                                "movedWhen": "released"},
}

#: Correlation keys an investigation starts from.
CORRELATION_KEYS = ("receiptId", "assetKey", "transferId", "requestId", "runId")

#: Chain correlation keys. Null means not observed - never zero, never empty.
CHAIN_KEYS = ("chainId", "txHash", "blockHash", "logIndex")

#: Which correlation keys the domain's own event shape carries, and how. An
#: event is ``{sequence, kind, receiptId, detail}``: the receipt is on the
#: event, the transfer and request appear inside the free-form detail where the
#: operation names them, and nothing carries the run or a chain position.
CORRELATION_SOURCES = {
    "receiptId": "on the event",
    "assetKey": "not on the event; resolved from the receipt this timeline belongs to",
    "transferId": "inside the free-form detail, where the operation names it",
    "requestId": "inside the free-form detail, where the operation names it",
    "runId": "not carried by the domain",
    "chainId": "not carried by the domain",
    "txHash": "not carried by the domain",
    "blockHash": "not carried by the domain",
    "logIndex": "not carried by the domain",
}

#: What the contract needs that this surface cannot supply, with its owner and
#: the next step. Each is a dependency, not a defect and not a local failure.
INTERFACE_GAPS = (
    {
        "gap": "currency admission decisions are not joined to the timeline",
        "neededFor": "the currency-admission audit group",
        "whyNotLocal": "a report cannot invent the original admission decision",
        "owner": "EX admission and original native financial integration owners",
        "nextStep": "record the actual source-bound decision without signing or dispatching a refused trade",
    },
    {
        "gap": "ETH gas warning and refusal decisions are not joined to the timeline",
        "neededFor": "the eth-gas-admission audit group",
        "whyNotLocal": "a gas amount alone is not an admission or refusal event",
        "owner": "EX gas admission and original native financial integration owners",
        "nextStep": "join the real ETH admission outcome before execution without creating an invented event",
    },
    {
        "gap": "original atomic remint evidence is not joined to the timeline",
        "neededFor": "the remint audit group",
        "whyNotLocal": "a mint record or historical collection burn is not atomic remint evidence",
        "owner": "EX remint and original native journal integration owners",
        "nextStep": "join the exact original request, old/new token binding and verified atomic result",
    },
    {
        "gap": "no event is recorded when an intent is accepted or refused",
        "neededFor": "the intent-decision audit group",
        "whyNotLocal": "recording it means writing to the recorder, which is the "
                       "domain and ledger surface",
        "owner": "the domain and ledger owner",
        "nextStep": "record the decision where an intent is acted on, keeping "
                    "validation a read that appends nothing, so a refreshing view "
                    "does not grow the trail",
    },
    {
        "gap": "the event shape carries no run identity",
        "neededFor": "correlating a trail with the run that produced it",
        "whyNotLocal": "the event shape is the domain's",
        "owner": "the domain and ledger owner",
        "nextStep": "carry the run on the event; where none was supplied, null is "
                    "the honest value and an invented one is not",
    },
    {
        "gap": "the event shape carries no chain position",
        "neededFor": "the transfer-observation and reorganisation audit groups",
        "whyNotLocal": "a chain position comes from a real chain, and the event "
                       "shape is the domain's",
        "owner": "the domain and ledger owner, for the shape; the deployment "
                 "owner, for the observation itself",
        "nextStep": "carry chainId, txHash, blockHash and logIndex, and refuse an "
                    "incomplete position rather than recording a partial one that "
                    "reads like an observation",
    },
    {
        "gap": "the recorder accepts any kind string",
        "neededFor": "a vocabulary a reader can rely on",
        "whyNotLocal": "the check belongs at the point of recording",
        "owner": "the domain and ledger owner",
        "nextStep": "refuse an undeclared kind where it is recorded; until then a "
                    "typo becomes a new kind and this conformance check is the "
                    "only thing that notices",
    },
)


def domain_recorded_kinds(root="."):
    """The kinds the domain's own source records, read from the source.

    A source read, not a run: a kind that only a rare path records still counts,
    which is the point - coverage of a run is a different question from what the
    vocabulary has to account for.
    """
    path = pathlib.Path(root) / LEDGER_SOURCE
    if not path.is_file():
        return {"source": LEDGER_SOURCE, "readable": False, "kinds": [],
                "error": "EX_LEDGER_SOURCE_UNREADABLE"}
    found = sorted(set(RECORD_CALL.findall(path.read_text(encoding="utf-8"))))
    return {"source": LEDGER_SOURCE, "readable": True, "kinds": found,
            "kindCount": len(found), "error": None}


def conformance(root="."):
    """Whether the declared vocabulary and the domain's own kinds agree.

    Two findings, kept apart because they mean different things. A kind the
    domain records and this contract does not declare is a vocabulary gap: the
    trail carries something unaccounted for. A kind the contract declares and
    the domain does not record is an interface gap: an audit group that cannot
    be evidenced until someone records it. Chain-only kinds are neither; they
    are listed separately because no local recorder could satisfy them.
    """
    recorded = domain_recorded_kinds(root)
    chain_only = {entry["kind"] for entry in CHAIN_ONLY_KINDS}
    declared = set(DECLARED_KINDS)
    undeclared = sorted(set(recorded["kinds"]) - declared)
    unrecorded = sorted(declared - chain_only - set(recorded["kinds"]))
    return {
        "schema": "8415ex-event-conformance/1",
        "prdVersion": "1.3",
        "domain": recorded,
        "declaredKinds": list(DECLARED_KINDS),
        "declaredKindCount": len(DECLARED_KINDS),
        "chainOnlyKinds": [dict(entry) for entry in CHAIN_ONLY_KINDS],
        "undeclaredKindsRecorded": undeclared,
        "declaredKindsNotRecorded": unrecorded,
        "retiredPhysicalKindsRecorded": sorted(set(recorded["kinds"]) & set(RETIRED_PHYSICAL_KINDS)),
        "requiredUnmappedAuditGroups": [group["group"] for group in AUDIT_GROUPS
                                       if group["evidence"] == "interface-gap"],
        "accountedFor": recorded["readable"] and not undeclared,
        "interfaceGaps": [dict(entry) for entry in INTERFACE_GAPS],
        "interfaceGapCount": len(INTERFACE_GAPS),
        "isNot": [
            "not an enforcement point: the recorder still accepts any kind, and "
            "this check is what notices",
        ],
    }


def derive_correlation(event, run_id=None, asset_key=None):
    """One event's correlation block, derived from the event as it stands.

    Every key is present. A key the domain does not carry is null, because an
    absent key and an unknown value read the same to a consumer and are not the
    same thing, and ``carriedByDomain`` says which keys were really on the event
    rather than resolved or supplied here.
    """
    detail = event.get("detail") or {}
    block = {
        "receiptId": event.get("receiptId"),
        "assetKey": list(asset_key) if asset_key is not None else None,
        "transferId": detail.get("transferId"),
        "requestId": detail.get("requestId"),
        "runId": run_id,
        "chainId": None,
        "txHash": None,
        "blockHash": None,
        "logIndex": None,
    }
    return {
        "derived": True,
        "correlation": block,
        "carriedByDomain": sorted(key for key in ("receiptId", "transferId", "requestId")
                                  if block[key] is not None),
        "resolvedHere": sorted(key for key in ("assetKey", "runId")
                               if block[key] is not None),
        "missing": sorted(key for key in CORRELATION_KEYS + CHAIN_KEYS
                          if block[key] is None),
        "observedOnChain": False,
        "whyNotObserved": "the domain's event shape carries no chain position",
        "sources": dict(CORRELATION_SOURCES),
    }


def event_identity(event, run_id=None, asset_key=None):
    """What makes two records the same event rather than two events.

    Taken from the kind, the sequence and the correlation, never from the
    free-form detail: two deliveries of one event that differ only in a detail
    are still one event, and a consumer treating them as two would double-count.
    """
    return digest({"kind": event["kind"], "sequence": event["sequence"],
                   "correlation": derive_correlation(event, run_id,
                                                     asset_key)["correlation"]})


def _final_prefix_from(timeline):
    """The confirmed prefix, derived from the results that carry it."""
    derived = None
    for event in timeline:
        if event["kind"] in ("registration-result", "registration-result-drained"):
            carried = (event.get("detail") or {}).get("holderIndex")
            if isinstance(carried, int) and not isinstance(carried, bool):
                derived = carried
    return derived


def coverage(timeline):
    """Which audit groups this timeline evidenced, and on what terms.

    A group evidenced by a derivation is reported as derived, never as recorded.
    A group that needs a chain observation is named with its reason rather than
    counted, because a locally produced record is not an observation.
    """
    counts = {}
    for event in timeline:
        counts[event["kind"]] = counts.get(event["kind"], 0) + 1
    chain_only = {entry["kind"]: entry["why"] for entry in CHAIN_ONLY_KINDS}
    groups = []
    for group in AUDIT_GROUPS:
        local = [kind for kind in group["kinds"] if kind not in chain_only]
        needs_chain = sorted(kind for kind in group["kinds"] if kind in chain_only)
        seen = {kind: counts.get(kind, 0) for kind in group["kinds"]}
        derived_prefix = (_final_prefix_from(timeline)
                          if group["evidence"] == "derived" else None)
        any_observed = any(seen.values()) or derived_prefix is not None
        all_local = bool(local) and all(seen[kind] for kind in local)
        # One status per group, so the buckets below cannot overlap. A group
        # with a chain-only kind is awaiting that observation however complete
        # its local half is: calling it recorded would be the exact conflation
        # this report exists to prevent.
        if group["evidence"] == "interface-gap":
            status = "not-recorded-interface-gap"
        elif needs_chain:
            status = "awaiting-chain-observation"
        elif group["evidence"] == "derived":
            status = "derived" if any_observed else "not-observed"
        elif all_local:
            status = "recorded"
        elif any_observed:
            status = "partly-recorded"
        else:
            status = "not-observed"
        groups.append({
            "group": group["group"],
            "requires": group["requires"],
            "evidence": group["evidence"],
            "status": status,
            "declaredKinds": list(group["kinds"]),
            "locallyRecordableKinds": local,
            "kindsNeedingAChain": needs_chain,
            "observedCounts": seen,
            "observedKinds": sorted(kind for kind, count in seen.items() if count),
            "anyObserved": any_observed,
            "allLocallyObserved": all_local,
            "localHalfObserved": all_local if local else None,
            "derivedValue": derived_prefix,
            "derivedFrom": list(group.get("derivedFrom", ())),
            "derivedBy": group.get("derivedBy"),
            "whyNotLocal": group.get("whyNotLocal") or
                           "; ".join(chain_only[kind] for kind in needs_chain) or None,
        })
    undeclared = sorted(set(counts) - set(DECLARED_KINDS) - set(RETIRED_PHYSICAL_KINDS))
    return {
        "schema": "8415ex-event-coverage/2",
        "groups": groups,
        "groupCount": len(groups),
        "byStatus": {name: sorted(entry["group"] for entry in groups
                                  if entry["status"] == name)
                     for name in sorted({entry["status"] for entry in groups})},
        "recordedGroups": sorted(entry["group"] for entry in groups
                                 if entry["status"] == "recorded"),
        "derivedGroups": sorted(entry["group"] for entry in groups
                                if entry["status"] == "derived"),
        "partlyRecordedGroups": sorted(entry["group"] for entry in groups
                                       if entry["status"] == "partly-recorded"),
        "notObserved": sorted(entry["group"] for entry in groups
                              if entry["status"] == "not-observed"),
        "groupsAwaitingChainObservation": sorted(
            entry["group"] for entry in groups
            if entry["status"] == "awaiting-chain-observation"),
        "statusesAreExclusive": True,
        "undeclaredKindsObserved": undeclared,
        "retiredPhysicalKindsObserved": sorted(set(counts) & set(RETIRED_PHYSICAL_KINDS)),
        "eventCount": len(timeline),
        "isNot": [
            "not a chain observation: a locally produced record is never evidence "
            "that a transaction or a reorganisation was seen on a chain",
            "not an acceptance result: coverage says an audit group was recorded, "
            "never that the behaviour it records is correct",
            "not a derivation presented as a record: a derived group says so",
            "not a complete group where only its local half was recorded: a "
            "group awaiting a chain observation says that instead",
        ],
    }


def replay(timeline, run_id=None, asset_key=None):
    """Rebuild the index from the events, refusing to move anything twice.

    Events are consumed in recorded order. A repeat of an event already consumed
    is counted as a duplicate and changes nothing, which is the rule that
    matters: re-consuming must not move an asset or money again.
    """
    state = {
        "schema": "8415ex-event-replay/2",
        "consumed": 0,
        "duplicatesIgnored": 0,
        "kindCounts": {},
        "assetMovements": [],
        "fundMovements": [],
        "attemptsThatMovedNothing": [],
        "undeclaredKinds": [],
        "retiredPhysicalKinds": [],
        "finalPrefix": None,
        "byTransfer": {},
        "byRequest": {},
        "correlationGaps": {},
        "outOfOrder": [],
    }
    seen = set()
    highest = -1
    for event in timeline:
        kind = event["kind"]
        identity = event_identity(event, run_id, asset_key)
        if identity in seen:
            state["duplicatesIgnored"] += 1
            continue
        seen.add(identity)
        if kind in RETIRED_PHYSICAL_KINDS:
            state["retiredPhysicalKinds"].append({"kind": kind, "sequence": event["sequence"],
                                                   "executable": False})
        elif kind not in DECLARED_KINDS:
            # Reported, not refused: this layer reads a trail it does not write,
            # and refusing would make an unaccounted kind look like a crash.
            state["undeclaredKinds"].append({"kind": kind,
                                             "sequence": event["sequence"]})
        if event["sequence"] < highest:
            state["outOfOrder"].append(event["sequence"])
        highest = max(highest, event["sequence"])
        state["consumed"] += 1
        state["kindCounts"][kind] = state["kindCounts"].get(kind, 0) + 1
        moves = MOVEMENT_KINDS.get(kind) or HISTORICAL_MOVEMENT_KINDS.get(kind)
        rule = CONDITIONAL_MOVEMENT_KINDS.get(kind)
        if rule is not None:
            observed = (event.get("detail") or {}).get(rule["key"])
            if observed == rule["movedWhen"]:
                moves = rule["moves"]
            else:
                state["attemptsThatMovedNothing"].append(
                    {"kind": kind, "sequence": event["sequence"],
                     rule["key"]: observed})
        if moves is not None:
            state["%sMovements" % moves].append({"kind": kind,
                                                 "sequence": event["sequence"],
                                                 "identity": identity})
        link = derive_correlation(event, run_id, asset_key)["correlation"]
        for key, bucket in (("transferId", "byTransfer"), ("requestId", "byRequest")):
            if link.get(key) is not None:
                state[bucket].setdefault(link[key], []).append(event["sequence"])
        for key in CORRELATION_KEYS:
            if link.get(key) is None:
                state["correlationGaps"][key] = state["correlationGaps"].get(key, 0) + 1
    state["finalPrefix"] = _final_prefix_from(timeline)
    state["assetMovementCount"] = len(state["assetMovements"])
    state["fundMovementCount"] = len(state["fundMovements"])
    state["attemptsThatMovedNothingCount"] = len(state["attemptsThatMovedNothing"])
    state["undeclaredKindCount"] = len(state["undeclaredKinds"])
    state["sequential"] = state["outOfOrder"] == []
    state["digest"] = digest({
        "kindCounts": state["kindCounts"],
        "assetMovements": state["assetMovements"],
        "fundMovements": state["fundMovements"],
        "attemptsThatMovedNothing": state["attemptsThatMovedNothing"],
        "finalPrefix": state["finalPrefix"],
        "byTransfer": state["byTransfer"],
        "byRequest": state["byRequest"],
    })
    return state


def rebuilt_identically(timeline, run_id=None, asset_key=None):
    """Whether one replay and a doubled replay of the same events agree."""
    once = replay(timeline, run_id, asset_key)
    twice = replay(list(timeline) + list(timeline), run_id, asset_key)
    return {
        "schema": "8415ex-event-rebuild/2",
        "digest": once["digest"],
        "repeatedDigest": twice["digest"],
        "identical": once["digest"] == twice["digest"],
        "consumed": once["consumed"],
        "duplicatesIgnoredOnRepeat": twice["duplicatesIgnored"],
        "assetMovementsOnce": once["assetMovementCount"],
        "assetMovementsOnRepeat": twice["assetMovementCount"],
        "fundMovementsOnce": once["fundMovementCount"],
        "fundMovementsOnRepeat": twice["fundMovementCount"],
        "meaning": ("repeated consumption of the same events rebuilds the same "
                    "index and moves no asset or money a second time"),
    }


def contract():
    """The declared contract, readable without a run."""
    return {
        "schema": "8415ex-event-contract/2",
        "groups": [dict(group, kinds=list(group["kinds"]),
                        derivedFrom=list(group.get("derivedFrom", ())))
                   for group in AUDIT_GROUPS],
        "ancillaryKinds": [dict(entry) for entry in ANCILLARY_KINDS],
        "prdVersion": "1.3",
        "retiredPhysicalKinds": list(RETIRED_PHYSICAL_KINDS),
        "chainOnlyKinds": [dict(entry) for entry in CHAIN_ONLY_KINDS],
        "declaredKinds": list(DECLARED_KINDS),
        "declaredKindCount": len(DECLARED_KINDS),
        "movementKinds": dict(MOVEMENT_KINDS),
        "conditionalMovementKinds": {kind: dict(rule) for kind, rule
                                     in CONDITIONAL_MOVEMENT_KINDS.items()},
        "correlationKeys": list(CORRELATION_KEYS),
        "chainKeys": list(CHAIN_KEYS),
        "correlationSources": dict(CORRELATION_SOURCES),
        "readOnly": True,
        "whyReadOnly": ("the recorder and the event shape are the domain and "
                        "ledger surface, which this task does not own; what "
                        "cannot be read is reported as an interface gap with its "
                        "owner"),
        "nullMeans": ("not known for this event; an absent key and an unknown "
                      "value must not read the same"),
        "isNot": [
            "not a standard event signature: these are logical names mapped onto "
            "what the domain already records, not an ABI or a published standard",
        ],
        "contractDigest": digest({
            "groups": [[group["group"], list(group["kinds"]), group["evidence"]]
                       for group in AUDIT_GROUPS],
            "kinds": list(DECLARED_KINDS),
            "retiredPhysicalKinds": list(RETIRED_PHYSICAL_KINDS),
            "movement": MOVEMENT_KINDS,
            "conditional": CONDITIONAL_MOVEMENT_KINDS,
            "correlation": list(CORRELATION_KEYS),
            "chain": list(CHAIN_KEYS),
        }),
    }


def demonstration_timeline():
    """One local timeline to read, built from the domain's own fixtures.

    This exists so the coverage and replay halves can be shown without a
    deployment. It is a local model run and evidences nothing about a chain.
    """
    from exchange import fixtures as F

    exchange, _ = F.funded_chain_to_d()
    requests = F.submit_all(exchange)
    for position in (0, 1):
        F.confirm(exchange, requests[position], "res-%d" % position)
    exchange.release_segment("rcpt-8415-0001", 0,
                             F.release_authority(exchange, 0, "rel-0"))
    return exchange, "rcpt-8415-0001"


def build(exchange=None, receipt_id=None, root=".", run_id=None):
    """The contract, its conformance against the domain, and a run's coverage.

    With no exchange this is the contract and its conformance only: a reviewer
    reading the declaration does not need a run. With one, the timeline is read
    and the coverage and replay are reported beside it.
    """
    report = {
        "schema": "8415ex-event-report/1",
        "contract": contract(),
        "conformance": conformance(root),
        "timelineRead": False,
        "coverage": None,
        "replay": None,
        "rebuild": None,
    }
    if exchange is None or receipt_id is None:
        return report
    timeline = list(exchange.receipt_timeline(receipt_id))
    asset_key = exchange.receipt(receipt_id).asset.key
    report["timelineRead"] = True
    report["receiptId"] = receipt_id
    report["coverage"] = coverage(timeline)
    report["replay"] = replay(timeline, run_id, asset_key)
    report["rebuild"] = rebuilt_identically(timeline, run_id, asset_key)
    return report

