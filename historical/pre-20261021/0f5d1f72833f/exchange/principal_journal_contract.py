"""EX-side principal journal translation. No store, signing or dispatch.

The verifier must be installed from the original authenticated native journal.
An unsigned mapping, local EscrowPosition or grant reservation is not funds.
"""
from copy import deepcopy
from dataclasses import dataclass, asdict

from .errors import require
from .ids import address, digest, identifier
from .model import Asset
from .settlement import EscrowPosition, ReleaseAuthority, segment_binding

CODE = "EX_PRINCIPAL_BRIDGE_REFUSED"
SCHEMA = "ex-principal-journal/1"
STATES = ("absent", "frozen", "released", "refunded", "unknown")


def _uint(value):
    require(type(value) is int and 0 <= value < 2 ** 256, CODE, "exact uint256 required")
    return value


@dataclass(frozen=True)
class PrincipalBinding:
    """One immutable EX leg and its original native principal operation."""
    position: EscrowPosition
    asset: Asset
    transfer_id: str
    payment_token: str
    token_decimals: int
    operation_id: str
    journal_reference: str

    def __post_init__(self):
        require(type(self.position) is EscrowPosition and type(self.asset) is Asset,
                CODE, "original escrow and whole asset required")
        require(self.asset.chain_id == 11155111, CODE, "EX Sepolia binding required")
        if self.payment_token == "ETH":
            require(type(self.token_decimals) is int and self.token_decimals == 18,
                    CODE, "native ETH principal must use wei")
        else:
            address(self.payment_token, CODE)
            require(self.payment_token != "0x" + "0" * 40, CODE, "configured payment token required")
        # ETH is the existing canonical native identity, never the zero-address
        # token or an alias. The escrow must already select this exact asset.
        require(self.position.quote_asset == self.payment_token, CODE, "principal currency mismatch")
        require(type(self.token_decimals) is int and 0 <= self.token_decimals <= 255,
                CODE, "verified token decimals required")
        for value in (self.transfer_id, self.operation_id, self.journal_reference):
            identifier(value, CODE)
        _uint(self.asset.token_id)
        require(self.position.payer != "0x" + "0" * 40
                and self.position.payee != "0x" + "0" * 40, CODE, "nonzero parties required")
        _uint(self.position.principal)
        require(self.position.principal > 0, CODE, "positive principal required")

    @property
    def terms(self):
        p = self.position
        result = {"schema": SCHEMA, "chainId": self.asset.chain_id,
                "contract": self.asset.contract, "tokenId": str(self.asset.token_id),
                "receiptId": p.receipt_id, "globalLegId": p.leg_index,
                "transferId": self.transfer_id, "escrowId": p.escrow_id,
                "buyer": p.payer, "seller": p.payee, "paymentToken": self.payment_token,
                "tokenDecimals": self.token_decimals, "principalBaseUnits": str(p.principal),
                "nativeOperationId": self.operation_id, "journalReference": self.journal_reference}
        if self.payment_token == "ETH":
            result.update(principalAssetKind="native-ETH", principalUnit="wei")
        return result

    @property
    def binding_digest(self):
        return digest(self.terms)


class PrincipalJournalBridge:
    """Pure, detached request preparation against an authenticated native read.

    verify_native(binding, snapshot) checks original source/store identity,
    exact operation membership, freshness and canonical financial proof.
    verify_authority(action, binding, snapshot, evidence) checks the original
    Oracle/native atomic condition; local observation time cannot substitute
    for effectiveAt. These are internal injection ports, not Wallet APIs.

    The eventual native writer must compare revision and binding atomically,
    persist UNKNOWN before any effect, and check current grant/nonce/balance
    and the independent confirmed ETH gas budget inside its held gate.
    """
    def __init__(self, verify_native, verify_authority):
        require(callable(verify_native) and callable(verify_authority), CODE,
                "explicit original verifiers required")
        self._verify_native = verify_native
        self._verify_authority = verify_authority

    def _snapshot(self, binding, raw):
        require(type(binding) is PrincipalBinding and type(raw) is dict, CODE,
                "binding and native snapshot required")
        s = deepcopy(raw)
        fields = {"binding", "sourceReference", "revision", "state", "freezeReference",
                  "lockedBaseUnits", "releasedBaseUnits", "refundedBaseUnits", "pendingAction"}
        require(set(s) == fields and type(s["binding"]) is dict
                and digest(s["binding"]) == binding.binding_digest, CODE,
                "native principal binding or fields differ")
        identifier(s["sourceReference"], CODE)
        require(type(s["revision"]) is int and s["revision"] >= 0, CODE, "native revision required")
        require(s["state"] in STATES, CODE, "unknown native state")
        if s["state"] == "unknown":
            require(s["pendingAction"] in ("freeze", "release", "refund"), CODE, "unknown action")
            require(all(s[k] is None for k in
                        ("lockedBaseUnits", "releasedBaseUnits", "refundedBaseUnits")),
                    CODE, "unknown outcome cannot assert balances")
            if s["freezeReference"] is not None:
                identifier(s["freezeReference"], CODE)
            require(s["pendingAction"] == "freeze" or s["freezeReference"] is not None,
                    CODE, "terminal attempt needs original freeze")
        else:
            require(s["pendingAction"] is None, CODE, "known state has pending effect")
            values = [_uint(s[k]) for k in
                      ("lockedBaseUnits", "releasedBaseUnits", "refundedBaseUnits")]
            principal = binding.position.principal
            expected = {"absent": [0, 0, 0], "frozen": [principal, 0, 0],
                        "released": [0, principal, 0], "refunded": [0, 0, principal]}
            require(values == expected[s["state"]], CODE, "principal conservation mismatch")
            if s["state"] == "absent":
                require(s["freezeReference"] is None, CODE, "absent record cannot name a freeze")
            else:
                identifier(s["freezeReference"], CODE)
        require(self._verify_native(binding, deepcopy(s)) is True, CODE,
                "original authenticated financial read refused")
        return s

    def observe(self, binding, raw):
        s = self._snapshot(binding, raw)
        return {"bindingDigest": binding.binding_digest, "state": s["state"],
                "revision": s["revision"], "freezeReference": s["freezeReference"],
                "principalKnownFrozen": s["state"] == "frozen",
                "reconcileOnly": s["state"] == "unknown",
                "fundsDispatched": False, "ledgerMutated": False,
                "gasAccounted": False, "tradeAdmission": "NOT_PERFORMED"}

    def prepare(self, action, binding, raw, evidence=None):
        """Return an internal request, never send it or mark the EX leg funded."""
        require(action in ("freeze", "release", "refund"), CODE, "unsupported principal action")
        s = self._snapshot(binding, raw)
        stable = digest({"bindingDigest": binding.binding_digest, "action": action})
        base = {"schema": SCHEMA, "action": action, "operationKey": stable,
                "binding": binding.terms, "expectedNativeRevision": s["revision"],
                "sourceReference": s["sourceReference"],
                "originalFreezeReference": s["freezeReference"],
                "fundsDispatched": False, "ledgerMutated": False}
        if s["state"] == "unknown":
            return dict(base, disposition="RECONCILE_ONLY", request=None)
        terminal = {"freeze": "frozen", "release": "released", "refund": "refunded"}[action]
        if s["state"] == terminal:
            return dict(base, disposition="ALREADY_RECORDED", request=None)
        require(s["state"] == ("absent" if action == "freeze" else "frozen"),
                CODE, "release/refund are exclusive; no second buyer payment")
        proof = deepcopy(evidence)
        if action == "release":
            require(type(proof) is ReleaseAuthority, CODE, "original release authority required")
            p = binding.position
            require(proof.receipt_id == p.receipt_id and proof.leg_index == p.leg_index
                    and proof.transfer_id == binding.transfer_id and proof.asset == binding.asset
                    and proof.journal_reference == binding.journal_reference
                    and proof.binding == segment_binding(binding.asset, p.receipt_id, p.leg_index,
                        binding.transfer_id, p.payer, p.payee, p.principal, p.quote_asset,
                        binding.journal_reference), CODE, "release authority belongs to another leg")
        else:
            require(type(proof) is dict and set(proof) ==
                    {"authorityReference", "bindingDigest", "action", "journalReference"}
                    and proof["bindingDigest"] == binding.binding_digest
                    and proof["action"] == action
                    and proof["journalReference"] == binding.journal_reference,
                    CODE, "exact original action authority reference required")
            identifier(proof["authorityReference"], CODE)
        # Freeze needs authentic buyer intent, balance and gas confirmation;
        # refund needs canonical rejection/cutoff and asset return ordering.
        # Both checks belong to the original native gate, not a local string.
        require(self._verify_authority(action, binding, deepcopy(s), proof) is True,
                CODE, "original action authority refused")
        request = {"principalAsset": binding.payment_token,
                   "principalBaseUnits": str(binding.position.principal),
                   "recipient": (binding.position.payee if action == "release" else
                                 binding.position.payer if action == "refund" else None),
                   "debitBuyerBaseUnits": str(binding.position.principal) if action == "freeze" else "0",
                   "consumeOriginalFreeze": action != "freeze",
                   "gasAsset": "ETH", "gasAccounting": "SEPARATE_ORIGINAL_CONFIRMED_BUDGET",
                   "restoreConsumedGas": False,
                   "requiresNativeCASAndRecheck": True,
                   "authorityBindingRequired": True}
        if binding.payment_token == "ETH":
            request.update(principalAssetKind="native-ETH", principalUnit="wei",
                           combinePrincipalWithGas=False)
        # This digest is an EX request identity only. It is not a native task,
        # grant, EIP-712 signature, calldata hash or Oracle commitment.
        return dict(base, disposition="PREPARED_NOT_DISPATCHED", request=request,
                    authority=asdict(proof) if type(proof) is ReleaseAuthority else proof)
