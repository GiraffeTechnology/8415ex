"""Stage 4: the trading deadline, exit eligibility, vouchers and the burn.

Two things this module refuses to pretend.

First, ``owner == holder`` is necessary and never sufficient. Eligibility also
needs the requester to be that party, a wallet authorization that actually
covers the exit action, and the other checks the requirements name. Those other
checks are supplied as verified facts by the caller; an unsupplied check is
treated as not met, never as passed.

Second, handing over a physical voucher and burning a token are not one atomic
act. Each exit step records its own completion instant, and the report states
plainly that they completed at different times.

Where the requirements leave an order undefined - the precedence between a
registration timeout, the trading deadline and an in-flight result, and the
exact confirmation and recovery order for the voucher hand-over and the burn -
this module refuses with a named code and reports the gap instead of inventing
a rule.
"""
from dataclasses import dataclass, replace

from .errors import require
from .ids import address, digest, identifier, instant

#: The exit sequence, in the order the requirements describe it. The exact
#: confirmation and recovery order inside the hand-over and burn pair is still
#: open, so a step is never auto-completed from a neighbour.
EXIT_STEPS = ("stop-resale", "voucher-issued", "voucher-handover-confirmed", "burn")

EXIT_STEP_STATUSES = ("pending", "done", "blocked")
EXIT_STATES = ("requested", "in-progress", "blocked", "complete")

#: Checks this layer cannot establish by itself. Each must be supplied as a
#: verified fact; absence means not met.
REQUIRED_OTHER_CHECKS = ("rights-holder-verification", "asset-validity", "other-eligibility")


@dataclass(frozen=True)
class RedemptionRequest:
    """One exit request by one account, under one wallet authorization."""

    request_id: str
    receipt_id: str
    requester: str
    authorization_id: str
    requested_at: int

    def __post_init__(self):
        identifier(self.request_id, "EX_REDEMPTION_REFUSED")
        identifier(self.receipt_id, "EX_REDEMPTION_REFUSED")
        address(self.requester, "EX_REDEMPTION_REFUSED")
        identifier(self.authorization_id, "EX_REDEMPTION_REFUSED")
        instant(self.requested_at, "EX_REDEMPTION_REFUSED")


@dataclass(frozen=True)
class ExitStep:
    """One exit step, with its own key, status and completion instant."""

    name: str
    key: str
    status: str = "pending"
    completed_at: int = None
    detail: tuple = ()

    def __post_init__(self):
        require(self.name in EXIT_STEPS, "EX_EXIT_STEP_REFUSED", self.name)
        identifier(self.key, "EX_EXIT_STEP_REFUSED")
        require(self.status in EXIT_STEP_STATUSES, "EX_EXIT_STEP_REFUSED", self.status)
        if self.completed_at is not None:
            instant(self.completed_at, "EX_EXIT_STEP_REFUSED")


def exit_step_key(step, receipt_id, request_id):
    """Bounded, unambiguous identity even when either identifier contains ':'."""
    require(step in EXIT_STEPS, "EX_EXIT_STEP_REFUSED", step)
    identifier(receipt_id, "EX_REDEMPTION_REFUSED")
    identifier(request_id, "EX_REDEMPTION_REFUSED")
    return f"{step}:{digest({'receiptId': receipt_id, 'requestId': request_id})}"


class SimulatedVoucherDesk:
    """A simulated collection desk for one registration path.

    It issues a voucher, records a hand-over confirmation and records a burn, as
    three separate acts with three separate instants. It is a simulated business
    role; it is not a real warehouse, registrar or custodian.

    ``outcomes`` lets a test drive the first answer for a key. A repeat of a key
    returns the stored record and does nothing again.
    """

    def __init__(self, clock, path, outcomes=None):
        self._clock = clock
        self.path = path
        self._records = {}
        self._outcomes = dict(outcomes or {})

    @property
    def simulated(self):
        return True

    @property
    def label(self):
        return f"{self.path} (simulated collection desk)"

    def lookup(self, key):
        return self._records.get(identifier(key, "EX_VOUCHER_REFUSED"))

    def act(self, key, step, receipt_id, account):
        """Perform one exit act once. A repeat returns the stored record."""
        identifier(key, "EX_VOUCHER_REFUSED")
        require(step in EXIT_STEPS, "EX_EXIT_STEP_REFUSED", step)
        existing = self._records.get(key)
        if existing is not None:
            require(existing["step"] == step and existing["account"] == account
                    and existing["receiptId"] == receipt_id,
                    "EX_VOUCHER_SUBSTITUTION_REFUSED",
                    f"{key} was already used for {existing['step']} by {existing['account']}")
            return dict(existing, repeated=True)
        outcome = self._outcomes.pop(key, "done")
        require(outcome in ("done", "failed", "unknown"), "EX_VOUCHER_REFUSED", outcome)
        record = {"key": key, "step": step, "receiptId": receipt_id, "account": account,
                  "status": outcome, "path": self.path, "simulated": True,
                  "observedAt": self._clock(),
                  "reference": f"sim-{step}:{key}"}
        if outcome != "failed":
            self._records[key] = record
        return dict(record, repeated=False)

    def resolve_unknown(self, key, status):
        """Record what a later enquiry established. This performs nothing new."""
        record = self._records.get(identifier(key, "EX_VOUCHER_REFUSED"))
        require(record is not None, "EX_VOUCHER_UNKNOWN_KEY", key)
        require(record["status"] == "unknown", "EX_VOUCHER_ALREADY_RESOLVED", record["status"])
        require(status in ("done", "failed"), "EX_VOUCHER_REFUSED", status)
        self._records[key] = dict(record, status=status, resolvedAt=self._clock())
        return self._records[key]
