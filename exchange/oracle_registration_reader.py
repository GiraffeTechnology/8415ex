"""Bind original canonical registration evidence to the real Oracle projection.

Installed in OriginalDeferredPorts.read_registration; no mutation or native
financial authority. The existing mint verifier and joint aggregate CAS remain
mandatory. Public Oracle JSON cannot manufacture block/proof evidence.
"""
from copy import deepcopy
from dataclasses import dataclass, replace

from .errors import require
from .exchange_fact_snapshot import decode_exchange_snapshot
from .joint_deferred_transition import JointTransitionInput, OriginalLegBinding
from .oracle_projection_join import OracleProjectionJoin
from .oracle_http_transport import OracleHTTPTransport
from .principal_journal_contract import PrincipalBinding
from .registration import RegistrationEvidence

CODE = "EX_ORACLE_REGISTRATION_REFUSED"


@dataclass(frozen=True)
class OriginalOracleRegistration:
    """Resolved by the installed original authority, never by a browser form."""
    evidence: RegistrationEvidence
    principal: PrincipalBinding
    projection_version: str


class OracleRegistrationReader:
    def __init__(self, join, resolve_original):
        require(type(join) is OracleProjectionJoin and callable(resolve_original),
                CODE, "original Oracle join and canonical evidence resolver required")
        self.join, self.resolve_original = join, resolve_original

    @classmethod
    def from_http(cls, *, origin, source, verify_mapping, resolve_original,
                  timeout_ms=5000):
        # Lazy construction; no environment defaults, credentials or network I/O.
        return cls(OracleProjectionJoin(source, OracleHTTPTransport(
            origin, timeout_ms=timeout_ms), verify_mapping), resolve_original)

    def __call__(self, context, binding):
        require(type(context) is JointTransitionInput and type(binding) is OriginalLegBinding,
                CODE, "original same-generation transition context required")
        require(context.aggregate_digest == binding.aggregate_digest
                and context.obligation_id == binding.obligation_id
                and context.command in ("observe_registration", "deadline"),
                CODE, "original aggregate/obligation differs")
        facts = decode_exchange_snapshot(context.owned_before)
        receipt = facts.receipts.get(binding.receipt_id)
        legs = facts.domain["_legs"].get(binding.receipt_id, ())
        require(type(binding.leg_index) is int and 0 <= binding.leg_index < len(legs)
                and receipt is not None, CODE, "original receipt/leg unavailable")
        leg = legs[binding.leg_index]
        require(leg.transfer_id == binding.transfer_id
                and leg.deferred_obligation_id == binding.obligation_id,
                CODE, "original leg obligation differs")
        resolved = self.resolve_original(context, binding)
        require(type(resolved) is OriginalOracleRegistration
                and type(resolved.evidence) is RegistrationEvidence
                and type(resolved.principal) is PrincipalBinding,
                CODE, "original typed canonical registration evidence required")
        evidence, principal = resolved.evidence, resolved.principal
        request = facts.domain["_requests"].get(evidence.request_id)
        require(request is not None and
                (evidence.receipt_id, evidence.leg_index, evidence.transfer_id, evidence.asset,
                 evidence.adapter) ==
                (binding.receipt_id, binding.leg_index, binding.transfer_id, receipt.asset,
                 request.adapter) and
                (request.receipt_id, request.leg_index, request.transfer_id, request.asset) ==
                (binding.receipt_id, binding.leg_index, binding.transfer_id, receipt.asset),
                CODE, "original request/asset/registration path differs")
        require((principal.position.receipt_id, principal.position.leg_index,
                 principal.transfer_id, principal.asset, principal.position.payer,
                 principal.position.payee, principal.position.principal,
                 principal.position.quote_asset) ==
                (binding.receipt_id, binding.leg_index, binding.transfer_id, receipt.asset,
                 leg.buyer, leg.seller, leg.price, leg.quote_asset),
                CODE, "original principal segment differs")
        require(evidence.simulated is False and evidence.outcome == "confirmed"
                and evidence.effective_at is not None and evidence.query_at is not None
                and evidence.observation_block is not None
                and evidence.observation_block_hash is not None
                and evidence.temporal_evidence_reference is not None
                and evidence.effective_at <= evidence.query_at <= evidence.observed_at <= context.now,
                CODE, "original real temporal/block evidence required")
        projection = self.join.inspect(
            principal, version=resolved.projection_version,
            record_commitment=evidence.record_commitment,
            as_of=str(evidence.query_at), cutoff=str(request.commitment_deadline_at))
        require(int(projection["entry"]["effectiveAt"]) == evidence.effective_at,
                CODE, "canonical evidence and Oracle effective instant differ")
        # No freshness, cutoff, finality or holder boolean becomes a release
        # permission. apply_registration_result still authenticates source and
        # registration-effective-time with the original mint verifier.
        return deepcopy(evidence)

    def install(self, original_ports):
        from .deferred_runtime_composition import OriginalDeferredPorts
        require(type(original_ports) is OriginalDeferredPorts,
                CODE, "original deferred runtime ports required")
        return replace(original_ports, read_registration=self)
