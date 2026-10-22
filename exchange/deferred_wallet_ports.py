"""Explicit two-chain original Wallet task ports for the V1.5 module.

No endpoints, credentials, signers, policies, child calls, vaults or routes are
created. The application resolves an existing authorized native-task binding
from its original durable journal, keyed by the exact deferred commitment.
"""
from copy import deepcopy
from dataclasses import dataclass
import re

from .deferred_settlement import DeferredRefused, Operation, Profile, identifier
from .wallet_api_client import WalletAPIClient


class HoodiCollateralWalletClient(WalletAPIClient):
    """Separate Hoodi session; the ordinary client remains Sepolia-only.

    Construction makes no requests. Its original account/message signer must
    be supplied explicitly via inherited login, with all original checks intact.
    """
    _BOUND_CHAIN = "560048"


@dataclass(frozen=True)
class NativeTaskBinding:
    commitment: str
    source_chain: int
    task_digest: str
    operation_id: str
    child_digest: str
    expected_budget_revision: str
    funding_payer: str | None = None
    funding_budget: str | None = None
    funding_asset: str | None = None
    funding_cap_units: int | None = None

    def __post_init__(self):
        hex32 = r"0x[0-9a-f]{64}"
        if (type(self.commitment) is not str or re.fullmatch(hex32, self.commitment) is None
                or type(self.source_chain) is not int
                or self.source_chain not in (11155111, 560048)
                or any(type(value) is not str or re.fullmatch(hex32, value) is None
                       for value in (self.task_digest, self.child_digest))
                or type(self.operation_id) is not str
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", self.operation_id) is None
                or type(self.expected_budget_revision) is not str
                or re.fullmatch(r"0|[1-9][0-9]{0,77}", self.expected_budget_revision) is None):
            raise DeferredRefused("invalid original native task binding")
        funding = (self.funding_payer, self.funding_budget, self.funding_asset, self.funding_cap_units)
        if any(value is not None for value in funding):
            if (any(type(value) is not str or
                    re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value) is None
                    for value in funding[:3]) or type(self.funding_cap_units) is not int
                    or not 0 < self.funding_cap_units < 2 ** 256):
                raise DeferredRefused("invalid original native funding binding")

    def payload(self):
        return {"taskDigest": self.task_digest, "operationId": self.operation_id,
                "childDigest": self.child_digest, "expectedBudgetRevision": self.expected_budget_revision}


class DeferredWalletPorts:
    """Reuse the existing Wallet task contract without mixing chain sessions.

    resolve_original is a trusted, side-effect-free reader of the application's
    original durable task/child binding. It must verify original policy and child
    terms cover the operation's amount/asset/recipient and liquidation quote/cap.
    It is not supplied by HTTP input, a global flag, or an unverified JSON file.
    A returned status/observation never becomes a DeferredSettlement Fact here.
    """
    def __init__(self, profile, settlement_client, collateral_client, resolve_original):
        if (not isinstance(profile, Profile)
                or profile.settlement_chain != 11155111 or profile.collateral_chain != 560048
                or not isinstance(settlement_client, WalletAPIClient)
                or not isinstance(collateral_client, HoodiCollateralWalletClient)
                or settlement_client is collateral_client
                or settlement_client._chain != "11155111" or collateral_client._chain != "560048"
                or settlement_client._execution_attempts is None or collateral_client._execution_attempts is None
                or not callable(resolve_original)):
            raise DeferredRefused("explicit original Sepolia and Hoodi task clients required")
        self.profile = profile
        self.settlement_client = settlement_client
        self.collateral_client = collateral_client
        self.resolve_original = resolve_original

    def _bound(self, operation):
        if not isinstance(operation, Operation):
            raise DeferredRefused("exact deferred operation required")
        if operation.kind in ("debt-liquidation", "collateral-unlock"):
            chain, client = 560048, self.collateral_client
        elif operation.kind in ("seller-payment", "excess-refund", "rollback"):
            chain, client = 11155111, self.settlement_client
        else:
            raise DeferredRefused("unsupported deferred native operation")
        binding = self.resolve_original(deepcopy(operation))
        if (not isinstance(binding, NativeTaskBinding) or binding.commitment != operation.commitment
                or binding.source_chain != chain):
            raise DeferredRefused("original task does not match deferred operation")
        if operation.kind == "debt-liquidation":
            terms = operation.liquidation_terms
            if (terms is None or operation.funding_record is None or
                    (binding.funding_payer, binding.funding_budget,
                     binding.funding_asset, binding.funding_cap_units) !=
                    (terms["gasPayer"], terms["gasBudget"], terms["gasAsset"], terms["gasCapUnits"])):
                raise DeferredRefused("original task lacks matching EX-funded execution budget")
        else:
            funding = operation.normal_funding
            if (type(funding) is not dict or set(funding) != {"chain", "asset", "allocation", "terms"}
                    or funding.get("chain") != chain or
                    funding.get("asset") != "ETH" or type(funding.get("terms")) is not dict):
                raise DeferredRefused("original chain-specific prepaid normal funding required")
            identifier(funding["allocation"])
            terms = funding["terms"]
            if ((binding.funding_payer, binding.funding_budget,
                 binding.funding_asset, binding.funding_cap_units) !=
                    (terms.get("payer"), terms.get("budget"), "ETH", terms.get("capWei"))):
                raise DeferredRefused("original task normal funding does not match the prepaid allocation")
        return client, binding

    def execute_original(self, operation):
        # Intended only as DeferredCheckpoint.dispatch_once's callback, after
        # its original aggregate has durably claimed UNKNOWN. This additional
        # state check cannot replace that durable caller contract.
        if not isinstance(operation, Operation) or operation.status != "UNKNOWN":
            raise DeferredRefused("durable dispatch claim required")
        client, binding = self._bound(operation)
        return client.task("execute", binding.payload())

    def prepare_original(self, operation):
        """Read-only resolution, before the durable UNKNOWN dispatch claim."""
        if not isinstance(operation, Operation) or operation.status != "PREPARED":
            raise DeferredRefused("prepared deferred operation required")
        client, binding = self._bound(operation)
        identity, commitment = operation.identity, operation.commitment
        def execute_bound(claimed):
            if (not isinstance(claimed, Operation) or claimed.status != "UNKNOWN"
                    or claimed.identity != identity or claimed.commitment != commitment):
                raise DeferredRefused("original dispatch claim changed")
            # Re-read the original task/budget immediately before execute. The
            # Wallet then applies its own atomic authority and funding checks.
            current_client, current_binding = self._bound(claimed)
            if current_client is not client or current_binding != binding:
                raise DeferredRefused("original task or funding changed after preflight")
            return current_client.task("execute", current_binding.payload())
        return execute_bound

    def observe_original(self, operation):
        client, binding = self._bound(operation)
        return client.task("observe", binding.payload())
