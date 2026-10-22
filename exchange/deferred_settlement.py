"""Deferred-mode policy and accounting, with no network or wallet execution.

Native effects are supplied through a configured evidence verifier. This module
never turns a caller's boolean into proof and never sends transactions. The
runtime must persist the aggregate through its existing checkpoint/CAS boundary
before dispatching a returned operation, and reconcile UNKNOWN outcomes first.
"""
from dataclasses import asdict, dataclass
from typing import Protocol

from . import ids
from .errors import DomainError
from .ids import digest


class DeferredRefused(ValueError):
    pass


def _field(validator, value):
    try:
        return validator(value)
    except DomainError:
        raise DeferredRefused("invalid structured field") from None


def amount(value):
    return _field(ids.amount, value)


def chain_id(value):
    return _field(ids.chain_id, value)


def identifier(value):
    return _field(ids.identifier, value)


def instant(value):
    return _field(ids.instant, value)


def require(condition, reason):
    if not condition:
        raise DeferredRefused(reason)


def settlement_deadline(mode, *, trade_at, registration_deadline, delay_seconds=None):
    """Resolve the explicitly agreed schedule to Unix seconds, never a default."""
    instant(trade_at)
    instant(registration_deadline)
    if mode == "T_PLUS_N":
        require(delay_seconds is not None, "explicit settlement delay required")
        amount(delay_seconds)
        require(delay_seconds > 0, "positive settlement delay required")
        value = trade_at + delay_seconds
    elif mode == "BEFORE_REGISTRATION_72H":
        require(delay_seconds is None, "unexpected alternate delay")
        value = registration_deadline - 72 * 60 * 60
    else:
        raise DeferredRefused("unknown settlement schedule")
    instant(value)
    require(value > trade_at, "settlement deadline is not after trade")
    return value


@dataclass(frozen=True)
class Profile:
    settlement_chain: int
    principal_asset: str
    collateral_chain: int
    collateral_asset: str
    vault: str
    escrow: str
    policy: str
    ratio_bps: int
    valuation_max_age: int
    checkpoint_scope: str
    fee_receiver: str

    def __post_init__(self):
        chain_id(self.settlement_chain)
        chain_id(self.collateral_chain)
        require(self.settlement_chain != self.collateral_chain, "cross-chain profile required")
        for value in (self.principal_asset, self.collateral_asset, self.vault,
                      self.escrow, self.policy, self.checkpoint_scope, self.fee_receiver):
            identifier(value)
        amount(self.ratio_bps)
        require(0 < self.ratio_bps <= 10000, "explicit collateral ratio required")
        instant(self.valuation_max_age)
        require(self.valuation_max_age > 0, "valuation freshness policy required")


@dataclass(frozen=True)
class Fact:
    """Canonical fact returned only by the trusted verifier implementation.

    principal_value is already denominated in the selected principal asset's
    minor units. The verifier must authenticate denomination and valuation.
    """
    identity: str
    kind: str
    chain: int
    asset: str
    account: str
    location: str
    reference: str
    units: int
    observed_at: int
    principal_value: int = 0
    destination_units: int = 0
    profile_commitment: str = ""


class EvidenceVerifier(Protocol):
    def verify(self, evidence: bytes, *, kind: str, now: int) -> Fact:
        """Authenticate/finalize canonical evidence or raise; no write effects."""


@dataclass
class Lock:
    identity: str
    borrower: str
    units: int
    capacity: int
    reserved: int = 0
    release_pending: bool = False
    released: bool = False
    liquidating: bool = False
    remainder_verified: bool = True
    valued_at: int = 0


@dataclass
class Obligation:
    identity: str
    lock: str
    borrower: str
    seller: str
    principal: int
    settlement_fee_wei: int
    deadline: int
    consent: str
    fee_receipt: str
    gas_allocation: str
    normal_gas: dict
    fee_receipt_record: dict
    gas_allocation_record: dict
    source_normal_gas: dict
    source_gas_allocation: str
    source_gas_record: dict
    collateral_remaining: int = 0
    registered: bool = False
    rollback: bool = False
    rollback_confirmed: bool = False
    escrow: int = 0
    paid: int = 0
    gas_required: int = 0
    gas_received: int = 0
    gas_assessed: bool = False
    resolved: bool = False
    normal_gas_availability: dict | None = None

    @property
    def due(self):
        return self.principal - self.paid


@dataclass
class Operation:
    identity: str
    obligation: str
    kind: str
    units: int
    asset: str
    chain: int
    recipient: str
    commitment: str
    status: str = "PREPARED"
    collateral_limit: int = 0
    quote: str = ""
    collateral_spent: int | None = None
    liquidation_terms: dict | None = None
    funding_record: dict | None = None
    cost_record: dict | None = None
    penalty_record: dict | None = None
    quote_record: dict | None = None
    authority_record: dict | None = None
    source_record: dict | None = None
    normal_funding: dict | None = None


class DeferredSettlement:
    """Single aggregate; caller owns serialization and durable CAS transaction.

    Mutating this object alone does not dispatch or certify an external effect.
    Each method returns only after validating every field it changes. Persist
    this complete object with the existing aggregate, never a separate balance.
    """
    def __init__(self, profile: Profile, verifier: EvidenceVerifier):
        require(isinstance(profile, Profile), "explicit profile required")
        require(callable(getattr(verifier, "verify", None)), "trusted verifier required")
        self.profile = profile
        self.verifier = verifier
        self.locks = {}
        self.obligations = {}
        self.operations = {}
        self.evidence = {}

    def _fact(self, raw, kind, now):
        instant(now)
        require(type(raw) is bytes and 0 < len(raw) <= 1024 * 1024, "bounded evidence bytes required")
        fact = self.verifier.verify(raw, kind=kind, now=now)
        self._validate_fact(fact, kind)
        require(fact.observed_at <= now, "future observation")
        commitment = digest(asdict(fact))
        old = self.evidence.get(fact.identity)
        require(old is None or old == commitment, "evidence identity collision")
        return fact, commitment, old is not None

    def _validate_fact(self, fact, kind):
        """Same canonical shape checks for verified input and private restore."""
        require(type(fact) is Fact and fact.kind == kind, "verifier fact mismatch")
        require(fact.profile_commitment == digest(asdict(self.profile)), "evidence belongs to another profile or instance")
        identifier(fact.identity)
        chain_id(fact.chain)
        for value in (fact.asset, fact.account, fact.location, fact.reference):
            identifier(value)
        amount(fact.units)
        amount(fact.principal_value)
        amount(fact.destination_units)
        instant(fact.observed_at)

    def _save_fact(self, fact, commitment):
        self.evidence[fact.identity] = commitment

    def admit_lock(self, raw, *, now):
        fact, commitment, duplicate = self._fact(raw, "collateral-lock", now)
        p = self.profile
        require((fact.chain, fact.asset, fact.location) ==
                (p.collateral_chain, p.collateral_asset, p.vault), "wrong collateral profile")
        require(now - fact.observed_at <= p.valuation_max_age, "stale valuation")
        require(fact.units > 0 and fact.principal_value > 0, "positive verified value required")
        if duplicate:
            require(fact.reference in self.locks, "evidence already consumed elsewhere")
            return self.locks[fact.reference]
        require(fact.reference not in self.locks, "lock already allocated")
        capacity = fact.principal_value * p.ratio_bps // 10000
        require(capacity > 0, "rounded allowance is zero")
        lock = Lock(fact.reference, fact.account, fact.units, capacity, valued_at=fact.observed_at)
        self.locks[lock.identity] = lock
        self._save_fact(fact, commitment)
        return lock

    def reserve(self, obligation_id, lock_id, *, borrower, seller, principal,
                settlement_fee_wei, normal_gas, deadline, now, seller_consent,
                borrower_authority, fee_receipt, gas_allocation,
                source_normal_gas, source_gas_allocation):
        """Bind an already received ETH fee and its original gas allocation.

        This records no transfer and creates no second freeze. The trusted
        verifier must establish canonical receipt identity and an exclusive
        allocation in the original gas journal, including quote and grant.
        A receipt is consumed once here; shared receipts require a separately
        specified original-journal allocation contract, not guessed balances.
        """
        for value in (obligation_id, lock_id, borrower, seller):
            identifier(value)
        amount(principal)
        amount(settlement_fee_wei)
        self._validate_normal_gas(normal_gas, settlement_fee_wei)
        self._validate_normal_gas(source_normal_gas)
        require(self.profile.collateral_chain == 560048,
                "supported source-native normal gas profile required")
        instant(deadline)
        instant(now)
        previous = self.obligations.get(obligation_id)
        require(principal > 0 and (previous is not None or deadline > now), "invalid amount or deadline")
        require(lock_id in self.locks, "verified collateral missing")
        lock = self.locks[lock_id]
        terms = digest({"id": obligation_id, "lock": lock_id, "borrower": borrower,
                        "seller": seller, "principal": principal,
                        "settlementFeeWei": settlement_fee_wei,
                        "normalGas": normal_gas,
                        "sourceNormalGas": source_normal_gas,
                        "deadline": deadline, "profile": asdict(self.profile)})
        fact, commitment, duplicate = self._fact(seller_consent, "seller-consent", now)
        require((fact.reference, fact.account, fact.asset, fact.chain, fact.location, fact.units) ==
                (terms, seller, self.profile.principal_asset, self.profile.settlement_chain,
                 self.profile.escrow, principal), "consent does not bind exact terms")
        admission, admission_commitment, admission_duplicate = self._fact(borrower_authority, "deferred-admission", now)
        require((admission.reference, admission.account, admission.chain, admission.asset, admission.location, admission.units) ==
                (terms, borrower, self.profile.settlement_chain, self.profile.principal_asset,
                 self.profile.escrow, principal), "wallet admission/gas/authority binding mismatch")
        receipt, receipt_commitment, receipt_duplicate = self._fact(
            fee_receipt, "settlement-fee-receipt", now)
        require((receipt.reference, receipt.chain, receipt.asset, receipt.account,
                 receipt.location, receipt.units) ==
                (terms, self.profile.settlement_chain, "ETH", borrower,
                 self.profile.fee_receiver, settlement_fee_wei),
                "received ETH settlement fee binding mismatch")
        allocation_reference = digest({"terms": terms, "feeReceipt": receipt.identity,
                                       "normalGas": normal_gas})
        allocation, allocation_commitment, allocation_duplicate = self._fact(
            gas_allocation, "normal-gas-allocation", now)
        require((allocation.reference, allocation.chain, allocation.asset,
                 allocation.account, allocation.location, allocation.units) ==
                (allocation_reference, self.profile.settlement_chain, "ETH", borrower,
                 normal_gas["location"], normal_gas["capWei"]),
                "original normal gas allocation binding mismatch")
        source_reference = digest({"terms": terms, "feeReceipt": receipt.identity,
                                   "sourceNormalGas": source_normal_gas})
        source, source_commitment, source_duplicate = self._fact(
            source_gas_allocation, "source-normal-gas-allocation", now)
        require((source.reference, source.chain, source.asset, source.account,
                 source.location, source.units) ==
                (source_reference, self.profile.collateral_chain, "ETH", borrower,
                 source_normal_gas["location"], source_normal_gas["capWei"]),
                "independent source-native normal gas allocation required")
        require(len({fact.identity, admission.identity, receipt.identity, allocation.identity, source.identity}) == 5,
                "admission evidence identity collision")
        if previous is not None:
            require(previous.consent == terms and
                    all((duplicate, admission_duplicate, receipt_duplicate, allocation_duplicate, source_duplicate)) and
                    previous.fee_receipt_record == asdict(receipt) and
                    previous.gas_allocation_record == asdict(allocation) and
                    previous.source_gas_record == asdict(source),
                    "obligation identity or admission evidence changed")
            return previous
        require(not any((duplicate, admission_duplicate, receipt_duplicate, allocation_duplicate, source_duplicate)),
                "admission evidence already consumed")
        require(lock.borrower == borrower and not lock.release_pending and not lock.released and not lock.liquidating,
                "collateral unavailable")
        require(lock.valued_at <= now and now - lock.valued_at <= self.profile.valuation_max_age,
                "collateral valuation expired before reservation")
        require(not any(x.normal_gas["budget"] == normal_gas["budget"]
                        for x in self.obligations.values()),
                "original gas budget already assigned to an obligation")
        require(not any(x.source_normal_gas["budget"] == source_normal_gas["budget"]
                        for x in self.obligations.values()),
                "original source gas budget already assigned to an obligation")
        require(not any(op.liquidation_terms is not None and
                        op.liquidation_terms["gasBudget"] == source_normal_gas["budget"]
                        for op in self.operations.values()),
                "normal source budget cannot reuse contingent liquidation funding")
        require(not self._pending_lock(lock_id), "collateral has unresolved operations")
        require(principal <= lock.capacity - lock.reserved, "allowance exhausted")
        collateral_units = (lock.units * principal + lock.capacity - 1) // lock.capacity
        allocated = sum(x.collateral_remaining for x in self.obligations.values()
                        if x.lock == lock_id and not x.resolved)
        require(collateral_units <= lock.units - allocated, "collateral units already allocated")
        result = Obligation(obligation_id, lock_id, borrower, seller, principal,
                            settlement_fee_wei, deadline, terms, receipt.identity,
                            allocation.identity, dict(normal_gas),
                            asdict(receipt), asdict(allocation),
                            dict(source_normal_gas), source.identity, asdict(source),
                            collateral_remaining=collateral_units)
        lock.reserved += principal
        self.obligations[obligation_id] = result
        self._save_fact(fact, commitment)
        self._save_fact(admission, admission_commitment)
        self._save_fact(receipt, receipt_commitment)
        self._save_fact(allocation, allocation_commitment)
        self._save_fact(source, source_commitment)
        return result

    @staticmethod
    def _validate_normal_gas(funding, fee_wei=None):
        require(type(funding) is dict and set(funding) ==
                {"budget", "quote", "scope", "grant", "location", "capWei", "maxAgeSeconds", "payer"},
                "explicit original normal gas allocation required")
        for name in ("budget", "quote", "scope", "grant", "location", "payer"):
            identifier(funding[name])
        amount(funding["capWei"])
        amount(funding["maxAgeSeconds"])
        require(0 < funding["capWei"] and (fee_wei is None or funding["capWei"] <= fee_wei),
                "received settlement fee must cover normal gas cap")
        require(funding["maxAgeSeconds"] > 0, "explicit normal gas observation validity required")

    def _normal_funding(self, item, kind):
        if kind == "debt-liquidation":
            return None
        source = kind == "collateral-unlock"
        return {"chain": self.profile.collateral_chain if source else self.profile.settlement_chain,
                "asset": "ETH", "allocation": item.source_gas_allocation if source else item.gas_allocation,
                "terms": dict(item.source_normal_gas if source else item.normal_gas)}

    def observe_registration(self, obligation_id, raw, *, now):
        item = self.obligations[obligation_id]
        fact, commitment, duplicate = self._fact(raw, "registration-cut", now)
        require((fact.reference, fact.chain, fact.account) ==
                (obligation_id, self.profile.settlement_chain, item.borrower), "registration binding mismatch")
        require(fact.observed_at <= item.deadline, "registration cut is after settlement deadline")
        if item.rollback:
            involved = [op for op in self.operations.values() if op.obligation == obligation_id
                        and op.kind == "rollback"]
            require(not any(op.status in ("UNKNOWN", "CONFIRMED") for op in involved),
                    "authoritative registration conflicts with an external recovery; reconcile")
            for op in involved:
                if op.status == "PREPARED":
                    op.status = "FAILED"
            item.rollback = False
        if not duplicate:
            item.registered = True
            self._save_fact(fact, commitment)
        return item.registered

    def observe_rollback_authority(self, obligation_id, raw, *, now):
        """Consume the original eligible suffix/refusal/cutoff authorization."""
        item = self.obligations[obligation_id]
        require(not item.registered and not item.resolved, "registered prefix cannot roll back")
        fact, commitment, duplicate = self._fact(raw, "original-rollback-authority", now)
        require((fact.reference, fact.chain, fact.account, fact.units) ==
                (obligation_id, self.profile.settlement_chain, item.borrower, 0),
                "rollback scope mismatch")
        if not duplicate:
            item.rollback = True
            self._save_fact(fact, commitment)
        return "ROLLBACK_REQUIRED"

    def credit_escrow(self, obligation_id, raw, *, now):
        """Verifier attests final, unencumbered allocation, not mere balance.

        Refundable resale funds must remain in the original segment journal and
        cannot be reported by the verifier as an unencumbered allocation here.
        """
        item = self.obligations[obligation_id]
        fact, commitment, duplicate = self._fact(raw, "principal-allocation", now)
        p = self.profile
        require((fact.reference, fact.chain, fact.asset, fact.account, fact.location) ==
                (obligation_id, p.settlement_chain, p.principal_asset, item.borrower, p.escrow),
                "escrow allocation mismatch")
        require(fact.units > 0 and not item.resolved and not item.rollback, "closed or empty allocation")
        require(not self._pending(obligation_id), "reconcile pending operation before allocation")
        if not duplicate:
            item.escrow += fact.units
            self._save_fact(fact, commitment)
        return item.escrow

    def deadline(self, obligation_id, *, now, registration_evidence=None):
        item = self.obligations[obligation_id]
        instant(now)
        require(now >= item.deadline and not item.resolved, "deadline not reached or closed")
        if not item.registered and not item.rollback:
            if registration_evidence is None:
                return "REGISTRATION_RECONCILIATION_REQUIRED"
            fact, commitment, duplicate = self._fact(registration_evidence, "deadline-registration", now)
            require((fact.reference, fact.chain, fact.account, fact.observed_at) ==
                    (obligation_id, self.profile.settlement_chain, item.borrower, item.deadline)
                    and fact.units in (0, 1), "exact authoritative deadline cut required")
            # The verifier authenticates the canonical original Oracle cut as of
            # the deadline. A missing local event or RPC failure cannot be 0.
            if fact.units == 1:
                item.registered = True
            else:
                item.rollback = True
            self._save_fact(fact, commitment)
        if item.rollback:
            return "ROLLBACK_REQUIRED"
        return "PAYMENT_READY" if item.escrow >= item.due else "DEBT_LIQUIDATION_REQUIRED"

    def _source_pending(self, lock_id):
        return [op for op in self.operations.values()
                if self.obligations[op.obligation].lock == lock_id
                and op.kind == "debt-liquidation" and op.collateral_spent is None]

    def _pending_lock(self, lock_id):
        return [op for op in self.operations.values()
                if self.obligations[op.obligation].lock == lock_id
                and (op.status not in ("CONFIRMED", "FAILED") or op in self._source_pending(lock_id)
                     or (op.kind == "debt-liquidation" and
                         (op.cost_record is None or op.penalty_record is None)))]

    def _pending(self, obligation_id):
        return [op for op in self.operations.values()
                if op.obligation == obligation_id and op.status not in ("CONFIRMED", "FAILED")]

    def prepare(self, operation_id, obligation_id, *, kind, now, units=None,
                liquidation_quote=None, liquidation_terms=None, liquidation_authority=None):
        identifier(operation_id)
        instant(now)
        item = self.obligations[obligation_id]
        require(kind != "gas-liquidation", "normal gas must use the original fee allocation")
        previous = self.operations.get(operation_id)
        if previous is not None:
            require(previous.obligation == obligation_id and previous.kind == kind,
                    "operation identity collision")
            if units is not None:
                amount(units)
                require(units == previous.units, "operation amount mismatch")
            if kind == "debt-liquidation":
                _, quote_hash, _ = self._fact(liquidation_quote, "liquidation-quote", now)
                require(quote_hash == previous.quote, "operation quote mismatch")
                require(liquidation_terms == previous.liquidation_terms,
                        "liquidation commercial terms changed")
            else:
                require(liquidation_quote is None, "unexpected liquidation quote")
                require(liquidation_terms is None and liquidation_authority is None,
                        "unexpected liquidation authority")
            expected = digest({"id": operation_id, "obligation": obligation_id, "kind": kind,
                "units": previous.units, "asset": previous.asset, "chain": previous.chain,
                "recipient": previous.recipient, "consent": item.consent,
                "profile": asdict(self.profile), "collateralLimit": previous.collateral_limit,
                "quote": previous.quote, "liquidationTerms": previous.liquidation_terms,
                "normalFunding": previous.normal_funding})
            require(expected == previous.commitment, "stored operation commitment mismatch")
            return previous
        require(not item.resolved or kind in ("excess-refund", "collateral-unlock"), "closed obligation")
        p = self.profile
        collateral_limit, quote_commitment, quote_fact, quote_duplicate = 0, "", None, False
        authority_fact, authority_commitment = None, None
        if kind == "seller-payment":
            require(item.registered and not item.rollback, "registration required for seller payment")
            value = item.due
            require(value > 0 and item.escrow >= value, "full exact-currency payment required")
            asset, chain, recipient = p.principal_asset, p.settlement_chain, item.seller
        elif kind == "debt-liquidation":
            require(item.registered and not item.rollback and now >= item.deadline,
                    "registered overdue debt required")
            value = max(0, item.due - item.escrow)
            require(value > 0, "no debt shortage")
            asset, chain, recipient = p.principal_asset, p.settlement_chain, p.escrow
        elif kind == "rollback":
            require(item.rollback and not item.registered and not item.rollback_confirmed,
                    "eligible rollback required")
            require(item.gas_assessed and item.gas_received >= item.gas_required, "rollback gas assessment or funding missing")
            value = item.escrow
            asset, chain, recipient = p.principal_asset, p.settlement_chain, item.borrower
        elif kind == "excess-refund":
            require(item.resolved and item.escrow > 0, "no resolved excess")
            value, asset, chain, recipient = item.escrow, p.principal_asset, p.settlement_chain, item.borrower
        elif kind == "collateral-unlock":
            lock = self.locks[item.lock]
            require(item.resolved and item.escrow == 0 and lock.reserved == 0
                    and all(x.resolved and x.escrow == 0 for x in self.obligations.values() if x.lock == item.lock),
                    "unresolved collateral obligations")
            require(not lock.released and not lock.release_pending and lock.remainder_verified
                    and not self._pending_lock(item.lock),
                    "collateral remainder not confirmed")
            value, asset, chain, recipient = lock.units, p.collateral_asset, p.collateral_chain, item.borrower
        else:
            raise DeferredRefused("unsupported operation")
        if kind == "debt-liquidation":
            self._validate_liquidation_terms(liquidation_terms, item.borrower)
            quote_fact, quote_commitment, quote_duplicate = self._fact(liquidation_quote, "liquidation-quote", now)
            quote_terms = digest({"obligation": obligation_id, "kind": kind, "target": value,
                                  "asset": asset, "chain": chain, "recipient": recipient,
                                  "consent": item.consent, "liquidationTerms": liquidation_terms})
            require((quote_fact.reference, quote_fact.chain, quote_fact.asset,
                    quote_fact.account, quote_fact.location) == (quote_terms, p.collateral_chain,
                    p.collateral_asset, item.borrower, p.vault), "invalid liquidation quote binding")
            require(now - quote_fact.observed_at <= p.valuation_max_age and
                    0 < quote_fact.units <= item.collateral_remaining -
                    sum(op.collateral_limit for op in self._source_pending(item.lock)
                        if op.obligation == obligation_id)
                    and quote_fact.destination_units >= value,
                    "unbounded or stale liquidation quote")
            collateral_limit = quote_fact.units
            require(liquidation_terms["penaltyCapUnits"] <= collateral_limit,
                    "penalty cap exceeds total source collateral cap")
            authority_reference = digest({"operation": operation_id, "quote": quote_commitment,
                                          "terms": quote_terms, "collateralCap": collateral_limit})
            authority_fact, authority_commitment, authority_duplicate = self._fact(
                liquidation_authority, "liquidation-authority", now)
            require(not authority_duplicate and authority_fact.identity != quote_fact.identity,
                    "liquidation authority replay")
            require((authority_fact.reference, authority_fact.chain, authority_fact.asset,
                     authority_fact.account, authority_fact.location, authority_fact.units) ==
                    (authority_reference, p.collateral_chain, p.collateral_asset,
                     item.borrower, p.vault, collateral_limit),
                    "original liquidation authority does not cover exact commercial terms")
        else:
            require(liquidation_terms is None and liquidation_authority is None,
                    "unexpected liquidation terms")
        if units is not None:
            amount(units)
            require(units == value, "operation amount mismatch")
        payload = {"id": operation_id, "obligation": obligation_id, "kind": kind,
                   "units": value, "asset": asset, "chain": chain, "recipient": recipient,
                   "consent": item.consent, "profile": asdict(p),
                   "collateralLimit": collateral_limit, "quote": quote_commitment,
                   "liquidationTerms": liquidation_terms,
                   "normalFunding": self._normal_funding(item, kind)}
        commitment = digest(payload)
        old = self.operations.get(operation_id)
        if old:
            require(old.commitment == commitment, "operation identity collision")
            return old
        require(not quote_duplicate, "liquidation quote already consumed")
        require(not self._pending(obligation_id), "reconcile pending operation first")
        op = Operation(operation_id, obligation_id, kind, value, asset, chain,
                       recipient, commitment, collateral_limit=collateral_limit, quote=quote_commitment,
                       liquidation_terms=None if liquidation_terms is None else dict(liquidation_terms),
                       quote_record=None if quote_fact is None else asdict(quote_fact),
                       authority_record=None if authority_fact is None else asdict(authority_fact),
                       normal_funding=self._normal_funding(item, kind))
        if quote_fact is not None:
            self._save_fact(quote_fact, quote_commitment)
            self._save_fact(authority_fact, authority_commitment)
        if kind == "collateral-unlock":
            self.locks[item.lock].release_pending = True
        self.operations[operation_id] = op
        return op

    def _validate_liquidation_terms(self, terms, borrower):
        require(type(terms) is dict and set(terms) ==
                {"gasPayer", "gasBudget", "gasAsset", "gasCapUnits", "fundingMaxAge",
                 "penaltyPolicy", "penaltyAsset", "penaltyCapUnits", "priorityPolicy", "conversionPolicy"},
                "explicit liquidation funding and penalty terms required")
        for name in ("gasPayer", "gasBudget", "gasAsset", "penaltyPolicy", "penaltyAsset",
                     "priorityPolicy", "conversionPolicy"):
            identifier(terms[name])
        for name in ("gasCapUnits", "fundingMaxAge", "penaltyCapUnits"):
            amount(terms[name])
        require(terms["gasPayer"] != borrower and terms["gasCapUnits"] > 0 and
                terms["fundingMaxAge"] > 0, "explicit EX-funded execution required")
        require(self.profile.collateral_chain == 560048 and terms["gasAsset"] == "ETH",
                "supported source-native execution fee binding required")
        require(not any(item.source_normal_gas["budget"] == terms["gasBudget"]
                        for item in self.obligations.values()),
                "contingent liquidation cannot consume prepaid normal gas")
        require(terms["penaltyAsset"] == self.profile.collateral_asset,
                "penalty must be an explicitly bounded source collateral deduction")

    def observe_liquidation_funding(self, operation_id, raw, *, now):
        op = self.operations[operation_id]
        require(op.kind == "debt-liquidation" and op.status == "PREPARED",
                "prepared liquidation required")
        terms = op.liquidation_terms
        fact, commitment, duplicate = self._fact(raw, "liquidation-ex-funding", now)
        require((fact.reference, fact.chain, fact.asset, fact.account, fact.location, fact.units) ==
                (op.commitment, self.profile.collateral_chain, terms["gasAsset"],
                 terms["gasPayer"], terms["gasBudget"], terms["gasCapUnits"]),
                "original EX execution funding mismatch")
        require(now - fact.observed_at <= terms["fundingMaxAge"], "stale EX funding observation")
        if op.funding_record is not None:
            if duplicate:
                require(op.funding_record == asdict(fact), "funding outcome conflict")
                return op
            require(fact.observed_at > op.funding_record["observed_at"],
                    "funding refresh must advance the original observation")
        require(not duplicate, "funding evidence already consumed")
        op.funding_record = asdict(fact)
        self._save_fact(fact, commitment)
        return op

    def observe_gas_requirement(self, obligation_id, raw, *, now):
        item = self.obligations[obligation_id]
        pending = self._pending(obligation_id)
        require(item.rollback and all(op.kind == "rollback" and op.status == "PREPARED"
                                      for op in pending),
                "normal gas refresh requires an unissued rollback")
        fact, commitment, duplicate = self._fact(raw, "normal-gas-availability", now)
        reference = digest({"obligation": obligation_id, "terms": item.consent,
                            "allocation": item.gas_allocation, "normalGas": item.normal_gas})
        require((fact.reference, fact.asset, fact.chain, fact.account, fact.location) ==
                (reference, "ETH", self.profile.settlement_chain, item.borrower,
                 item.normal_gas["location"]), "original normal gas scope mismatch")
        require(fact.units <= item.normal_gas["capWei"] and
                fact.destination_units <= item.normal_gas["capWei"],
                "normal gas exceeds the original confirmed cap")
        require(now - fact.observed_at <= item.normal_gas["maxAgeSeconds"],
                "stale original normal gas observation")
        if item.normal_gas_availability is not None:
            if duplicate:
                require(item.normal_gas_availability == asdict(fact),
                        "historical normal gas observation cannot replace current funding")
                return max(0, item.gas_required - item.gas_received)
            require(fact.observed_at > item.normal_gas_availability["observed_at"],
                    "normal gas observation must advance")
        if not duplicate:
            item.gas_assessed = True
            item.gas_received = fact.units
            item.gas_required = fact.destination_units
            item.normal_gas_availability = asdict(fact)
            self._save_fact(fact, commitment)
        return max(0, item.gas_required - item.gas_received)

    def mark_dispatched(self, operation_id, *, now):
        instant(now)
        op = self.operations[operation_id]
        require(op.status == "PREPARED", "operation is not dispatchable")
        item = self.obligations[op.obligation]
        if op.kind == "collateral-unlock":
            lock = self.locks[item.lock]
            require(item.resolved and item.escrow == 0 and lock.reserved == 0
                    and all(x.resolved and x.escrow == 0 for x in self.obligations.values() if x.lock == item.lock)
                    and lock.release_pending and lock.remainder_verified
                    and all(p.identity == operation_id for p in self._pending_lock(item.lock)),
                    "collateral release precondition changed")
        if op.kind == "rollback":
            require(item.rollback and not item.registered and not item.rollback_confirmed,
                    "rollback authority changed")
            require(item.gas_assessed and item.gas_received >= item.gas_required,
                    "original normal gas allocation is insufficient")
            require(item.normal_gas_availability is not None and
                    item.normal_gas_availability["observed_at"] <= now and
                    now - item.normal_gas_availability["observed_at"] <= item.normal_gas["maxAgeSeconds"],
                    "current original normal gas observation required")
        if op.kind == "debt-liquidation":
            require(op.funding_record is not None and
                    op.funding_record["observed_at"] <= now and
                    now - op.funding_record["observed_at"] <= op.liquidation_terms["fundingMaxAge"],
                    "current EX liquidation funding required before dispatch")
        op.status = "UNKNOWN"
        if op.kind == "debt-liquidation":
            lock = self.locks[self.obligations[op.obligation].lock]
            lock.liquidating = True
            lock.remainder_verified = False
        if op.kind == "collateral-unlock":
            self.locks[self.obligations[op.obligation].lock].release_pending = True
        # The runtime must durably save UNKNOWN before dispatch. If saving fails,
        # it must not dispatch. UNKNOWN is reconciled, never automatically retried.
        return op

    def confirm(self, operation_id, raw, *, now):
        op = self.operations[operation_id]
        require(op.status in ("UNKNOWN", "CONFIRMED"), "operation was not dispatched")
        # This is an authenticated terminal aggregate of the original route's
        # complete net destination effect, not its first transfer or a pending
        # fragment. Partial recovery relative to target may still be terminal.
        fact, commitment, duplicate = self._fact(raw, "terminal-operation-receipt", now)
        require((fact.reference, fact.chain, fact.asset, fact.account) ==
                (op.commitment, op.chain, op.asset, op.recipient), "receipt mismatch")
        if op.kind == "debt-liquidation":
            # units in the operation is the requested debt target, not a cap on
            # actual net proceeds. Keep verified excess for the existing refund
            # path; the separately enforced source collateral cap still holds.
            require(fact.units >= 0, "invalid liquidation destination amount")
        else:
            require(fact.units == op.units, "receipt amount mismatch")
        if op.status == "CONFIRMED":
            require(duplicate, "different receipt for completed operation")
            return op
        require(not duplicate, "receipt already allocated")
        item = self.obligations[op.obligation]
        was_resolved = item.resolved
        if op.kind == "seller-payment":
            require(item.registered and item.escrow >= op.units, "payment state conflict")
            item.escrow -= op.units
            item.paid += op.units
            item.resolved = item.due == 0
        elif op.kind == "debt-liquidation":
            item.escrow += fact.units  # Receipt is destination principal, NOT source sale.
        elif op.kind == "rollback":
            require(not item.registered and item.escrow == op.units, "rollback state conflict")
            item.escrow = 0
            item.rollback_confirmed = True
            item.resolved = True
        elif op.kind == "excess-refund":
            require(item.escrow == op.units, "excess allocation changed")
            item.escrow = 0
        elif op.kind == "collateral-unlock":
            lock = self.locks[item.lock]
            lock.released = True
            lock.release_pending = False
        if item.resolved and not was_resolved:
            self.locks[item.lock].reserved -= item.principal
        op.status = "CONFIRMED"
        self._save_fact(fact, commitment)
        return op

    def confirm_nonexecution(self, operation_id, raw, *, now):
        """Consume terminal original-port proof, never a timeout/not-found result.

        The verifier must establish that the exact authorized operation cannot
        execute later (for example final nonce replacement/expired authority),
        not merely that one RPC currently cannot find it.
        """
        op = self.operations[operation_id]
        require(op.status in ("UNKNOWN", "FAILED"), "no uncertain issued operation")
        fact, commitment, duplicate = self._fact(raw, "terminal-nonexecution", now)
        require((fact.reference, fact.chain, fact.asset, fact.account, fact.units) ==
                (op.commitment, op.chain, op.asset, op.recipient, 0), "terminal proof mismatch")
        if op.status == "FAILED":
            require(duplicate, "different terminal outcome")
            return op
        require(not duplicate, "terminal evidence already consumed")
        item = self.obligations[op.obligation]
        if op.kind == "collateral-unlock":
            self.locks[item.lock].release_pending = False
        if op.kind == "rollback":
            item.gas_assessed = False  # Re-read the original remaining gas budget.
        op.status = "FAILED"
        self._save_fact(fact, commitment)
        return op

    def observe_liquidation_source(self, operation_id, raw, *, now):
        op = self.operations[operation_id]
        require(op.kind == "debt-liquidation" and
                op.status in ("UNKNOWN", "CONFIRMED", "FAILED"), "no issued liquidation")
        item = self.obligations[op.obligation]
        lock = self.locks[item.lock]
        fact, commitment, duplicate = self._fact(raw, "liquidation-source", now)
        p = self.profile
        require((fact.reference, fact.chain, fact.asset, fact.account, fact.location) ==
                (op.commitment, p.collateral_chain, p.collateral_asset, item.borrower, p.vault),
                "source liquidation mismatch")
        require(fact.units <= op.collateral_limit, "source exceeds approved collateral limit")
        require(op.penalty_record is None or op.penalty_record["units"] <= fact.units,
                "penalty exceeds gross source consumption")
        if op.collateral_spent is not None:
            require(duplicate and op.collateral_spent == fact.units, "source outcome conflict")
            return op.collateral_spent
        require(not duplicate and fact.units <= lock.units and fact.units <= item.collateral_remaining,
                "collateral accounting conflict")
        # A finalized source execution/non-execution fact releases its unused
        # cap, but does not confirm any destination funds or discharge debt.
        lock.units -= fact.units
        item.collateral_remaining -= fact.units
        op.collateral_spent = fact.units
        op.source_record = asdict(fact)
        self._save_fact(fact, commitment)
        return fact.units

    def observe_liquidation_cost(self, operation_id, raw, *, now):
        """Record EX's actual native fee, not an automatic new borrower debt."""
        op = self.operations[operation_id]
        require(op.kind == "debt-liquidation" and op.status in ("UNKNOWN", "CONFIRMED", "FAILED")
                and op.funding_record is not None, "issued EX-funded liquidation required")
        terms = op.liquidation_terms
        fact, commitment, duplicate = self._fact(raw, "liquidation-cost", now)
        require((fact.reference, fact.chain, fact.asset, fact.account, fact.location) ==
                (op.commitment, self.profile.collateral_chain, terms["gasAsset"],
                 terms["gasPayer"], terms["gasBudget"]), "EX cost binding mismatch")
        require(fact.units <= terms["gasCapUnits"], "actual execution cost exceeds approved cap")
        if op.cost_record is not None:
            require(duplicate and op.cost_record == asdict(fact), "EX cost conflict")
            return op
        require(not duplicate, "EX cost evidence already consumed")
        op.cost_record = asdict(fact)
        self._save_fact(fact, commitment)
        return op

    def observe_liquidation_penalty(self, operation_id, raw, *, now):
        """Penalty is a component of gross source use, never a second debit."""
        op = self.operations[operation_id]
        require(op.kind == "debt-liquidation" and op.status in ("UNKNOWN", "CONFIRMED", "FAILED"),
                "issued liquidation required")
        item, terms = self.obligations[op.obligation], op.liquidation_terms
        reference = digest({"operation": op.commitment, "policy": terms["penaltyPolicy"],
                            "priority": terms["priorityPolicy"], "conversion": terms["conversionPolicy"]})
        fact, commitment, duplicate = self._fact(raw, "liquidation-penalty", now)
        require((fact.reference, fact.chain, fact.asset, fact.account, fact.location) ==
                (reference, self.profile.collateral_chain, terms["penaltyAsset"],
                 item.borrower, self.profile.vault), "collateral penalty binding mismatch")
        require(fact.units <= terms["penaltyCapUnits"] and
                (op.collateral_spent is None or fact.units <= op.collateral_spent),
                "penalty exceeds approved or actual gross source consumption")
        if op.penalty_record is not None:
            require(duplicate and op.penalty_record == asdict(fact), "penalty evidence conflict")
            return op
        require(not duplicate, "penalty evidence already consumed")
        op.penalty_record = asdict(fact)
        self._save_fact(fact, commitment)
        return op

    def observe_collateral_remainder(self, lock_id, raw, *, now):
        lock = self.locks[lock_id]
        require(lock.reserved == 0 and not lock.release_pending and not lock.released,
                "collateral obligations remain")
        require(not self._pending_lock(lock_id),
                "collateral outcome unknown")
        fact, commitment, duplicate = self._fact(raw, "collateral-remainder", now)
        p = self.profile
        require((fact.reference, fact.chain, fact.asset, fact.account, fact.location) ==
                (lock_id, p.collateral_chain, p.collateral_asset, lock.borrower, p.vault),
                "collateral remainder mismatch")
        require(now - fact.observed_at <= p.valuation_max_age and fact.units <= lock.units,
                "stale or inconsistent remainder")
        if not duplicate:
            lock.units = fact.units
            lock.capacity = 0  # Final release only; a new lock needs new evidence.
            lock.remainder_verified = True
            self._save_fact(fact, commitment)
        return lock.units

    def public_status(self, obligation_id):
        """Identity-free data for existing UI; not authorization to read it."""
        item = self.obligations[obligation_id]
        lock = self.locks[item.lock]
        reconciliation_pending = any(op.obligation == obligation_id
                                     for op in self._pending_lock(item.lock))
        state = ("ROLLED_BACK" if item.rollback_confirmed else "SETTLED" if item.resolved else
                 "ROLLBACK_PENDING" if item.rollback else "UNSETTLED")
        return {"schema": "8415ex-deferred-status/2", "state": state,
                "registration": "COMPLETE" if item.registered else "NOT_CONFIRMED",
                "nftRollbackDetached": item.registered,
                "debtStatus": "CANCELLED_BY_ROLLBACK" if item.rollback_confirmed else
                              "ROLLBACK_PENDING" if item.rollback else
                              "OUTSTANDING" if item.registered and item.due else
                              "SETTLED" if item.resolved else "CONTINGENT",
                "principalUnits": item.principal,
                "settlementFeeWei": item.settlement_fee_wei,
                "settlementFeeAsset": "ETH",
                "settlementFeeChain": self.profile.settlement_chain,
                "normalGasCapWei": item.normal_gas["capWei"],
                "sourceNormalGasCapWei": item.source_normal_gas["capWei"],
                "sourceNormalGasChain": self.profile.collateral_chain,
                "paidUnits": item.paid, "escrowUnits": item.escrow,
                "shortfallUnits": 0 if item.rollback else max(0, item.due - item.escrow),
                "settlementDeadline": item.deadline,
                "collateralUnits": 0 if lock.released or (item.resolved and not reconciliation_pending)
                                   else item.collateral_remaining,
                "collateralReconciliationPending": reconciliation_pending,
                "recordedCollateralAllocationUnits": item.collateral_remaining,
                "collateralLockState": "RELEASED" if lock.released else
                                       "RELEASE_PENDING" if lock.release_pending else "LOCKED",
                "sourceExposurePending": any(op.obligation == obligation_id for op in self._source_pending(item.lock)),
                "operations": [{"kind": op.kind, "status": op.status,
                                "liquidationCostUnits": None if op.cost_record is None else op.cost_record["units"],
                                "liquidationCostAsset": None if op.liquidation_terms is None else op.liquidation_terms["gasAsset"],
                                "liquidationCostChain": None if op.liquidation_terms is None else self.profile.collateral_chain,
                                "collateralPenaltyUnits": None if op.penalty_record is None else op.penalty_record["units"],
                                "collateralPenaltyAsset": None if op.liquidation_terms is None else op.liquidation_terms["penaltyAsset"]}
                               for op in self.operations.values()
                               if op.obligation == obligation_id]}

    def snapshot(self):
        """Canonical private checkpoint input; does not itself persist anything."""
        return {"schema": "8415ex-deferred/2", "profile": asdict(self.profile),
                "locks": {k: asdict(v) for k, v in self.locks.items()},
                "obligations": {k: asdict(v) for k, v in self.obligations.items()},
                "operations": {k: asdict(v) for k, v in self.operations.items()},
                "evidence": dict(self.evidence)}

    @classmethod
    def restore(cls, profile, verifier, state):
        """Restore trusted private checkpoint bytes, refusing accounting drift.

        A checkpoint is not proof authority. Only the original configured store
        may provide this state; callers cannot import arbitrary client snapshots.
        """
        require(type(state) is dict and set(state) ==
                {"schema", "profile", "locks", "obligations", "operations", "evidence"},
                "invalid checkpoint fields")
        require(state["schema"] != "8415ex-deferred/1",
                "LEGACY_FEE_ACCOUNTING_RECONCILIATION_REQUIRED")
        require(state["schema"] == "8415ex-deferred/2" and state["profile"] == asdict(profile),
                "checkpoint profile mismatch")
        result = cls(profile, verifier)
        for key, constructor in (("locks", Lock), ("obligations", Obligation), ("operations", Operation)):
            require(type(state[key]) is dict, "invalid checkpoint map")
            for identity, raw in state[key].items():
                identifier(identity)
                require(type(raw) is dict, "invalid checkpoint record")
                try:
                    record = constructor(**raw)
                except (TypeError, ValueError) as error:
                    raise DeferredRefused("invalid checkpoint record") from error
                require(record.identity == identity, "checkpoint identity mismatch")
                getattr(result, key)[identity] = record
        require(type(state["evidence"]) is dict, "invalid evidence index")
        for identity, commitment in state["evidence"].items():
            identifier(identity)
            require(type(commitment) is str and len(commitment) == 66 and commitment.startswith("0x")
                    and all(c in "0123456789abcdef" for c in commitment[2:]), "invalid evidence commitment")
        result.evidence = dict(state["evidence"])
        for lock in result.locks.values():
            identifier(lock.borrower)
            instant(lock.valued_at)
            for value in (lock.units, lock.capacity, lock.reserved):
                amount(value)
            require(lock.units >= 0 and 0 <= lock.reserved <= lock.capacity, "invalid lock balance")
            require(all(type(v) is bool for v in (lock.release_pending, lock.released, lock.liquidating, lock.remainder_verified)),
                    "invalid lock flags")
        claimed_receipts, claimed_allocations, claimed_budgets = set(), set(), set()
        claimed_source_allocations, claimed_source_budgets = set(), set()
        for item in result.obligations.values():
            require(item.lock in result.locks and item.borrower == result.locks[item.lock].borrower,
                    "obligation collateral mismatch")
            identifier(item.seller)
            instant(item.deadline)
            for value in (item.principal, item.settlement_fee_wei, item.escrow,
                          item.paid, item.gas_required, item.gas_received, item.collateral_remaining):
                amount(value)
            require(item.principal > 0 and 0 <= item.paid <= item.principal,
                    "invalid obligation amount")
            result._validate_normal_gas(item.normal_gas, item.settlement_fee_wei)
            result._validate_normal_gas(item.source_normal_gas)
            require(item.gas_received <= item.normal_gas["capWei"] and
                    item.gas_required <= item.normal_gas["capWei"], "stored normal gas exceeds cap")
            if item.normal_gas_availability is None:
                require(not item.gas_assessed and item.gas_received == 0 and item.gas_required == 0,
                        "unearned normal gas observation")
            else:
                raw = item.normal_gas_availability
                require(type(raw) is dict and set(raw) == set(Fact.__dataclass_fields__),
                        "invalid normal gas observation")
                availability = Fact(**raw)
                result._validate_fact(availability, "normal-gas-availability")
                reference = digest({"obligation": item.identity, "terms": item.consent,
                                    "allocation": item.gas_allocation, "normalGas": item.normal_gas})
                require((availability.reference, availability.chain, availability.asset,
                         availability.account, availability.location, availability.units,
                         availability.destination_units) ==
                        (reference, profile.settlement_chain, "ETH", item.borrower,
                         item.normal_gas["location"], item.gas_received, item.gas_required) and
                        result.evidence.get(availability.identity) == digest(raw),
                        "stored original normal gas observation mismatch")
            terms = digest({"id": item.identity, "lock": item.lock, "borrower": item.borrower,
                            "seller": item.seller, "principal": item.principal,
                            "settlementFeeWei": item.settlement_fee_wei,
                            "normalGas": item.normal_gas, "sourceNormalGas": item.source_normal_gas,
                            "deadline": item.deadline,
                            "profile": asdict(profile)})
            require(item.consent == terms, "stored fee terms mismatch")
            receipt_reference = digest({"terms": terms, "feeReceipt": item.fee_receipt,
                                        "normalGas": item.normal_gas})
            source_reference = digest({"terms": terms, "feeReceipt": item.fee_receipt,
                                       "sourceNormalGas": item.source_normal_gas})
            for raw, identity, kind, reference, chain, location, units in (
                (item.fee_receipt_record, item.fee_receipt, "settlement-fee-receipt",
                 terms, profile.settlement_chain, profile.fee_receiver, item.settlement_fee_wei),
                (item.gas_allocation_record, item.gas_allocation, "normal-gas-allocation",
                 receipt_reference, profile.settlement_chain, item.normal_gas["location"], item.normal_gas["capWei"]),
                (item.source_gas_record, item.source_gas_allocation, "source-normal-gas-allocation",
                 source_reference, profile.collateral_chain, item.source_normal_gas["location"], item.source_normal_gas["capWei"]),
            ):
                require(type(raw) is dict and set(raw) == set(Fact.__dataclass_fields__),
                        "invalid stored funding fact")
                stored = Fact(**raw)
                result._validate_fact(stored, kind)
                require((stored.identity, stored.kind, stored.reference, stored.chain,
                         stored.asset, stored.account, stored.location, stored.units,
                         stored.profile_commitment) ==
                        (identity, kind, reference, chain, "ETH",
                         item.borrower, location, units, digest(asdict(profile))),
                        "stored funding binding mismatch")
                instant(stored.observed_at)
                require(stored.observed_at < item.deadline and
                        result.evidence.get(identity) == digest(raw),
                        "stored funding evidence missing or inconsistent")
            require(item.fee_receipt not in claimed_receipts and
                    item.gas_allocation not in claimed_allocations and
                    item.fee_receipt != item.gas_allocation and
                    item.normal_gas["budget"] not in claimed_budgets,
                    "funding consumed by multiple obligations")
            claimed_receipts.add(item.fee_receipt)
            claimed_allocations.add(item.gas_allocation)
            claimed_budgets.add(item.normal_gas["budget"])
            require(item.source_gas_allocation not in claimed_source_allocations and
                    item.source_normal_gas["budget"] not in claimed_source_budgets and
                    item.source_gas_allocation not in (item.fee_receipt, item.gas_allocation),
                    "source funding consumed by multiple obligations")
            claimed_source_allocations.add(item.source_gas_allocation)
            claimed_source_budgets.add(item.source_normal_gas["budget"])
            require(all(type(v) is bool for v in (item.registered, item.rollback,
                    item.rollback_confirmed, item.resolved, item.gas_assessed)), "invalid obligation flags")
            require(not (item.registered and item.rollback), "registered rollback contradiction")
            require(not item.rollback_confirmed or item.rollback, "unrequested rollback completion")
            require(item.resolved == (item.rollback_confirmed or item.paid == item.principal),
                    "unearned resolution")
        # Validate references and numeric shape before any cross-record sums.
        for op in result.operations.values():
            require(op.obligation in result.obligations, "orphan operation")
            amount(op.units)
            amount(op.collateral_limit)
            if op.collateral_spent is not None:
                amount(op.collateral_spent)
            require(op.status in ("PREPARED", "UNKNOWN", "CONFIRMED", "FAILED"),
                    "invalid operation state")
        for identity, lock in result.locks.items():
            required = sum(x.principal for x in result.obligations.values()
                           if x.lock == identity and not x.resolved)
            require(required == lock.reserved, "lost collateral reservation")
            allocated = sum(x.collateral_remaining for x in result.obligations.values()
                            if x.lock == identity and not x.resolved)
            allocated += sum(op.collateral_limit for op in result._source_pending(identity)
                             if result.obligations[op.obligation].resolved)
            require(allocated <= lock.units, "collateral allocation overdrawn")
        for op in result.operations.values():
            require(op.obligation in result.obligations, "orphan operation")
            amount(op.units)
            amount(op.collateral_limit)
            if op.collateral_spent is not None:
                amount(op.collateral_spent)
                require(op.collateral_spent <= op.collateral_limit, "invalid source consumption")
            chain_id(op.chain)
            require(op.kind in ("seller-payment", "debt-liquidation", "rollback", "excess-refund", "collateral-unlock"),
                    "invalid operation kind")
            require(op.status in ("PREPARED", "UNKNOWN", "CONFIRMED", "FAILED"), "invalid operation state")
            item = result.obligations[op.obligation]
            for value in (op.identity, op.obligation, op.asset, op.recipient):
                identifier(value)
            expected_commitment = digest({"id": op.identity, "obligation": op.obligation,
                "kind": op.kind, "units": op.units, "asset": op.asset, "chain": op.chain,
                "recipient": op.recipient, "consent": item.consent, "profile": asdict(profile),
                "collateralLimit": op.collateral_limit, "quote": op.quote,
                "liquidationTerms": op.liquidation_terms, "normalFunding": op.normal_funding})
            require(op.commitment == expected_commitment, "stored operation commitment mismatch")
            require(op.normal_funding == result._normal_funding(item, op.kind),
                    "stored original normal funding binding mismatch")
            if op.kind != "debt-liquidation":
                require(all(value is None for value in (op.liquidation_terms, op.funding_record,
                        op.cost_record, op.penalty_record, op.quote_record, op.authority_record,
                        op.source_record, op.collateral_spent)),
                        "unexpected liquidation accounting")
                require(op.quote == "" and op.collateral_limit == 0,
                        "unexpected liquidation source reservation")
                continue
            result._validate_liquidation_terms(op.liquidation_terms, item.borrower)
            terms = op.liquidation_terms
            require(terms["penaltyCapUnits"] <= op.collateral_limit,
                    "stored penalty cap exceeds source limit")
            quote_terms = digest({"obligation": op.obligation, "kind": op.kind, "target": op.units,
                                  "asset": op.asset, "chain": op.chain, "recipient": op.recipient,
                                  "consent": item.consent, "liquidationTerms": terms})
            authority_reference = digest({"operation": op.identity, "quote": op.quote,
                                          "terms": quote_terms, "collateralCap": op.collateral_limit})
            for raw, kind, reference in ((op.quote_record, "liquidation-quote", quote_terms),
                                        (op.authority_record, "liquidation-authority", authority_reference)):
                require(type(raw) is dict and set(raw) == set(Fact.__dataclass_fields__),
                        "original liquidation evidence missing")
                original = Fact(**raw)
                result._validate_fact(original, kind)
                require((original.reference, original.chain, original.asset, original.account,
                         original.location, original.units) ==
                        (reference, profile.collateral_chain, profile.collateral_asset,
                         item.borrower, profile.vault, op.collateral_limit),
                        "original liquidation evidence binding mismatch")
                require(result.evidence.get(original.identity) == digest(raw),
                        "original liquidation evidence index mismatch")
                if kind == "liquidation-quote":
                    require(digest(raw) == op.quote and original.destination_units >= op.units,
                            "original liquidation quote changed")
            if op.status != "PREPARED":
                require(op.funding_record is not None, "issued liquidation lacks EX funding")
            require((op.collateral_spent is None) == (op.source_record is None),
                    "source outcome lacks original evidence")
            if op.source_record is not None:
                raw = op.source_record
                require(type(raw) is dict and set(raw) == set(Fact.__dataclass_fields__),
                        "invalid source liquidation fact")
                source = Fact(**raw)
                result._validate_fact(source, "liquidation-source")
                require(op.status != "PREPARED" and
                        (source.reference, source.chain, source.asset, source.account,
                         source.location, source.units) ==
                        (op.commitment, profile.collateral_chain, profile.collateral_asset,
                         item.borrower, profile.vault, op.collateral_spent) and
                        result.evidence.get(source.identity) == digest(raw),
                        "stored gross source consumption mismatch")
            penalty_reference = digest({"operation": op.commitment, "policy": terms["penaltyPolicy"],
                                        "priority": terms["priorityPolicy"], "conversion": terms["conversionPolicy"]})
            for raw, kind, reference, asset, account, location, cap in (
                (op.funding_record, "liquidation-ex-funding", op.commitment,
                 terms["gasAsset"], terms["gasPayer"], terms["gasBudget"], terms["gasCapUnits"]),
                (op.cost_record, "liquidation-cost", op.commitment,
                 terms["gasAsset"], terms["gasPayer"], terms["gasBudget"], terms["gasCapUnits"]),
                (op.penalty_record, "liquidation-penalty", penalty_reference,
                 terms["penaltyAsset"], item.borrower, profile.vault, terms["penaltyCapUnits"]),
            ):
                if raw is None:
                    continue
                require(type(raw) is dict and set(raw) == set(Fact.__dataclass_fields__),
                        "invalid liquidation accounting fact")
                stored = Fact(**raw)
                result._validate_fact(stored, kind)
                require((stored.reference, stored.chain, stored.asset, stored.account, stored.location) ==
                        (reference, profile.collateral_chain, asset, account, location),
                        "stored liquidation accounting binding mismatch")
                require(stored.units <= cap and result.evidence.get(stored.identity) == digest(raw),
                        "stored liquidation accounting amount or evidence mismatch")
                if kind == "liquidation-ex-funding":
                    require(stored.units == cap, "stored EX funding cap mismatch")
                else:
                    require(op.status != "PREPARED", "unissued liquidation expense")
                if kind == "liquidation-penalty" and op.collateral_spent is not None:
                    require(stored.units <= op.collateral_spent, "stored penalty exceeds gross source use")
        for identity, lock in result.locks.items():
            require(sum(op.collateral_limit for op in result._source_pending(identity)) <= lock.units,
                    "collateral over-reserved")
        for identity in result.obligations:
            require(len(result._pending(identity)) <= 1, "overlapping pending operations")
        return result
