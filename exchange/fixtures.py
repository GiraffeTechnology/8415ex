"""Deterministic local fixtures. Clearly marked, never real data.

Every value here is synthetic: the accounts are not real wallets, the quote
asset is a local test label rather than a deployed token, and the registrars are
simulated roles. Nothing in this module reaches a network or a chain, and the
price is a reproducible fixture, not a commercial quotation.
"""
from .ledger import Exchange
from .model import Asset, AuthorizationReference, TradeIntent, WarehouseReceipt

#: Synthetic accounts. The letters name chain positions in the demonstrations,
#: not an ordering of the addresses themselves.
A = "0x" + "a" * 40
B = "0x" + "b" * 40
C = "0x" + "c" * 40
D = "0x" + "d" * 40

CHAIN_ID = 11155111  # the Sepolia test network id; no address or endpoint is configured here
CONTRACT = "0x" + "11" * 20
TOKEN_ID = 8415
QUOTE_ASSET = "local-test-quote"  # a fixture label, NOT a deployed token address
PRICE = 1_000_000  # smallest units, integer only


class ManualClock:
    """A fixed, advanceable clock so a run is reproducible."""

    def __init__(self, start=1_700_000_000):
        self.now = int(start)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += int(seconds)
        return self.now


def asset():
    return Asset(CHAIN_ID, CONTRACT, TOKEN_ID)


def receipt(registration_path="REG_DIRECT", trade_stop_at=1_700_900_000, origin=A):
    return WarehouseReceipt(
        receipt_id="rcpt-8415-0001", asset=asset(), commodity_name="Whole painting lot",
        commodity_quantity=1, commodity_unit="piece", receipt_number="WR-8415-0001",
        registration_path=registration_path, trade_stop_at=trade_stop_at,
        origin_account=origin, minted_at=1_699_000_000)


def authorization(account, authorization_id, session_id, counterparties=(), actions=("sell", "buy"),
                  max_amount=PRICE, not_before=1_699_000_000, expires_at=1_700_800_000, asset_override=None):
    return AuthorizationReference(
        authorization_id=authorization_id, account=account, chain_id=CHAIN_ID,
        asset=asset_override or asset(), allowed_actions=tuple(actions),
        counterparties=tuple(counterparties), max_amount=max_amount, quote_asset=QUOTE_ASSET,
        not_before=not_before, expires_at=expires_at, session_id=session_id)


def intent(intent_id, side, signer, authorization_id, counterparty, nonce,
           limit_price=PRICE, expires_at=1_700_800_000, units=1):
    return TradeIntent(intent_id=intent_id, side=side, signer=signer, asset=asset(),
                       limit_price=limit_price, quote_asset=QUOTE_ASSET, units=units, nonce=nonce,
                       expires_at=expires_at, authorization_id=authorization_id,
                       counterparty=counterparty)


def minted(registration_path="REG_DIRECT", clock=None):
    """An exchange holding one minted receipt, with A connected."""
    clock = clock or ManualClock()
    exchange = Exchange(clock)
    exchange.mint(receipt(registration_path=registration_path))
    exchange.connect_wallet(A, "session-a")
    return exchange, clock


def hop(exchange, seller, buyer, nonce, transfer_id, seller_session, buyer_session, now=None):
    """One explicitly paired sell/buy, executed as one leg.

    The seller and buyer each submit their own order; the pairing fixture only
    decides that these two specific orders face each other.
    """
    suffix = transfer_id.replace("transfer-", "")
    sell_auth, buy_auth = f"auth-sell-{suffix}", f"auth-buy-{suffix}"
    exchange.connect_wallet(seller, seller_session)
    exchange.connect_wallet(buyer, buyer_session)
    exchange.register_authorization(authorization(seller, sell_auth, seller_session, counterparties=(buyer,)))
    exchange.register_authorization(authorization(buyer, buy_auth, buyer_session, counterparties=(seller,)))
    sell = exchange.submit_intent(intent(f"sell-{suffix}", "sell", seller, sell_auth, buyer, nonce))
    buy = exchange.submit_intent(intent(f"buy-{suffix}", "buy", buyer, buy_auth, seller, nonce))
    match = exchange.match_intents(sell.intent_id, buy.intent_id, now)
    return exchange.execute_transfer(match, transfer_id, now)


def chain_to_d(registration_path="REG_DIRECT", clock=None):
    """A -> B -> C -> D on chain, with no registration applied yet."""
    exchange, clock = minted(registration_path=registration_path, clock=clock)
    hop(exchange, A, B, 1, "transfer-ab", "session-a", "session-b")
    hop(exchange, B, C, 2, "transfer-bc", "session-b", "session-c")
    hop(exchange, C, D, 3, "transfer-cd", "session-c", "session-d")
    return exchange, clock


def submit_all(exchange, receipt_id="rcpt-8415-0001", window=86_400):
    """File one request per leg, each independently."""
    requests = []
    for leg in exchange.legs(receipt_id):
        request, _ = exchange.submit_registration(receipt_id, leg.leg_index,
                                                  f"req-leg-{leg.leg_index}", window)
        requests.append(request)
    return requests


def confirm(exchange, request, result_id, outcome="confirmed", receipt_id="rcpt-8415-0001",
            result_version=1, record_commitment=None):
    """Apply a simulated registrar result for one already-filed request."""
    path = exchange.receipt(receipt_id).registration_path
    evidence = exchange.registrars[path].result(request, outcome, result_id,
                                                result_version=result_version,
                                                record_commitment=record_commitment)
    return evidence, exchange.apply_registration_result(evidence)


# ----------------------------------------------------------- Stage 2 fixtures

#: The source whose evidence may release a segment in these fixtures. It stands
#: in for a verified settlement authority and is supplied explicitly, never
#: defaulted by the domain layer.
RELEASE_SOURCE = "sim-settlement-authority"


def funded_exchange(registration_path="REG_DIRECT", clock=None, outcomes=None):
    """An exchange in funded mode: a leg only forms once its escrow is locked."""
    from .ledger import Exchange
    from .settlement import SimulatedPaymentAdapter

    clock = clock or ManualClock()
    payments = SimulatedPaymentAdapter(clock, outcomes=outcomes)
    exchange = Exchange(clock, payment_adapter=payments, release_sources=(RELEASE_SOURCE,),
                        funding_required=True)
    exchange.mint(receipt(registration_path=registration_path))
    exchange.connect_wallet(A, "session-a")
    return exchange, clock


def funded_hop(exchange, seller, buyer, nonce, transfer_id, seller_session, buyer_session,
               price=PRICE, now=None, lock=True):
    """Lock this leg's own escrow, then form the leg. Returns (escrow, leg)."""
    suffix = transfer_id.replace("transfer-", "")
    sell_auth, buy_auth = f"auth-sell-{suffix}", f"auth-buy-{suffix}"
    exchange.connect_wallet(seller, seller_session)
    exchange.connect_wallet(buyer, buyer_session)
    exchange.register_authorization(authorization(seller, sell_auth, seller_session,
                                                  counterparties=(buyer,), max_amount=price))
    exchange.register_authorization(authorization(buyer, buy_auth, buyer_session,
                                                  counterparties=(seller,), max_amount=price))
    sell = exchange.submit_intent(intent(f"sell-{suffix}", "sell", seller, sell_auth, buyer, nonce,
                                         limit_price=price))
    buy = exchange.submit_intent(intent(f"buy-{suffix}", "buy", buyer, buy_auth, seller, nonce,
                                        limit_price=price))
    match = exchange.match_intents(sell.intent_id, buy.intent_id, now)
    if not lock:
        return match, None
    escrow = exchange.lock_escrow(match, f"escrow-{suffix}", now)
    return escrow, exchange.execute_transfer(match, transfer_id, escrow_id=escrow.escrow_id, now=now)


#: The three segment prices are deliberately different, so a figure from one
#: segment cannot silently stand in for another.
PRICE_AB, PRICE_BC, PRICE_CD = 1_000_000, 1_250_000, 900_000


def funded_chain_to_d(registration_path="REG_DIRECT", clock=None, outcomes=None):
    """A -> B -> C -> D, each leg funded by its own buyer at its own price."""
    exchange, clock = funded_exchange(registration_path=registration_path, clock=clock,
                                      outcomes=outcomes)
    funded_hop(exchange, A, B, 1, "transfer-ab", "session-a", "session-b", price=PRICE_AB)
    funded_hop(exchange, B, C, 2, "transfer-bc", "session-b", "session-c", price=PRICE_BC)
    funded_hop(exchange, C, D, 3, "transfer-cd", "session-c", "session-d", price=PRICE_CD)
    return exchange, clock


def release_authority(exchange, leg_index, authority_id, receipt_id="rcpt-8415-0001",
                      source=RELEASE_SOURCE, now=1_700_000_500, **overrides):
    """Correctly bound release evidence for one segment, unless overridden."""
    from .settlement import ReleaseAuthority, segment_binding

    receipt_record = exchange.receipt(receipt_id)
    leg = exchange.leg(receipt_id, leg_index)
    escrow = exchange.escrow_for_leg(receipt_id, leg_index)
    fields = dict(authority_id=authority_id, source=source, receipt_id=receipt_id,
                  leg_index=leg_index, transfer_id=leg.transfer_id, asset=receipt_record.asset,
                  journal_reference=f"journal:{leg.transfer_id}",
                  binding=segment_binding(receipt_record.asset, receipt_id, leg_index,
                                          leg.transfer_id, escrow.payer, escrow.payee,
                                          escrow.principal, escrow.quote_asset),
                  observed_at=now)
    fields.update(overrides)
    return ReleaseAuthority(**fields)


# ----------------------------------------------------------- Stage 3 fixtures

#: The source whose evidence may unwind a suffix in these fixtures. The real
#: asset-return control is still open in the requirements, so this stands in for
#: verified configuration and is supplied explicitly.
ROLLBACK_SOURCE = "sim-rollback-authority"


def rollback_exchange(registration_path="REG_DIRECT", clock=None, outcomes=None,
                      return_outcomes=None, gas_budgets=None):
    """A funded exchange that also has the simulated asset-return control."""
    from .ledger import Exchange
    from .rollback import SimulatedAssetControl
    from .settlement import SimulatedPaymentAdapter

    clock = clock or ManualClock()
    payments = SimulatedPaymentAdapter(clock, outcomes=outcomes)
    control = SimulatedAssetControl(clock, outcomes=return_outcomes)
    exchange = Exchange(clock, payment_adapter=payments, release_sources=(RELEASE_SOURCE,),
                        funding_required=True, asset_control=control,
                        rollback_sources=(ROLLBACK_SOURCE,), gas_budgets=gas_budgets)
    exchange.mint(receipt(registration_path=registration_path))
    exchange.connect_wallet(A, "session-a")
    return exchange, clock


def rollback_chain_to_d(**kwargs):
    """A -> B -> C -> D, each leg funded, with the return control available."""
    exchange, clock = rollback_exchange(**kwargs)
    funded_hop(exchange, A, B, 1, "transfer-ab", "session-a", "session-b", price=PRICE_AB)
    funded_hop(exchange, B, C, 2, "transfer-bc", "session-b", "session-c", price=PRICE_BC)
    funded_hop(exchange, C, D, 3, "transfer-cd", "session-c", "session-d", price=PRICE_CD)
    return exchange, clock


def rollback_authority(exchange, refused_leg_index, authority_id,
                       receipt_id="rcpt-8415-0001", source=ROLLBACK_SOURCE,
                       now=1_700_000_800, **overrides):
    """Correctly bound rollback evidence for the current interval."""
    from .rollback import RollbackAuthority, rollback_binding

    receipt_record = exchange.receipt(receipt_id)
    interval = exchange.rollback_interval(receipt_id, refused_leg_index)
    fields = dict(authority_id=authority_id, source=source, receipt_id=receipt_id,
                  refused_leg_index=refused_leg_index, asset=receipt_record.asset,
                  boundary_account=interval["boundaryAccount"],
                  binding=rollback_binding(receipt_record.asset, receipt_id, refused_leg_index,
                                           interval["boundaryAccount"],
                                           interval["affectedLegs"]),
                  observed_at=now)
    fields.update(overrides)
    return RollbackAuthority(**fields)


def refuse(exchange, request, result_id, receipt_id="rcpt-8415-0001"):
    """Record a registrar refusal for one already-filed request."""
    return confirm(exchange, request, result_id, outcome="rejected", receipt_id=receipt_id)
