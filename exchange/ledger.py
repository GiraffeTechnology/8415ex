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

from .errors import DomainError, require
from .ids import address, amount, digest, identifier, instant
from .model import WHOLE_RECEIPT_UNITS, Asset, AuthorizationReference, TradeIntent, WarehouseReceipt
from .registration import (DISPOSITIONS, RegistrationEvidence, RegistrationRequest,
                           default_registrars)

EXECUTION_STATUSES = ("executed",)
REGISTRATION_STATUSES = ("not-submitted", "pending", "confirmed", "rejected")
FUNDING_STATUSES = ("not-modelled",)


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

    def __init__(self, clock):
        require(callable(clock), "EX_CLOCK_REFUSED", "a clock function is required")
        self._clock = clock
        self._receipts = {}
        self._asset_keys = {}
        self._authorizations = {}
        self._sessions = {}
        self._intents = {}
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

    # ---------------------------------------------------------------- receipts

    def mint(self, receipt):
        """Record one whole receipt as exactly one NFT.

        Minting is a technical record. It asserts no legal right, and a second
        receipt may not map to an NFT that is already mapped.
        """
        require(isinstance(receipt, WarehouseReceipt), "EX_RECEIPT_REFUSED", "receipt type")
        require(receipt.receipt_id not in self._receipts, "EX_RECEIPT_DUPLICATE_REFUSED", receipt.receipt_id)
        existing = self._asset_keys.get(receipt.asset.key)
        require(existing is None, "EX_ASSET_DUPLICATE_REFUSED",
                f"{receipt.asset.key} already maps to receipt {existing}")
        self._receipts[receipt.receipt_id] = receipt
        self._asset_keys[receipt.asset.key] = receipt.receipt_id
        self._legs[receipt.receipt_id] = []
        self._holder_index[receipt.receipt_id] = 0
        self._requests_by_leg[receipt.receipt_id] = {}
        self._deferred[receipt.receipt_id] = {}
        self._rejections[receipt.receipt_id] = []
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
            if now >= receipt.trade_stop_at:
                reasons.append("EX_TRADE_WINDOW_CLOSED")
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
            if auth.counterparties and (intent.counterparty is None
                                        or intent.counterparty not in auth.counterparties):
                reasons.append("EX_AUTH_COUNTERPARTY_REFUSED")
        ordered = tuple(dict.fromkeys(reasons))
        return {"intentId": intent.intent_id, "side": intent.side, "signer": intent.signer,
                "signedTermsDigest": intent.digest, "units": intent.units,
                "executable": ordered == (), "reasons": ordered,
                "authorization": auth_state, "observedAt": now}

    def match_intents(self, sell_intent_id, buy_intent_id, now=None):
        """Deterministically pair two explicitly paired intents.

        This is the Stage 1 demonstration fixture, not a decision about the final
        matching algorithm. It never changes a signed limit or condition.
        """
        now = self._now(now)
        sell, buy = self.intent(sell_intent_id), self.intent(buy_intent_id)
        require(sell.side == "sell" and buy.side == "buy", "EX_MATCH_SIDE_REFUSED",
                "one sell and one buy are required")
        require(sell.asset.key == buy.asset.key, "EX_MATCH_ASSET_REFUSED", "both sides must name one asset")
        require(sell.quote_asset == buy.quote_asset, "EX_MATCH_QUOTE_ASSET_REFUSED", "quote assets must agree")
        require(sell.units == buy.units == WHOLE_RECEIPT_UNITS, "EX_WHOLE_RECEIPT_REFUSED",
                "a match covers exactly one whole receipt")
        require(sell.counterparty == buy.signer and buy.counterparty == sell.signer,
                "EX_MATCH_PAIRING_REFUSED", "this fixture requires an explicit, mutual pairing")
        for report in (self.validate_intent(sell.intent_id, now), self.validate_intent(buy.intent_id, now)):
            require(report["executable"], "EX_MATCH_UNEXECUTABLE",
                    f"{report['intentId']}: {','.join(report['reasons'])}")
        require(buy.limit_price >= sell.limit_price, "EX_MATCH_PRICE_REFUSED",
                "the buy limit does not reach the sell limit")
        price = sell.limit_price
        basis = {"rule": "explicit-pairing-limit-fixture", "sellLimit": str(sell.limit_price),
                 "buyLimit": str(buy.limit_price), "executionPrice": str(price),
                 "quoteAsset": sell.quote_asset, "units": sell.units,
                 "sellIntentId": sell.intent_id, "buyIntentId": buy.intent_id,
                 "registrationAndSettlement": "not-performed-by-matching"}
        return MatchResult(sell_intent_digest=sell.digest, buy_intent_digest=buy.digest,
                           seller=sell.signer, buyer=buy.signer, asset=sell.asset, price=price,
                           quote_asset=sell.quote_asset, units=sell.units, basis=basis, matched_at=now)

    # ------------------------------------------------------------- transfers

    def owner_index(self, receipt_id):
        """How many legs the trade chain has advanced. 0 means the origin holder."""
        self.receipt(receipt_id)
        return len(self._legs[receipt_id])

    def holder_index(self, receipt_id):
        """How many legs the registrar has confirmed, always a prefix."""
        self.receipt(receipt_id)
        return self._holder_index[receipt_id]

    def owner_of(self, receipt_id):
        receipt = self.receipt(receipt_id)
        legs = self._legs[receipt_id]
        return legs[-1].buyer if legs else receipt.origin_account

    def holder_of(self, receipt_id):
        receipt = self.receipt(receipt_id)
        index = self._holder_index[receipt_id]
        return self._legs[receipt_id][index - 1].buyer if index else receipt.origin_account

    def legs(self, receipt_id):
        self.receipt(receipt_id)
        return tuple(self._legs[receipt_id])

    def execute_transfer(self, match, transfer_id, now=None):
        """Append one leg, advancing the owner position by exactly one.

        Only the current head may be sold. Two attempts from the same head mean
        the second one is refused: a receipt has one valid continuous order.
        """
        now = self._now(now)
        require(isinstance(match, MatchResult), "EX_TRANSFER_REFUSED", "match type")
        receipt_id = self._asset_keys.get(match.asset.key)
        require(receipt_id is not None, "EX_ASSET_UNKNOWN", str(match.asset.key))
        receipt = self._receipts[receipt_id]
        require(now < receipt.trade_stop_at, "EX_TRADE_WINDOW_CLOSED",
                "new trades are refused at or after the stop-trading instant")
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
        require(transfer_id not in self._transfer_ids(), "EX_TRANSFER_DUPLICATE_REFUSED", transfer_id)
        leg = Transfer(transfer_id=identifier(transfer_id, "EX_TRANSFER_REFUSED"), receipt_id=receipt_id,
                       leg_index=len(legs), seller=match.seller, buyer=match.buyer,
                       predecessor_transfer_id=legs[-1].transfer_id if legs else None,
                       price=amount(match.price, "EX_TRANSFER_REFUSED"), quote_asset=match.quote_asset,
                       sell_intent_digest=match.sell_intent_digest, buy_intent_digest=match.buy_intent_digest,
                       sell_authorization_id=sell.authorization_id, buy_authorization_id=buy.authorization_id,
                       executed_at=now)
        legs.append(leg)
        self._used_nonces.add((sell.signer, sell.nonce))
        self._used_nonces.add((buy.signer, buy.nonce))
        self._record(receipt_id, "transfer-executed", {
            "transferId": leg.transfer_id, "legIndex": leg.leg_index, "seller": leg.seller,
            "buyer": leg.buyer, "price": str(leg.price), "quoteAsset": leg.quote_asset,
            "matchBasis": match.basis, "ownerIndex": len(legs), "holderIndex": self._holder_index[receipt_id],
            "registrationStatus": leg.registration_status, "fundingStatus": leg.funding_status})
        return leg

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
        expected = self._holder_index[receipt_id]
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
            nxt = self._holder_index[receipt_id]
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

    # ------------------------------------------------------------- reporting

    def receipt_view(self, receipt_id, now=None):
        """Everything a holder needs at once, with nothing collapsed."""
        now = self._now(now)
        receipt = self.receipt(receipt_id)
        legs = self._legs[receipt_id]
        owner_index, holder_index = len(legs), self._holder_index[receipt_id]
        return {
            "receiptId": receipt.receipt_id,
            "asset": {"chainId": receipt.asset.chain_id, "contract": receipt.asset.contract,
                      "tokenId": receipt.asset.token_id},
            "commodity": {"name": receipt.commodity_name, "quantity": receipt.commodity_quantity,
                          "unit": receipt.commodity_unit, "receiptNumber": receipt.receipt_number},
            "tradeableUnits": receipt.tradeable_units,
            "owner": {"account": self.owner_of(receipt_id), "position": owner_index,
                      "meaning": "trade-chain position reached on chain"},
            "holder": {"account": self.holder_of(receipt_id), "position": holder_index,
                       "meaning": "registration-confirmed position"},
            "ownerEqualsHolder": owner_index == holder_index,
            "registeredPrefixLegs": holder_index,
            "outstandingLegs": owner_index - holder_index,
            "deferredLegs": self.deferred_legs(receipt_id),
            "rejectedLegs": tuple(e.leg_index for e in self._rejections[receipt_id]),
            "registrationPath": receipt.registration_path,
            "registrationPathLabel": self.registrars[receipt.registration_path].label,
            "simulatedRegistration": True,
            "tradeStopAt": receipt.trade_stop_at,
            "tradingOpen": now < receipt.trade_stop_at,
            "fundingModelled": False,
            "observedAt": now,
            "legs": tuple({"legIndex": leg.leg_index, "transferId": leg.transfer_id,
                           "seller": leg.seller, "buyer": leg.buyer, "price": str(leg.price),
                           "quoteAsset": leg.quote_asset, "executionStatus": leg.execution_status,
                           "registrationStatus": leg.registration_status,
                           "fundingStatus": leg.funding_status, "rollbackStatus": leg.rollback_status,
                           "executedAt": leg.executed_at} for leg in legs),
        }

    def redemption_readiness(self, receipt_id, requester, now=None):
        """Whether the necessary condition holds, and what is still unchecked.

        ``owner == holder`` is necessary and never sufficient. This returns the
        remaining checks by name instead of a verdict; Stage 4 implements the
        exit flow itself.
        """
        now = self._now(now)
        view = self.receipt_view(receipt_id, now)
        address(requester, "EX_REDEMPTION_REFUSED")
        blocking = []
        if not view["ownerEqualsHolder"]:
            blocking.append("EX_OWNER_HOLDER_DIVERGED")
        if view["owner"]["account"] != requester or view["holder"]["account"] != requester:
            blocking.append("EX_REDEMPTION_REQUESTER_REFUSED")
        return {"receiptId": receipt_id, "requester": requester,
                "ownerEqualsHolder": view["ownerEqualsHolder"],
                "necessaryConditionMet": blocking == [],
                "blockingReasons": tuple(blocking),
                "furtherChecksNotPerformedHere": ("rights-holder-verification", "asset-validity",
                                                  "other-eligibility", "voucher-handover", "burn"),
                "redeemable": False,
                "redeemableMeaning": "Stage 1 performs no redemption; this is a readiness report only",
                "observedAt": now}

    def receipt_timeline(self, receipt_id):
        """Trade, registration, funding and rollback records in one order."""
        self.receipt(receipt_id)
        return tuple(self._events[receipt_id])

    def _record(self, receipt_id, kind, detail):
        self._events[receipt_id].append({"sequence": len(self._events[receipt_id]), "kind": kind,
                                         "receiptId": receipt_id, "detail": detail})

    def _now(self, now):
        return instant(self._clock() if now is None else now, "EX_INSTANT_REFUSED")
