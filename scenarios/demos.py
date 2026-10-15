"""The six confirmed local scenarios, DEMO-01 to DEMO-06.

Each runner drives the existing domain API with labelled synthetic fixtures and
records the initial receipt and accounts, the deterministic prices and gas
conditions, every step, the expected and observed owner and holder, the
registration prefix, each segment's funds, the rollback and exit state, and any
failure detail.

A runner never changes domain behaviour to make itself pass, and it never
invents an ordering the requirements leave open: where a branch is undecided the
runner records what the implementation reports about it instead.

Each scenario names one selected main registrar path. The three paths are
covered across the six scenarios and separately by the path contract tests in
``scenarios.paths``; success on one path never stands in for another.
"""
from exchange import fixtures as F
from exchange.exit import exit_step_key

from .harness import Scenario

RECEIPT = "rcpt-8415-0001"

#: The selected main path per scenario. All three are exercised, without
#: multiplying every scenario by every path.
MAIN_PATHS = {
    "DEMO-01": "REG_DIRECT",
    "DEMO-02": "REG_ELECTRONIC",
    "DEMO-03": "REG_INTERMEDIARY",
    "DEMO-04": "REG_DIRECT",
    "DEMO-05": "REG_ELECTRONIC",
    "DEMO-06": "REG_INTERMEDIARY",
}

#: Deterministic fixture prices, in the smallest unit of a local test label.
#: They are reproducible inputs, not a commercial quotation.
PRICES = {"AB": F.PRICE_AB, "BC": F.PRICE_BC, "CD": F.PRICE_CD}

#: Deterministic fixture gas amounts. These exercise responsibility and the
#: refusal of a double charge. They are not an approved fee mechanism.
GAS = {"trade": 21_000, "refund": 23_000, "shared-return": 48_000}

#: Gas is counted in gas units. It is never the quote asset, so a gas figure and a
#: principal are never added to or subtracted from one another.
GAS_UNIT = "gas-units"


def _accounts():
    return {"A": F.A, "B": F.B, "C": F.C, "D": F.D}


def _setup(recorder, exchange, prices, gas_conditions, extra=None):
    receipt = exchange.receipt(RECEIPT)
    recorder.describe_setup(
        receipt={"receiptId": receipt.receipt_id, "receiptNumber": receipt.receipt_number,
                 "commodity": receipt.commodity_name, "commodityQuantity": receipt.commodity_quantity,
                 "tradeableUnits": receipt.tradeable_units, "chainId": receipt.asset.chain_id,
                 "contract": receipt.asset.contract, "tokenId": receipt.asset.token_id,
                 "registrationPath": receipt.registration_path,
                 "tradeStopAt": receipt.trade_stop_at, "origin": receipt.origin_account},
        accounts=_accounts(), prices=prices, gasConditions=gas_conditions,
        quoteAsset=F.QUOTE_ASSET,
        simulatedAdapters={"registrar": exchange.registrars[receipt.registration_path].label,
                           "payment": "SimulatedPaymentAdapter",
                           "assetControl": "SimulatedAssetControl" if exchange.asset_control else None,
                           "voucherDesk": exchange.voucher_desk.label if exchange.voucher_desk else None},
        **(extra or {}))


def _positions(exchange):
    view = exchange.receipt_view(RECEIPT)
    return {"owner": view["owner"]["account"], "ownerPosition": view["owner"]["position"],
            "holder": view["holder"]["account"], "holderPosition": view["holder"]["position"],
            "registeredPrefixLegs": view["registeredPrefixLegs"],
            "outstandingLegs": view["outstandingLegs"]}


def _segment_funds(exchange):
    report = exchange.reconciliation(RECEIPT)
    return {segment["legIndex"]: {"principal": segment["principal"],
                                  "escrowStatus": segment["escrowStatus"],
                                  "paymentStatus": segment["paymentStatus"],
                                  "released": segment["released"],
                                  "refunded": segment["refunded"],
                                  "netToPayee": segment["netToPayee"],
                                  "netToPayer": segment["netToPayer"],
                                  "gasTotal": segment["gasTotal"],
                                  "gasBorneBy": segment["gasBorneBy"],
                                  "rollbackStatus": segment["rollbackStatus"]}
            for segment in report["segments"]}


def _record_common(recorder, exchange, expected_positions, cases):
    observed = _positions(exchange)
    recorder.expect("owner and holder positions", cases,
                    expected_positions, {key: observed[key] for key in expected_positions})
    return observed


def _not_run_chain(recorder):
    recorder.not_run("public test network execution", ("T-35", "T-36", "T-38"),
                     "Codex owns deployment and authorized Sepolia execution; this run sends "
                     "no transaction and has no verified token address")
    recorder.not_run("operable UI acceptance", ("T-36",),
                     "a rendered status page is development evidence; a real browser journey "
                     "on a deployed build is required")


# ---------------------------------------------------------------- DEMO-01

def demo_01(recorder):
    """A to B succeeds, the segment releases, then an eligible B exits."""
    path = MAIN_PATHS["DEMO-01"]
    exchange, clock = F.exit_exchange(registration_path=path)
    _setup(recorder, exchange, {"AB": PRICES["AB"]}, {"trade": GAS["trade"]})
    recorder.step("initial state", **_positions(exchange))
    recorder.expect("origin is both owner and holder", ("T-02",),
                    {"owner": F.A, "holder": F.A, "ownerPosition": 0, "holderPosition": 0},
                    {key: _positions(exchange)[key]
                     for key in ("owner", "holder", "ownerPosition", "holderPosition")})

    escrow, leg = F.funded_hop(exchange, F.A, F.B, 1, "transfer-ab", "session-a", "session-b",
                               price=PRICES["AB"])
    recorder.step("A to B funded and executed", escrowId=escrow.escrow_id,
                  escrowStatus=escrow.status, legIndex=leg.leg_index,
                  fundingStatus=leg.funding_status, **_positions(exchange))
    recorder.expect("the buyer funded its own segment before the trade formed", ("T-11",),
                    {"payer": F.B, "payee": F.A, "principal": PRICES["AB"], "status": "locked"},
                    {"payer": escrow.payer, "payee": escrow.payee,
                     "principal": escrow.principal, "status": escrow.status})

    request, _ = exchange.submit_registration(RECEIPT, 0, "req-leg-0", 86_400)
    F.confirm(exchange, request, "res-ab")
    recorder.step("registration confirmed", requestId=request.request_id, **_positions(exchange))

    exchange.record_gas(RECEIPT, 0, "trade", GAS["trade"])
    outcome = exchange.release_segment(RECEIPT, 0, F.release_authority(exchange, 0, "auth-0"))
    recorder.step("segment released", released=outcome["released"],
                  paymentStatus=outcome["paymentStatus"], payee=outcome["payee"],
                  **_positions(exchange))
    recorder.expect("the segment released to its own seller", ("T-11", "T-12"),
                    {"released": True, "payee": F.A, "principal": PRICES["AB"]},
                    {"released": outcome["released"], "payee": outcome["payee"],
                     "principal": outcome["principal"]})
    _record_common(recorder, exchange, {"owner": F.B, "holder": F.B, "ownerPosition": 1,
                                        "holderPosition": 1, "registeredPrefixLegs": 1,
                                        "outstandingLegs": 0}, ("T-02",))
    recorder.expect("segment funds", ("T-11", "T-31"),
                    {"escrowStatus": "released", "released": True, "refunded": False,
                     "netToPayee": str(PRICES["AB"]), "gasBorneBy": F.B},
                    {key: _segment_funds(exchange)[0][key]
                     for key in ("escrowStatus", "released", "refunded", "netToPayee", "gasBorneBy")})

    F.redeem_authorization(exchange)
    eligibility = exchange.exit_eligibility(RECEIPT, F.B, "auth-redeem", F.ALL_CHECKS)
    recorder.expect("an eligible rights holder may request the exit", ("T-25",),
                    {"eligible": True, "ownerEqualsHolder": True},
                    {"eligible": eligibility["eligible"],
                     "ownerEqualsHolder": eligibility["ownerEqualsHolder"]},
                    detail=",".join(eligibility["reasons"]) or None)
    short = exchange.exit_eligibility(RECEIPT, F.B, "auth-redeem", ())
    recorder.expect("agreement alone is not sufficient", ("T-25",),
                    {"eligible": False, "ownerEqualsHolder": True},
                    {"eligible": short["eligible"], "ownerEqualsHolder": short["ownerEqualsHolder"]})

    exchange.request_redemption(RECEIPT, F.B, "auth-redeem", "rdm-1", F.ALL_CHECKS)
    # One step per call with the clock advanced between them, so the record shows
    # four distinct completion instants rather than one batched moment.
    report = None
    for step_name, gap in (("stop-resale", 5), ("voucher-issued", 30),
                           ("voucher-handover-confirmed", 600), ("burn", 120)):
        clock.advance(gap)
        report = exchange.advance_exit(RECEIPT, through=step_name)
        recorder.step(f"exit step {step_name}", status=next(
            entry["status"] for entry in report["steps"] if entry["step"] == step_name),
            completedAt=next(entry["completedAt"] for entry in report["steps"]
                             if entry["step"] == step_name))
    recorder.step("exit completed", state=report["state"], burned=report["burned"],
                  instants=report["distinctCompletionInstants"])
    recorder.expect("each exit step has its own record and instant", ("T-32",),
                    {"stepCount": 4, "allDone": True, "distinctInstants": 4},
                    {"stepCount": len(report["steps"]),
                     "allDone": all(step["status"] == "done" for step in report["steps"]),
                     "distinctInstants": len(report["distinctCompletionInstants"])})
    recorder.expect("the voucher hand-over and the burn are not atomic", ("T-32",),
                    {"atomic": False, "instantsDiffer": True},
                    {"atomic": report["physicalAndOnChainAreAtomic"],
                     "instantsDiffer": report["completionInstantsDiffer"]})
    second = exchange.exit_eligibility(RECEIPT, F.B, "auth-redeem", F.ALL_CHECKS)
    recorder.expect("a second redemption is refused", ("T-33",),
                    {"eligible": False, "alreadyRequested": True},
                    {"eligible": second["eligible"],
                     "alreadyRequested": "EX_REDEMPTION_ALREADY_REQUESTED" in second["reasons"]})
    kinds = [entry["kind"] for entry in exchange.receipt_timeline(RECEIPT)]
    burned = next(e for e in exchange.receipt_timeline(RECEIPT) if e["kind"] == "receipt-burned")
    recorder.expect("history is preserved after the burn", ("T-33",),
                    {"minted": True, "transfer": True, "release": True, "burn": True,
                     "assetLink": "retained", "registrationOrder": "retained",
                     "fundsRecord": "retained", "collectionRecord": "retained"},
                    {"minted": "receipt-minted" in kinds,
                     "transfer": "transfer-executed" in kinds,
                     "release": "segment-release-attempt" in kinds,
                     "burn": "receipt-burned" in kinds,
                     "assetLink": burned["detail"]["assetLink"],
                     "registrationOrder": burned["detail"]["registrationOrder"],
                     "fundsRecord": burned["detail"]["fundsRecord"],
                     "collectionRecord": burned["detail"]["collectionRecord"]})
    recorder.expect("the registrar and desk are labelled simulated", ("T-10", "T-26"),
                    {"registrarSimulated": True, "deskSimulated": True},
                    {"registrarSimulated": exchange.registrars[path].simulated,
                     "deskSimulated": exchange.voucher_desk.simulated})
    recorder.note("payment movements: " + str(exchange.payments.movements))
    _not_run_chain(recorder)


# ---------------------------------------------------------------- DEMO-02

def demo_02(recorder):
    """A to B to C to D, with serial registration and per-segment release."""
    path = MAIN_PATHS["DEMO-02"]
    exchange, _ = F.funded_chain_to_d(registration_path=path)
    _setup(recorder, exchange, dict(PRICES), {"trade": GAS["trade"]})
    recorder.expect("the owner ran ahead while the holder is still the origin", ("T-03",),
                    {"owner": F.D, "ownerPosition": 3, "holder": F.A, "holderPosition": 0},
                    {key: _positions(exchange)[key]
                     for key in ("owner", "ownerPosition", "holder", "holderPosition")})
    legs = exchange.legs(RECEIPT)
    recorder.step("three legs recorded", legs=[(leg.leg_index, leg.seller, leg.buyer) for leg in legs])
    recorder.expect("each hop is recorded in order with its own predecessor", ("T-03",),
                    [(0, F.A, F.B, None), (1, F.B, F.C, "transfer-ab"), (2, F.C, F.D, "transfer-bc")],
                    [(leg.leg_index, leg.seller, leg.buyer, leg.predecessor_transfer_id)
                     for leg in legs])

    requests = F.submit_all(exchange)
    recorder.expect("each hop files its own registration request", ("T-03",),
                    {"requests": 3, "distinct": 3},
                    {"requests": len(requests),
                     "distinct": len({request.request_id for request in requests})})

    _, deferred = F.confirm(exchange, requests[2], "res-cd-early")
    recorder.step("the CD result arrives first", disposition=deferred["disposition"],
                  deferredLegs=deferred.get("deferredLegs"), **_positions(exchange))
    recorder.expect("a later result waits for the gap and is not a refusal", ("T-04",),
                    {"disposition": "deferred", "holderPosition": 0, "rejectedLegs": ()},
                    {"disposition": deferred["disposition"],
                     "holderPosition": exchange.holder_index(RECEIPT),
                     "rejectedLegs": exchange.receipt_view(RECEIPT)["rejectedLegs"]})

    _, advanced = F.confirm(exchange, requests[0], "res-ab")
    recorder.step("AB confirmed", disposition=advanced["disposition"], **_positions(exchange))
    release_ab = exchange.release_segment(RECEIPT, 0, F.release_authority(exchange, 0, "auth-0"))
    recorder.step("AB released before the holder reached D", released=release_ab["released"],
                  **_positions(exchange))
    recorder.expect("AB releases without waiting for C or D", ("T-12",),
                    {"released": True, "principal": PRICES["AB"], "payee": F.A,
                     "holderPosition": 1, "ownerPosition": 3},
                    {"released": release_ab["released"], "principal": release_ab["principal"],
                     "payee": release_ab["payee"], "holderPosition": exchange.holder_index(RECEIPT),
                     "ownerPosition": exchange.owner_index(RECEIPT)})
    funds = _segment_funds(exchange)
    recorder.expect("the later segments stay locked while AB is released", ("T-12", "T-13"),
                    {1: "locked", 2: "locked"},
                    {1: funds[1]["escrowStatus"], 2: funds[2]["escrowStatus"]})
    recorder.expect("AB's rollback capability is gone for good", ("T-12",),
                    {"legZero": "detached"}, {"legZero": funds[0]["rollbackStatus"]})

    _, bc = F.confirm(exchange, requests[1], "res-bc")
    recorder.step("BC confirmed, draining the buffered CD result",
                  disposition=bc["disposition"], **_positions(exchange))
    recorder.expect("filling the gap drains the buffer in order", ("T-04",),
                    {"holderPosition": 3, "holder": F.D, "deferredLegs": ()},
                    {"holderPosition": exchange.holder_index(RECEIPT),
                     "holder": exchange.holder_of(RECEIPT),
                     "deferredLegs": exchange.deferred_legs(RECEIPT)})

    for leg_index, authority in ((1, "auth-1"), (2, "auth-2")):
        outcome = exchange.release_segment(RECEIPT, leg_index,
                                           F.release_authority(exchange, leg_index, authority))
        recorder.step(f"segment {leg_index} released independently",
                      released=outcome["released"], principal=outcome["principal"],
                      payee=outcome["payee"])
    funds = _segment_funds(exchange)
    recorder.expect("every segment released its own principal to its own seller", ("T-13",),
                    {0: (str(PRICES["AB"]), F.A), 1: (str(PRICES["BC"]), F.B),
                     2: (str(PRICES["CD"]), F.C)},
                    {index: (funds[index]["principal"], exchange.leg(RECEIPT, index).seller)
                     for index in (0, 1, 2)})
    recorder.expect("the three principals never merged", ("T-13",),
                    3, len({funds[index]["principal"] for index in (0, 1, 2)}))
    recorder.expect("one payment movement per segment", ("T-13", "T-28"),
                    3, exchange.payments.movements)
    _not_run_chain(recorder)


# ---------------------------------------------------------------- DEMO-03

def demo_03(recorder):
    """B is refused with owner D and holder A: the whole suffix returns to A."""
    path = MAIN_PATHS["DEMO-03"]
    exchange, _ = F.rollback_chain_to_d(registration_path=path)
    _setup(recorder, exchange, dict(PRICES),
           {"trade": GAS["trade"], "refund": GAS["refund"]})
    requests = F.submit_all(exchange)
    for leg_index in (0, 1, 2):
        exchange.record_gas(RECEIPT, leg_index, "trade", GAS["trade"])
    F.refuse(exchange, requests[0], "res-ab-refused")
    recorder.step("the registrar refused the first hop", **_positions(exchange),
                  rejectedLegs=exchange.receipt_view(RECEIPT)["rejectedLegs"])
    recorder.expect("the state before the rollback is owner D and holder A", ("T-17",),
                    {"owner": F.D, "ownerPosition": 3, "holder": F.A, "holderPosition": 0},
                    {key: _positions(exchange)[key]
                     for key in ("owner", "ownerPosition", "holder", "holderPosition")})

    exchange.begin_rollback(RECEIPT, 0, F.rollback_authority(exchange, 0, "rb-1"))
    report = exchange.advance_rollback(RECEIPT)
    recorder.step("rollback advanced", state=report["state"], complete=report["complete"],
                  segmentFunds=_segment_funds(exchange),
                  affectedLegs=report["affectedLegs"], boundary=report["returnBoundaryAccount"],
                  **_positions(exchange))
    recorder.expect("every unfinished segment is in the interval", ("T-17",),
                    (0, 1, 2), report["affectedLegs"])
    recorder.expect("the receipt returns to the origin", ("T-17",),
                    {"boundary": F.A, "owner": F.A, "ownerPosition": 0, "returned": True},
                    {"boundary": report["returnBoundaryAccount"],
                     "owner": exchange.owner_of(RECEIPT),
                     "ownerPosition": exchange.owner_index(RECEIPT),
                     "returned": report["assetControl"]["returned"]})
    recorder.expect("each buyer receives its own unreleased funds", ("T-19",),
                    {0: (F.B, True), 1: (F.C, True), 2: (F.D, True)},
                    {entry["legIndex"]: (entry["originalBuyer"], entry["refundedToOriginalBuyer"])
                     for entry in report["funds"]})
    # Principal and gas are two different obligations in two different units.
    # The refund returns the whole principal in the quote asset; the gas figure
    # is a fixture count of gas units borne by that leg's buyer. Subtracting one
    # from the other would state a net in no unit at all, and whether a fee is
    # deducted from a refund at all is open decision D-04.
    funds = _segment_funds(exchange)
    recorder.expect("each refund returns the whole principal in the quote asset", ("T-19",),
                    {0: (str(PRICES["AB"]), F.QUOTE_ASSET, True),
                     1: (str(PRICES["BC"]), F.QUOTE_ASSET, True),
                     2: (str(PRICES["CD"]), F.QUOTE_ASSET, True)},
                    {segment["legIndex"]: (segment["netToPayer"], segment["quoteAsset"],
                                           segment["netToPayer"] == segment["principal"])
                     for segment in exchange.reconciliation(RECEIPT)["segments"]})
    recorder.expect("gas is recorded on its own, in gas units, by bearer", ("T-19", "T-21"),
                    {0: (str(GAS["trade"]), "gas-units", F.B),
                     1: (str(GAS["trade"]), "gas-units", F.C),
                     2: (str(GAS["trade"]), "gas-units", F.D)},
                    {index: (funds[index]["gasTotal"], GAS_UNIT, funds[index]["gasBorneBy"])
                     for index in (0, 1, 2)})
    recorder.expect("no quoted principal is reduced by a gas figure", ("T-19", "T-21"),
                    {0: str(PRICES["AB"]), 1: str(PRICES["BC"]), 2: str(PRICES["CD"])},
                    {index: funds[index]["principal"] for index in (0, 1, 2)})
    recorder.not_run("actual fee deduction from a refunded principal", ("T-19", "T-21"),
                     "D-04 is open: whether a real fee is deducted from a refund, in which "
                     "asset, and who bears it, is not decided, so no deduction is modelled "
                     "and no net across the two units is asserted here")
    recorder.note("the legacy rollback report also carries netToOriginalBuyer, a figure "
                  "derived by subtracting a gas-unit count from a quote-asset principal. It "
                  f"is observed as {[entry['netToOriginalBuyer'] for entry in report['funds']]} "
                  "and is not read here as the amount returned to any buyer.")
    recorder.expect("the rollback is complete only with every step evidenced", ("T-17",),
                    {"state": "complete", "complete": True, "outstanding": 0},
                    {"state": report["state"], "complete": report["complete"],
                     "outstanding": len(report["outstandingSteps"])})
    recorder.expect("one refund movement per segment and one return", ("T-19",),
                    {"payments": 3, "returns": 1},
                    {"payments": exchange.payments.movements,
                     "returns": exchange.asset_control.returns})
    recorder.expect("history is preserved rather than erased", ("T-17",),
                    {"recordedLegs": 3, "historyPreserved": True},
                    {"recordedLegs": exchange.recorded_legs(RECEIPT),
                     "historyPreserved": report["assetControl"]["historyPreserved"]})

    try:
        exchange.record_gas(RECEIPT, 1, "shared-return", GAS["shared-return"], shared_with=(2,))
        exchange.record_gas(RECEIPT, 2, "shared-return", GAS["shared-return"], shared_with=(1,))
        double = "accepted"
    except Exception as refusal:  # the refusal is the expected behaviour
        double = getattr(refusal, "code", type(refusal).__name__)
    recorder.expect("a shared operation cannot be charged in full twice", ("T-21",),
                    "EX_GAS_DOUBLE_CHARGE_REFUSED", double)
    _not_run_chain(recorder)


# ---------------------------------------------------------------- DEMO-04

def demo_04(recorder):
    """AB is finalized and C is refused: only BC and CD unwind, back to B."""
    path = MAIN_PATHS["DEMO-04"]
    exchange, _ = F.rollback_chain_to_d(registration_path=path)
    _setup(recorder, exchange, dict(PRICES), {"trade": GAS["trade"]})
    requests = F.submit_all(exchange)
    F.confirm(exchange, requests[0], "res-ab")
    release_ab = exchange.release_segment(RECEIPT, 0, F.release_authority(exchange, 0, "auth-0"))
    recorder.step("AB finalized", released=release_ab["released"], payee=release_ab["payee"],
                  **_positions(exchange))
    F.refuse(exchange, requests[1], "res-bc-refused")
    recorder.step("the registrar refused the second hop",
                  rejectedLegs=exchange.receipt_view(RECEIPT)["rejectedLegs"], **_positions(exchange))

    exchange.begin_rollback(RECEIPT, 1, F.rollback_authority(exchange, 1, "rb-2"))
    report = exchange.advance_rollback(RECEIPT)
    recorder.step("rollback advanced", affectedLegs=report["affectedLegs"],
                  segmentFunds=_segment_funds(exchange),
                  boundary=report["returnBoundaryAccount"], complete=report["complete"],
                  **_positions(exchange))
    recorder.expect("only the later two segments unwind", ("T-18",),
                    (1, 2), report["affectedLegs"])
    recorder.expect("the receipt returns to B, not to the origin", ("T-18",),
                    {"boundary": F.B, "owner": F.B, "finalizedPrefixLegs": 1},
                    {"boundary": report["returnBoundaryAccount"],
                     "owner": exchange.owner_of(RECEIPT),
                     "finalizedPrefixLegs": report["finalizedPrefixLegs"]})
    funds = _segment_funds(exchange)
    recorder.expect("AB and the payment to A are unchanged", ("T-18", "T-29"),
                    {"escrowStatus": "released", "refunded": False,
                     "netToPayee": str(PRICES["AB"]), "rollbackStatus": "detached"},
                    {key: funds[0][key] for key in ("escrowStatus", "refunded", "netToPayee",
                                                    "rollbackStatus")})
    _record_common(recorder, exchange,
                   {"owner": F.B, "ownerPosition": 1, "holder": F.B, "holderPosition": 1,
                    "registeredPrefixLegs": 1, "outstandingLegs": 0}, ("T-18", "T-02"))
    recorder.expect("AB is not in the refund set", ("T-18",),
                    [1, 2], [entry["legIndex"] for entry in report["funds"]])
    recorder.expect("C and D receive their own unreleased funds", ("T-19",),
                    {1: (F.C, True), 2: (F.D, True)},
                    {entry["legIndex"]: (entry["originalBuyer"], entry["refundedToOriginalBuyer"])
                     for entry in report["funds"]})
    try:
        exchange.rollback_interval(RECEIPT, 0)
        prefix = "accepted"
    except Exception as refusal:
        prefix = getattr(refusal, "code", type(refusal).__name__)
    recorder.expect("a refusal inside the finalized prefix is refused", ("T-29",),
                    "EX_ROLLBACK_PREFIX_IMMUTABLE", prefix)
    recorder.expect("one release and two refunds, nothing more", ("T-29",),
                    3, exchange.payments.movements)
    _not_run_chain(recorder)


# ---------------------------------------------------------------- DEMO-05

def demo_05(recorder):
    """The intermediate ordinary wallets hold no gas budget."""
    path = MAIN_PATHS["DEMO-05"]
    exchange, _ = F.rollback_chain_to_d(registration_path=path,
                                        gas_budgets={F.B: 0, F.C: 0, F.D: 0})
    _setup(recorder, exchange, dict(PRICES),
           {"budgets": {"B": 0, "C": 0, "D": 0},
            "note": "a fixture ceiling used to exercise the shortfall path; not a fee mechanism"})
    requests = F.submit_all(exchange)
    F.refuse(exchange, requests[0], "res-ab-refused")
    exchange.begin_rollback(RECEIPT, 0, F.rollback_authority(exchange, 0, "rb-1"))
    first = exchange.advance_rollback(RECEIPT)
    recorder.step("rollback attempted with an exhausted budget", state=first["state"],
                  outstanding=[step["stepId"] for step in first["outstandingSteps"]],
                  **_positions(exchange))
    blocked = [step for step in first["outstandingSteps"] if step["status"] == "blocked"]
    recorder.expect("the shortfall blocks the return with a named reason", ("T-22",),
                    {"state": "blocked", "blockedSteps": 1, "kind": "asset-return",
                     "reason": "EX_GAS_BUDGET_EXHAUSTED"},
                    {"state": first["state"], "blockedSteps": len(blocked),
                     "kind": blocked[0]["kind"] if blocked else None,
                     "reason": blocked[0]["detail"].get("reason") if blocked else None})
    record = next(entry for entry in exchange.receipt_timeline(RECEIPT)
                  if entry["kind"] == "rollback-step-blocked")
    recorder.expect("no custody, forced sale or liquidation is used", ("T-22",),
                    {"custodyTaken": False, "forcedSale": False, "liquidation": False,
                     "resumable": True},
                    {key: record["detail"][key]
                     for key in ("custodyTaken", "forcedSale", "liquidation", "resumable")})
    recorder.expect("the refunds still reached their own buyers", ("T-20", "T-19"),
                    {0: True, 1: True, 2: True},
                    {entry["legIndex"]: entry["refundedToOriginalBuyer"]
                     for entry in first["funds"]})
    recorder.expect("the withdrawn mechanisms are reported unused", ("T-22",),
                    ("temporary-custody", "time-limited-redemption", "overdue-sale",
                     "instant-liquidation"),
                    first["withdrawnMechanismsNotUsed"])

    exchange._budgets[F.D] = 100_000
    second = exchange.advance_rollback(RECEIPT)
    recorder.step("rollback resumed once the budget allowed", state=second["state"],
                  complete=second["complete"], segmentFunds=_segment_funds(exchange),
                  **_positions(exchange))
    recorder.expect("the rollback resumes and completes", ("T-23",),
                    {"complete": True, "owner": F.A}, 
                    {"complete": second["complete"], "owner": exchange.owner_of(RECEIPT)})
    recorder.expect("nothing was repeated across the interruption", ("T-23",),
                    {"payments": 3, "returns": 1},
                    {"payments": exchange.payments.movements,
                     "returns": exchange.asset_control.returns})
    _record_common(recorder, exchange,
                   {"owner": F.A, "ownerPosition": 0, "holder": F.A, "holderPosition": 0,
                    "registeredPrefixLegs": 0, "outstandingLegs": 0}, ("T-23", "T-02"))
    returned = exchange.asset_control.lookup("return:rcpt-8415-0001:rb-1")
    recorder.expect("the return is one operation and needs no intermediate gas", ("T-20",),
                    {"operations": 1, "walkedIntermediateWallets": False,
                     "requiredIntermediateGas": False},
                    {key: returned[key] for key in ("operations", "walkedIntermediateWallets",
                                                     "requiredIntermediateGas")})
    recorder.expect("each leg's buyer still bears that leg's gas", ("T-21",),
                    {0: F.B, 1: F.C, 2: F.D},
                    {entry["legIndex"]: entry["gasBorneBy"] for entry in second["funds"]})
    _not_run_chain(recorder)


# ---------------------------------------------------------------- DEMO-06

def demo_06(recorder):
    """The cutoff refuses a new trade while in-flight work follows its rules."""
    path = MAIN_PATHS["DEMO-06"]
    exchange, clock = F.exit_exchange(registration_path=path)
    stop = exchange.receipt(RECEIPT).trade_stop_at
    _setup(recorder, exchange, {"AB": PRICES["AB"]}, {"trade": GAS["trade"]},
           extra={"tradeStopAt": stop})

    F.funded_hop(exchange, F.A, F.B, 1, "transfer-ab", "session-a", "session-b",
                 price=PRICES["AB"], expires_at=stop + 1)
    request, _ = exchange.submit_registration(RECEIPT, 0, "req-leg-0", 86_400)
    recorder.step("a hop is filed before the cutoff", **_positions(exchange))

    clock.now = stop - 1
    before = exchange.evaluate_deadline(RECEIPT)
    recorder.expect("the instant before the cutoff still accepts trades", ("T-24",),
                    {"pastDeadline": False, "newTradesAccepted": True},
                    {"pastDeadline": before["pastDeadline"],
                     "newTradesAccepted": before["newTradesAccepted"]})

    clock.now = stop
    after = exchange.evaluate_deadline(RECEIPT)
    recorder.step("the cutoff instant is reached", pastDeadline=after["pastDeadline"],
                  inFlight=after["inFlightRegistrationLegs"],
                  undefinedOrdering=after["undefinedOrdering"])
    recorder.expect("the cutoff instant itself refuses new trades", ("T-24",),
                    {"pastDeadline": True, "newTradesAccepted": False},
                    {"pastDeadline": after["pastDeadline"],
                     "newTradesAccepted": after["newTradesAccepted"]})
    try:
        F.funded_hop(exchange, F.B, F.C, 2, "transfer-late", "session-b", "session-c",
                     price=PRICES["BC"], now=stop, expires_at=stop + 1)
        refusal = "accepted"
    except Exception as problem:
        refusal = getattr(problem, "code", type(problem).__name__)
    recorder.expect("a new trade at the cutoff is refused", ("T-24",),
                    True, refusal in ("EX_MATCH_UNEXECUTABLE", "EX_TRADE_WINDOW_CLOSED"),
                    detail=f"refusal code {refusal}")
    recorder.expect("the refused trade left no leg behind", ("T-24",),
                    1, exchange.recorded_legs(RECEIPT))

    F.confirm(exchange, request, "res-ab")
    recorder.step("the in-flight registration completed after the cutoff",
                  segmentFunds=_segment_funds(exchange), **_positions(exchange))
    recorder.expect("in-flight registration continues under its own rules", ("T-24",),
                    {"holderPosition": 1, "holder": F.B},
                    {"holderPosition": exchange.holder_index(RECEIPT),
                     "holder": exchange.holder_of(RECEIPT)})
    exchange.release_segment(RECEIPT, 0, F.release_authority(exchange, 0, "auth-0"))
    recorder.expect("the eligible segment still settles after the cutoff", ("T-24",),
                    {"escrowStatus": "released"}, {"escrowStatus": _segment_funds(exchange)[0]["escrowStatus"]})

    # The exit happens after the cutoff, so the grant must still be valid then.
    exchange.connect_wallet(F.B, "session-b")
    exchange.register_authorization(F.authorization(
        F.B, "auth-redeem", "session-b", actions=("sell", "buy", "redeem"),
        expires_at=stop + 86_400))
    eligibility = exchange.exit_eligibility(RECEIPT, F.B, "auth-redeem", F.ALL_CHECKS)
    recorder.expect("the eligible exit is checked after the cutoff", ("T-25",),
                    {"eligible": True}, {"eligible": eligibility["eligible"]},
                    detail=",".join(eligibility["reasons"]) or None)
    wrong = exchange.exit_eligibility(RECEIPT, F.C, "auth-redeem", F.ALL_CHECKS)
    recorder.expect("another account cannot exit", ("T-25",),
                    {"eligible": False, "requesterRefused": True},
                    {"eligible": wrong["eligible"],
                     "requesterRefused": "EX_REDEMPTION_REQUESTER_REFUSED" in wrong["reasons"]})

    exchange.request_redemption(RECEIPT, F.B, "auth-redeem", "rdm-1", F.ALL_CHECKS)
    clock.advance(10)
    report = exchange.advance_exit(RECEIPT)
    recorder.step("exit completed after the cutoff", state=report["state"], burned=report["burned"])
    recorder.expect("the exit records its steps and the burn", ("T-32",),
                    {"complete": True, "burned": True},
                    {"complete": report["complete"], "burned": report["burned"]})
    _record_common(recorder, exchange,
                   {"owner": F.B, "ownerPosition": 1, "holder": F.B, "holderPosition": 1,
                    "registeredPrefixLegs": 1, "outstandingLegs": 0}, ("T-24", "T-02"))
    key = exit_step_key("burn", RECEIPT, "rdm-1")
    try:
        exchange.voucher_desk.act(key, "voucher-issued", RECEIPT, F.B)
        replay = "accepted"
    except Exception as refusal_problem:
        replay = getattr(refusal_problem, "code", type(refusal_problem).__name__)
    recorder.expect("a replayed voucher key for another step is refused", ("T-33",),
                    "EX_VOUCHER_SUBSTITUTION_REFUSED", replay)
    recorder.expect("the undecided orderings are reported, not invented", ("T-24", "T-32"),
                    {"deadlineOrderingReported": True, "exitOrderingReported": True},
                    {"deadlineOrderingReported": bool(after["undefinedOrdering"]),
                     "exitOrderingReported": bool(report["undefinedOrdering"])},
                    detail="; ".join(after["undefinedOrdering"] + report["undefinedOrdering"]))
    _not_run_chain(recorder)


DEMOS = (
    Scenario("DEMO-01", "single trade, segment release and eligible exit",
             ("T-02", "T-11", "T-25", "T-32", "T-33"), MAIN_PATHS["DEMO-01"], demo_01),
    Scenario("DEMO-02", "serial registration with independent prefix release",
             ("T-03", "T-04", "T-12", "T-13"), MAIN_PATHS["DEMO-02"], demo_02),
    Scenario("DEMO-03", "first-hop refusal returns the whole suffix to the origin",
             ("T-17", "T-19", "T-21"), MAIN_PATHS["DEMO-03"], demo_03),
    Scenario("DEMO-04", "finalized prefix survives a later refusal",
             ("T-18", "T-19", "T-29"), MAIN_PATHS["DEMO-04"], demo_04),
    Scenario("DEMO-05", "intermediate wallets hold no gas budget",
             ("T-20", "T-21", "T-22", "T-23"), MAIN_PATHS["DEMO-05"], demo_05),
    Scenario("DEMO-06", "cutoff refuses a new trade while in-flight work continues",
             ("T-24", "T-25", "T-32", "T-33"), MAIN_PATHS["DEMO-06"], demo_06),
)
