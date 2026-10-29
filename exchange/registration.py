"""The registration contract and its three simulated registrar adapters.

Registration is serial and physical: the chain can change hands faster than a
registrar records each hop. This module keeps that lag visible and never lets a
later result jump a gap:

* a result for a leg beyond the next expected one is **deferred**, not applied;
* a repeat of the same request is **idempotent**, returning the first result;
* the same request id with different content is a **conflict**, never a silent
  overwrite;
* a result must bind to the right asset, transfer, leg index, network and a
  trusted registrar, or it advances nothing.

A deferred result is not a rejection, and a rejection is not a delay. The three
adapters are simulated business roles; none of them is a real institution.
"""
from dataclasses import dataclass, field

from .errors import require
from .ids import HEX32, digest, identifier, instant
from .model import REGISTRATION_PATHS, Asset

OUTCOMES = ("confirmed", "rejected")

#: Result dispositions this layer can return for an applied result.
DISPOSITIONS = ("advanced", "deferred", "idempotent", "rejected")


@dataclass(frozen=True)
class RegistrationRequest:
    """One submitted holder-change request for exactly one transfer leg."""

    request_id: str
    receipt_id: str
    transfer_id: str
    leg_index: int
    predecessor_transfer_id: str
    adapter: str
    asset: Asset
    submitted_at: int
    commitment_deadline_at: int
    attempt: int = 1

    def __post_init__(self):
        identifier(self.request_id, "EX_REGISTRATION_REQUEST_REFUSED")
        identifier(self.receipt_id, "EX_REGISTRATION_REQUEST_REFUSED")
        identifier(self.transfer_id, "EX_REGISTRATION_REQUEST_REFUSED")
        require(isinstance(self.leg_index, int) and not isinstance(self.leg_index, bool) and self.leg_index >= 0,
                "EX_REGISTRATION_REQUEST_REFUSED", "leg index must be a non-negative integer")
        if self.predecessor_transfer_id is not None:
            identifier(self.predecessor_transfer_id, "EX_REGISTRATION_REQUEST_REFUSED")
        require(self.adapter in REGISTRATION_PATHS, "EX_REGISTRATION_PATH_REFUSED", self.adapter)
        require(isinstance(self.asset, Asset), "EX_REGISTRATION_REQUEST_REFUSED", "asset must be an Asset")
        instant(self.submitted_at, "EX_REGISTRATION_REQUEST_REFUSED")
        instant(self.commitment_deadline_at, "EX_REGISTRATION_REQUEST_REFUSED")
        require(self.submitted_at < self.commitment_deadline_at, "EX_REGISTRATION_REQUEST_REFUSED",
                "the commitment window must be non-empty")
        require(isinstance(self.attempt, int) and not isinstance(self.attempt, bool) and self.attempt >= 1,
                "EX_REGISTRATION_REQUEST_REFUSED", "attempt must be a positive integer")

    @property
    def content_digest(self):
        """Identity of what was asked. A repeat with a different digest under the
        same request id is a conflict, not a retry."""
        return digest({
            "requestId": self.request_id,
            "receiptId": self.receipt_id,
            "transferId": self.transfer_id,
            "legIndex": self.leg_index,
            "predecessorTransferId": self.predecessor_transfer_id,
            "adapter": self.adapter,
            "chainId": self.asset.chain_id,
            "contract": self.asset.contract,
            "tokenId": self.asset.token_id,
        })


@dataclass(frozen=True)
class RegistrationEvidence:
    """A registrar's result for one request, as this layer observed it.

    ``source`` is the registrar identity the result is attributed to. It is
    checked against the adapter's trusted source; an unknown or mismatched
    source advances nothing.
    """

    result_id: str
    request_id: str
    receipt_id: str
    transfer_id: str
    leg_index: int
    adapter: str
    source: str
    outcome: str
    asset: Asset
    observed_at: int
    result_version: int = 1
    record_commitment: str = None
    simulated: bool = True
    effective_at: int = None
    query_at: int = None
    observation_block: int = None
    observation_block_hash: str = None
    temporal_evidence_reference: str = None

    def __post_init__(self):
        identifier(self.result_id, "EX_REGISTRATION_EVIDENCE_REFUSED")
        identifier(self.request_id, "EX_REGISTRATION_EVIDENCE_REFUSED")
        identifier(self.receipt_id, "EX_REGISTRATION_EVIDENCE_REFUSED")
        identifier(self.transfer_id, "EX_REGISTRATION_EVIDENCE_REFUSED")
        require(isinstance(self.leg_index, int) and not isinstance(self.leg_index, bool) and self.leg_index >= 0,
                "EX_REGISTRATION_EVIDENCE_REFUSED", "leg index must be a non-negative integer")
        require(self.adapter in REGISTRATION_PATHS, "EX_REGISTRATION_PATH_REFUSED", self.adapter)
        identifier(self.source, "EX_REGISTRATION_EVIDENCE_REFUSED")
        require(self.outcome in OUTCOMES, "EX_REGISTRATION_EVIDENCE_REFUSED", self.outcome)
        require(isinstance(self.asset, Asset), "EX_REGISTRATION_EVIDENCE_REFUSED", "asset must be an Asset")
        instant(self.observed_at, "EX_REGISTRATION_EVIDENCE_REFUSED")
        require(isinstance(self.result_version, int) and not isinstance(self.result_version, bool)
                and self.result_version >= 1, "EX_REGISTRATION_EVIDENCE_REFUSED",
                "result version must be a positive integer")
        if self.record_commitment is not None:
            identifier(self.record_commitment, "EX_REGISTRATION_EVIDENCE_REFUSED")
        require(isinstance(self.simulated, bool), "EX_REGISTRATION_EVIDENCE_REFUSED",
                "the simulated flag must be a boolean")
        temporal = (self.effective_at, self.query_at, self.observation_block,
                    self.observation_block_hash, self.temporal_evidence_reference)
        require(all(v is None for v in temporal) or all(v is not None for v in temporal),
                "EX_REGISTRATION_EVIDENCE_REFUSED", "partial temporal evidence refused")
        if self.effective_at is not None:
            instant(self.effective_at, "EX_REGISTRATION_EVIDENCE_REFUSED")
            instant(self.query_at, "EX_REGISTRATION_EVIDENCE_REFUSED")
            require(type(self.observation_block) is int and self.observation_block >= 0,
                    "EX_REGISTRATION_EVIDENCE_REFUSED", "original observation block required")
            require(type(self.observation_block_hash) is str and HEX32.fullmatch(self.observation_block_hash),
                    "EX_REGISTRATION_EVIDENCE_REFUSED", "original bytes32 block identity required")
            identifier(self.temporal_evidence_reference, "EX_REGISTRATION_EVIDENCE_REFUSED")

    @property
    def temporal_projection(self):
        return {"effectiveAt": self.effective_at, "queryAt": self.query_at,
                "observationBlock": self.observation_block,
                "observationBlockHash": self.observation_block_hash,
                "evidenceReference": self.temporal_evidence_reference}

    @property
    def content_digest(self):
        payload = {
            "resultId": self.result_id,
            "requestId": self.request_id,
            "receiptId": self.receipt_id,
            "transferId": self.transfer_id,
            "legIndex": self.leg_index,
            "adapter": self.adapter,
            "source": self.source,
            "outcome": self.outcome,
            "chainId": self.asset.chain_id,
            "contract": self.asset.contract,
            "tokenId": self.asset.token_id,
            "resultVersion": self.result_version,
            "recordCommitment": self.record_commitment,
        }
        if self.effective_at is not None:
            payload["temporalProjection"] = self.temporal_projection
            payload["observedAt"] = self.observed_at
            payload["simulated"] = self.simulated
        return digest(payload)


class SimulatedRegistrar:
    """One simulated registration path behind the shared contract.

    The three paths differ in who files the change and how a result comes back.
    They do **not** differ in what counts as evidence: the same binding checks
    apply to all three, so success on one path never implies success on another.
    """

    #: Set by each subclass. Part of the user-visible label, always marked.
    path = None
    role = None

    def __init__(self, source, clock):
        self.source = identifier(source, "EX_REGISTRAR_REFUSED")
        self._clock = clock
        self._submitted = {}

    @property
    def label(self):
        return f"{self.path} (simulated {self.role})"

    @property
    def simulated(self):
        """Always true. This package contains no real registrar integration."""
        return True

    def submit(self, request):
        """Record a submission. Returns the acknowledgement this path gives."""
        require(isinstance(request, RegistrationRequest), "EX_REGISTRATION_REQUEST_REFUSED", "request type")
        require(request.adapter == self.path, "EX_REGISTRATION_PATH_REFUSED",
                f"{request.adapter} submitted to {self.path}")
        previous = self._submitted.get(request.request_id)
        if previous is not None:
            require(previous.content_digest == request.content_digest, "EX_REGISTRATION_CONFLICT",
                    f"request {request.request_id} was already submitted with different content")
            return self._acknowledge(previous, repeated=True)
        self._submitted[request.request_id] = request
        return self._acknowledge(request, repeated=False)

    def _acknowledge(self, request, repeated):
        return {
            "requestId": request.request_id,
            "adapter": self.path,
            "source": self.source,
            "label": self.label,
            "simulated": True,
            "accepted": True,
            "repeated": repeated,
            "handover": self.handover_record(request),
            "observedAt": self._clock(),
            "commitmentDeadlineAt": request.commitment_deadline_at,
        }

    def handover_record(self, request):
        """What this path records about who is handling the filing."""
        raise NotImplementedError

    def result(self, request, outcome, result_id, result_version=1, record_commitment=None):
        """Build the evidence this path would return. A fixture, not a feed."""
        require(request.request_id in self._submitted, "EX_REGISTRATION_UNKNOWN_REQUEST", request.request_id)
        return RegistrationEvidence(
            result_id=result_id, request_id=request.request_id, receipt_id=request.receipt_id,
            transfer_id=request.transfer_id, leg_index=request.leg_index, adapter=self.path,
            source=self.source, outcome=outcome, asset=request.asset, observed_at=self._clock(),
            result_version=result_version, record_commitment=record_commitment, simulated=True)


class DirectRegistrar(SimulatedRegistrar):
    """The platform itself files the holder change and the collection voucher."""

    path = "REG_DIRECT"
    role = "platform-filed role"

    def handover_record(self, request):
        return {"filedBy": "platform", "intermediary": None, "externalRegistrar": None}


class ElectronicRegistrar(SimulatedRegistrar):
    """An external registrar that accepts the platform's electronic data.

    The platform submits as an intermediary and receives a simulated external
    result. A different data format never relaxes the evidence requirements.
    """

    path = "REG_ELECTRONIC"
    role = "external electronic-data role"

    def handover_record(self, request):
        return {"filedBy": "platform-as-intermediary", "intermediary": None,
                "externalRegistrar": self.source}


class IntermediaryRegistrar(SimulatedRegistrar):
    """A designated member or law firm files on the holder's behalf.

    The hand-off is recorded, and a relayed filing is still not the platform
    confirming registration itself.
    """

    path = "REG_INTERMEDIARY"
    role = "designated-intermediary role"

    def handover_record(self, request):
        return {"filedBy": "designated-intermediary", "intermediary": self.source,
                "externalRegistrar": self.source}


def default_registrars(clock):
    """One adapter per path, all simulated, sharing the single contract."""
    return {
        "REG_DIRECT": DirectRegistrar("sim-direct-desk", clock),
        "REG_ELECTRONIC": ElectronicRegistrar("sim-electronic-registry", clock),
        "REG_INTERMEDIARY": IntermediaryRegistrar("sim-member-firm", clock),
    }
