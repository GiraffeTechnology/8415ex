"""Stage 3: rolling back the unfinished suffix, and who pays for it.

A rollback acts only on the suffix that still carries rollback capability. A
finalized prefix - a segment whose money was released - is immutable: it is not
reopened, not reversed and not re-collected, and the asset returns only as far
as the boundary that prefix established.

Three things this module deliberately does not do, because the requirements
withdrew them: it never takes the asset into temporary custody, never imposes a
time-limited redemption or an overdue sale, and never liquidates a position to
cover a shortfall. A shortfall is reported as a blocked, resumable state.

The asset return is one control operation from the current owner to the
boundary account. It does not walk back through each intermediate wallet and it
does not depend on those wallets holding gas at that moment.
"""
from dataclasses import dataclass, replace

from .errors import DomainError, require
from .ids import HEX32, address, amount, digest, identifier, instant
from .model import Asset

STEP_KINDS = ("refund", "asset-return")
STEP_STATUSES = ("pending", "blocked", "done")
ROLLBACK_STATES = ("in-progress", "blocked", "complete")

#: Mechanisms the requirements withdrew. Named so their absence is testable.
WITHDRAWN_MECHANISMS = ("temporary-custody", "time-limited-redemption",
                        "overdue-sale", "instant-liquidation")


@dataclass(frozen=True)
class RollbackAuthority:
    """Permission to return the asset and refund the suffix.

    The real asset-return control and its wallet permissions are still open in
    the requirements, so this is evidence supplied from verified configuration.
    Nothing here mints that permission, and an unverified source is refused.
    """

    authority_id: str
    source: str
    receipt_id: str
    refused_leg_index: int
    asset: Asset
    boundary_account: str
    binding: str
    observed_at: int

    def __post_init__(self):
        identifier(self.authority_id, "EX_ROLLBACK_AUTHORITY_REFUSED")
        identifier(self.source, "EX_ROLLBACK_AUTHORITY_REFUSED")
        identifier(self.receipt_id, "EX_ROLLBACK_AUTHORITY_REFUSED")
        require(isinstance(self.refused_leg_index, int) and not isinstance(self.refused_leg_index, bool)
                and self.refused_leg_index >= 0, "EX_ROLLBACK_AUTHORITY_REFUSED", "leg index")
        require(isinstance(self.asset, Asset), "EX_ROLLBACK_AUTHORITY_REFUSED", "asset must be an Asset")
        address(self.boundary_account, "EX_ROLLBACK_AUTHORITY_REFUSED")
        require(isinstance(self.binding, str) and HEX32.match(self.binding) is not None,
                "EX_ROLLBACK_AUTHORITY_REFUSED", "the binding must be a 32-byte digest")
        instant(self.observed_at, "EX_ROLLBACK_AUTHORITY_REFUSED")


def rollback_binding(asset, receipt_id, refused_leg_index, boundary_account, affected_legs):
    """The digest a rollback authority must carry for one interval."""
    return digest({"chainId": asset.chain_id, "contract": asset.contract, "tokenId": asset.token_id,
                   "receiptId": receipt_id, "refusedLegIndex": refused_leg_index,
                   "boundaryAccount": boundary_account,
                   "affectedLegs": list(affected_legs)})


@dataclass(frozen=True)
class RollbackStep:
    """One recoverable unit of a rollback, with its own idempotency key."""

    step_id: str
    kind: str
    receipt_id: str
    leg_index: int
    key: str
    status: str = "pending"
    detail: tuple = ()

    def __post_init__(self):
        identifier(self.step_id, "EX_ROLLBACK_STEP_REFUSED")
        require(self.kind in STEP_KINDS, "EX_ROLLBACK_STEP_REFUSED", self.kind)
        require(self.status in STEP_STATUSES, "EX_ROLLBACK_STEP_REFUSED", self.status)
        identifier(self.key, "EX_ROLLBACK_STEP_REFUSED")


class SimulatedAssetControl:
    """A simulated, pre-arranged asset-return control.

    One call moves the receipt from wherever the chain head is to the boundary
    account. It is deliberately not a walk through the intermediate wallets, and
    it does not read their balances: the requirement is that a return never
    depends on an intermediate ordinary wallet holding gas at that moment.

    ``outcomes`` lets a test drive the first answer for a key. A repeat of that
    key returns the stored record and moves nothing again.
    """

    def __init__(self, clock, outcomes=None):
        self._clock = clock
        self._records = {}
        self._outcomes = dict(outcomes or {})
        self.returns = 0
        self.hops_walked = 0

    def lookup(self, key):
        return self._records.get(identifier(key, "EX_ASSET_CONTROL_REFUSED"))

    def return_asset(self, key, from_account, to_account, asset):
        """Return the receipt to the boundary account in one operation."""
        identifier(key, "EX_ASSET_CONTROL_REFUSED")
        existing = self._records.get(key)
        if existing is not None:
            require(existing["toAccount"] == to_account, "EX_ASSET_CONTROL_SUBSTITUTION_REFUSED",
                    f"{key} was already used to return to {existing['toAccount']}")
            return dict(existing, repeated=True)
        address(from_account, "EX_ASSET_CONTROL_REFUSED")
        address(to_account, "EX_ASSET_CONTROL_REFUSED")
        require(from_account != to_account, "EX_ASSET_CONTROL_REFUSED",
                "a return needs a different destination")
        outcome = self._outcomes.pop(key, "returned")
        require(outcome in ("returned", "failed", "unknown"), "EX_ASSET_CONTROL_REFUSED", outcome)
        record = {"key": key, "fromAccount": from_account, "toAccount": to_account,
                  "chainId": asset.chain_id, "contract": asset.contract,
                  "tokenId": asset.token_id, "status": outcome,
                  "reference": f"sim-return:{key}", "observedAt": self._clock(),
                  "operations": 1, "walkedIntermediateWallets": False,
                  "requiredIntermediateGas": False, "simulated": True}
        if outcome != "failed":
            self._records[key] = record
        if outcome == "returned":
            self.returns += 1
        return dict(record, repeated=False)

    def resolve_unknown(self, key, status):
        """Record what a later enquiry established. This sends nothing."""
        record = self._records.get(identifier(key, "EX_ASSET_CONTROL_REFUSED"))
        require(record is not None, "EX_ASSET_CONTROL_UNKNOWN_KEY", key)
        require(record["status"] == "unknown", "EX_ASSET_CONTROL_ALREADY_RESOLVED", record["status"])
        require(status in ("returned", "failed"), "EX_ASSET_CONTROL_REFUSED", status)
        self._records[key] = dict(record, status=status, resolvedAt=self._clock())
        return self._records[key]


@dataclass(frozen=True)
class GasBudget:
    """A configurable test fixture for gas responsibility, not a fee mechanism.

    The product rule it encodes is settled: each leg's buyer bears that leg's
    trade, refund and return gas. How a fee is actually deducted, and how a
    shared operation is split, are still open, so a budget here is a fixture
    ceiling used to exercise the shortfall path - never an approved charging
    method.
    """

    account: str
    available: int

    def __post_init__(self):
        address(self.account, "EX_GAS_BUDGET_REFUSED")
        amount(self.available, "EX_GAS_BUDGET_REFUSED")
