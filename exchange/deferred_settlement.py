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

    def __post_init__(self):
        chain_id(self.settlement_chain)
        chain_id(self.collateral_chain)
        require(self.settlement_chain != self.collateral_chain, "cross-chain profile required")
        for value in (self.principal_asset, self.collateral_asset, self.vault,
                      self.escrow, self.policy, self.checkpoint_scope):
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
    fee: int
    deadline: int
    consent: str
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

    @property
    def due(self):
        return self.principal + self.fee - self.paid


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
        require(fact.observed_at <= now, "future observation")
        commitment = digest(asdict(fact))
        old = self.evidence.get(fact.identity)
        require(old is None or old == commitment, "evidence identity collision")
        return fact, commitment, old is not None

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
                fee, deadline, now, seller_consent, borrower_authority):
        """Consent must bind the complete terms; verifier checks its signature."""
        for value in (obligation_id, lock_id, borrower, seller):
            identifier(value)
        amount(principal)
        amount(fee)
        instant(deadline)
        instant(now)
        require(principal > 0 and deadline > now, "invalid amount or deadline")
        require(obligation_id not in self.obligations, "obligation already exists")
        require(lock_id in self.locks, "verified collateral missing")
        lock = self.locks[lock_id]
        require(lock.borrower == borrower and not lock.release_pending and not lock.released and not lock.liquidating,
                "collateral unavailable")
        require(lock.valued_at <= now and now - lock.valued_at <= self.profile.valuation_max_age, "collateral valuation expired before reservation")
        terms = digest({"id": obligation_id, "lock": lock_id, "borrower": borrower,
                        "seller": seller, "principal": principal, "fee": fee,
                        "deadline": deadline, "profile": asdict(self.profile)})
        fact, commitment, duplicate = self._fact(seller_consent, "seller-consent", now)
        require(not duplicate, "consent replay")
        require((fact.reference, fact.account, fact.asset, fact.chain, fact.location, fact.units) ==
                (terms, seller, self.profile.principal_asset, self.profile.settlement_chain,
                 self.profile.escrow, principal + fee), "consent does not bind exact terms")
        admission, admission_commitment, admission_duplicate = self._fact(borrower_authority, "deferred-admission", now)
        require(not admission_duplicate and admission.identity != fact.identity, "admission replay")
        require((admission.reference, admission.account, admission.chain, admission.asset, admission.location, admission.units) ==
                (terms, borrower, self.profile.settlement_chain, self.profile.principal_asset,
                 self.profile.escrow, principal + fee), "wallet admission/gas/authority binding mismatch")
        require(not self._pending_lock(lock_id), "collateral has unresolved operations")
        require(principal + fee <= lock.capacity - lock.reserved, "allowance exhausted")
        collateral_units = (lock.units * (principal + fee) + lock.capacity - 1) // lock.capacity
        allocated = sum(x.collateral_remaining for x in self.obligations.values()
                        if x.lock == lock_id and not x.resolved)
        require(collateral_units <= lock.units - allocated, "collateral units already allocated")
        result = Obligation(obligation_id, lock_id, borrower, seller, principal, fee,
                            deadline, terms, collateral_remaining=collateral_units)
        lock.reserved += principal + fee
        self.obligations[obligation_id] = result
        self._save_fact(fact, commitment)
        self._save_fact(admission, admission_commitment)
        return result

    def observe_registration(self, obligation_id, raw, *, now):
        item = self.obligations[obligation_id]
        fact, commitment, duplicate = self._fact(raw, "registration-cut", now)
        require((fact.reference, fact.chain, fact.account) ==
                (obligation_id, self.profile.settlement_chain, item.borrower), "registration binding mismatch")
        require(fact.observed_at <= item.deadline, "registration cut is after settlement deadline")
        if item.rollback:
            involved = [op for op in self.operations.values() if op.obligation == obligation_id
                        and op.kind in ("rollback", "gas-liquidation")]
            require(not any(op.status in ("UNKNOWN", "CONFIRMED") for op in involved),
                    "authoritative registration conflicts with an external recovery; reconcile")
            for op in involved:
                if op.status == "PREPARED":
                    op.status = "FAILED"
                    if op.kind == "gas-liquidation":
                        op.collateral_spent = 0
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
                and op.kind in ("debt-liquidation", "gas-liquidation") and op.collateral_spent is None]

    def _pending_lock(self, lock_id):
        return [op for op in self.operations.values()
                if self.obligations[op.obligation].lock == lock_id
                and (op.status not in ("CONFIRMED", "FAILED") or op in self._source_pending(lock_id))]

    def _pending(self, obligation_id):
        return [op for op in self.operations.values()
                if op.obligation == obligation_id and op.status not in ("CONFIRMED", "FAILED")]

    def prepare(self, operation_id, obligation_id, *, kind, now, units=None, liquidation_quote=None):
        identifier(operation_id)
        instant(now)
        item = self.obligations[obligation_id]
        previous = self.operations.get(operation_id)
        if previous is not None:
            require(previous.obligation == obligation_id and previous.kind == kind,
                    "operation identity collision")
            if units is not None:
                amount(units)
                require(units == previous.units, "operation amount mismatch")
            if kind in ("debt-liquidation", "gas-liquidation"):
                _, quote_hash, _ = self._fact(liquidation_quote, "liquidation-quote", now)
                require(quote_hash == previous.quote, "operation quote mismatch")
            else:
                require(liquidation_quote is None, "unexpected liquidation quote")
            expected = digest({"id": operation_id, "obligation": obligation_id, "kind": kind,
                "units": previous.units, "asset": previous.asset, "chain": previous.chain,
                "recipient": previous.recipient, "consent": item.consent,
                "profile": asdict(self.profile), "collateralLimit": previous.collateral_limit,
                "quote": previous.quote})
            require(expected == previous.commitment, "stored operation commitment mismatch")
            return previous
        require(not item.resolved or kind in ("excess-refund", "collateral-unlock"), "closed obligation")
        p = self.profile
        collateral_limit, quote_commitment, quote_fact, quote_duplicate = 0, "", None, False
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
        elif kind == "gas-liquidation":
            require(item.rollback, "rollback gas recovery only")
            value = item.gas_required - item.gas_received
            require(value > 0, "no verified gas shortage")
            asset, chain, recipient = "ETH", p.settlement_chain, p.escrow
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
        if kind in ("debt-liquidation", "gas-liquidation"):
            quote_fact, quote_commitment, quote_duplicate = self._fact(liquidation_quote, "liquidation-quote", now)
            quote_terms = digest({"obligation": obligation_id, "kind": kind, "target": value,
                                  "asset": asset, "chain": chain, "recipient": recipient,
                                  "consent": item.consent})
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
        if units is not None:
            amount(units)
            require(units == value, "operation amount mismatch")
        payload = {"id": operation_id, "obligation": obligation_id, "kind": kind,
                   "units": value, "asset": asset, "chain": chain, "recipient": recipient,
                   "consent": item.consent, "profile": asdict(p),
                   "collateralLimit": collateral_limit, "quote": quote_commitment}
        commitment = digest(payload)
        old = self.operations.get(operation_id)
        if old:
            require(old.commitment == commitment, "operation identity collision")
            return old
        require(not quote_duplicate, "liquidation quote already consumed")
        require(not self._pending(obligation_id), "reconcile pending operation first")
        op = Operation(operation_id, obligation_id, kind, value, asset, chain,
                       recipient, commitment, collateral_limit=collateral_limit, quote=quote_commitment)
        if quote_fact is not None:
            self._save_fact(quote_fact, quote_commitment)
        if kind == "collateral-unlock":
            self.locks[item.lock].release_pending = True
        self.operations[operation_id] = op
        return op

    def observe_gas_requirement(self, obligation_id, raw, *, now):
        item = self.obligations[obligation_id]
        require(item.rollback and not self._pending(obligation_id), "rollback must be quiescent")
        fact, commitment, duplicate = self._fact(raw, "rollback-gas-shortfall", now)
        require((fact.reference, fact.asset, fact.chain, fact.account) ==
                (obligation_id, "ETH", self.profile.settlement_chain, item.borrower),
                "gas scope mismatch")
        if not duplicate:
            item.gas_assessed = True
            item.gas_required = item.gas_received + fact.units
            self._save_fact(fact, commitment)
        return fact.units

    def mark_dispatched(self, operation_id):
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
        op.status = "UNKNOWN"
        if op.kind in ("debt-liquidation", "gas-liquidation"):
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
        fact, commitment, duplicate = self._fact(raw, "operation-receipt", now)
        require((fact.reference, fact.chain, fact.asset, fact.account) ==
                (op.commitment, op.chain, op.asset, op.recipient), "receipt mismatch")
        if op.kind in ("debt-liquidation", "gas-liquidation"):
            require(0 <= fact.units <= op.units, "invalid liquidation destination amount")
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
        elif op.kind == "gas-liquidation":
            item.gas_received += fact.units  # Receipt is destination ETH, NOT Hoodi ETH.
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
            self.locks[item.lock].reserved -= item.principal + item.fee
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
        require(op.kind in ("debt-liquidation", "gas-liquidation") and
                op.status in ("UNKNOWN", "CONFIRMED", "FAILED"), "no issued liquidation")
        item = self.obligations[op.obligation]
        lock = self.locks[item.lock]
        fact, commitment, duplicate = self._fact(raw, "liquidation-source", now)
        p = self.profile
        require((fact.reference, fact.chain, fact.asset, fact.account, fact.location) ==
                (op.commitment, p.collateral_chain, p.collateral_asset, item.borrower, p.vault),
                "source liquidation mismatch")
        require(fact.units <= op.collateral_limit, "source exceeds approved collateral limit")
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
        self._save_fact(fact, commitment)
        return fact.units

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
        state = ("ROLLED_BACK" if item.rollback_confirmed else "SETTLED" if item.resolved else
                 "ROLLBACK_PENDING" if item.rollback else "UNSETTLED")
        return {"schema": "8415ex-deferred-status/1", "state": state,
                "registration": "COMPLETE" if item.registered else "NOT_CONFIRMED",
                "nftRollbackDetached": item.registered,
                "debtStatus": "CANCELLED_BY_ROLLBACK" if item.rollback_confirmed else
                              "ROLLBACK_PENDING" if item.rollback else
                              "OUTSTANDING" if item.registered and item.due else
                              "SETTLED" if item.resolved else "CONTINGENT",
                "principalUnits": item.principal, "feeUnits": item.fee,
                "paidUnits": item.paid, "escrowUnits": item.escrow,
                "shortfallUnits": 0 if item.rollback else max(0, item.due - item.escrow),
                "settlementDeadline": item.deadline,
                "collateralUnits": 0 if item.resolved or lock.released else item.collateral_remaining,
                "recordedCollateralAllocationUnits": item.collateral_remaining,
                "collateralLockState": "RELEASED" if lock.released else
                                       "RELEASE_PENDING" if lock.release_pending else "LOCKED",
                "sourceExposurePending": any(op.obligation == obligation_id for op in self._source_pending(item.lock)),
                "operations": [{"kind": op.kind, "status": op.status} for op in self.operations.values()
                               if op.obligation == obligation_id]}

    def snapshot(self):
        """Canonical private checkpoint input; does not itself persist anything."""
        return {"schema": "8415ex-deferred/1", "profile": asdict(self.profile),
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
        require(state["schema"] == "8415ex-deferred/1" and state["profile"] == asdict(profile),
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
        for item in result.obligations.values():
            require(item.lock in result.locks and item.borrower == result.locks[item.lock].borrower,
                    "obligation collateral mismatch")
            identifier(item.seller)
            instant(item.deadline)
            for value in (item.principal, item.fee, item.escrow, item.paid, item.gas_required, item.gas_received, item.collateral_remaining):
                amount(value)
            require(item.principal > 0 and 0 <= item.paid <= item.principal + item.fee,
                    "invalid obligation amount")
            require(all(type(v) is bool for v in (item.registered, item.rollback,
                    item.rollback_confirmed, item.resolved, item.gas_assessed)), "invalid obligation flags")
            require(not (item.registered and item.rollback), "registered rollback contradiction")
            require(not item.rollback_confirmed or item.rollback, "unrequested rollback completion")
            require(item.resolved == (item.rollback_confirmed or item.paid == item.principal + item.fee),
                    "unearned resolution")
        for identity, lock in result.locks.items():
            required = sum(x.principal + x.fee for x in result.obligations.values()
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
            require(op.kind in ("seller-payment", "debt-liquidation", "gas-liquidation", "rollback", "excess-refund", "collateral-unlock"),
                    "invalid operation kind")
            require(op.status in ("PREPARED", "UNKNOWN", "CONFIRMED", "FAILED"), "invalid operation state")
        for identity, lock in result.locks.items():
            require(sum(op.collateral_limit for op in result._source_pending(identity)) <= lock.units,
                    "collateral over-reserved")
        for identity in result.obligations:
            require(len(result._pending(identity)) <= 1, "overlapping pending operations")
        return result
