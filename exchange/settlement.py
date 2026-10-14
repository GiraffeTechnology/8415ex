"""Stage 2: one escrow position per leg, and an optional payment adapter.

Each leg funds itself. A later leg's unreleased money can never support an
earlier one, so every position carries its own payer, payee, asset and
principal, and a release pays exactly that position to exactly that payee.

Release and refund are mutually exclusive terminal outcomes. Neither can happen
twice, and a payment whose outcome is unknown is never "fixed" by sending a
second one: the adapter is asked what actually happened first.

Authority for a release is evidence bound to a source, an asset, a segment and a
journal reference. A plain signature, the text ``VALID``, public JSON or a bare
settlement identifier is not authority and is refused here.
"""
from dataclasses import dataclass, replace

from .errors import DomainError, require
from .ids import HEX32, address, amount, digest, identifier, instant
from .model import Asset

ESCROW_STATUSES = ("locked", "released", "refunded")
PAYMENT_OUTCOMES = ("settled", "failed", "unknown")

#: Things that are explicitly not release authority, kept as a named list so the
#: refusal is testable rather than implied.
NOT_AUTHORITY = ("plain-signature", "valid-text", "public-json", "bare-settlement-id")


@dataclass(frozen=True)
class EscrowPosition:
    """One leg's own funds. Never pooled with another leg's."""

    escrow_id: str
    receipt_id: str
    leg_index: int
    payer: str
    payee: str
    quote_asset: str
    principal: int
    status: str = "locked"
    locked_at: int = 0
    settled_at: int = None
    refunded_at: int = None
    payment_key: str = None
    payment_status: str = None
    payment_reference: str = None
    #: What the recorded payment was for, so a resumed enquiry applies the
    #: outcome that was actually attempted instead of assuming a release.
    payment_intent: str = None
    gas_record: tuple = ()

    def __post_init__(self):
        identifier(self.escrow_id, "EX_ESCROW_REFUSED")
        identifier(self.receipt_id, "EX_ESCROW_REFUSED")
        require(isinstance(self.leg_index, int) and not isinstance(self.leg_index, bool)
                and self.leg_index >= 0, "EX_ESCROW_REFUSED", "leg index must be a non-negative integer")
        address(self.payer, "EX_ESCROW_REFUSED")
        address(self.payee, "EX_ESCROW_REFUSED")
        require(self.payer != self.payee, "EX_ESCROW_REFUSED", "a position needs two distinct parties")
        identifier(self.quote_asset, "EX_ESCROW_REFUSED")
        amount(self.principal, "EX_ESCROW_REFUSED")
        require(self.principal > 0, "EX_ESCROW_REFUSED", "a funded position needs a positive principal")
        require(self.status in ESCROW_STATUSES, "EX_ESCROW_REFUSED", self.status)
        require(not (self.settled_at is not None and self.refunded_at is not None),
                "EX_ESCROW_DOUBLE_OUTCOME_REFUSED",
                "release and refund are mutually exclusive")
        if self.payment_status is not None:
            require(self.payment_status in PAYMENT_OUTCOMES, "EX_ESCROW_REFUSED", self.payment_status)
        if self.payment_intent is not None:
            require(self.payment_intent in ("release", "refund"), "EX_ESCROW_REFUSED",
                    self.payment_intent)

    @property
    def terminal(self):
        return self.status in ("released", "refunded")

    @property
    def gas_total(self):
        """What this leg's buyer bore, in the gas asset's smallest unit."""
        return sum(entry["amount"] for entry in self.gas_record)


@dataclass(frozen=True)
class ReleaseAuthority:
    """Evidence that a specific segment of a specific asset may be released.

    Every field is required. The journal reference ties the release to the
    operation journal the authority wrote it in, and ``binding`` is a digest over
    the segment's own facts so the evidence cannot be re-pointed at another leg.
    """

    authority_id: str
    source: str
    receipt_id: str
    leg_index: int
    transfer_id: str
    asset: Asset
    journal_reference: str
    binding: str
    observed_at: int

    def __post_init__(self):
        identifier(self.authority_id, "EX_RELEASE_AUTHORITY_REFUSED")
        identifier(self.source, "EX_RELEASE_AUTHORITY_REFUSED")
        identifier(self.receipt_id, "EX_RELEASE_AUTHORITY_REFUSED")
        require(isinstance(self.leg_index, int) and not isinstance(self.leg_index, bool)
                and self.leg_index >= 0, "EX_RELEASE_AUTHORITY_REFUSED", "leg index")
        identifier(self.transfer_id, "EX_RELEASE_AUTHORITY_REFUSED")
        require(isinstance(self.asset, Asset), "EX_RELEASE_AUTHORITY_REFUSED", "asset must be an Asset")
        identifier(self.journal_reference, "EX_RELEASE_AUTHORITY_REFUSED")
        require(isinstance(self.binding, str) and HEX32.match(self.binding) is not None,
                "EX_RELEASE_AUTHORITY_REFUSED", "the binding must be a 32-byte digest")
        instant(self.observed_at, "EX_RELEASE_AUTHORITY_REFUSED")


def segment_binding(asset, receipt_id, leg_index, transfer_id, payer, payee, principal, quote_asset):
    """The digest a release authority must carry for one segment."""
    return digest({"chainId": asset.chain_id, "contract": asset.contract, "tokenId": asset.token_id,
                   "receiptId": receipt_id, "legIndex": leg_index, "transferId": transfer_id,
                   "payer": payer, "payee": payee, "principal": str(principal),
                   "quoteAsset": quote_asset})


class SimulatedPaymentAdapter:
    """An optional, separate payment path. Simulated, local, and idempotent.

    The adapter is deliberately not part of the responsibility model: an escrow
    record, an amount or a released payment is never authority for completion.
    It only moves a recorded amount and reports what happened.

    ``outcomes`` lets a test drive the first answer for a key; a repeat of that
    key always returns the stored record instead of moving anything again.
    """

    def __init__(self, clock, outcomes=None):
        self._clock = clock
        self._records = {}
        self._outcomes = dict(outcomes or {})
        self.movements = 0

    def lookup(self, payment_key):
        """What actually happened, if anything. Asked before any retry."""
        return self._records.get(identifier(payment_key, "EX_PAYMENT_REFUSED"))

    def pay(self, payment_key, payer, payee, quote_asset, principal):
        """Move one principal once. A repeat never moves anything again."""
        identifier(payment_key, "EX_PAYMENT_REFUSED")
        existing = self._records.get(payment_key)
        if existing is not None:
            require(existing["payee"] == payee and existing["payer"] == payer
                    and existing["principal"] == principal
                    and existing["quoteAsset"] == quote_asset,
                    "EX_PAYMENT_SUBSTITUTION_REFUSED",
                    f"{payment_key} was already used for different payment terms")
            return dict(existing, repeated=True)
        address(payer, "EX_PAYMENT_REFUSED")
        address(payee, "EX_PAYMENT_REFUSED")
        require(payer != payee, "EX_PAYMENT_REFUSED", "a payment needs two distinct parties")
        amount(principal, "EX_PAYMENT_REFUSED")
        require(principal > 0, "EX_PAYMENT_REFUSED", "a payment needs a positive amount")
        outcome = self._outcomes.pop(payment_key, "settled")
        require(outcome in PAYMENT_OUTCOMES, "EX_PAYMENT_REFUSED", outcome)
        record = {"paymentKey": payment_key, "payer": payer, "payee": payee,
                  "quoteAsset": quote_asset, "principal": principal, "status": outcome,
                  "reference": f"sim-payment:{payment_key}", "observedAt": self._clock(),
                  "simulated": True}
        if outcome != "failed":
            # A failed attempt leaves no record to resume from; an unknown one
            # does, because the money may well have moved.
            self._records[payment_key] = record
        if outcome == "settled":
            self.movements += 1
        return dict(record, repeated=False)

    def resolve_unknown(self, payment_key, status):
        """Record what a later enquiry established about an unknown outcome.

        This is the adapter being asked; it is not a second payment. The movement
        counter is untouched, because nothing new is sent.
        """
        record = self._records.get(identifier(payment_key, "EX_PAYMENT_REFUSED"))
        require(record is not None, "EX_PAYMENT_UNKNOWN_KEY", payment_key)
        require(record["status"] == "unknown", "EX_PAYMENT_ALREADY_RESOLVED", record["status"])
        require(status in ("settled", "failed"), "EX_PAYMENT_REFUSED", status)
        self._records[payment_key] = dict(record, status=status, resolvedAt=self._clock())
        return self._records[payment_key]
