"""The Stage 1 state machine: trade chain, owner/holder dual track, registration.

Three statuses are recorded separately for every leg, because one "success"
field would hide a partially complete hop:

* ``execution_status`` - what happened on the trade side;
* ``registration_status`` - what the registrar has confirmed;
* ``funding_status`` - segmented escrow, which Stage 2 implements. Stage 1
  records ``not-modelled`` and never shows an unfunded leg as settled.

Positions are occurrence indices in one receipt's accepted chain. "owner has
reached B or later" is a statement about that index, never about the numeric
value of an address.
"""
from dataclasses import dataclass, field, replace
from copy import deepcopy

from .errors import DomainError, require
from .eth_trade_gas import ETHTradeGasGate
from .price_balance import NFT0PriceBalanceGate
from .ids import address, amount, digest, identifier, instant
from .model import WHOLE_RECEIPT_UNITS, Asset, AuthorizationReference, TradeIntent, WarehouseReceipt
from .mint_specification import MintSpecification, MintDeclarationBook
from .priority_exchange import PriorityBook, PriorityRefused
from .registration import (DISPOSITIONS, RegistrationEvidence, RegistrationRequest,
                           default_registrars)
from .rollback import (ROLLBACK_STATES, WITHDRAWN_MECHANISMS, GasBudget, RollbackAuthority,
                       RollbackStep, SimulatedAssetControl, rollback_binding)
from .settlement import (EscrowPosition, ReleaseAuthority, SimulatedPaymentAdapter,
                         segment_binding)

EXECUTION_STATUSES = ("executed",)
REGISTRATION_STATUSES = ("not-submitted", "pending", "confirmed", "rejected")
FUNDING_STATUSES = ("not-modelled", "locked", "released", "refunded",
                    "release-failed", "release-outcome-unknown")

#: Rollback capability. A released segment loses it and never regains it.
ROLLBACK_STATUSES = ("none", "available", "detached", "in-progress", "returned")


@dataclass(frozen=True)
class Transfer:
    """One hop of one receipt's trade chain."""

    transfer_id: str
    receipt_id: str
    leg_index: int
    seller: str
    buyer: str
    predecessor_transfer_id: str
    price: int
    quote_asset: str
    sell_intent_digest: str
    buy_intent_digest: str
    sell_authorization_id: str
    buy_authorization_id: str
    executed_at: int
    execution_status: str = "executed"
    registration_status: str = "not-submitted"
    funding_status: str = "not-modelled"
    rollback_status: str = "none"

    def __post_init__(self):
        identifier(self.transfer_id, "EX_TRANSFER_REFUSED")
        require(self.registration_status in REGISTRATION_STATUSES, "EX_TRANSFER_REFUSED", self.registration_status)
        require(self.funding_status in FUNDING_STATUSES, "EX_TRANSFER_REFUSED", self.funding_status)
        require(self.rollback_status in ROLLBACK_STATUSES, "EX_TRANSFER_REFUSED", self.rollback_status)
        require(self.seller != self.buyer, "EX_TRANSFER_REFUSED", "a leg must move the receipt between parties")


@dataclass(frozen=True)
class MatchResult:
    """A deterministic pairing of two explicitly paired intents.

    A match is not a registration and not a settlement. It records the basis it
    used and leaves both intents exactly as signed.
    """

    sell_intent_digest: str
    buy_intent_digest: str
    seller: str
    buyer: str
    asset: Asset
    price: int
    quote_asset: str
    units: int
    basis: dict
    matched_at: int


class Exchange:
    """Holds every receipt's chain and the registration state around it.

    Nothing here signs, pays, deploys or touches a chain. Wallet authorization
    facts are supplied by the caller and treated as a trust boundary: this layer
    checks them and refuses, it never widens them or adds an approval step of
    its own.
    """

    def __init__(self, clock, payment_adapter=None, release_sources=(), funding_required=False,
                 asset_control=None, rollback_sources=(), gas_budgets=None,
                 voucher_desk=None, mint_verifier=None, eth_gas_gate=None, price_balance_gate=None):
        """``funding_required`` turns on the Stage 2 rule that a leg only forms
        once its own buyer's money is in escrow. Stage 1 leaves it off and
        records funding as not modelled rather than implying a payment.

        ``release_sources`` is the set of sources whose evidence may release a
        segment. It is supplied by the caller from verified configuration; this
        layer never widens it and has no default member.
        """
        require(callable(clock), "EX_CLOCK_REFUSED", "a clock function is required")
        self._clock = clock
        self._eth_gas_gate = eth_gas_gate
        self._price_balance_gate = price_balance_gate
        self.payments = payment_adapter
        self.funding_required = bool(funding_required)
        self._release_sources = frozenset(identifier(s, "EX_RELEASE_SOURCE_REFUSED")
                                          for s in release_sources)
        self.asset_control = asset_control
        self._rollback_sources = frozenset(identifier(s, "EX_ROLLBACK_SOURCE_REFUSED")
                                           for s in rollback_sources)
        self._budgets = {address(a, "EX_GAS_BUDGET_REFUSED"): amount(v, "EX_GAS_BUDGET_REFUSED")
                         for a, v in (gas_budgets or {}).items()}
        self._escrows = {}
        self._escrow_by_leg = {}
        self._gas = {}
        self._rollbacks = {}
        self._returned_to = {}
        self._active_legs = {}
        self._rollback_history = {}
        self.voucher_desk = voucher_desk
        self._exits = {}
        self._mint_book = MintDeclarationBook(mint_verifier) if callable(mint_verifier) else None
        self._mint_declarations = {}
        self._receipts = {}
        self._asset_keys = {}
        self._authorizations = {}
        self._sessions = {}
        self._intents = {}
        self._order_books = {}
        self._used_nonces = set()
        self._legs = {}
        self._holder_index = {}
        self._requests = {}
        self._requests_by_leg = {}
        self._applied_results = {}
        self._deferred = {}
        self._rejections = {}
        self._events = {}
        self.registrars = default_registrars(clock)
        if self.funding_required:
            require(self.payments is not None, "EX_PAYMENT_ADAPTER_REQUIRED",
                    "funded mode needs a payment adapter")

    # ---------------------------------------------------------------- receipts

    def mint(self, receipt, specification=None):
        """Record one whole receipt as exactly one NFT.

        Minting is a technical record. It asserts no legal right, and a second
        receipt may not map to an NFT that is already mapped.
        """
        require(isinstance(receipt, WarehouseReceipt), "EX_RECEIPT_REFUSED", "receipt type")
        require(receipt.price_currency is not None, "EX_NFT0_CURRENCY_REQUIRED",
                "NFT0 must specify the price currency; EX cannot select or substitute one")
        require(isinstance(specification, MintSpecification), "EX_MINT_DECLARATION_REQUIRED",
                "a bare WarehouseReceipt is not a complete v1.2 mint declaration")
        require(specification.receipt == receipt, "EX_MINT_DECLARATION_BINDING_REFUSED",
                "declaration and original receipt differ")
        require(self._mint_book is not None, "EX_MINT_VERIFIER_REQUIRED",
                "existing schema, controlled-storage and privacy verification is required")
        require(receipt.receipt_id not in self._receipts, "EX_RECEIPT_DUPLICATE_REFUSED", receipt.receipt_id)
        existing = self._asset_keys.get(receipt.asset.key)
        require(existing is None, "EX_ASSET_DUPLICATE_REFUSED",
                f"{receipt.asset.key} already maps to receipt {existing}")
        declaration = self._mint_book.admit(specification)
        self._mint_declarations[receipt.receipt_id] = deepcopy(declaration)
        self._receipts[receipt.receipt_id] = receipt
        self._asset_keys[receipt.asset.key] = receipt.receipt_id
        self._legs[receipt.receipt_id] = []
        self._active_legs[receipt.receipt_id] = []
        self._rollback_history[receipt.receipt_id] = []
        self._holder_index[receipt.receipt_id] = 0
        self._requests_by_leg[receipt.receipt_id] = {}
        self._deferred[receipt.receipt_id] = {}
        self._rejections[receipt.receipt_id] = []
        self._escrow_by_leg[receipt.receipt_id] = {}
        self._gas[receipt.receipt_id] = {}
        self._rollbacks[receipt.receipt_id] = None
        self._returned_to[receipt.receipt_id] = None
        self._exits[receipt.receipt_id] = None
        self._events[receipt.receipt_id] = []
        self._record(receipt.receipt_id, "receipt-minted", {
            "receiptId": receipt.receipt_id, "asset": list(receipt.asset.key),
            "commodityQuantity": receipt.commodity_quantity, "tradeableUnits": receipt.tradeable_units,
            "registrationPath": receipt.registration_path, "tradeStopAt": receipt.trade_stop_at,
            "origin": receipt.origin_account})
        return receipt

    def receipt(self, receipt_id):
        receipt = self._receipts.get(receipt_id)
        require(receipt is not None, "EX_RECEIPT_UNKNOWN", receipt_id)
        return receipt

    # ----------------------------------------------------------- wallet facts

    def connect_wallet(self, account, session_id):
        """Record which session a connected account is acting under."""
        address(account, "EX_AUTH_REFUSED")
        identifier(session_id, "EX_AUTH_REFUSED")
        self._sessions[account] = session_id
        return session_id

    def disconnect_wallet(self, account):
        """Session loss. Authorizations bound to the lost session stop applying."""
        self._sessions.pop(address(account, "EX_AUTH_REFUSED"), None)

    def switch_account(self, account, session_id):
        """Switching the selected account does not carry the previous account's
        authorization over to it."""
        return self.connect_wallet(account, session_id)

    def register_authorization(self, authorization):
        require(isinstance(authorization, AuthorizationReference), "EX_AUTH_REFUSED", "authorization type")
        self._authorizations[authorization.authorization_id] = authorization
        return authorization

    def revoke_authorization(self, authorization_id):
        current = self._authorization(authorization_id)
        revoked = current.revoke()
        self._authorizations[authorization_id] = revoked
        return revoked

    def authorization(self, authorization_id):
        """The authorization exactly as registered. Callers may read it; nothing
        here lets them widen it."""
        return self._authorization(authorization_id)

    def _authorization(self, authorization_id):
        found = self._authorizations.get(identifier(authorization_id, "EX_AUTH_REFUSED"))
        require(found is not None, "EX_AUTH_UNKNOWN", authorization_id)
        return found

    def authorization_state(self, authorization_id, now=None):
        """Why an authorization does or does not currently apply."""
        now = self._now(now)
        auth = self._authorization(authorization_id)
        active_session = self._sessions.get(auth.account)
        reasons = []
        if auth.revoked:
            reasons.append("EX_AUTH_REVOKED")
        if now < auth.not_before:
            reasons.append("EX_AUTH_NOT_YET_VALID")
        if now >= auth.expires_at:
            reasons.append("EX_AUTH_EXPIRED")
        if active_session is None:
            reasons.append("EX_AUTH_SESSION_LOST")
        elif active_session != auth.session_id:
            reasons.append("EX_AUTH_SESSION_REFUSED")
        return {"authorizationId": auth.authorization_id, "account": auth.account,
                "activeSession": active_session, "boundSession": auth.session_id,
                "applies": reasons == [], "reasons": tuple(reasons), "observedAt": now}

    # ------------------------------------------------------------- intents

    def submit_intent(self, intent):
        """Record a signed intent exactly as signed. Reporting is separate from
        execution: an unexecutable intent is still recorded with its reasons."""
        require(isinstance(intent, TradeIntent), "EX_INTENT_REFUSED", "intent type")
        previous = self._intents.get(intent.intent_id)
        if previous is not None:
            require(previous.digest == intent.digest, "EX_INTENT_CONFLICT",
                    f"intent {intent.intent_id} was already submitted with different signed terms")
            return previous
        self._intents[intent.intent_id] = intent
        if intent.counterparty is None and self.validate_intent(intent.intent_id)["executable"]:
            self.enter_order(intent.intent_id)
        return intent

    def intent(self, intent_id):
        found = self._intents.get(identifier(intent_id, "EX_INTENT_REFUSED"))
        require(found is not None, "EX_INTENT_UNKNOWN", intent_id)
        return found

    def validate_intent(self, intent_id, now=None):
        """Executability, the exact refusal reasons, and the authorization identity
        that was checked. This never mutates the intent."""
        now = self._now(now)
        intent = self.intent(intent_id)
        reasons = []
        receipt_id = self._asset_keys.get(intent.asset.key)
        receipt = self._receipts.get(receipt_id) if receipt_id else None
        if receipt is None:
            reasons.append("EX_ASSET_UNKNOWN")
        else:
            if intent.quote_asset != receipt.price_currency:
                reasons.append("EX_NFT0_CURRENCY_MISMATCH")
            if now >= receipt.trade_stop_at:
                reasons.append("EX_TRADE_WINDOW_CLOSED")
            if self._returned_to[receipt_id] is not None:
                reasons.append("EX_TRADE_RETURNED_CHAIN_CLOSED")
            if self._rollbacks[receipt_id] is not None:
                reasons.append("EX_TRADE_ROLLBACK_OPEN")
            if self._exits[receipt_id] is not None:
                reasons.append("EX_TRADE_EXIT_OPEN")
        if now >= intent.expires_at:
            reasons.append("EX_INTENT_EXPIRED")
        if (intent.signer, intent.nonce) in self._used_nonces:
            reasons.append("EX_INTENT_NONCE_REPLAYED")
        auth_state = None
        try:
            auth = self._authorization(intent.authorization_id)
        except DomainError as error:
            reasons.append(error.code)
            auth = None
        if auth is not None:
            auth_state = self.authorization_state(auth.authorization_id, now)
            reasons.extend(auth_state["reasons"])
            if auth.account != intent.signer:
                reasons.append("EX_AUTH_ACCOUNT_REFUSED")
            if auth.asset.key != intent.asset.key:
                reasons.append("EX_AUTH_ASSET_REFUSED")
            if auth.chain_id != intent.asset.chain_id:
                reasons.append("EX_AUTH_CHAIN_REFUSED")
            if intent.side not in auth.allowed_actions:
                reasons.append("EX_AUTH_ACTION_REFUSED")
            if intent.limit_price > auth.max_amount:
                reasons.append("EX_AUTH_AMOUNT_REFUSED")
            if auth.quote_asset != intent.quote_asset:
                reasons.append("EX_AUTH_QUOTE_ASSET_REFUSED")
            if auth.counterparties and intent.counterparty is not None and (
                    intent.counterparty not in auth.counterparties):
                reasons.append("EX_AUTH_COUNTERPARTY_REFUSED")
        ordered = tuple(dict.fromkeys(reasons))
        return {"intentId": intent.intent_id, "side": intent.side, "signer": intent.signer,
                "signedTermsDigest": intent.digest, "units": intent.units,
                "executable": ordered == (), "reasons": ordered,
                "authorization": auth_state, "observedAt": now}

    def enter_order(self, intent_id):
        """Accept into the existing price/time book with server sequence only."""
        intent = self.intent(intent_id)
        receipt_id = self._asset_keys.get(intent.asset.key)
        require(receipt_id is not None, "EX_ASSET_UNKNOWN", str(intent.asset.key))
        key = (receipt_id, intent.quote_asset)
        if key not in self._order_books:
            self._order_books[key] = PriorityBook(self, receipt_id, intent.quote_asset, self._clock)
        try:
            return self._order_books[key].enter(intent_id)
        except PriorityRefused as error:
            raise DomainError("EX_ORDER_REFUSED", str(error)) from None

    def match_intents(self, sell_intent_id, buy_intent_id, now=None):
        """Match the best executable pair, preserving limits and server FIFO.

        For crossing orders, execution uses the older accepted order's limit:
        an arriving buyer gets the best eligible resting ask; an arriving seller
        gets the best eligible resting bid. A caller cannot name a worse pair.
        """
        now = self._now(now)
        sell, buy = self.intent(sell_intent_id), self.intent(buy_intent_id)
        require(sell.side == "sell" and buy.side == "buy", "EX_MATCH_SIDE_REFUSED",
                "one sell and one buy are required")
        require(sell.asset.key == buy.asset.key, "EX_MATCH_ASSET_REFUSED",
                "both sides must name one asset")
        require(sell.quote_asset == buy.quote_asset, "EX_MATCH_QUOTE_ASSET_REFUSED",
                "quote assets must agree")
        require(sell.units == buy.units == WHOLE_RECEIPT_UNITS, "EX_WHOLE_RECEIPT_REFUSED",
                "one whole receipt is required")
        receipt_id = self._asset_keys.get(sell.asset.key)
        require(receipt_id is not None, "EX_ASSET_UNKNOWN", str(sell.asset.key))
        book = self._order_books.get((receipt_id, sell.quote_asset))
        require(book is not None, "EX_ORDER_NOT_ACCEPTED", "server book acceptance is required")
        require(now == book._now(), "EX_ORDER_OBSERVATION_REFUSED",
                "matching uses the current trusted server observation")
        proposal = book.proposal()
        chosen = None
        for ask_id in proposal["askPriority"]:
            ask = self.intent(ask_id)
            ask_grant = self.authorization(ask.authorization_id)
            for bid_id in proposal["bidPriority"]:
                bid = self.intent(bid_id)
                if bid.limit_price < ask.limit_price:
                    break
                bid_grant = self.authorization(bid.authorization_id)
                if ask_grant.counterparties and bid.signer not in ask_grant.counterparties:
                    continue
                if bid_grant.counterparties and ask.signer not in bid_grant.counterparties:
                    continue
                ask_seq = book._entries[ask_id][1]
                bid_seq = book._entries[bid_id][1]
                execution_price = ask.limit_price if ask_seq < bid_seq else bid.limit_price
                if execution_price > ask_grant.max_amount or execution_price > bid_grant.max_amount:
                    continue
                chosen = (ask_id, bid_id)
                break
            if chosen:
                break
        require(chosen is not None, "EX_MATCH_UNEXECUTABLE", "no executable crossing pair")
        require(chosen == (sell.intent_id, buy.intent_id), "EX_MATCH_PRIORITY_REFUSED",
                "caller-selected pair is not the best executable server-priority pair")
        ask_sequence = book._entries[sell.intent_id][1]
        bid_sequence = book._entries[buy.intent_id][1]
        price = sell.limit_price if ask_sequence < bid_sequence else buy.limit_price
        basis = {"rule": "price-time-resting-order-limit",
                 "sellLimit": str(sell.limit_price), "buyLimit": str(buy.limit_price),
                 "executionPrice": str(price), "quoteAsset": sell.quote_asset,
                 "units": sell.units, "sellIntentId": sell.intent_id, "buyIntentId": buy.intent_id,
                 "askSequence": ask_sequence, "bidSequence": bid_sequence,
                 "registrationAndSettlement": "not-performed-by-matching"}
        return MatchResult(sell_intent_digest=sell.digest, buy_intent_digest=buy.digest,
                           seller=sell.signer, buyer=buy.signer, asset=sell.asset, price=price,
                           quote_asset=sell.quote_asset, units=sell.units, basis=basis, matched_at=now)

    def _check_match_binding(self, match, now):
        require(isinstance(match, MatchResult), "EX_TRANSFER_REFUSED", "match type")
        sell = self._intent_by_digest(match.sell_intent_digest)
        buy = self._intent_by_digest(match.buy_intent_digest)
        canonical = self.match_intents(sell.intent_id, buy.intent_id, now)
        require(all(getattr(match, name) == getattr(canonical, name)
                    for name in ("seller", "buyer", "asset", "price", "quote_asset", "units", "basis")),
                "EX_MATCH_BINDING_REFUSED", "match terms differ from the signed pairing")
        return canonical

    def _check_trade_open(self, receipt_id, now):
        require(now < self.receipt(receipt_id).trade_stop_at, "EX_TRADE_WINDOW_CLOSED",
                "new trades are refused at or after the stop-trading instant")
        require(self._returned_to[receipt_id] is None, "EX_TRADE_RETURNED_CHAIN_CLOSED",
                "this chain has returned; further trading is not defined")
        require(self._rollbacks[receipt_id] is None, "EX_TRADE_ROLLBACK_OPEN",
                "a rollback freezes the receipt's trade chain")
        require(self._exits[receipt_id] is None, "EX_TRADE_EXIT_OPEN",
                "an exit freezes resale, including while a step is unresolved")

    # ------------------------------------------------------------- transfers

    def active_leg_indices(self, receipt_id):
        """Stable global leg IDs in the current chain, including protected prefix."""
        self.receipt(receipt_id)
        return tuple(self._active_legs[receipt_id])

    def _next_registration_index(self, receipt_id):
        for index in self._active_legs[receipt_id]:
            if self.leg(receipt_id, index).registration_status != "confirmed":
                return index
        return len(self._legs[receipt_id])

    def resume_trading(self, receipt_id, now=None):
        """Open a fresh chain only after complete recovery and current validity.

        The configured original verifier must attest current asset validity for
        this binding. No validity is inferred from a return, CI or an old mint.
        Global leg IDs, consumed nonces, escrow/gas references and old evidence
        stay unique; only the executable path drops the withdrawn suffix.
        """
        now = self._now(now)
        receipt = self.receipt(receipt_id)
        require(now == self._now(None), "EX_RECOVERY_OBSERVATION_REFUSED",
                "recovery uses the current trusted observation")
        state = self._rollbacks[receipt_id]
        require(state is not None and state["state"] == "complete"
                and all(step.status == "done" for step in state["steps"]),
                "EX_RECOVERY_INCOMPLETE", "all refund and asset-return steps need their own result")
        require(self._returned_to[receipt_id] == (state["boundaryIndex"], state["boundaryAccount"]),
                "EX_RECOVERY_POSITION_REFUSED", "recorded return does not match the recovery boundary")
        require(self.owner_index(receipt_id) == self.holder_index(receipt_id)
                and self.owner_of(receipt_id) == self.holder_of(receipt_id),
                "EX_RECOVERY_POSITION_REFUSED", "recovery must start at effective holder")
        require(self._exits[receipt_id] is None, "EX_RECOVERY_LEGACY_OUTCOME_UNRESOLVED",
                "a historical physical-operation outcome must be reconciled without resuming it")
        require(now < receipt.trade_stop_at, "EX_TRADE_WINDOW_CLOSED",
                "completed rollback cannot reopen an expired asset")
        binding = {"receiptId": receipt_id, "asset": list(receipt.asset.key),
                   "mintDeclarationDigest": self._mint_declarations[receipt_id]["declarationDigest"],
                   "owner": self.owner_of(receipt_id), "holder": self.holder_of(receipt_id),
                   "boundaryIndex": state["boundaryIndex"], "observedAt": now}
        binding_digest = digest(binding)
        try:
            valid = self._mint_book.verify("current-asset-validity", binding)
        except Exception:
            raise DomainError("EX_ASSET_VALIDITY_NOT_VERIFIED",
                              "current asset validity verifier failed") from None
        require(valid is True and digest(binding) == binding_digest,
                "EX_ASSET_VALIDITY_NOT_VERIFIED", "current validity and unchanged binding required")
        require(self._rollbacks[receipt_id] is state
                and self.owner_of(receipt_id) == self.holder_of(receipt_id) == state["boundaryAccount"]
                and self.owner_index(receipt_id) == self.holder_index(receipt_id) == state["boundaryIndex"],
                "EX_RECOVERY_POSITION_REFUSED", "recovery position changed during verification")
        require(self._now(None) < receipt.trade_stop_at, "EX_TRADE_WINDOW_CLOSED",
                "deadline passed during current validity verification")
        withdrawn = frozenset(state["affectedLegs"])
        survivors = [i for i in self._active_legs[receipt_id] if i not in withdrawn]
        require(all(self.leg(receipt_id, i).registration_status == "confirmed" for i in survivors),
                "EX_RECOVERY_POSITION_REFUSED", "the surviving path must be the registered prefix")
        report = deepcopy(self.rollback_report(receipt_id, now))
        report["historical"] = True
        withdrawn_deferred = {i: deepcopy(e) for i, e in self._deferred[receipt_id].items()
                              if i not in survivors}
        old_orders = tuple({"quoteAsset": key[1], "intentId": order.intent_id,
                            "digest": order.digest, "sequence": sequence}
                           for key, book in self._order_books.items() if key[0] == receipt_id
                           for order, sequence in book._entries.values())
        self._rollback_history[receipt_id].append({
            "state": deepcopy(state), "report": report,
            "withdrawnDeferredEvidence": withdrawn_deferred, "retiredOrders": old_orders})
        self._active_legs[receipt_id] = survivors
        self._deferred[receipt_id] = {i: e for i, e in self._deferred[receipt_id].items()
                                      if i in survivors}
        self._rollbacks[receipt_id] = None
        self._returned_to[receipt_id] = None
        self._order_books = {key: book for key, book in self._order_books.items()
                             if key[0] != receipt_id}
        self._record(receipt_id, "trading-resumed", {
            "generation": len(self._rollback_history[receipt_id]),
            "boundaryIndex": state["boundaryIndex"], "account": state["boundaryAccount"],
            "withdrawnLegs": list(state["affectedLegs"]), "activeLegs": list(survivors),
            "nextGlobalLegIndex": len(self._legs[receipt_id]), "oldOrdersReadmitted": False,
            "historyPreserved": True})
        return {"receiptId": receipt_id, "resumed": True, "account": self.owner_of(receipt_id),
                "activeLegs": tuple(survivors), "nextGlobalLegIndex": len(self._legs[receipt_id]),
                "generation": len(self._rollback_history[receipt_id]), "observedAt": now}

    def historical_rollbacks(self, receipt_id):
        self.receipt(receipt_id)
        return tuple(deepcopy(item["report"]) for item in self._rollback_history[receipt_id])

    def owner_index(self, receipt_id):
        """The position the asset is actually at now.

        Normally that is how far the trade chain advanced. After a rollback
        returned the receipt, it is the boundary the return stopped at; the legs
        above it stay in history rather than being deleted.
        """
        self.receipt(receipt_id)
        returned = self._returned_to[receipt_id]
        active = self._active_legs[receipt_id]
        return returned[0] if returned is not None else (active[-1] + 1 if active else 0)

    def holder_index(self, receipt_id):
        """Stable global position of the last registered active leg, or zero.

        Withdrawn IDs are never reused; use registeredPrefixLegs for the count.
        """
        self.receipt(receipt_id)
        return self._holder_index[receipt_id]

    def owner_of(self, receipt_id):
        receipt = self.receipt(receipt_id)
        returned = self._returned_to[receipt_id]
        if returned is not None:
            return returned[1]
        legs = self._legs[receipt_id]
        active = self._active_legs[receipt_id]
        return legs[active[-1]].buyer if active else receipt.origin_account

    def recorded_legs(self, receipt_id):
        """How many legs the history holds, whatever the asset's position is."""
        self.receipt(receipt_id)
        return len(self._legs[receipt_id])

    def holder_of(self, receipt_id):
        receipt = self.receipt(receipt_id)
        index = self._holder_index[receipt_id]
        return self._legs[receipt_id][index - 1].buyer if index else receipt.origin_account

    def legs(self, receipt_id):
        self.receipt(receipt_id)
        return tuple(self._legs[receipt_id])

    def execute_transfer(self, match, transfer_id, escrow_id=None, now=None):
        """Append one leg, advancing the owner position by exactly one.

        Only the current head may be sold. Two attempts from the same head mean
        the second one is refused: a receipt has one valid continuous order.

        In funded mode the buyer's own escrow for this leg must already be
        locked and must match the agreed terms exactly, so a failed lock leaves
        no trade and no registration request behind.
        """
        now = self._now(now)
        require(isinstance(match, MatchResult), "EX_TRANSFER_REFUSED", "match type")
        receipt_id = self._asset_keys.get(match.asset.key)
        require(receipt_id is not None, "EX_ASSET_UNKNOWN", str(match.asset.key))
        self._check_trade_open(receipt_id, now)
        legs = self._legs[receipt_id]
        require(self.owner_of(receipt_id) == match.seller, "EX_TRADE_HEAD_MOVED",
                "only the current owner position may transfer the receipt")
        sell = self._intent_by_digest(match.sell_intent_digest)
        buy = self._intent_by_digest(match.buy_intent_digest)
        for intent in (sell, buy):
            require((intent.signer, intent.nonce) not in self._used_nonces,
                    "EX_INTENT_NONCE_REPLAYED", f"{intent.signer}#{intent.nonce}")
        for report in (self.validate_intent(sell.intent_id, now), self.validate_intent(buy.intent_id, now)):
            require(report["executable"], "EX_TRANSFER_AUTHORIZATION_REFUSED",
                    f"{report['intentId']}: {','.join(report['reasons'])}")
        match = self._check_match_binding(match, now)
        require(transfer_id not in self._transfer_ids(), "EX_TRANSFER_DUPLICATE_REFUSED", transfer_id)
        require(isinstance(self._eth_gas_gate, ETHTradeGasGate),
                "EX_ETH_GAS_UNVERIFIED",
                "Warning: authenticated ETH gas balance is unavailable; trading is disabled")
        gas_admission = self._eth_gas_gate.admit(match, now)
        require(gas_admission["allowed"], gas_admission["code"], gas_admission["warning"])
        self._check_price_balance(match, escrow_id, now)
        funding_status, rollback_status = "not-modelled", "none"
        if self.funding_required or escrow_id is not None:
            require(escrow_id is not None, "EX_SEGMENT_NOT_FUNDED",
                    "this leg has no escrow position, so no trade is formed")
            escrow = self.escrow(escrow_id)
            require(escrow.receipt_id == receipt_id and escrow.leg_index == len(legs),
                    "EX_SEGMENT_NOT_FUNDED", "the escrow is for another receipt or leg")
            require(escrow.status == "locked", "EX_SEGMENT_NOT_FUNDED", escrow.status)
            require(escrow.payer == match.buyer and escrow.payee == match.seller
                    and escrow.principal == match.price
                    and escrow.quote_asset == match.quote_asset,
                    "EX_SEGMENT_FUNDING_MISMATCH",
                    "the escrow terms are not the agreed terms of this leg")
            funding_status, rollback_status = "locked", "available"
        leg = Transfer(transfer_id=identifier(transfer_id, "EX_TRANSFER_REFUSED"), receipt_id=receipt_id,
                       leg_index=len(legs), seller=match.seller, buyer=match.buyer,
                       predecessor_transfer_id=legs[self._active_legs[receipt_id][-1]].transfer_id
                       if self._active_legs[receipt_id] else None,
                       price=amount(match.price, "EX_TRANSFER_REFUSED"), quote_asset=match.quote_asset,
                       sell_intent_digest=match.sell_intent_digest, buy_intent_digest=match.buy_intent_digest,
                       sell_authorization_id=sell.authorization_id, buy_authorization_id=buy.authorization_id,
                       executed_at=now, funding_status=funding_status, rollback_status=rollback_status)
        legs.append(leg)
        self._active_legs[receipt_id].append(leg.leg_index)
        self._used_nonces.add((sell.signer, sell.nonce))
        self._used_nonces.add((buy.signer, buy.nonce))
        self._record(receipt_id, "transfer-executed", {
            "transferId": leg.transfer_id, "legIndex": leg.leg_index, "seller": leg.seller,
            "buyer": leg.buyer, "price": str(leg.price), "quoteAsset": leg.quote_asset,
            "matchBasis": match.basis, "ownerIndex": len(legs), "holderIndex": self._holder_index[receipt_id],
            "registrationStatus": leg.registration_status, "fundingStatus": leg.funding_status,
            "escrowId": escrow_id})
        return leg

    def _check_price_balance(self, match, escrow_id, now):
        receipt_id = self._asset_keys.get(match.asset.key)
        receipt = self.receipt(receipt_id)
        require(match.quote_asset == receipt.price_currency, "EX_NFT0_CURRENCY_MISMATCH",
                "trade price must use NFT0 currency; conversion and substitution are unavailable")
        require(isinstance(self._price_balance_gate, NFT0PriceBalanceGate),
                "EX_PRICE_BALANCE_UNVERIFIED",
                "NFT0 currency balance is unverified; trading is disabled")
        report = self._price_balance_gate.admit(match, receipt.price_currency, escrow_id, now)
        require(report["allowed"], report["code"], report["warning"])

    def _transfer_ids(self):
        return {leg.transfer_id for legs in self._legs.values() for leg in legs}

    def _intent_by_digest(self, intent_digest):
        for intent in self._intents.values():
            if intent.digest == intent_digest:
                return intent
        raise DomainError("EX_INTENT_UNKNOWN", intent_digest)

    def leg(self, receipt_id, leg_index):
        legs = self._legs[self.receipt(receipt_id).receipt_id]
        require(0 <= leg_index < len(legs), "EX_TRANSFER_UNKNOWN", str(leg_index))
        return legs[leg_index]

    def _replace_leg(self, receipt_id, leg_index, **changes):
        legs = self._legs[receipt_id]
        legs[leg_index] = replace(legs[leg_index], **changes)
        return legs[leg_index]

    # ---------------------------------------------------------- registration

    def submit_registration(self, receipt_id, leg_index, request_id, commitment_window, now=None):
        """File the holder change for one leg through this receipt's path.

        Every hop files its own request. Submitting a later leg is allowed while
        an earlier one is still open: the lag is real and stays visible.
        """
        now = self._now(now)
        receipt = self.receipt(receipt_id)
        leg = self.leg(receipt_id, leg_index)
        require(leg_index in self._active_legs[receipt_id], "EX_WITHDRAWN_LEG_REFUSED",
                "withdrawn history cannot start another registration request")
        require(isinstance(commitment_window, int) and not isinstance(commitment_window, bool)
                and commitment_window > 0, "EX_REGISTRATION_REQUEST_REFUSED",
                "the commitment window must be a positive number of seconds")
        existing = self._requests_by_leg[receipt_id].get(leg_index)
        if existing is not None:
            require(existing.request_id == request_id, "EX_REGISTRATION_CONFLICT",
                    f"leg {leg_index} already has request {existing.request_id}")
        request = RegistrationRequest(
            request_id=request_id, receipt_id=receipt_id, transfer_id=leg.transfer_id,
            leg_index=leg_index, predecessor_transfer_id=leg.predecessor_transfer_id,
            adapter=receipt.registration_path, asset=receipt.asset, submitted_at=now,
            commitment_deadline_at=now + commitment_window,
            attempt=1 if existing is None else existing.attempt + 1)
        registrar = self.registrars[receipt.registration_path]
        acknowledgement = registrar.submit(request)
        self._requests[request_id] = request
        self._requests_by_leg[receipt_id][leg_index] = request
        if leg.registration_status == "not-submitted":
            self._replace_leg(receipt_id, leg_index, registration_status="pending")
        self._record(receipt_id, "registration-submitted", {
            "requestId": request.request_id, "transferId": request.transfer_id,
            "legIndex": leg_index, "adapter": request.adapter, "label": registrar.label,
            "simulated": True, "commitmentDeadlineAt": request.commitment_deadline_at,
            "attempt": request.attempt, "repeated": acknowledgement["repeated"],
            "handover": acknowledgement["handover"]})
        return request, acknowledgement

    def registration_request(self, request_id):
        found = self._requests.get(identifier(request_id, "EX_REGISTRATION_REQUEST_REFUSED"))
        require(found is not None, "EX_REGISTRATION_UNKNOWN_REQUEST", request_id)
        return found

    def apply_registration_result(self, evidence):
        """Apply one registrar result, or say exactly why it did not apply.

        Dispositions: ``advanced`` when the confirmed prefix grew, ``deferred``
        when the result is for a leg beyond the next expected one, ``idempotent``
        for an exact repeat, ``rejected`` when the registrar refused the hop.
        A deferred result is not a rejection.
        """
        require(isinstance(evidence, RegistrationEvidence), "EX_REGISTRATION_EVIDENCE_REFUSED", "evidence type")
        request = self.registration_request(evidence.request_id)
        receipt = self.receipt(evidence.receipt_id)
        registrar = self.registrars[receipt.registration_path]
        require(evidence.adapter == request.adapter, "EX_REGISTRATION_BINDING_REFUSED",
                f"adapter {evidence.adapter} does not match request adapter {request.adapter}")
        require(evidence.source == registrar.source, "EX_REGISTRATION_SOURCE_REFUSED",
                f"{evidence.source} is not the trusted source for {request.adapter}")
        require(evidence.asset.key == receipt.asset.key, "EX_REGISTRATION_BINDING_REFUSED",
                "the result names a different asset or network")
        require(evidence.receipt_id == request.receipt_id and evidence.transfer_id == request.transfer_id
                and evidence.leg_index == request.leg_index, "EX_REGISTRATION_BINDING_REFUSED",
                "the result does not name this request's receipt, transfer and leg")
        previous = self._applied_results.get(evidence.result_id)
        if previous is not None:
            require(previous["contentDigest"] == evidence.content_digest, "EX_REGISTRATION_CONFLICT",
                    f"result {evidence.result_id} was already applied with different content")
            self._record(evidence.receipt_id, "registration-result-idempotent", {
                "resultId": evidence.result_id, "requestId": evidence.request_id,
                "legIndex": evidence.leg_index, "disposition": "idempotent"})
            return {"disposition": "idempotent", "resultId": evidence.result_id,
                    "legIndex": evidence.leg_index, "holderIndex": self._holder_index[evidence.receipt_id],
                    "appliedAt": previous["appliedAt"]}
        receipt_id = evidence.receipt_id
        expected = self._next_registration_index(receipt_id)
        rollback = self._rollbacks[receipt_id]
        if ((rollback is not None and evidence.leg_index in rollback["affectedLegs"])
                or self.leg(receipt_id, evidence.leg_index).rollback_status == "returned"):
            # The suffix is frozen or unwound. A late success cannot revive the leg
            # or release money again; it is kept as conflict evidence.
            outcome = self.record_late_registration_conflict(receipt_id, evidence)
            self._applied_results[evidence.result_id] = {
                "contentDigest": evidence.content_digest, "appliedAt": evidence.observed_at,
                "disposition": "late-conflict"}
            return {"disposition": "late-conflict", "resultId": evidence.result_id,
                    "legIndex": evidence.leg_index,
                    "holderIndex": self._holder_index[receipt_id], **outcome}
        require(evidence.leg_index >= expected, "EX_REGISTRATION_ALREADY_CONFIRMED",
                "a new result cannot rewrite the confirmed prefix")
        if evidence.outcome == "rejected":
            disposition = "rejected"
            self._rejections[receipt_id].append(evidence)
            self._replace_leg(receipt_id, evidence.leg_index, registration_status="rejected")
        elif evidence.leg_index > expected:
            disposition = "deferred"
            self._deferred[receipt_id][evidence.leg_index] = evidence
        elif evidence.leg_index < expected:
            raise DomainError("EX_REGISTRATION_ALREADY_CONFIRMED",
                              f"leg {evidence.leg_index} is already inside the confirmed prefix")
        else:
            disposition = "advanced"
            self._confirm(receipt_id, evidence)
            self._drain_deferred(receipt_id)
        self._applied_results[evidence.result_id] = {
            "contentDigest": evidence.content_digest, "appliedAt": evidence.observed_at,
            "disposition": disposition}
        self._record(receipt_id, "registration-result", {
            "resultId": evidence.result_id, "requestId": evidence.request_id,
            "legIndex": evidence.leg_index, "outcome": evidence.outcome, "disposition": disposition,
            "source": evidence.source, "simulated": evidence.simulated,
            "holderIndex": self._holder_index[receipt_id], "ownerIndex": self.owner_index(receipt_id),
            "deferredLegs": sorted(self._deferred[receipt_id])})
        return {"disposition": disposition, "resultId": evidence.result_id,
                "legIndex": evidence.leg_index, "holderIndex": self._holder_index[receipt_id],
                "deferredLegs": tuple(sorted(self._deferred[receipt_id])),
                "appliedAt": evidence.observed_at}

    def _confirm(self, receipt_id, evidence):
        self._replace_leg(receipt_id, evidence.leg_index, registration_status="confirmed")
        self._holder_index[receipt_id] = evidence.leg_index + 1

    def _drain_deferred(self, receipt_id):
        """Apply buffered results that the filled gap has now made contiguous."""
        buffered = self._deferred[receipt_id]
        while True:
            nxt = self._next_registration_index(receipt_id)
            rollback = self._rollbacks[receipt_id]
            if rollback is not None and nxt in rollback["affectedLegs"]:
                return
            evidence = buffered.pop(nxt, None)
            if evidence is None:
                return
            self._confirm(receipt_id, evidence)
            self._record(receipt_id, "registration-result-drained", {
                "resultId": evidence.result_id, "legIndex": evidence.leg_index,
                "disposition": "advanced", "holderIndex": self._holder_index[receipt_id]})

    def deferred_legs(self, receipt_id):
        self.receipt(receipt_id)
        return tuple(sorted(self._deferred[receipt_id]))

    def overdue_requests(self, receipt_id, now=None):
        """Requests whose agreed commitment window has passed.

        Reporting that the window passed is all this does. It is not a rejection,
        not a settlement decision and not advice about what to do next.
        """
        now = self._now(now)
        self.receipt(receipt_id)
        overdue = []
        for leg_index, request in sorted(self._requests_by_leg[receipt_id].items()):
            leg = self.leg(receipt_id, leg_index)
            if leg.registration_status == "pending" and now >= request.commitment_deadline_at:
                overdue.append({"legIndex": leg_index, "requestId": request.request_id,
                                "transferId": request.transfer_id,
                                "commitmentDeadlineAt": request.commitment_deadline_at,
                                "observedAt": now, "meaning": "commitment-window-passed"})
        return tuple(overdue)

    # ------------------------------------------------- segmented settlement

    def escrow(self, escrow_id):
        found = self._escrows.get(identifier(escrow_id, "EX_ESCROW_REFUSED"))
        require(found is not None, "EX_ESCROW_UNKNOWN", escrow_id)
        return found

    def escrow_for_leg(self, receipt_id, leg_index):
        self.receipt(receipt_id)
        found = self._escrow_by_leg[receipt_id].get(leg_index)
        require(found is not None, "EX_ESCROW_UNKNOWN", f"leg {leg_index}")
        return self._escrows[found]

    def lock_escrow(self, match, escrow_id, now=None):
        """Put this leg's buyer's own money in its own position.

        The position is for the leg this match would create next, and it is
        funded before that leg exists: no trade and no registration request is
        formed until the money is here.
        """
        now = self._now(now)
        match = self._check_match_binding(match, now)
        receipt_id = self._asset_keys.get(match.asset.key)
        require(receipt_id is not None, "EX_ASSET_UNKNOWN", str(match.asset.key))
        self._check_trade_open(receipt_id, now)
        require(self.owner_of(receipt_id) == match.seller, "EX_TRADE_HEAD_MOVED",
                "only the current owner may fund the next transfer")
        leg_index = len(self._legs[receipt_id])
        require(leg_index not in self._escrow_by_leg[receipt_id], "EX_ESCROW_DUPLICATE_REFUSED",
                f"leg {leg_index} is already funded")
        require(escrow_id not in self._escrows, "EX_ESCROW_DUPLICATE_REFUSED", escrow_id)
        self._check_price_balance(match, None, now)
        position = EscrowPosition(escrow_id=escrow_id, receipt_id=receipt_id, leg_index=leg_index,
                                  payer=match.buyer, payee=match.seller,
                                  quote_asset=match.quote_asset, principal=match.price,
                                  locked_at=now)
        self._escrows[escrow_id] = position
        self._escrow_by_leg[receipt_id][leg_index] = escrow_id
        self._record(receipt_id, "escrow-locked", {
            "escrowId": escrow_id, "legIndex": leg_index, "payer": position.payer,
            "payee": position.payee, "principal": str(position.principal),
            "quoteAsset": position.quote_asset, "status": position.status})
        return position

    def _update_escrow(self, escrow_id, **changes):
        self._escrows[escrow_id] = replace(self._escrows[escrow_id], **changes)
        return self._escrows[escrow_id]

    def segment_release_state(self, receipt_id, leg_index, now=None):
        """Whether this segment meets its own release condition, and why.

        The condition is positional: owner and holder have both reached this
        leg's buyer or a later position in the same chain. A later leg still
        pending never freezes an earlier one that already qualifies.
        """
        now = self._now(now)
        self.receipt(receipt_id)
        leg = self.leg(receipt_id, leg_index)
        owner_index, holder_index = self.owner_index(receipt_id), self._holder_index[receipt_id]
        reasons = []
        if leg_index not in self._active_legs[receipt_id]:
            reasons.append("EX_WITHDRAWN_LEG_REFUSED")
        if owner_index < leg_index + 1:
            reasons.append("EX_OWNER_POSITION_NOT_REACHED")
        if holder_index < leg_index + 1:
            reasons.append("EX_HOLDER_POSITION_NOT_REACHED")
        if leg.rollback_status in ("in-progress", "returned"):
            reasons.append("EX_SEGMENT_ROLLBACK_OPEN")
        if leg.registration_status != "confirmed":
            reasons.append("EX_SEGMENT_REGISTRATION_NOT_CONFIRMED")
        escrow_id = self._escrow_by_leg[receipt_id].get(leg_index)
        if escrow_id is None:
            reasons.append("EX_SEGMENT_NOT_FUNDED")
        else:
            escrow = self._escrows[escrow_id]
            if escrow.status == "released":
                reasons.append("EX_SEGMENT_ALREADY_RELEASED")
            elif escrow.status == "refunded":
                reasons.append("EX_SEGMENT_REFUNDED")
        return {"receiptId": receipt_id, "legIndex": leg_index, "escrowId": escrow_id,
                "ownerIndex": owner_index, "holderIndex": holder_index,
                "eligible": reasons == [], "reasons": tuple(reasons), "observedAt": now}

    def _check_release_authority(self, receipt_id, leg_index, authority):
        """Bind the evidence to this source, asset, segment and journal, or refuse."""
        require(isinstance(authority, ReleaseAuthority), "EX_RELEASE_AUTHORITY_REFUSED",
                "release needs bound authority evidence, not a signature or a settlement id")
        receipt = self.receipt(receipt_id)
        leg = self.leg(receipt_id, leg_index)
        escrow = self.escrow_for_leg(receipt_id, leg_index)
        require(authority.source in self._release_sources, "EX_RELEASE_SOURCE_REFUSED",
                f"{authority.source} is not a verified release source")
        require(authority.asset.key == receipt.asset.key, "EX_RELEASE_BINDING_REFUSED",
                "the authority names a different asset or network")
        require(authority.receipt_id == receipt_id and authority.leg_index == leg_index
                and authority.transfer_id == leg.transfer_id, "EX_RELEASE_BINDING_REFUSED",
                "the authority names a different receipt, leg or transfer")
        expected = segment_binding(receipt.asset, receipt_id, leg_index, leg.transfer_id,
                                   escrow.payer, escrow.payee, escrow.principal, escrow.quote_asset,
                                   authority.journal_reference)
        require(authority.binding == expected, "EX_RELEASE_BINDING_REFUSED",
                "the authority's segment binding does not match this segment's facts")
        return escrow

    def _attempt_payment(self, escrow, payment_key, intent):
        # Persist the attempt before crossing the adapter boundary. A raised
        # error or invalid response cannot make an attempted action look new.
        self._update_escrow(escrow.escrow_id, payment_key=payment_key,
                            payment_intent=intent, payment_status="unknown")
        if intent == "release":
            self._replace_leg(escrow.receipt_id, escrow.leg_index,
                              funding_status="release-outcome-unknown")
        self._record(escrow.receipt_id, "payment-attempt-started", {
            "escrowId": escrow.escrow_id, "paymentKey": payment_key,
            "intent": intent, "paymentStatus": "unknown"})
        payer, payee = ((escrow.payer, escrow.payee) if intent == "release"
                        else (escrow.payee, escrow.payer))
        return self.payments.pay(payment_key, payer, payee, escrow.quote_asset, escrow.principal)

    def _check_payment_record(self, record, escrow, payment_key, intent):
        require(intent in ("release", "refund"), "EX_PAYMENT_INTENT_CONFLICT",
                "a payment result needs its original operation intent")
        payer, payee = ((escrow.payer, escrow.payee) if intent == "release"
                        else (escrow.payee, escrow.payer))
        require(isinstance(record, dict)
                and record.get("paymentKey") == payment_key
                and record.get("payer") == payer and record.get("payee") == payee
                and record.get("quoteAsset") == escrow.quote_asset
                and record.get("principal") == escrow.principal,
                "EX_PAYMENT_SUBSTITUTION_REFUSED", "payment evidence does not match this operation")
        require(record.get("status") in ("settled", "failed", "unknown"),
                "EX_PAYMENT_REFUSED", "unknown payment status")
        return record

    def release_segment(self, receipt_id, leg_index, authority, now=None):
        """Release one segment's own money to that segment's own payee.

        Nothing is paid from another leg's position, and the payment is keyed so
        a retry cannot move money twice. A payment that fails or returns an
        unknown outcome leaves the position locked and recorded: the segment is
        not swept into a refund suffix just because its payment is late.
        """
        now = self._now(now)
        state = self.segment_release_state(receipt_id, leg_index, now)
        require(state["eligible"], "EX_SEGMENT_NOT_RELEASABLE", ",".join(state["reasons"]))
        escrow = self._check_release_authority(receipt_id, leg_index, authority)
        require(self.payments is not None, "EX_PAYMENT_ADAPTER_REQUIRED",
                "releasing needs the optional payment adapter to be configured")
        require(escrow.payment_intent in (None, "release"), "EX_PAYMENT_INTENT_CONFLICT",
                "a refund operation cannot become a release")
        payment_key = escrow.payment_key or f"release:{escrow.escrow_id}"
        # Ask what already happened before sending anything. An unknown first
        # attempt is resolved by enquiry, never by a second payment.
        known = self.payments.lookup(payment_key)
        if known is not None:
            self._check_payment_record(known, escrow, payment_key, "release")
        require(known is not None or escrow.payment_status is None,
                "EX_PAYMENT_OUTCOME_UNRESOLVED", "an attempted payment needs an observed outcome")
        if known is not None and known["status"] == "failed":
            require(known.get("effect") == "not-applied" and known.get("retryable") is True,
                    "EX_PAYMENT_OUTCOME_UNRESOLVED", "retry needs a confirmed no-effect failure")
        record = known if known is not None and known["status"] in ("settled", "unknown") \
            else self._attempt_payment(escrow, payment_key, "release")
        self._check_payment_record(record, escrow, payment_key, "release")
        status = record["status"]
        if status == "settled":
            escrow = self._update_escrow(escrow.escrow_id, status="released", settled_at=now,
                                         payment_key=payment_key, payment_status=status,
                                         payment_intent="release",
                                         payment_reference=record["reference"])
            self._replace_leg(receipt_id, leg_index, funding_status="released",
                              rollback_status="detached")
        else:
            escrow = self._update_escrow(escrow.escrow_id, payment_key=payment_key,
                                         payment_status=status, payment_intent="release",
                                         payment_reference=record.get("reference"))
            self._replace_leg(receipt_id, leg_index,
                              funding_status="release-failed" if status == "failed"
                              else "release-outcome-unknown")
        self._record(receipt_id, "segment-release-attempt", {
            "legIndex": leg_index, "escrowId": escrow.escrow_id, "authorityId": authority.authority_id,
            "source": authority.source, "journalReference": authority.journal_reference,
            "paymentKey": payment_key, "paymentStatus": status,
            "principal": str(escrow.principal), "payee": escrow.payee,
            "escrowStatus": escrow.status, "rollbackStatus": self.leg(receipt_id, leg_index).rollback_status,
            "registrationConfirmed": True})
        return {"legIndex": leg_index, "escrowId": escrow.escrow_id, "paymentStatus": status,
                "escrowStatus": escrow.status, "released": escrow.status == "released",
                "paymentKey": payment_key, "principal": escrow.principal,
                "payee": escrow.payee, "observedAt": now}

    def settle_eligible_segments(self, receipt_id, authorities, now=None):
        """Release every segment that already qualifies, in prefix order.

        ``authorities`` maps a leg index to its own authority evidence. A
        segment with no evidence is skipped and reported, never released.
        """
        now = self._now(now)
        self.receipt(receipt_id)
        outcomes = []
        for leg_index in self._active_legs[receipt_id]:
            state = self.segment_release_state(receipt_id, leg_index, now)
            if not state["eligible"]:
                outcomes.append({"legIndex": leg_index, "released": False,
                                 "reasons": state["reasons"]})
                continue
            authority = authorities.get(leg_index)
            if authority is None:
                outcomes.append({"legIndex": leg_index, "released": False,
                                 "reasons": ("EX_RELEASE_AUTHORITY_MISSING",)})
                continue
            outcomes.append(self.release_segment(receipt_id, leg_index, authority, now))
        return tuple(outcomes)

    def resume_payments(self, receipt_id):
        """Query every unresolved payment before anything is retried.

        A restart must not read ``unknown`` as ``failed``, and it must not send a
        second payment to repair an unknown first one. The outcome it records is
        the one the payment was actually for: an enquiry about a refund never
        turns into a release.
        """
        self.receipt(receipt_id)
        resumed = []
        for leg_index, escrow_id in sorted(self._escrow_by_leg[receipt_id].items()):
            escrow = self._escrows[escrow_id]
            if escrow.payment_key is None or escrow.terminal:
                continue
            record = self.payments.lookup(escrow.payment_key) if self.payments else None
            if record is None:
                resumed.append({"legIndex": leg_index, "escrowId": escrow_id,
                                "paymentStatus": escrow.payment_status,
                                "action": ("unknown outcome; keep the original operation pending"
                                           if escrow.payment_status == "unknown" else
                                           "no payment record; restore evidence before retrying the original operation")})
                continue
            self._check_payment_record(record, escrow, escrow.payment_key, escrow.payment_intent)
            if record["status"] == "settled":
                refund = escrow.payment_intent == "refund"
                escrow = self._update_escrow(
                    escrow_id, status="refunded" if refund else "released",
                    refunded_at=record["observedAt"] if refund else None,
                    settled_at=None if refund else record["observedAt"],
                    payment_status="settled", payment_reference=record["reference"])
                self._replace_leg(receipt_id, leg_index,
                                  funding_status="refunded" if refund else "released",
                                  rollback_status="returned" if refund else "detached")
                resumed.append({"legIndex": leg_index, "escrowId": escrow_id,
                                "paymentStatus": "settled", "intent": escrow.payment_intent,
                                "action": "the enquiry found the payment had settled; recorded, not resent"})
            else:
                resumed.append({"legIndex": leg_index, "escrowId": escrow_id,
                                "paymentStatus": record["status"],
                                "action": "still unresolved; no second payment is sent"})
            self._record(receipt_id, "payment-enquiry", {
                "legIndex": leg_index, "escrowId": escrow_id, "paymentStatus": record["status"],
                "secondPaymentSent": False})
        return tuple(resumed)

    def record_gas(self, receipt_id, leg_index, kind, spent, shared_with=(), note=None):
        """Record actual gas this leg's buyer bore.

        The product rule is settled: each leg's buyer bears that leg's trade,
        refund and return gas, and a refusal elsewhere does not move that
        responsibility. How a shared on-chain operation is apportioned, and how
        a fee is actually deducted, are still open, so this records the shared
        set and refuses to charge a shared operation to every leg at full
        amount. No apportionment formula is treated here as approved.
        """
        self.receipt(receipt_id)
        leg = self.leg(receipt_id, leg_index)
        escrow = self.escrow_for_leg(receipt_id, leg_index)
        amount(spent, "EX_GAS_REFUSED")
        identifier(kind, "EX_GAS_REFUSED")
        shared = tuple(sorted(set(shared_with) | {leg_index}))
        for other in shared:
            self.leg(receipt_id, other)
        entry = {"kind": kind, "legIndex": leg_index, "bearer": escrow.payer,
                 "asset": "ETH", "unit": "wei",
                 "chainId": self.receipt(receipt_id).asset.chain_id,
                 "amount": spent, "sharedWith": shared,
                 "sharedOperation": len(shared) > 1,
                 "apportionment": "undecided" if len(shared) > 1 else "single-leg",
                 "note": note}
        if len(shared) > 1:
            # A shared operation is recorded once against the leg that is paying
            # for it here. Charging every sharer the full amount is exactly what
            # the requirement forbids, and the split rule is not ours to invent.
            already = [e for index in shared for e in self._gas[receipt_id].get(index, ())
                       if e["kind"] == kind and e["sharedWith"] == shared]
            require(already == [], "EX_GAS_DOUBLE_CHARGE_REFUSED",
                    f"the shared {kind} operation for legs {shared} is already recorded once")
        self._gas[receipt_id].setdefault(leg_index, [])
        self._gas[receipt_id][leg_index].append(entry)
        self._update_escrow(escrow.escrow_id,
                            gas_record=tuple(self._escrows[escrow.escrow_id].gas_record) + (entry,))
        self._record(receipt_id, "gas-recorded", dict(entry, amount=str(spent)))
        return entry

    def reconciliation(self, receipt_id, now=None):
        """Per-segment principal, gas and net, with no figure merged.

        Release and refund are reported as the mutually exclusive outcomes they
        are, and a segment whose payment has not settled is shown as unsettled
        rather than as paid.
        """
        now = self._now(now)
        self.receipt(receipt_id)
        segments = []
        for leg in self._legs[receipt_id]:
            escrow_id = self._escrow_by_leg[receipt_id].get(leg.leg_index)
            escrow = self._escrows.get(escrow_id) if escrow_id else None
            gas = tuple(self._gas[receipt_id].get(leg.leg_index, ()))
            gas_total = sum(entry["amount"] for entry in gas)
            segments.append({
                "legIndex": leg.leg_index, "transferId": leg.transfer_id,
                "seller": leg.seller, "buyer": leg.buyer,
                "principal": str(leg.price), "quoteAsset": leg.quote_asset,
                "principalAsset": leg.quote_asset, "principalUnit": "base-units",
                "escrowId": escrow_id,
                "escrowStatus": escrow.status if escrow else "not-funded",
                "paymentStatus": escrow.payment_status if escrow else None,
                "released": bool(escrow and escrow.status == "released"),
                "refunded": bool(escrow and escrow.status == "refunded"),
                "registrationStatus": leg.registration_status,
                "fundingStatus": leg.funding_status,
                "rollbackStatus": leg.rollback_status,
                "gasEntries": gas,
                "gasBorneBy": leg.buyer,
                "gasAsset": "ETH", "gasUnit": "wei",
                "gasTotal": str(gas_total),
                "netToPayee": str(leg.price) if escrow and escrow.status == "released" else "0",
                "netToPayer": str(leg.price) if escrow and escrow.status == "refunded" else "0",
            })
        return {"receiptId": receipt_id, "observedAt": now, "segments": tuple(segments),
                "gasApportionmentForSharedOperations": "undecided; recorded once, never charged in full to each leg",
                "releaseAndRefundMutuallyExclusive": True}

    # ---------------------------------------------------- suffix rollback

    def rollback_boundary(self, receipt_id):
        """Where a return stops: the end of the finalized prefix.

        Confirmed registration protects the prefix even when its release is
        pending or unknown. Payment recovery stays independent of the suffix;
        a late payment never changes a release into a refund.
        """
        receipt = self.receipt(receipt_id)
        legs = self._legs[receipt_id]
        boundary_index, boundary_account = 0, receipt.origin_account
        for active_index in self._active_legs[receipt_id]:
            leg = legs[active_index]
            if leg.registration_status == "confirmed" and leg.leg_index < self._holder_index[receipt_id]:
                boundary_index, boundary_account = leg.leg_index + 1, leg.buyer
            else:
                break
        return {"boundaryIndex": boundary_index, "boundaryAccount": boundary_account,
                "finalizedPrefixLegs": sum(
                    self.leg(receipt_id, i).registration_status == "confirmed"
                    for i in self._active_legs[receipt_id])}

    def deadline_boundary(self, receipt_id):
        """Where a post-deadline return stops: the last confirmed holder.

        Unfinished segments return to the last confirmed holder. Confirmed
        segments remain protected while any payment recovery is pending.
        """
        receipt = self.receipt(receipt_id)
        index = self._holder_index[receipt_id]
        settled = self.rollback_boundary(receipt_id)["boundaryIndex"]
        require(index >= settled, "EX_ROLLBACK_PREFIX_IMMUTABLE",
                "the confirmed holder is behind the settled prefix")
        return {"boundaryIndex": index, "boundaryAccount": self.holder_of(receipt_id),
                "finalizedPrefixLegs": sum(
                    self.leg(receipt_id, i).registration_status == "confirmed"
                    for i in self._active_legs[receipt_id])}

    def rollback_interval(self, receipt_id, refused_leg_index):
        """The legs a refusal at ``refused_leg_index`` may unwind.

        Only the still-unresolved suffix, from the boundary to the current head.
        A refusal inside the finalized prefix is refused outright rather than
        rewriting a completed segment.
        """
        self.receipt(receipt_id)
        self.leg(receipt_id, refused_leg_index)
        require(refused_leg_index in self._active_legs[receipt_id], "EX_WITHDRAWN_LEG_REFUSED",
                "a prior withdrawn leg cannot trigger a new rollback")
        boundary = self.rollback_boundary(receipt_id)
        require(refused_leg_index >= boundary["boundaryIndex"], "EX_ROLLBACK_PREFIX_IMMUTABLE",
                f"leg {refused_leg_index} is inside the finalized prefix")
        affected = tuple(i for i in self._active_legs[receipt_id]
                         if i >= boundary["boundaryIndex"])
        return {"affectedLegs": affected, **boundary}

    def _check_rollback_authority(self, receipt_id, refused_leg_index, authority, interval):
        require(isinstance(authority, RollbackAuthority), "EX_ROLLBACK_AUTHORITY_REFUSED",
                "a rollback needs bound authority evidence")
        receipt = self.receipt(receipt_id)
        require(authority.source in self._rollback_sources, "EX_ROLLBACK_SOURCE_REFUSED",
                f"{authority.source} is not a verified rollback source")
        require(authority.asset.key == receipt.asset.key, "EX_ROLLBACK_BINDING_REFUSED",
                "the authority names a different asset or network")
        require(authority.receipt_id == receipt_id
                and authority.refused_leg_index == refused_leg_index,
                "EX_ROLLBACK_BINDING_REFUSED", "the authority names a different receipt or leg")
        require(authority.boundary_account == interval["boundaryAccount"],
                "EX_ROLLBACK_BINDING_REFUSED",
                "the authority names a different return boundary than the finalized prefix")
        expected = rollback_binding(receipt.asset, receipt_id, refused_leg_index,
                                    interval["boundaryAccount"], interval["affectedLegs"])
        require(authority.binding == expected, "EX_ROLLBACK_BINDING_REFUSED",
                "the authority's interval binding does not match this interval")

    def begin_rollback(self, receipt_id, refused_leg_index, authority, trigger="registrar-refusal",
                       now=None):
        """Open a rollback over the unresolved suffix and plan its steps.

        ``trigger`` selects the boundary the requirements define for that cause:
        both causes preserve the confirmed prefix, including pending releases.

        Nothing moves here. Each step carries its own idempotency key so an
        interrupted rollback resumes without repeating a refund or a return.
        """
        now = self._now(now)
        require(trigger in ("registrar-refusal", "deadline"), "EX_ROLLBACK_TRIGGER_REFUSED", trigger)
        require(self._rollbacks[receipt_id] is None, "EX_ROLLBACK_ALREADY_OPEN",
                "a rollback is already open for this receipt")
        receipt_record = self.receipt(receipt_id)
        if trigger == "registrar-refusal":
            leg = self.leg(receipt_id, refused_leg_index)
            require(leg.registration_status == "rejected", "EX_ROLLBACK_TRIGGER_REFUSED",
                    "a rollback needs a recorded registrar refusal for that leg")
            interval = self.rollback_interval(receipt_id, refused_leg_index)
        else:
            require(now >= receipt_record.trade_stop_at, "EX_ROLLBACK_TRIGGER_REFUSED",
                    "the trading deadline has not passed")
            boundary = self.deadline_boundary(receipt_id)
            interval = {"affectedLegs": tuple(i for i in self._active_legs[receipt_id]
                                               if i >= boundary["boundaryIndex"]),
                        **boundary}
            require(interval["affectedLegs"] != (), "EX_ROLLBACK_TRIGGER_REFUSED",
                    "owner and the last confirmed holder agree; there is nothing unfinished")
            refused_leg_index = interval["affectedLegs"][0]
        self._check_rollback_authority(receipt_id, refused_leg_index, authority, interval)
        steps = []
        for index in interval["affectedLegs"]:
            affected = self.leg(receipt_id, index)
            require(affected.rollback_status != "detached", "EX_ROLLBACK_PREFIX_IMMUTABLE",
                    f"leg {index} is detached and cannot be unwound")
            escrow_id = self._escrow_by_leg[receipt_id].get(index)
            if escrow_id is None:
                continue
            escrow = self._escrows[escrow_id]
            require(escrow.status != "released" and escrow.payment_intent != "release",
                    "EX_ROLLBACK_PREFIX_IMMUTABLE", "a release cannot become a refund")
            steps.append(RollbackStep(step_id=f"{authority.authority_id}:refund:{index}",
                                      kind="refund", receipt_id=receipt_id, leg_index=index,
                                      key=f"refund:{escrow_id}"))
        for index in interval["affectedLegs"]:
            self._replace_leg(receipt_id, index, rollback_status="in-progress")
        steps.append(RollbackStep(step_id=f"{authority.authority_id}:asset-return",
                                  kind="asset-return", receipt_id=receipt_id,
                                  leg_index=interval["boundaryIndex"],
                                  key=f"return:{receipt_id}:{authority.authority_id}"))
        self._rollbacks[receipt_id] = {
            "authorityId": authority.authority_id, "source": authority.source,
            "refusedLegIndex": refused_leg_index,
            "trigger": ("registrar refusal for that leg" if trigger == "registrar-refusal"
                        else "trading deadline passed with the holder behind the owner"),
            "triggerKind": trigger,
            "boundaryIndex": interval["boundaryIndex"],
            "boundaryAccount": interval["boundaryAccount"],
            "finalizedPrefixLegs": interval["finalizedPrefixLegs"],
            "affectedLegs": interval["affectedLegs"], "steps": steps,
            "state": "in-progress", "openedAt": now, "conflicts": []}
        self._record(receipt_id, "rollback-opened", {
            "authorityId": authority.authority_id, "triggerKind": trigger,
            "refusedLegIndex": refused_leg_index,
            "affectedLegs": list(interval["affectedLegs"]),
            "boundaryIndex": interval["boundaryIndex"],
            "boundaryAccount": interval["boundaryAccount"],
            "finalizedPrefixLegs": interval["finalizedPrefixLegs"],
            "plannedSteps": [{"stepId": step.step_id, "kind": step.kind,
                              "legIndex": step.leg_index} for step in steps],
            "withdrawnMechanismsNotUsed": list(WITHDRAWN_MECHANISMS)})
        return self._rollbacks[receipt_id]

    def _gas_available(self, account):
        return self._budgets.get(account)

    def advance_rollback(self, receipt_id, now=None):
        """Run the pending steps once each, and report what is still open.

        Every step asks what already happened before acting, so a resumed
        rollback never refunds twice and never returns the asset twice. A step
        the bearer cannot pay for is blocked and resumable; nothing is taken
        into custody and nothing is liquidated to cover it.
        """
        now = self._now(now)
        state = self._rollbacks[receipt_id]
        require(state is not None, "EX_ROLLBACK_NOT_OPEN", receipt_id)
        require(self.payments is not None and self.asset_control is not None,
                "EX_ROLLBACK_ADAPTERS_REQUIRED",
                "a rollback needs the payment adapter and the asset-return control")
        receipt = self.receipt(receipt_id)
        updated = []
        for step in state["steps"]:
            if step.status == "done":
                updated.append(step)
                continue
            if step.kind == "refund":
                updated.append(self._advance_refund(receipt_id, step, now))
            else:
                updated.append(self._advance_return(receipt_id, receipt, state, step, now))
        state["steps"] = updated
        outstanding = [step for step in updated if step.status != "done"]
        blocked = [step for step in updated if step.status == "blocked"]
        state["state"] = ("complete" if not outstanding else
                          "blocked" if blocked else "in-progress")
        self._record(receipt_id, "rollback-advanced", {
            "authorityId": state["authorityId"], "state": state["state"],
            "stepsDone": [s.step_id for s in updated if s.status == "done"],
            "stepsOutstanding": [s.step_id for s in outstanding],
            "stepsBlocked": [s.step_id for s in blocked]})
        return self.rollback_report(receipt_id, now)

    def _advance_refund(self, receipt_id, step, now):
        escrow = self.escrow_for_leg(receipt_id, step.leg_index)
        if escrow.status == "refunded":
            return replace(step, status="done", detail=(("already", "refunded"),))
        require(escrow.status != "released" and escrow.payment_intent != "release"
                and self.leg(receipt_id, step.leg_index).registration_status != "confirmed",
                "EX_ROLLBACK_PREFIX_IMMUTABLE",
                f"leg {step.leg_index} is protected and is not refundable")
        require(escrow.payment_key in (None, step.key), "EX_PAYMENT_INTENT_CONFLICT",
                "recovery must retain the original operation key")
        # The refund goes to this leg's own original buyer, for this leg's own
        # unreleased principal. Nothing is netted against another segment.
        known = self.payments.lookup(step.key)
        if known is not None:
            self._check_payment_record(known, escrow, step.key, "refund")
        require(known is not None or escrow.payment_status is None,
                "EX_PAYMENT_OUTCOME_UNRESOLVED", "an attempted refund needs an observed outcome")
        if known is not None and known["status"] == "failed":
            require(known.get("effect") == "not-applied" and known.get("retryable") is True,
                    "EX_PAYMENT_OUTCOME_UNRESOLVED", "retry needs a confirmed no-effect failure")
        record = known if known is not None and known["status"] in ("settled", "unknown") \
            else self._attempt_payment(escrow, step.key, "refund")
        self._check_payment_record(record, escrow, step.key, "refund")
        if record["status"] == "settled":
            self._update_escrow(escrow.escrow_id, status="refunded", refunded_at=now,
                                payment_key=step.key, payment_status="settled",
                                payment_intent="refund",
                                payment_reference=record["reference"])
            self._replace_leg(receipt_id, step.leg_index, funding_status="refunded",
                              rollback_status="returned")
            self._record(receipt_id, "segment-refunded", {
                "legIndex": step.leg_index, "escrowId": escrow.escrow_id,
                "paidTo": escrow.payer, "principal": str(escrow.principal),
                "paymentKey": step.key, "paymentStatus": "settled"})
            return replace(step, status="done",
                           detail=(("paidTo", escrow.payer), ("principal", str(escrow.principal))))
        self._update_escrow(escrow.escrow_id, payment_key=step.key,
                            payment_status=record["status"], payment_intent="refund",
                            payment_reference=record.get("reference"))
        self._record(receipt_id, "segment-refund-attempt", {
            "legIndex": step.leg_index, "escrowId": escrow.escrow_id,
            "paymentStatus": record["status"], "secondPaymentSent": False})
        return replace(step, status="blocked", detail=(("paymentStatus", record["status"]),))

    def _advance_return(self, receipt_id, receipt, state, step, now):
        destination = state["boundaryAccount"]
        current = self.owner_of(receipt_id)
        if current == destination:
            # Equal addresses can be different occurrences in a circular chain.
            for index in state["affectedLegs"]:
                self._replace_leg(receipt_id, index, rollback_status="returned")
            self._returned_to[receipt_id] = (state["boundaryIndex"], destination)
            self._record(receipt_id, "asset-returned", {
                "stepId": step.step_id, "fromAccount": current, "toAccount": destination,
                "operations": 0, "boundaryIndex": state["boundaryIndex"]})
            return replace(step, status="done", detail=(("already", "at the boundary"),))
        bearer = self.leg(receipt_id, self.recorded_legs(receipt_id) - 1).buyer
        available = self._gas_available(bearer)
        if available is not None and available <= 0:
            # A shortfall is a blocked, resumable state. It is never a reason to
            # take custody, force a sale or liquidate.
            self._record(receipt_id, "rollback-step-blocked", {
                "stepId": step.step_id, "reason": "EX_GAS_BUDGET_EXHAUSTED", "bearer": bearer,
                "custodyTaken": False, "forcedSale": False, "liquidation": False,
                "resumable": True})
            return replace(step, status="blocked", detail=(("reason", "EX_GAS_BUDGET_EXHAUSTED"),
                                                           ("bearer", bearer)))
        known = self.asset_control.lookup(step.key)
        record = known if known is not None and known["status"] in ("returned", "unknown") \
            else self.asset_control.return_asset(step.key, current, destination, receipt.asset)
        if record["status"] != "returned":
            self._record(receipt_id, "asset-return-attempt", {
                "stepId": step.step_id, "status": record["status"], "secondReturnSent": False})
            return replace(step, status="blocked", detail=(("returnStatus", record["status"]),))
        # The chain head is now the boundary account. The legs above it stay in
        # history; they are marked returned rather than erased.
        for index in state["affectedLegs"]:
            if self.leg(receipt_id, index).rollback_status == "in-progress":
                self._replace_leg(receipt_id, index, rollback_status="returned")
        self._returned_to[receipt_id] = (state["boundaryIndex"], destination)
        self._record(receipt_id, "asset-returned", {
            "stepId": step.step_id, "fromAccount": record["fromAccount"],
            "toAccount": record["toAccount"], "operations": record["operations"],
            "walkedIntermediateWallets": record["walkedIntermediateWallets"],
            "requiredIntermediateGas": record["requiredIntermediateGas"],
            "boundaryIndex": state["boundaryIndex"]})
        return replace(step, status="done", detail=(("toAccount", destination),
                                                     ("operations", "1")))

    def asset_position_after_rollback(self, receipt_id):
        """Who holds the receipt once a rollback returned it, by record.

        The trade legs above the boundary are preserved as history. This reports
        the boundary the return stopped at rather than deleting the chain.
        """
        state = self._rollbacks[self.receipt(receipt_id).receipt_id]
        if state is None:
            return {"returned": False, "account": self.owner_of(receipt_id)}
        returned = any(step.kind == "asset-return" and step.status == "done"
                       for step in state["steps"])
        return {"returned": returned,
                "account": state["boundaryAccount"] if returned else self.owner_of(receipt_id),
                "boundaryIndex": state["boundaryIndex"],
                "historyPreserved": True}

    def record_late_registration_conflict(self, receipt_id, evidence):
        """A success that arrives after the suffix was unwound.

        It cannot revive the leg and it cannot release funds again. The
        conflicting evidence is kept and the matter goes to investigation.
        """
        state = self._rollbacks[self.receipt(receipt_id).receipt_id]
        archived = None
        if state is None or evidence.leg_index not in state["affectedLegs"]:
            archived = next((item for item in reversed(self._rollback_history[receipt_id])
                             if evidence.leg_index in item["state"]["affectedLegs"]), None)
            state = archived["state"] if archived is not None else None
        require(state is not None, "EX_ROLLBACK_NOT_OPEN", receipt_id)
        state["conflicts"].append({"resultId": evidence.result_id, "legIndex": evidence.leg_index,
                                   "outcome": evidence.outcome, "observedAt": evidence.observed_at})
        self._record(receipt_id, "late-result-conflict", {
            "resultId": evidence.result_id, "legIndex": evidence.leg_index,
            "outcome": evidence.outcome, "legRevived": False, "fundsReleasedAgain": False,
            "disposition": "retained as conflict evidence for investigation"})
        if archived is not None:
            archived["report"]["conflicts"] = tuple(deepcopy(state["conflicts"]))
        return {"legRevived": False, "fundsReleasedAgain": False,
                "conflicts": tuple(state["conflicts"])}

    def rollback_report(self, receipt_id, now=None):
        """Trigger, interval, last finalized position, money, asset and steps.

        ``complete`` appears only when every step has its own evidence.
        """
        now = self._now(now)
        state = self._rollbacks[self.receipt(receipt_id).receipt_id]
        if state is None:
            return {"receiptId": receipt_id, "open": False, "state": None,
                    "complete": False, "observedAt": now}
        funds = []
        for index in state["affectedLegs"]:
            escrow_id = self._escrow_by_leg[receipt_id].get(index)
            escrow = self._escrows.get(escrow_id) if escrow_id else None
            leg = self.leg(receipt_id, index)
            gas = tuple(self._gas[receipt_id].get(index, ()))
            gas_total = sum(entry["amount"] for entry in gas)
            funds.append({"legIndex": index, "originalBuyer": leg.buyer,
                          "principal": str(leg.price),
                          "principalAsset": leg.quote_asset, "principalUnit": "base-units",
                          "escrowStatus": escrow.status if escrow else "not-funded",
                          "paymentStatus": escrow.payment_status if escrow else None,
                          "refundedToOriginalBuyer": bool(escrow and escrow.status == "refunded"),
                          "gasBorneBy": leg.buyer, "gasTotal": str(gas_total),
                          "gasAsset": "ETH", "gasUnit": "wei",
                          # Principal and gas are different assets. Consumed ETH
                          # remains charged separately; it cannot reduce a token refund.
                          "netToOriginalBuyer": str(leg.price)
                          if escrow and escrow.status == "refunded" else "0",
                          "rollbackStatus": leg.rollback_status})
        outstanding = [{"stepId": step.step_id, "kind": step.kind, "legIndex": step.leg_index,
                        "status": step.status, "detail": dict(step.detail)}
                       for step in state["steps"] if step.status != "done"]
        asset = self.asset_position_after_rollback(receipt_id)
        return {
            "receiptId": receipt_id, "open": True, "state": state["state"],
            "complete": state["state"] == "complete",
            "trigger": state["trigger"], "refusedLegIndex": state["refusedLegIndex"],
            "authorityId": state["authorityId"], "source": state["source"],
            "affectedLegs": state["affectedLegs"],
            "finalizedPrefixLegs": state["finalizedPrefixLegs"],
            "lastFinalizedPosition": state["boundaryIndex"],
            "returnBoundaryAccount": state["boundaryAccount"],
            "funds": tuple(funds), "assetControl": asset,
            "outstandingSteps": tuple(outstanding),
            "safeRetryCondition": "every step is keyed; a retry asks what already happened "
                                  "and repeats no refund and no return",
            "withdrawnMechanismsNotUsed": WITHDRAWN_MECHANISMS,
            "conflicts": tuple(state["conflicts"]),
            "observedAt": now}

    # ------------------------------------ deadline and historical exit enquiry

    def evaluate_deadline(self, receipt_id, now=None):
        """Report fixed v1.2 rules and the original authority still needed.

        A local clock is enough to stop new trades. It cannot prove whether
        registration became effective within mint conditions; that decision
        needs the single authoritative Oracle state, never a grace receipt.
        This read method does not issue refunds, returns or holder writes.
        """
        now = self._now(now)
        receipt = self.receipt(receipt_id)
        overdue = self.overdue_requests(receipt_id, now)
        past = now >= receipt.trade_stop_at
        active = self._active_legs[receipt_id]
        in_flight = tuple(i for i in active
                          if self.leg(receipt_id, i).registration_status == "pending")
        deferred = self.deferred_legs(receipt_id)
        blockers = []
        if not receipt.minted_at <= now < receipt.trade_stop_at:
            blockers.append("EX_TRADE_WINDOW_CLOSED")
        if self._rollbacks[receipt_id] is not None:
            blockers.append("EX_TRADE_ROLLBACK_OPEN")
        if self._returned_to[receipt_id] is not None:
            blockers.append("EX_RECOVERY_REQUIRED")
        if self._exits[receipt_id] is not None:
            blockers.append("EX_RECOVERY_LEGACY_OUTCOME_UNRESOLVED")
        return {"receiptId": receipt_id, "tradeStopAt": receipt.trade_stop_at,
                "observedAt": now, "pastDeadline": past,
                "newTradesAccepted": not blockers, "tradeBlockingReasons": tuple(blockers),
                "inFlightRegistrationLegs": in_flight,
                "overdueRequests": tuple(entry["legIndex"] for entry in overdue
                                         if entry["legIndex"] in active),
                "deferredLegs": deferred,
                "ownerIndex": self.owner_index(receipt_id),
                "holderIndex": self._holder_index[receipt_id],
                "unfinishedSuffixReturnsTo": self.holder_of(receipt_id)
                if self.owner_index(receipt_id) != self._holder_index[receipt_id] else None,
                "undefinedOrdering": (),
                "requiresAuthoritativeReconciliation": bool(past and
                    self.owner_index(receipt_id) != self.holder_index(receipt_id)),
                "deadlineRule": "preserve effective registered prefix; fail and return only unregistered suffix",
                "registrationTimeSource": "single authoritative Oracle record under mint conditions",
                "graceReceiptRequired": False, "recoveryExecutedByReport": False}

    def bill_of_lading_view(self, receipt_id, now=None):
        """Read existing bill terms and positions without physical fulfillment.

        This is the model's recorded view, not independent chain evidence or an
        assertion that every v1.2 mint field has already been implemented.
        """
        view = self.receipt_view(receipt_id, now)
        return {"prdVersion": "1.2", "receipt": view,
                "scope": "bill-of-lading-transfer",
                "physicalFulfillment": "outside-ex-scope",
                "physicalActions": (), "historyPreserved": True}

    def exit_eligibility(self, receipt_id, requester, authorization_id=None, verified_checks=(),
                         now=None):
        """Compatibility report for a retired operation; no fulfillment gate."""
        view = self.bill_of_lading_view(receipt_id, now)
        return {"receiptId": receipt_id, "requester": requester, "eligible": False,
                "reasons": ("EX_PHYSICAL_FULFILLMENT_RETIRED",),
                "prdVersion": "1.2", "scope": view["scope"],
                "physicalActions": (), "observedAt": view["receipt"]["observedAt"]}

    def request_redemption(self, receipt_id, requester, authorization_id, request_id,
                           verified_checks=(), now=None):
        """Never create a new retired physical operation, even with a grant."""
        require(False, "EX_PHYSICAL_FULFILLMENT_RETIRED",
                "EX v1.2 transfers the bill of lading; physical fulfillment is outside scope")

    def advance_exit(self, receipt_id, through=None, now=None):
        """Preserve old records for enquiry; never resume their physical acts."""
        require(False, "EX_PHYSICAL_FULFILLMENT_RETIRED",
                "query historical exit evidence without executing a retired step")

    def _replace_leg_free_burn(self, receipt_id):
        """Retired private entry must not manufacture a destruction event."""
        require(False, "EX_PHYSICAL_FULFILLMENT_RETIRED",
                "collection-driven destruction is outside EX v1.2")

    def exit_report(self, receipt_id, now=None):
        """Read retained historical evidence without making it executable."""
        now = self._now(now)
        state = self._exits[self.receipt(receipt_id).receipt_id]
        if state is None:
            return {"receiptId": receipt_id, "open": False, "state": None, "complete": False,
                    "retiredOperation": True, "executable": False, "prdVersion": "1.2",
                    "observedAt": now}
        steps = tuple({"step": step.name, "status": step.status,
                       "completedAt": step.completed_at, "detail": dict(step.detail)}
                      for step in state["steps"])
        done = [entry for entry in steps if entry["status"] == "done"]
        instants = sorted({entry["completedAt"] for entry in done if entry["completedAt"]})
        burned = any(entry["step"] == "burn" and entry["status"] == "done" for entry in steps)
        return {"receiptId": receipt_id, "open": True, "state": state["state"],
                "complete": state["state"] == "complete",
                "requestId": state["request"].request_id,
                "requester": state["request"].requester,
                "verifiedChecks": state["verifiedChecks"],
                "steps": steps, "burned": burned,
                "physicalAndOnChainAreAtomic": False,
                "distinctCompletionInstants": tuple(instants),
                "completionInstantsDiffer": len(instants) > 1,
                "undefinedOrdering": (),
                "retiredOperation": True, "executable": False,
                "prdVersion": "1.2",
                "historyPreserved": True,
                "observedAt": now}

    # ------------------------------------------------------------- reporting

    def receipt_view(self, receipt_id, now=None):
        """Everything a holder needs at once, with nothing collapsed."""
        now = self._now(now)
        receipt = self.receipt(receipt_id)
        legs = self._legs[receipt_id]
        owner_index, holder_index = self.owner_index(receipt_id), self._holder_index[receipt_id]
        return {
            "receiptId": receipt.receipt_id,
            "priceCurrency": receipt.price_currency,
            "currencySource": "NFT0", "conversionAvailable": False,
            "gasCurrency": "ETH",
            "mintDeclaration": deepcopy(self._mint_declarations[receipt_id]),
            "asset": {"chainId": receipt.asset.chain_id, "contract": receipt.asset.contract,
                      "tokenId": receipt.asset.token_id},
            "commodity": {"name": receipt.commodity_name, "quantity": receipt.commodity_quantity,
                          "unit": receipt.commodity_unit, "receiptNumber": receipt.receipt_number},
            "tradeableUnits": receipt.tradeable_units,
            "owner": {"account": self.owner_of(receipt_id), "position": owner_index,
                      "meaning": "the position the asset is at on chain now"},
            "recordedLegs": len(legs),
            "assetReturnedByRollback": self._returned_to[receipt_id] is not None,
            "holder": {"account": self.holder_of(receipt_id), "position": holder_index,
                       "meaning": "registration-confirmed position"},
            "ownerEqualsHolder": owner_index == holder_index,
            "registeredPrefixLegs": sum(
                self.leg(receipt_id, i).registration_status == "confirmed"
                for i in self._active_legs[receipt_id]),
            "activeLegIndices": tuple(self._active_legs[receipt_id]),
            "historicalWithdrawnLegIndices": tuple(i for i in range(len(legs))
                                                     if i not in self._active_legs[receipt_id]),
            "chainGeneration": len(self._rollback_history[receipt_id]),
            "outstandingLegs": sum(
                self.leg(receipt_id, i).registration_status != "confirmed"
                for i in self._active_legs[receipt_id]),
            "deferredLegs": self.deferred_legs(receipt_id),
            "rejectedLegs": tuple(e.leg_index for e in self._rejections[receipt_id]),
            "registrationPath": receipt.registration_path,
            "registrationPathLabel": self.registrars[receipt.registration_path].label,
            "simulatedRegistration": True,
            "tradeStopAt": receipt.trade_stop_at,
            "tradingOpen": now < receipt.trade_stop_at,
            "fundingModelled": self.funding_required or bool(self._escrow_by_leg[receipt_id]),
            "observedAt": now,
            "legs": tuple({"legIndex": leg.leg_index, "transferId": leg.transfer_id,
                           "seller": leg.seller, "buyer": leg.buyer, "price": str(leg.price),
                           "quoteAsset": leg.quote_asset, "executionStatus": leg.execution_status,
                           "registrationStatus": leg.registration_status,
                           "fundingStatus": leg.funding_status, "rollbackStatus": leg.rollback_status,
                           "executedAt": leg.executed_at} for leg in legs),
        }

    def redemption_readiness(self, receipt_id, requester, now=None):
        """Legacy read route reports retirement, not a new acceptance checklist."""
        return self.exit_eligibility(receipt_id, requester, now=now)

    def receipt_timeline(self, receipt_id):
        """Trade, registration, funding and rollback records in one order."""
        self.receipt(receipt_id)
        return tuple(self._events[receipt_id])

    def _record(self, receipt_id, kind, detail):
        self._events[receipt_id].append({"sequence": len(self._events[receipt_id]), "kind": kind,
                                         "receiptId": receipt_id, "detail": detail})

    def _now(self, now):
        return instant(self._clock() if now is None else now, "EX_INSTANT_REFUSED")
