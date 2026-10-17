"""Historical physical-exit records. EX v1.2 performs no new fulfillment.

Old record shapes and enquiry/resolution remain for audit only.
"""
from dataclasses import dataclass

from .errors import require
from .ids import address, digest, identifier, instant

#: Historical values for decoding retained evidence only, never an executable plan.
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
    """Historical simulator storage; new physical attempts are permanently retired.

    Lookup, history and observed UNKNOWN resolution preserve old evidence only.
    """

    def __init__(self, clock, path, outcomes=None):
        self._clock = clock
        self.path = path
        self._records = {}
        self._history = {}
        self._outcomes = dict(outcomes or {})

    @property
    def simulated(self):
        return True

    @property
    def label(self):
        return f"{self.path} (simulated collection desk)"

    def lookup(self, key):
        return self._records.get(identifier(key, "EX_VOUCHER_REFUSED"))

    def history(self, key):
        """Snapshots of attempts and resolutions, without exposing mutable state."""
        identifier(key, "EX_VOUCHER_REFUSED")
        return tuple(dict(record) for record in self._history.get(key, ()))

    def act(self, key, step, receipt_id, account):
        """No new attempt or retry of a retired physical operation."""
        require(False, "EX_PHYSICAL_FULFILLMENT_RETIRED",
                "EX v1.2 transfers the bill of lading; query old records without executing them")

    def resolve_unknown(self, key, status):
        """Record what a later enquiry established. This performs nothing new."""
        record = self._records.get(identifier(key, "EX_VOUCHER_REFUSED"))
        require(record is not None, "EX_VOUCHER_UNKNOWN_KEY", key)
        require(record["status"] == "unknown", "EX_VOUCHER_ALREADY_RESOLVED", record["status"])
        require(status in ("done", "failed"), "EX_VOUCHER_REFUSED", status)
        self._records[key] = dict(record, status=status, resolvedAt=self._clock(),
                                  effect="applied" if status == "done" else "not-applied",
                                  retryable=status == "failed")
        self._history.setdefault(key, []).append(dict(self._records[key]))
        return dict(self._records[key])
