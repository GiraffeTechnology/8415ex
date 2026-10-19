"""Domain guarantees the six scenarios never assert, recorded as contracts.

Ten acceptance cases reached the matrix as ``unit-suite-only``: the domain's own
suite exercised them and no local scenario did, so the delivery report said
nothing about them. That is not a defect in the domain - it is a gap in what
this package demonstrates, and the matrix was right to name it rather than let
a reader assume the scenarios covered everything.

Each contract below drives the real domain API with the same labelled synthetic
fixtures the scenarios use, and records what the domain reports. Nothing here
re-implements a domain rule or relaxes one to pass: a refusal is recorded as the
code the domain raised, and a code that stops matching is a failed expectation
rather than a silently updated expectation.

These are local model runs, exactly as limited as the scenarios: no deployment,
no chain transaction, no real wallet, registrar or payment provider.
"""
from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.exit import exit_step_key
from exchange.ids import canonical_json, digest
from exchange.model import Asset, TradeIntent, WHOLE_RECEIPT_UNITS, WarehouseReceipt
from exchange.rollback import rollback_binding

from .harness import Scenario

RECEIPT = "rcpt-8415-0001"

#: Every contract runs on one path. The three paths carry their own contract
#: results in ``scenarios.paths``; these guarantees are path-independent, and
#: saying so once is better than multiplying each by three.
CONTRACT_PATH = "REG_DIRECT"


def _refusal(action):
    """The domain's own refusal code, or what happened instead.

    ``accepted`` is recorded when nothing was refused, so an expectation that
    wanted a refusal fails loudly instead of passing because an exception
    happened to have no code.
    """
    try:
        action()
    except DomainError as problem:
        return problem.code
    except Exception as problem:
        return "%s: %s" % (type(problem).__name__, problem)
    return "accepted"


def _paired(exchange, seller, buyer, seller_session, buyer_session, suffix, nonce,
            **intent_changes):
    """Two independently submitted, explicitly paired intents."""
    sell_auth, buy_auth = "auth-sell-%s" % suffix, "auth-buy-%s" % suffix
    exchange.connect_wallet(seller, seller_session)
    exchange.connect_wallet(buyer, buyer_session)
    exchange.register_authorization(F.authorization(seller, sell_auth, seller_session,
                                                    counterparties=(buyer,)))
    exchange.register_authorization(F.authorization(buyer, buy_auth, buyer_session,
                                                    counterparties=(seller,)))
    sell = exchange.submit_intent(F.intent("sell-%s" % suffix, "sell", seller, sell_auth,
                                           None, nonce, **intent_changes))
    buy = exchange.submit_intent(F.intent("buy-%s" % suffix, "buy", buyer, buy_auth,
                                          None, nonce))
    return sell, buy


# ------------------------------------------------------- T-01: a whole receipt

def _whole_receipt(recorder):
    receipt = F.receipt()
    bulk = WarehouseReceipt(
        receipt_id="rcpt-bulk-local", asset=Asset(F.CHAIN_ID, F.CONTRACT, 99),
        commodity_name="Grain lot", commodity_quantity=25_000, commodity_unit="kg",
        receipt_number="WR-BULK-LOCAL", registration_path=CONTRACT_PATH,
        trade_stop_at=1_700_900_000, origin_account=F.A, minted_at=1_699_000_000)
    recorder.describe_setup(
        receipt={"receiptId": receipt.receipt_id, "tradeableUnits": receipt.tradeable_units,
                 "commodityQuantity": receipt.commodity_quantity},
        bulkReceipt={"receiptId": bulk.receipt_id, "tradeableUnits": bulk.tradeable_units,
                     "commodityQuantity": bulk.commodity_quantity},
        wholeReceiptUnits=WHOLE_RECEIPT_UNITS, path=CONTRACT_PATH,
        accounts={"A": F.A, "B": F.B})

    recorder.step("two receipts of very different size",
                  singlePiece=receipt.commodity_quantity, bulkKilograms=bulk.commodity_quantity)
    recorder.expect("the tradeable quantity is the receipt, not the goods inside it",
                    ("T-01",),
                    {"singlePiece": WHOLE_RECEIPT_UNITS, "bulk": WHOLE_RECEIPT_UNITS},
                    {"singlePiece": receipt.tradeable_units, "bulk": bulk.tradeable_units},
                    detail="25,000 kg and one piece are both exactly one tradeable unit")
    recorder.expect("the goods quantity inside the receipt is preserved, not normalised",
                    ("T-01",), {"singlePiece": 1, "bulk": 25_000},
                    {"singlePiece": receipt.commodity_quantity,
                     "bulk": bulk.commodity_quantity})

    for units in (0, 2, 10):
        recorder.expect("an intent for %s units is refused" % units, ("T-01",),
                        "EX_WHOLE_RECEIPT_REFUSED",
                        _refusal(lambda units=units: F.intent("sell-units", "sell", F.A,
                                                              "auth-a", F.B, 1, units=units)))
    recorder.expect("a fractional share cannot even be expressed", ("T-01",),
                    "EX_WHOLE_RECEIPT_REFUSED",
                    _refusal(lambda: F.intent("sell-half", "sell", F.A, "auth-a", F.B, 1,
                                              units=0.5)),
                    detail="a half unit is refused at construction, not reconciled later")

    exchange, _ = F.minted(registration_path=CONTRACT_PATH)
    recorder.step("one receipt minted", owner=exchange.owner_of(RECEIPT))
    second_claim = WarehouseReceipt(
        receipt_id="rcpt-second-local", asset=F.asset(), commodity_name="Second claim",
        commodity_quantity=1, commodity_unit="piece", receipt_number="WR-8415-SECOND",
        registration_path=CONTRACT_PATH, trade_stop_at=1_700_900_000, origin_account=F.B,
        minted_at=1_699_000_000, allowed_price_currencies=(F.QUOTE_ASSET,),
        nft0_currency_reference=F.NFT0_CURRENCY_SET_REF)
    recorder.expect("a second receipt over the same token is refused", ("T-01",),
                    "EX_ASSET_DUPLICATE_REFUSED",
                    _refusal(lambda: exchange.mint(second_claim, specification=F.mint_specification(second_claim))),
                    detail="one NFT stands for one receipt, so two claims on it are refused")
    repeated = F.receipt(registration_path=CONTRACT_PATH)
    recorder.expect("the same receipt cannot be minted twice", ("T-01",),
                    "EX_RECEIPT_DUPLICATE_REFUSED",
                    _refusal(lambda: exchange.mint(repeated,
                        specification=F.mint_specification(repeated))))
    recorder.expect("no refusal created a position", ("T-01",), {"owner": 0, "holder": 0},
                    {"owner": exchange.owner_index(RECEIPT),
                     "holder": exchange.holder_index(RECEIPT)})
    recorder.note("a receipt is indivisible here; nothing in this package can split one")


# -------------------------------------------- T-06, T-08, T-34: the wallet grant

def _authorization(recorder):
    exchange, clock = F.minted(registration_path=CONTRACT_PATH)
    exchange.connect_wallet(F.B, "session-b")
    exchange.register_authorization(F.authorization(F.A, "auth-a", "session-a",
                                                    counterparties=(F.B,)))
    exchange.register_authorization(F.authorization(F.B, "auth-b", "session-b",
                                                    counterparties=(F.A,)))
    sell = exchange.submit_intent(F.intent("sell-1", "sell", F.A, "auth-a", None, 1))
    exchange.submit_intent(F.intent("buy-1", "buy", F.B, "auth-b", None, 1))
    recorder.describe_setup(
        path=CONTRACT_PATH, accounts={"A": F.A, "B": F.B, "C": F.C},
        grant={"account": F.A, "authorizationId": "auth-a", "session": "session-a",
               "maxAmount": F.PRICE, "quoteAsset": F.QUOTE_ASSET,
               "counterparties": [F.B], "actions": ["sell", "buy"]},
        simulatedAdapters={"wallet": "simulated authorization reference, no wallet adapter"})
    recorder.step("both sides have a grant and an intent on record",
                  intents=[sell.intent_id, "buy-1"])

    def refused(name, cases, code, intent_id, **arguments):
        report = exchange.validate_intent(intent_id, **arguments)
        recorder.expect(name, cases, {"executable": False, "reasonPresent": True},
                        {"executable": report["executable"],
                         "reasonPresent": code in report["reasons"]},
                        detail="%s in %s" % (code, sorted(report["reasons"])))

    missing = exchange.submit_intent(F.intent("sell-no-grant", "sell", F.A, "auth-missing",
                                              F.B, 11))
    refused("an intent naming no grant on record does not execute", ("T-06",),
            "EX_AUTH_UNKNOWN", missing.intent_id)

    over = exchange.submit_intent(F.intent("sell-over-bound", "sell", F.A, "auth-a", F.B, 12,
                                           limit_price=F.PRICE + 1))
    refused("an amount above the signed bound does not execute", ("T-06",),
            "EX_AUTH_AMOUNT_REFUSED", over.intent_id)

    exchange.register_authorization(F.authorization(F.A, "auth-other-asset", "session-a",
                                                    counterparties=(F.B,),
                                                    asset_override=Asset(F.CHAIN_ID,
                                                                         F.CONTRACT, 777)))
    other_asset = exchange.submit_intent(F.intent("sell-other-asset", "sell", F.A,
                                                  "auth-other-asset", F.B, 13))
    refused("a grant for another token does not cover this one", ("T-06",),
            "EX_AUTH_ASSET_REFUSED", other_asset.intent_id)

    exchange.register_authorization(F.authorization(F.A, "auth-buy-only", "session-a",
                                                    counterparties=(F.B,), actions=("buy",)))
    wrong_action = exchange.submit_intent(F.intent("sell-wrong-action", "sell", F.A,
                                                   "auth-buy-only", F.B, 14))
    refused("an action outside the signed scope does not execute", ("T-06",),
            "EX_AUTH_ACTION_REFUSED", wrong_action.intent_id)

    wrong_party = exchange.submit_intent(F.intent("sell-wrong-party", "sell", F.A, "auth-a",
                                                  F.C, 15))
    refused("a counterparty the grant does not list does not execute", ("T-06",),
            "EX_AUTH_COUNTERPARTY_REFUSED", wrong_party.intent_id)

    exchange.register_authorization(F.authorization(F.A, "auth-future", "session-a",
                                                    counterparties=(F.B,),
                                                    not_before=1_700_500_000))
    future = exchange.submit_intent(F.intent("sell-future", "sell", F.A, "auth-future",
                                             F.B, 16))
    refused("a grant that is not yet valid does not execute", ("T-06",),
            "EX_AUTH_NOT_YET_VALID", future.intent_id, now=1_700_000_000)

    stale = exchange.submit_intent(F.intent("sell-stale", "sell", F.A, "auth-a", F.B, 17,
                                            expires_at=1_700_000_000))
    refused("an expired intent does not execute under a valid grant", ("T-06",),
            "EX_INTENT_EXPIRED", stale.intent_id, now=1_700_000_001)

    recorder.expect("a grant for another chain cannot be constructed at all", ("T-06",),
                    "EX_AUTH_CHAIN_REFUSED",
                    _refusal(lambda: F.authorization(F.A, "auth-foreign", "session-a",
                                                     asset_override=Asset(1, F.CONTRACT,
                                                                          F.TOKEN_ID))),
                    detail="refused at construction, so no foreign-chain grant can be filed")

    altered = F.intent("sell-1", "sell", F.A, "auth-a", F.B, 1, limit_price=F.PRICE - 1)
    recorder.expect("altering a signed term changes the digest", ("T-06",), False,
                    sell.digest == altered.digest)
    recorder.expect("resubmitting an altered intent under the same id is refused", ("T-06",),
                    "EX_INTENT_CONFLICT", _refusal(lambda: exchange.submit_intent(altered)))

    clock.now = 1_700_800_001
    refused("an expired grant stops being usable with no further action", ("T-06",),
            "EX_AUTH_EXPIRED", sell.intent_id)
    clock.now = 1_700_000_000
    exchange.revoke_authorization("auth-a")
    refused("a revoked grant stops being usable immediately", ("T-06",),
            "EX_AUTH_REVOKED", sell.intent_id)
    recorder.expect("a revoked grant cannot start a trade", ("T-06", "T-34"),
                    "EX_MATCH_UNEXECUTABLE",
                    _refusal(lambda: exchange.match_intents("sell-1", "buy-1")))
    recorder.expect("no refused check moved a position", ("T-06",), {"owner": 0, "holder": 0},
                    {"owner": exchange.owner_index(RECEIPT),
                     "holder": exchange.holder_index(RECEIPT)})

    # T-08: the session and the selected account are part of the grant.
    sessions, _ = F.minted(registration_path=CONTRACT_PATH)
    sessions.register_authorization(F.authorization(F.A, "auth-a", "session-a",
                                                    counterparties=(F.B,)))
    sessions.connect_wallet(F.B, "session-b")
    sessions.register_authorization(F.authorization(F.B, "auth-b", "session-b",
                                                    counterparties=(F.A,)))
    sessions.submit_intent(F.intent("sell-1", "sell", F.A, "auth-a", None, 1))
    sessions.submit_intent(F.intent("buy-1", "buy", F.B, "auth-b", None, 1))
    recorder.step("a second exchange, to vary the session rather than the grant",
                  activeAccounts=[F.A, F.B])

    lost = F.minted(registration_path=CONTRACT_PATH)[0]
    lost.register_authorization(F.authorization(F.A, "auth-a", "session-a",
                                                counterparties=(F.B,)))
    lost.submit_intent(F.intent("sell-1", "sell", F.A, "auth-a", None, 1))
    lost.disconnect_wallet(F.A)
    state = lost.authorization_state("auth-a")
    recorder.expect("a lost session withdraws the grant", ("T-08",),
                    {"applies": False, "sessionLost": True},
                    {"applies": state["applies"],
                     "sessionLost": "EX_AUTH_SESSION_LOST" in state["reasons"]},
                    detail=str(sorted(state["reasons"])))
    recorder.expect("the intent is refused for the same reason", ("T-08",), True,
                    "EX_AUTH_SESSION_LOST" in lost.validate_intent("sell-1")["reasons"])

    sessions.connect_wallet(F.A, "session-a-new")
    reconnected = sessions.authorization_state("auth-a")
    recorder.expect("a new session does not inherit the old grant", ("T-08",),
                    {"applies": False, "bound": "session-a", "active": "session-a-new"},
                    {"applies": reconnected["applies"],
                     "bound": reconnected["boundSession"],
                     "active": reconnected["activeSession"]})

    switched = F.minted(registration_path=CONTRACT_PATH)[0]
    switched.register_authorization(F.authorization(F.A, "auth-a", "session-a",
                                                    counterparties=(F.B,)))
    switched.connect_wallet(F.B, "session-b")
    switched.register_authorization(F.authorization(F.B, "auth-b", "session-b",
                                                    counterparties=(F.A,)))
    switched.submit_intent(F.intent("sell-1", "sell", F.A, "auth-a", None, 1))
    switched.submit_intent(F.intent("buy-1", "buy", F.B, "auth-b", None, 1))
    switched.switch_account(F.C, "session-c")
    recorder.expect("selecting another account leaves this account's grant alone", ("T-08",),
                    True, switched.validate_intent("sell-1")["executable"],
                    detail="switching to C is not a change to A's own session")
    switched.switch_account(F.A, "session-a-switched")
    recorder.expect("returning on a different session does not revive the grant", ("T-08",),
                    "EX_MATCH_UNEXECUTABLE",
                    _refusal(lambda: switched.match_intents("sell-1", "buy-1")))

    impostor = sessions.submit_intent(F.intent("sell-impostor", "sell", F.B, "auth-a",
                                               F.A, 21))
    recorder.expect("one account's grant cannot be used by another", ("T-08",), True,
                    "EX_AUTH_ACCOUNT_REFUSED"
                    in sessions.validate_intent(impostor.intent_id)["reasons"])

    # T-34: inside the grant, no extra per-step approval exists to be withheld.
    import inspect

    from exchange.ledger import Exchange

    chain, _ = F.minted(registration_path=CONTRACT_PATH)
    statuses = []
    for seller, buyer, nonce, transfer in ((F.A, F.B, 1, "transfer-ab"),
                                           (F.B, F.C, 2, "transfer-bc"),
                                           (F.C, F.D, 3, "transfer-cd")):
        leg = F.hop(chain, seller, buyer, nonce, transfer,
                    "session-%s" % seller[-1], "session-%s" % buyer[-1])
        statuses.append(leg.execution_status)
    recorder.step("three consecutive hops under the grants already given",
                  statuses=statuses, ownerIndex=chain.owner_index(RECEIPT))
    recorder.expect("three hops execute with no further approval step", ("T-34",),
                    {"statuses": ["executed"] * 3, "ownerIndex": 3},
                    {"statuses": statuses, "ownerIndex": chain.owner_index(RECEIPT)})
    parameters = sorted(inspect.signature(Exchange.execute_transfer).parameters)
    recorder.expect("there is no approval argument to pass", ("T-34",),
                    ["escrow_id", "match", "now", "self", "transfer_id"], parameters,
                    detail="escrow_id funds the leg; it is not an approval token")

    beyond, _ = F.minted(registration_path=CONTRACT_PATH)
    F.hop(beyond, F.A, F.B, 1, "transfer-ab", "session-a", "session-b")
    beyond.register_authorization(F.authorization(F.B, "auth-b-scoped", "session-b",
                                                  counterparties=(F.C,),
                                                  max_amount=F.PRICE - 1))
    beyond.connect_wallet(F.C, "session-c")
    beyond.register_authorization(F.authorization(F.C, "auth-c", "session-c",
                                                  counterparties=(F.B,)))
    beyond.submit_intent(F.intent("sell-over", "sell", F.B, "auth-b-scoped", F.C, 8))
    beyond.submit_intent(F.intent("buy-over", "buy", F.C, "auth-c", F.B, 8))
    recorder.expect("an action beyond the grant is still refused in the same session",
                    ("T-34",), "EX_MATCH_UNEXECUTABLE",
                    _refusal(lambda: beyond.match_intents("sell-over", "buy-over")))
    recorder.expect("the refusal left the chain where it was", ("T-34",), 1,
                    beyond.owner_index(RECEIPT))
    recorder.note("no platform approval layer exists to grant or withhold; the wallet "
                  "grant is the whole authority, and its bounds are enforced")
    recorder.not_run("real wallet authorization", ("T-38",),
                     "authorization here is a simulated reference; no wallet, signature or "
                     "chain is involved")


# ------------------------------------------------------------- T-09: matching

def _matching(recorder):
    exchange, _ = F.minted(registration_path=CONTRACT_PATH)
    sell, buy = _paired(exchange, F.A, F.B, "session-a", "session-b", "cross", 1,
                        limit_price=F.PRICE - 1)
    recorder.describe_setup(path=CONTRACT_PATH, accounts={"A": F.A, "B": F.B, "C": F.C},
        prices={"sellLimit": F.PRICE - 1, "buyLimit": F.PRICE},
        quoteAsset=F.QUOTE_ASSET, simulatedAdapters={"matching": "simulated server price-time priority fixture"})
    before = (sell.digest, buy.digest)
    match = exchange.match_intents(sell.intent_id, buy.intent_id)
    recorder.step("independent orders admitted and matched", basis=dict(match.basis))
    recorder.expect("resting ask limit is used without changing either signature", ("T-09",),
                    {"rule": "price-time-resting-order-limit", "price": F.PRICE - 1,
                     "digests": before},
                    {"rule": match.basis["rule"], "price": match.price,
                     "digests": (sell.digest, buy.digest)})
    recorder.expect("the matcher names both original server sequences", ("T-09",),
                    True, match.basis["askSequence"] < match.basis["bidSequence"])
    recorder.expect("matching performs no transfer or funding", ("T-09",),
                    {"owner": 0, "escrows": 0},
                    {"owner": exchange.owner_index(RECEIPT), "escrows": len(exchange._escrows)})
    exchange.connect_wallet(F.C, "session-c")
    exchange.register_authorization(F.authorization(F.C, "auth-c", "session-c",
                                                    max_amount=F.PRICE + 1))
    other = exchange.submit_intent(F.intent("buy-c", "buy", F.C, "auth-c", None, 2,
                                             limit_price=F.PRICE + 1))
    recorder.expect("a better bid outside the seller grant cannot displace its allowed buyer", ("T-09",),
                    F.B, exchange.match_intents(sell.intent_id, buy.intent_id).buyer)
    recorder.expect("the caller cannot choose a pair outside current priority and grants", ("T-09",),
                    "EX_MATCH_PRIORITY_REFUSED",
                    _refusal(lambda: exchange.match_intents(sell.intent_id, other.intent_id)))
    recorder.expect("two buys are refused before any matching", ("T-09",),
                    "EX_MATCH_SIDE_REFUSED",
                    _refusal(lambda: exchange.match_intents(buy.intent_id, other.intent_id)))
    uncrossed, _ = F.minted(registration_path=CONTRACT_PATH)
    low_sell, low_buy = _paired(uncrossed, F.A, F.B, "session-a", "session-b", "low", 1)
    # The original higher resting ask remains valid, while a lower bid cannot cross.
    uncrossed.revoke_authorization(low_buy.authorization_id)
    uncrossed.register_authorization(F.authorization(F.B, "auth-low-bid", "session-b"))
    uncrossed.submit_intent(F.intent("buy-lower", "buy", F.B, "auth-low-bid", None, 2,
                                     limit_price=F.PRICE - 1))
    recorder.expect("uncrossed price limits never form a trade", ("T-09",),
                    "EX_MATCH_UNEXECUTABLE",
                    _refusal(lambda: uncrossed.match_intents(low_sell.intent_id, "buy-lower")))
    recorder.expect("refusals preserve owner and holder positions", ("T-09",),
                    (0, 0), (uncrossed.owner_index(RECEIPT), uncrossed.holder_index(RECEIPT)))
    recorder.not_run("real market order and signature acceptance", ("T-38",),
                     "Synthetic signed intent references and deterministic server clock only")


def _one_head(recorder):
    exchange, _ = F.minted(registration_path=CONTRACT_PATH)
    F.hop(exchange, F.A, F.B, 1, "transfer-ab", "session-a", "session-b")
    recorder.describe_setup(path=CONTRACT_PATH, accounts={"A": F.A, "B": F.B, "C": F.C},
                            initialOwner=F.B, consumedBuyerNonce=1)
    sell, buy = _paired(exchange, F.B, F.C, "session-b", "session-c", "replay", 1)
    report = exchange.validate_intent(sell.intent_id)
    recorder.step("reused signer nonce observed", reasons=report["reasons"])
    recorder.expect("a replayed nonce never executes", ("T-07",),
                    {"executable": False, "replayed": True},
                    {"executable": report["executable"],
                     "replayed": "EX_INTENT_NONCE_REPLAYED" in report["reasons"]})
    recorder.expect("the replay cannot become a current server proposal", ("T-07",),
                    "EX_MATCH_UNEXECUTABLE",
                    _refusal(lambda: exchange.match_intents(sell.intent_id, buy.intent_id)))
    book, _ = F.minted(registration_path=CONTRACT_PATH)
    book.register_authorization(F.authorization(F.A, "auth-ask", "session-a"))
    book.submit_intent(F.intent("ask", "sell", F.A, "auth-ask", None, 1))
    for buyer, session, price in ((F.B, "session-b", F.PRICE), (F.C, "session-c", F.PRICE + 1)):
        book.connect_wallet(buyer, session)
        book.register_authorization(F.authorization(buyer, "bid-" + session, session,
                                                      max_amount=price, counterparties=(F.A,)))
        book.submit_intent(F.intent("order-" + session, "buy", buyer, "bid-" + session,
                                     None, 2, limit_price=price))
        if buyer == F.B:
            first = book.match_intents("ask", "order-session-b")
    second = book.match_intents("ask", "order-session-c")
    book.execute_transfer(second, "transfer-ac")
    recorder.step("the current best proposal executes", buyer=book.owner_of(RECEIPT))
    recorder.expect("the stale proposal cannot sell the same head again", ("T-07",),
                    "EX_TRADE_HEAD_MOVED", _refusal(lambda: book.execute_transfer(first, "transfer-ab")))
    recorder.expect("exactly one proposal advances the head", ("T-07",),
                    {"owner": F.C, "index": 1, "legs": 1},
                    {"owner": book.owner_of(RECEIPT), "index": book.owner_index(RECEIPT),
                     "legs": book.recorded_legs(RECEIPT)})
    duplicate, _ = F.minted(registration_path=CONTRACT_PATH)
    F.hop(duplicate, F.A, F.B, 1, "transfer-ab", "session-a", "session-b")
    ds, db = _paired(duplicate, F.B, F.C, "session-b", "session-c", "dup", 7)
    dm = duplicate.match_intents(ds.intent_id, db.intent_id)
    recorder.expect("a consumed transfer identifier cannot append another leg", ("T-07",),
                    "EX_TRANSFER_DUPLICATE_REFUSED",
                    _refusal(lambda: duplicate.execute_transfer(dm, "transfer-ab")))
    recorder.expect("the duplicate leaves the original one-leg history", ("T-07",),
                    1, duplicate.recorded_legs(RECEIPT))
    late, clock = F.minted(registration_path=CONTRACT_PATH)
    ls, lb = _paired(late, F.A, F.B, "session-a", "session-b", "cutoff", 1)
    pending = late.match_intents(ls.intent_id, lb.intent_id)
    clock.now = late.receipt(RECEIPT).trade_stop_at
    recorder.expect("an actual pending proposal is refused at the exact cutoff", ("T-07",),
                    "EX_TRADE_WINDOW_CLOSED", _refusal(lambda: late.execute_transfer(pending, "late")))
    recorder.expect("cutoff refusal changes neither owner nor history", ("T-07",),
                    (F.A, 0), (late.owner_of(RECEIPT), late.recorded_legs(RECEIPT)))


def _segment_evidence(recorder):
    exchange, _ = F.funded_chain_to_d(registration_path=CONTRACT_PATH)
    requests = F.submit_all(exchange)
    recorder.describe_setup(
        path=CONTRACT_PATH, accounts={"A": F.A, "B": F.B, "C": F.C, "D": F.D},
        prices={"AB": F.PRICE_AB, "BC": F.PRICE_BC, "CD": F.PRICE_CD},
        quoteAsset=F.QUOTE_ASSET,
        requests=[request.request_id for request in requests],
        simulatedAdapters={"payment": "SimulatedPaymentAdapter",
                           "registrar": exchange.registrars[CONTRACT_PATH].label})

    for index, result in enumerate(("res-ab", "res-bc")):
        F.confirm(exchange, requests[index], result)
    recorder.step("AB and BC confirmed, CD not yet",
                  holderIndex=exchange.holder_index(RECEIPT))
    recorder.expect("an earlier leg's confirmation still stands while the holder moves on",
                    ("T-15",), {"holderIndex": 2, "legZero": "confirmed"},
                    {"holderIndex": exchange.holder_index(RECEIPT),
                     "legZero": exchange.leg(RECEIPT, 0).registration_status},
                    detail="a current observation does not erase a past one")

    outcomes = [exchange.release_segment(RECEIPT, leg,
                                         F.release_authority(exchange, leg, "auth-%d" % leg))
                for leg in (0, 1)]
    attempts = [entry["detail"] for entry in exchange.receipt_timeline(RECEIPT)
                if entry["kind"] == "segment-release-attempt"]
    references = [entry["journalReference"] for entry in attempts]
    recorder.step("AB and BC released, each on its own authority",
                  released=[outcome["legIndex"] for outcome in outcomes if outcome["released"]],
                  journalReferences=references)
    recorder.expect("each segment release carries its own journal reference", ("T-15",),
                    {"released": [0, 1], "distinctReferences": 2},
                    {"released": [outcome["legIndex"] for outcome in outcomes
                                  if outcome["released"]],
                     "distinctReferences": len(set(references))},
                    detail="two releases, two references: one cannot stand in for the other")
    recorder.expect("each segment paid exactly its own principal", ("T-15",),
                    [str(F.PRICE_AB), str(F.PRICE_BC)],
                    [str(outcome["principal"]) for outcome in outcomes])

    failed, _ = F.funded_chain_to_d(registration_path=CONTRACT_PATH,
                                    outcomes={"release:escrow-ab": "failed"})
    failed_requests = F.submit_all(failed)
    F.confirm(failed, failed_requests[0], "res-ab")
    outcome = failed.release_segment(RECEIPT, 0, F.release_authority(failed, 0, "auth-0"))
    leg = failed.leg(RECEIPT, 0)
    escrow = failed.escrow_for_leg(RECEIPT, 0)
    recorder.step("the payment for a confirmed segment fails", outcome=dict(outcome))
    recorder.expect("a failed payment leaves the segment locked and says so", ("T-16",),
                    {"released": False, "paymentStatus": "failed", "escrow": "locked",
                     "funding": "release-failed", "movements": 0},
                    {"released": outcome["released"],
                     "paymentStatus": outcome["paymentStatus"],
                     "escrow": escrow.status, "funding": leg.funding_status,
                     "movements": failed.payments.movements})
    recorder.expect("a confirmed segment with a failed payment is not swept into a refund",
                    ("T-16",),
                    {"registration": "confirmed", "refunded": False, "refundedAt": None},
                    {"registration": leg.registration_status,
                     "refunded": leg.funding_status == "refunded",
                     "refundedAt": escrow.refunded_at},
                    detail="a payment problem is not a registration refusal")
    retried = failed.release_segment(RECEIPT, 0, F.release_authority(failed, 0, "auth-0-retry"))
    recorder.expect("the retry uses the same payment key and moves the principal once",
                    ("T-16",),
                    {"released": True, "paymentKey": "release:escrow-ab", "movements": 1},
                    {"released": retried["released"], "paymentKey": retried["paymentKey"],
                     "movements": failed.payments.movements})

    unknown, _ = F.funded_chain_to_d(registration_path=CONTRACT_PATH,
                                     outcomes={"release:escrow-ab": "unknown"})
    unknown_requests = F.submit_all(unknown)
    F.confirm(unknown, unknown_requests[0], "res-ab")
    unresolved = unknown.release_segment(RECEIPT, 0,
                                         F.release_authority(unknown, 0, "auth-0"))
    recorder.expect("an unknown outcome is reported as unknown, not as failed", ("T-16",),
                    {"paymentStatus": "unknown", "released": False},
                    {"paymentStatus": unresolved["paymentStatus"],
                     "released": unresolved["released"]},
                    detail="an unknown result is its own state; reading it as failed would "
                           "invite a second payment")
    recorder.note("each segment settles on its own evidence: neither a later confirmation "
                  "nor another segment's payment decides this one")
    recorder.not_run("real settlement execution", ("T-35", "T-38"),
                     "the payment adapter is simulated; no value moves and no settlement "
                     "system is contacted")


# ------------------------------------------------------- T-27: reproducibility

def _reproducibility(recorder):
    def run():
        clock = F.ManualClock()
        exchange, _ = F.chain_to_d(registration_path=CONTRACT_PATH, clock=clock)
        requests = F.submit_all(exchange)
        # Deliberately out of order, then the gap filled, because a run that
        # only ever sees the easy order proves nothing about determinism.
        F.confirm(exchange, requests[2], "res-cd")
        F.confirm(exchange, requests[0], "res-ab")
        F.confirm(exchange, requests[1], "res-bc")
        return exchange

    first, second = run(), run()
    recorder.describe_setup(
        path=CONTRACT_PATH, accounts={"A": F.A, "B": F.B, "C": F.C, "D": F.D},
        prices={"AB": F.PRICE, "BC": F.PRICE, "CD": F.PRICE},
        clock="fixed manual clock, advanced only where a scenario says so",
        confirmationOrder=["CD", "AB", "BC"])
    recorder.step("the same fixtures run twice, independently",
                  firstOwner=first.receipt_view(RECEIPT)["owner"]["account"],
                  secondOwner=second.receipt_view(RECEIPT)["owner"]["account"])
    recorder.expect("two runs of the same fixtures give the same view", ("T-27",),
                    digest(first.receipt_view(RECEIPT)),
                    digest(second.receipt_view(RECEIPT)))
    recorder.expect("two runs of the same fixtures give the same timeline", ("T-27",),
                    digest(list(first.receipt_timeline(RECEIPT))),
                    digest(list(second.receipt_timeline(RECEIPT))))

    view = first.receipt_view(RECEIPT)
    recorder.expect("the out-of-order confirmations still reach the expected end state",
                    ("T-27",),
                    {"owner": F.D, "holder": F.D, "equal": True, "prefix": 3,
                     "outstanding": 0, "deferred": []},
                    {"owner": view["owner"]["account"], "holder": view["holder"]["account"],
                     "equal": view["ownerEqualsHolder"],
                     "prefix": view["registeredPrefixLegs"],
                     "outstanding": view["outstandingLegs"],
                     "deferred": list(view["deferredLegs"])})
    recorder.expect("every amount is an exact integer in the smallest unit", ("T-27",),
                    {"legPricesAreIntegers": True, "reportedAsExactDigits": True},
                    {"legPricesAreIntegers": all(isinstance(leg.price, int)
                                                 for leg in first.legs(RECEIPT)),
                     "reportedAsExactDigits": all(
                         isinstance(leg["price"], str) and leg["price"].isdigit()
                         for leg in view["legs"])})
    recorder.expect("a float cannot enter a canonical record at all", ("T-27",),
                    "EX_CANONICAL_REFUSED",
                    _refusal(lambda: canonical_json({"price": 1.5})),
                    detail="refused rather than rounded, so no amount is ever approximate")
    recorder.note("the digest is over the record, not over the wall clock: a second run of "
                  "the same source over the same fixtures compares equal")


# ------------------------------- T-30: duplicate and re-ordered observations

def _idempotence(recorder):
    exchange, _ = F.rollback_chain_to_d(registration_path=CONTRACT_PATH)
    requests = F.submit_all(exchange)
    F.refuse(exchange, requests[0], "res-ab-refused")
    recorder.describe_setup(
        path=CONTRACT_PATH, accounts={"A": F.A, "B": F.B, "C": F.C, "D": F.D},
        prices={"AB": F.PRICE_AB, "BC": F.PRICE_BC, "CD": F.PRICE_CD},
        refusedLeg=0, ownerIndex=exchange.owner_index(RECEIPT),
        holderIndex=exchange.holder_index(RECEIPT),
        simulatedAdapters={"payment": "SimulatedPaymentAdapter",
                           "assetControl": "SimulatedAssetControl",
                           "registrar": exchange.registrars[CONTRACT_PATH].label})

    evidence = exchange.registrars[CONTRACT_PATH].result(requests[0], "rejected", "res-dup")
    first = exchange.apply_registration_result(evidence)
    second = exchange.apply_registration_result(evidence)
    recorder.step("the same registrar result arrives twice",
                  first=first["disposition"], second=second["disposition"])
    recorder.expect("a repeated result is recorded as repeated, not applied again", ("T-30",),
                    {"first": "rejected", "second": "idempotent"},
                    {"first": first["disposition"], "second": second["disposition"]})

    exchange.begin_rollback(RECEIPT, 0, F.rollback_authority(exchange, 0, "rb-1"))
    for _ in range(4):
        report = exchange.advance_rollback(RECEIPT)
    recorder.step("the rollback is advanced four times", complete=report["complete"],
                  movements=exchange.payments.movements,
                  assetReturns=exchange.asset_control.returns)
    recorder.expect("repeating the advance repeats no movement", ("T-30",),
                    {"complete": True, "movements": 3, "assetReturns": 3},
                    {"complete": report["complete"],
                     "movements": exchange.payments.movements,
                     "assetReturns": exchange.asset_control.returns},
                    detail="three original buyer refunds and three original reverse hops, "
                           "however many times the same recovery is asked")
    state = exchange.segment_release_state(RECEIPT, 1)
    recorder.expect("a release replayed after a refund is refused", ("T-30",),
                    {"eligible": False, "refunded": True},
                    {"eligible": state["eligible"],
                     "refunded": "EX_SEGMENT_REFUNDED" in state["reasons"]},
                    detail=str(sorted(state["reasons"])))

    reordered, _ = F.rollback_chain_to_d(registration_path=CONTRACT_PATH)
    reordered_requests = F.submit_all(reordered)
    _, deferred = F.confirm(reordered, reordered_requests[2], "res-cd-early")
    recorder.step("a later leg's confirmation arrives before the earlier refusal",
                  disposition=deferred["disposition"])
    recorder.expect("the early later-leg result is deferred, not applied", ("T-30",),
                    "deferred", deferred["disposition"])
    F.refuse(reordered, reordered_requests[0], "res-ab-refused")
    recorder.expect("the buffered result moved no holder position", ("T-30",),
                    {"holderIndex": 0, "deferred": [2]},
                    {"holderIndex": reordered.holder_index(RECEIPT),
                     "deferred": list(reordered.deferred_legs(RECEIPT))})
    reordered.begin_rollback(RECEIPT, 0, F.rollback_authority(reordered, 0, "rb-1"))
    reordered_report = reordered.advance_rollback(RECEIPT)
    recorder.expect("a buffered later result releases nothing during the rollback", ("T-30",),
                    {"complete": True, "movements": 3},
                    {"complete": reordered_report["complete"],
                     "movements": reordered.payments.movements})
    recorder.note("a repeated or re-ordered observation is answered with what already "
                  "happened, never with a second movement")


# ------------------- recovery, the deadline boundary and redemption readiness

def _recovery_and_exit(recorder):
    """The five domain methods nothing in this delivery had ever called.

    Measuring which domain methods a run actually reaches turned up five that no
    scenario, route contract or guarantee touched. Four of them are recovery and
    boundary behaviour - exactly the paths a reviewer most wants demonstrated -
    so they are exercised here rather than written off.
    """
    batch, _ = F.funded_chain_to_d(registration_path=CONTRACT_PATH)
    requests = F.submit_all(batch)
    recorder.describe_setup(
        path=CONTRACT_PATH, accounts={"A": F.A, "B": F.B, "C": F.C, "D": F.D},
        prices={"AB": F.PRICE_AB, "BC": F.PRICE_BC, "CD": F.PRICE_CD},
        quoteAsset=F.QUOTE_ASSET,
        simulatedAdapters={"payment": "SimulatedPaymentAdapter",
                           "assetControl": "SimulatedAssetControl",
                           "registrar": batch.registrars[CONTRACT_PATH].label})

    waiting = batch.settle_eligible_segments(RECEIPT, {})
    recorder.step("settlement is asked for before anything is confirmed",
                  reported=[entry["legIndex"] for entry in waiting],
                  reasons=list(waiting[0]["reasons"]))
    recorder.expect("before confirmation the batch says why, not that authority is "
                    "missing", ("T-14",),
                    {"released": False, "movements": 0,
                     "reasons": ["EX_HOLDER_POSITION_NOT_REACHED",
                                 "EX_SEGMENT_REGISTRATION_NOT_CONFIRMED"]},
                    {"released": bool(waiting[0].get("released")),
                     "movements": batch.payments.movements,
                     "reasons": sorted(waiting[0]["reasons"])},
                    detail="asking for a batch release is not an instruction to pay, and "
                           "the reason it cannot is the registration, not the authority")

    unauthorized, _ = F.funded_chain_to_d(registration_path=CONTRACT_PATH)
    unauthorized_requests = F.submit_all(unauthorized)
    F.confirm(unauthorized, unauthorized_requests[0], "res-ab")
    missing = unauthorized.settle_eligible_segments(RECEIPT, {})
    recorder.step("AB is confirmed but no release authority is offered",
                  reasons=list(missing[0]["reasons"]))
    recorder.expect("a confirmed segment with no authority is reported, not released",
                    ("T-14",),
                    {"released": False, "authorityMissing": True, "movements": 0},
                    {"released": bool(missing[0].get("released")),
                     "authorityMissing": "EX_RELEASE_AUTHORITY_MISSING"
                                         in missing[0]["reasons"],
                     "movements": unauthorized.payments.movements})

    released_each_round = []
    for index, result in enumerate(("res-ab", "res-bc", "res-cd")):
        F.confirm(batch, requests[index], result)
        authorities = {leg: F.release_authority(batch, leg, "auth-%d" % leg)
                       for leg in range(index + 1)}
        outcomes = batch.settle_eligible_segments(RECEIPT, authorities)
        released_each_round.append([entry["legIndex"] for entry in outcomes
                                    if entry.get("released")])
    recorder.step("each hop is confirmed in turn and the batch is asked again",
                  releasedPerRound=released_each_round,
                  movements=batch.payments.movements)
    recorder.expect("the registration prefix releases each segment exactly once",
                    ("T-13",), [[0], [1], [2]], released_each_round,
                    detail="an authority offered again for an already released segment "
                           "releases nothing more")
    recorder.expect("every segment ends released, with one movement each", ("T-13",),
                    {"statuses": ["released"] * 3, "movements": 3},
                    {"statuses": [batch.escrow_for_leg(RECEIPT, leg).status
                                  for leg in range(3)],
                     "movements": batch.payments.movements})

    unknown, _ = F.funded_chain_to_d(registration_path=CONTRACT_PATH,
                                     outcomes={"release:escrow-ab": "unknown"})
    unknown_requests = F.submit_all(unknown)
    F.confirm(unknown, unknown_requests[0], "res-ab")
    unknown.release_segment(RECEIPT, 0, F.release_authority(unknown, 0, "auth-0"))
    enquiry = unknown.resume_payments(RECEIPT)
    recorder.step("a restart asks what already happened", enquiry=enquiry[0])
    recorder.expect("a restart enquires and sends no second payment", ("T-16", "T-28"),
                    {"paymentStatus": "unknown", "saysNoSecondPayment": True,
                     "movements": 0},
                    {"paymentStatus": enquiry[0]["paymentStatus"],
                     "saysNoSecondPayment": "no second payment" in enquiry[0]["action"],
                     "movements": unknown.payments.movements})
    unknown.payments.resolve_unknown("release:escrow-ab", "settled")
    resolved = unknown.resume_payments(RECEIPT)
    recorder.expect("once the outcome is known the enquiry records it rather than paying",
                    ("T-16", "T-28"),
                    {"paymentStatus": "settled", "escrow": "released", "movements": 0},
                    {"paymentStatus": resolved[0]["paymentStatus"],
                     "escrow": unknown.escrow_for_leg(RECEIPT, 0).status,
                     "movements": unknown.payments.movements},
                    detail="the enquiry recorded the result; it sent nothing")

    late, _ = F.rollback_chain_to_d(registration_path=CONTRACT_PATH)
    late_requests = F.submit_all(late)
    F.refuse(late, late_requests[0], "res-ab-refused")
    late.begin_rollback(RECEIPT, 0, F.rollback_authority(late, 0, "rb-1"))
    late.advance_rollback(RECEIPT)
    _, conflict = F.confirm(late, late_requests[1], "res-bc-late")
    recorder.step("a success arrives after the suffix was already unwound",
                  disposition=conflict["disposition"])
    recorder.expect("a late success revives nothing and pays nothing again", ("T-23",),
                    {"disposition": "late-conflict", "legRevived": False,
                     "fundsReleasedAgain": False, "holderIndex": 0,
                     "escrow": "refunded", "movements": 3},
                    {"disposition": conflict["disposition"],
                     "legRevived": conflict["legRevived"],
                     "fundsReleasedAgain": conflict["fundsReleasedAgain"],
                     "holderIndex": late.holder_index(RECEIPT),
                     "escrow": late.escrow_for_leg(RECEIPT, 1).status,
                     "movements": late.payments.movements})
    report = late.rollback_report(RECEIPT)
    recorder.expect("the conflicting evidence is kept for investigation", ("T-23",),
                    {"count": 1, "resultId": "res-bc-late"},
                    {"count": len(report["conflicts"]),
                     "resultId": report["conflicts"][0]["resultId"]},
                    detail="discarded evidence is the one thing an investigation "
                           "cannot recover")

    original_movements = late.payments.movements
    recovered = late.resume_trading(RECEIPT)
    recorder.expect("completed unexpired recovery starts a fresh generation without replay", ("T-23", "T-30"),
                    {"generation": 1, "active": (), "history": 1, "payments": original_movements},
                    {"generation": recovered["generation"], "active": late.active_leg_indices(RECEIPT),
                     "history": len(late.historical_rollbacks(RECEIPT)), "payments": late.payments.movements})

    deadline, deadline_clock = F.rollback_chain_to_d(registration_path=CONTRACT_PATH)
    deadline_requests = F.submit_all(deadline)
    F.confirm(deadline, deadline_requests[0], "res-ab")
    deadline_clock.now = deadline.receipt(RECEIPT).trade_stop_at
    state = deadline.evaluate_deadline(RECEIPT)
    boundary = deadline.deadline_boundary(RECEIPT)
    recorder.step("the deadline is reached with an unfinished suffix",
                  returnsTo=state["unfinishedSuffixReturnsTo"], boundary=dict(boundary))
    recorder.expect("the boundary is the end of the settled prefix, named exactly",
                    ("T-24",),
                    {"boundaryIndex": 1, "boundaryAccount": F.B, "returnsTo": F.B},
                    {"boundaryIndex": boundary["boundaryIndex"],
                     "boundaryAccount": boundary["boundaryAccount"],
                     "returnsTo": state["unfinishedSuffixReturnsTo"]},
                    detail="not the origin and not the current owner: the confirmed holder")
    authority = F.rollback_authority(
        deadline, 1, "rb-deadline", boundary_account=F.B,
        binding=rollback_binding(deadline.receipt(RECEIPT).asset, RECEIPT, 1, F.B, (1, 2)))
    deadline.begin_rollback(RECEIPT, 1, authority, trigger="deadline")
    deadline_report = deadline.advance_rollback(RECEIPT)
    recorder.expect("only the unfinished suffix is unwound, to that boundary", ("T-24",),
                    {"complete": True, "affectedLegs": [1, 2], "owner": F.B},
                    {"complete": deadline_report["complete"],
                     "affectedLegs": list(deadline_report["affectedLegs"]),
                     "owner": deadline.owner_of(RECEIPT)})

    ready, _ = F.minted(registration_path=CONTRACT_PATH)
    agreed = ready.redemption_readiness(RECEIPT, F.A)
    recorder.expect("physical redemption is retired even when owner equals holder", ("T-02",),
                    {"eligible": False, "reasons": ("EX_PHYSICAL_FULFILLMENT_RETIRED",)},
                    {key: agreed[key] for key in ("eligible", "reasons")})
    diverged, _ = F.chain_to_d(registration_path=CONTRACT_PATH)
    split = diverged.redemption_readiness(RECEIPT, F.D)
    recorder.expect("retirement is independent of owner holder equality", ("T-02",),
                    agreed["reasons"], split["reasons"])
    F.hop(diverged, F.D, F.A, 4, "transfer-da", "session-d", "session-a")
    recorder.expect("retired physical operations add no ordinary transfer gate", ("T-02", "T-34"),
                    {"owner": F.A, "holder": F.A, "position": 4},
                    {"owner": diverged.owner_of(RECEIPT), "holder": diverged.holder_of(RECEIPT),
                     "position": diverged.owner_index(RECEIPT)})
    recorder.not_run("real deadline and native recovery enforcement", ("T-37", "T-38"),
                     "Synthetic boundary and registrar only; real Oracle timing and native results remain separate")


# --------------------- what the simulated adapters themselves were asked

def _adapter_enquiry(recorder):
    """The adapters' own enquiry surface, which nothing here had ever read.

    Every adapter role is simulated, and each one stands in for an interface
    whose defining property is that it can be *asked* what happened. The
    delivery drove the adapters and never once asked them: no history was read,
    and an unknown asset return or voucher outcome was never resolved. An
    enquiry surface nothing exercises is the part of a simulation most likely to
    be wrong when a real adapter replaces it.
    """
    payments, _ = F.funded_chain_to_d(registration_path=CONTRACT_PATH,
                                      outcomes={"release:escrow-ab": "failed"})
    payment_requests = F.submit_all(payments)
    F.confirm(payments, payment_requests[0], "res-ab")
    recorder.describe_setup(
        path=CONTRACT_PATH, accounts={"A": F.A, "B": F.B, "C": F.C, "D": F.D},
        prices={"AB": F.PRICE_AB, "BC": F.PRICE_BC, "CD": F.PRICE_CD},
        quoteAsset=F.QUOTE_ASSET,
        simulatedAdapters={"payment": "SimulatedPaymentAdapter",
                           "assetControl": "SimulatedAssetControl",
                           "voucherDesk": "SimulatedVoucherDesk",
                           "registrar": payments.registrars[CONTRACT_PATH].label},
        enquiryMeaning=("asking an adapter what happened is never a second "
                        "instruction to it"))

    payments.release_segment(RECEIPT, 0, F.release_authority(payments, 0, "auth-0"))
    payments.release_segment(RECEIPT, 0, F.release_authority(payments, 0, "auth-0-retry"))
    history = payments.payments.history("release:escrow-ab")
    recorder.step("the payment adapter is asked what it did",
                  attempts=[entry["attempt"] for entry in history],
                  statuses=[entry["status"] for entry in history])
    recorder.expect("the adapter kept every attempt rather than the latest one",
                    ("T-28",),
                    {"statuses": ["failed", "settled"], "attempts": [1, 2]},
                    {"statuses": [entry["status"] for entry in history],
                     "attempts": [entry["attempt"] for entry in history]},
                    detail="an overwritten first attempt is the evidence an "
                           "investigation would need and could not recover")
    recorder.expect("the adapter's own count agrees with the ledger's", ("T-28",),
                    {"settledInHistory": 1, "ledgerMovements": 1},
                    {"settledInHistory": sum(1 for entry in history
                                             if entry["status"] == "settled"),
                     "ledgerMovements": payments.payments.movements})
    before_reading = payments.payments.movements
    read_again = payments.payments.history("release:escrow-ab")
    recorder.expect("reading the history moved nothing and changed nothing",
                    ("T-16", "T-28"),
                    {"movements": before_reading, "sameHistory": True},
                    {"movements": payments.payments.movements,
                     "sameHistory": read_again == history},
                    detail="an enquiry is a read: two reads give the same answer and "
                           "neither is an instruction")

    control, _ = F.rollback_chain_to_d(registration_path=CONTRACT_PATH)
    control_requests = F.submit_all(control)
    F.refuse(control, control_requests[0], "res-ab-refused")
    state = control.begin_rollback(RECEIPT, 0, F.rollback_authority(control, 0, "rb-1"))
    return_key = state["assetHops"][0]["key"]
    control.asset_control._outcomes[return_key] = "unknown"
    control.advance_rollback(RECEIPT)
    control.advance_rollback(RECEIPT)
    recorder.step("the asset return comes back unknown and is asked about again",
                  returns=control.asset_control.returns,
                  status=control.asset_control.lookup(return_key)["status"])
    recorder.expect("an unknown return is not sent again while it stays unknown",
                    ("T-23",), {"status": "unknown", "returns": 0},
                    {"status": control.asset_control.lookup(return_key)["status"],
                     "returns": control.asset_control.returns})
    resolved = control.asset_control.resolve_unknown(return_key, "returned")
    completed = control.advance_rollback(RECEIPT)
    recorder.expect("the enquiry records the return and sends nothing", ("T-23",),
                    {"status": "returned", "resolved": True, "complete": True,
                     "returns": 2},
                    {"status": resolved["status"], "resolved": "resolvedAt" in resolved,
                     "complete": completed["complete"],
                     "returns": control.asset_control.returns},
                    detail="the rollback completes on the enquiry's answer, not on a "
                           "second return")
    recorder.expect("an already resolved return cannot be resolved again", ("T-23",),
                    "EX_ASSET_CONTROL_ALREADY_RESOLVED",
                    _refusal(lambda: control.asset_control.resolve_unknown(return_key,
                                                                          "failed")))
    recorder.expect("a key the control never saw is refused, not invented", ("T-23",),
                    "EX_ASSET_CONTROL_UNKNOWN_KEY",
                    _refusal(lambda: control.asset_control.resolve_unknown(
                        "return:%s:never-asked" % RECEIPT, "returned")))

    burn_key = exit_step_key("burn", RECEIPT, "rdm-1")
    legacy, _ = F.exit_exchange(registration_path=CONTRACT_PATH)
    desk = legacy.voucher_desk
    original = {"key": burn_key, "step": "burn", "receiptId": RECEIPT,
                "account": F.A, "status": "unknown", "attempt": 1,
                "effect": "unknown", "retryable": False}
    desk._records[burn_key] = dict(original)
    desk._history[burn_key] = [dict(original)]
    recorder.step("retained historical unknown outcome", observation=desk.lookup(burn_key))
    for _ in range(2):
        recorder.expect("a retired unknown act cannot be replayed", ("T-33",),
                        "EX_PHYSICAL_FULFILLMENT_RETIRED",
                        _refusal(lambda: desk.act(burn_key, "burn", RECEIPT, F.A)))
    recorder.expect("reading and refusal preserve original evidence", ("T-33",),
                    (original,), desk.history(burn_key))
    resolved = desk.resolve_unknown(burn_key, "failed")
    recorder.expect("original unknown can still be reconciled without execution", ("T-33",),
                    {"status": "failed", "attempt": 1},
                    {key: resolved[key] for key in ("status", "attempt")})
    recorder.expect("reconciliation never reactivates a retired act", ("T-33",),
                    "EX_PHYSICAL_FULFILLMENT_RETIRED",
                    _refusal(lambda: desk.act(burn_key, "burn", RECEIPT, F.A)))
    recorder.expect("history retains unknown and its resolution only", ("T-33",),
                    ["unknown", "failed"], [row["status"] for row in desk.history(burn_key)])
    recorder.note("every adapter here can be asked what happened, and asking is never "
                  "an instruction: no enquiry moved value, returned an asset or "
                  "performed an exit act")
    recorder.not_run("real adapter enquiry", ("T-35", "T-38"),
                     "these are simulated roles; a real provider's enquiry semantics, "
                     "including what its failure and unknown answers mean, are not "
                     "established by this fixture")


GUARANTEE_CONTRACTS = (
    Scenario("GUARANTEE-WHOLE-RECEIPT", "one NFT is one whole receipt, indivisibly",
             ("T-01",), CONTRACT_PATH, _whole_receipt),
    Scenario("GUARANTEE-AUTHORIZATION",
             "the wallet grant is the whole authority, and its bounds hold",
             ("T-06", "T-08", "T-34"), CONTRACT_PATH, _authorization),
    Scenario("GUARANTEE-MATCHING", "two named orders face each other or nothing happens",
             ("T-09",), CONTRACT_PATH, _matching),
    Scenario("GUARANTEE-ONE-HEAD", "the chain has exactly one valid head",
             ("T-07",), CONTRACT_PATH, _one_head),
    Scenario("GUARANTEE-SEGMENT-EVIDENCE",
             "each segment settles on its own evidence, and a payment problem is not a "
             "registration refusal",
             ("T-15", "T-16"), CONTRACT_PATH, _segment_evidence),
    Scenario("GUARANTEE-REPRODUCIBILITY",
             "the same source over the same fixtures gives the same record",
             ("T-27",), CONTRACT_PATH, _reproducibility),
    Scenario("GUARANTEE-IDEMPOTENCE",
             "a repeated or re-ordered observation moves nothing twice",
             ("T-30",), CONTRACT_PATH, _idempotence),
    Scenario("GUARANTEE-RECOVERY-AND-EXIT",
             "batch settlement, a restart's enquiry, a late success, the deadline "
             "boundary and redemption readiness",
             ("T-02", "T-13", "T-14", "T-16", "T-23", "T-24", "T-28"), CONTRACT_PATH,
             _recovery_and_exit),
    Scenario("GUARANTEE-ADAPTER-ENQUIRY",
             "every simulated adapter can be asked what happened, and asking is "
             "never an instruction",
             ("T-16", "T-23", "T-28", "T-33"), CONTRACT_PATH, _adapter_enquiry),
)

#: The cases these contracts exist to cover: the ten the matrix reported as
#: evidenced only by the domain's own suite. Stated here so a contract that
#: stops covering one is caught by a test rather than noticed in the matrix.
COVERED_CASES = ("T-01", "T-06", "T-07", "T-08", "T-09", "T-15", "T-16", "T-27",
                 "T-30", "T-34")

#: Cases the recovery contract also records, which already had scenario evidence.
#: They are listed apart from ``COVERED_CASES`` because the contract exists to
#: reach five domain methods nothing called, not to close a matrix gap.
ALSO_RECORDED_CASES = ("T-02", "T-13", "T-14", "T-23", "T-24", "T-28", "T-33")


def coverage_map():
    """Which contract covers which case, and what these contracts are not."""
    return {
        "schema": "8415ex-guarantee-coverage/1",
        "path": CONTRACT_PATH,
        "coveredCases": list(COVERED_CASES),
        "alsoRecordedCases": list(ALSO_RECORDED_CASES),
        "contracts": [{"scenarioId": contract.scenario_id, "title": contract.title,
                       "cases": list(contract.cases)}
                      for contract in GUARANTEE_CONTRACTS],
        "why": ("these ten cases reached the matrix evidenced only by the domain's own "
                "suite; the delivery report said nothing about them, so each is now "
                "exercised through the domain API and recorded like any other scenario"),
        "isNot": [
            "not a second copy of the domain suite: it records what the domain reports "
            "into the delivery report, and asserts no rule of its own",
            "not real execution: no deployment, no chain transaction, no real wallet, "
            "registrar or payment provider",
            "not a replacement for the domain suite, which stays the implementation's "
            "own test surface",
        ],
    }
