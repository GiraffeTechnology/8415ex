"""Explicit deferred principal admission over the original aggregate preimage.

No payment, reserve, persistence or dispatch occurs here. The caller operates a
detached Exchange and commits its new leg and this reservation in ONE original
aggregate CAS. A read/port result alone does not establish durable admission.
"""
from copy import deepcopy
from dataclasses import dataclass

from .deferred_settlement import DeferredSettlement, Profile
from .errors import DomainError, require
from .ids import digest, identifier

CODE = "EX_DEFERRED_ADMISSION_REFUSED"


@dataclass(frozen=True)
class DeferredAdmission:
    obligation_id: str
    terms_digest: str
    deadline: int


class DeferredTradeAdmissionPort:
    """Trusted read-only original-journal boundary, never a caller flag.

read_original(request, now) returns the same-generation complete deferred
snapshot (including a staged reserve in a joint admission), its original scope
and generation, and current disjoint available/required normal-process ETH.
verify_original(request, row) must authenticate that original snapshot and
generation, exact signed seller deferred consent and buyer authority for BOTH
intent digests, receipt/transfer occurrence, reservation exclusivity, selected
USD-stablecoin identity and original gas quote/confirmation/grant/allocation.
It must include pending/UNKNOWN exposure, reject revoked/stale evidence, and
ensure available normal gas is not also pledged elsewhere. No fresh ETH charge,
contingent liquidation reserve, synthetic principal or new store is created.
The port is explicitly installed by the original aggregate owner, not accepted
as untrusted API data. Actual host/evidence binding remains separately required.
"""
    def __init__(self, profile, evidence_verifier, read_original, verify_original):
        require(type(profile) is Profile and callable(read_original)
                and callable(verify_original), CODE, "explicit original admission ports required")
        self.profile = profile
        self.evidence_verifier = evidence_verifier
        self.read_original = read_original
        self.verify_original = verify_original

    def admit(self, match, *, receipt_id, leg_index, transfer_id,
              registration_deadline, now):
        request = {"receiptId": receipt_id, "legIndex": leg_index,
                   "transferId": transfer_id, "asset": list(match.asset.key),
                   "seller": match.seller, "buyer": match.buyer,
                   "principal": match.price, "quoteAsset": match.quote_asset,
                   "sellIntentDigest": match.sell_intent_digest,
                   "buyIntentDigest": match.buy_intent_digest,
                   "registrationDeadline": registration_deadline}
        require(type(now) is int and now >= 0 and type(leg_index) is int
                and leg_index >= 0 and type(registration_deadline) is int, CODE,
                "exact trusted time and occurrence required")
        try:
            row = deepcopy(self.read_original(deepcopy(request), now))
            require(type(row) is dict and set(row) == {
                "request", "snapshot", "obligationId", "scope", "generation",
                "observedAt", "normalGasRequiredWei", "normalGasAvailableWei", "principalPolicy"},
                CODE, "complete original reservation envelope required")
            require(row["request"] == request and row["observedAt"] == now, CODE,
                    "admission must bind exact current match and occurrence")
            identifier(row["scope"], CODE)
            require(type(row["generation"]) is int and row["generation"] >= 0, CODE,
                    "original generation required")
            policy = row["principalPolicy"]
            require(type(policy) is dict and set(policy) == {"chain", "asset", "kind", "denomination", "evidenceReference"}
                    and policy["chain"] == match.asset.chain_id and policy["asset"] == match.quote_asset
                    and policy["kind"] == "stablecoin" and policy["denomination"] == "USD",
                    CODE, "authenticated USD stablecoin metadata policy required")
            identifier(policy["evidenceReference"], CODE)
            before = digest(row)
            require(self.verify_original(deepcopy(request), deepcopy(row)) is True,
                    CODE, "original reservation, signed terms and gas not authenticated")
            require(digest(row) == before, CODE, "admission envelope changed")
            model = DeferredSettlement.restore(self.profile, self.evidence_verifier,
                                               deepcopy(row["snapshot"]))
            item = model.obligations[row["obligationId"]]
            lock = model.locks[item.lock]
            require((item.borrower, item.seller, item.principal) ==
                    (match.buyer, match.seller, match.price), CODE,
                    "reservation parties or principal differ from signed trade")
            require((self.profile.settlement_chain, self.profile.principal_asset) ==
                    (match.asset.chain_id, match.quote_asset), CODE,
                    "reserved principal currency/network differs from NFT0 selection")
            require(match.quote_asset != "ETH" and now < item.deadline <= registration_deadline,
                    CODE, "deferred stablecoin selection or exact deadline invalid")
            require(not item.registered and not item.rollback and not item.resolved
                    and not item.rollback_confirmed and item.paid == 0
                    and not lock.release_pending and not lock.released and not lock.liquidating
                    and lock.reserved >= item.principal and item.collateral_remaining > 0,
                    CODE, "reservation is no longer an unused secured trade allowance")
            require(not model._pending(item.identity) and not model._pending_lock(item.lock),
                    CODE, "unresolved original effects block new admission")
            required, available = row["normalGasRequiredWei"], row["normalGasAvailableWei"]
            require(type(required) is int and type(available) is int
                    and 0 < required <= available <= item.normal_gas["capWei"]
                    and item.fee_receipt and item.gas_allocation and item.source_gas_allocation,
                    CODE, "original upfront normal ETH allocation is insufficient or unverified")
            return DeferredAdmission(item.identity, item.consent, item.deadline)
        except DomainError:
            raise
        except Exception:
            raise DomainError(CODE, "original deferred admission evidence unavailable or invalid") from None
