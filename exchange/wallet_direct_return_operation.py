"""Bind an existing Wallet ERC-721 operation to the original EX return boundary.

Pure correlation only: no task/grant creation, RPC, signing, execution or storage.
"""
from copy import deepcopy

from .durable_operation import _scope
from .ids import address
from .model import Asset
from .rollback import RollbackAuthority, rollback_binding


class DirectReturnOperationRefused(ValueError):
    pass


def bind_wallet_direct_return(scope, authority, from_account, affected_legs,
                              original_operation):
    """Match an ORIGINAL operation; never widen it or substitute returnHop.

    The trusted composition supplies the original current-owner observation and
    rollback interval. Wallet retains its actual grant, owner/simulation, funds,
    gas, nonce and execution checks. This binding is not any of those proofs.
    """
    binding = _scope(scope)
    if (binding["action"] != "rollback" or type(authority) is not RollbackAuthority
            or type(affected_legs) not in (list, tuple) or not affected_legs):
        raise DirectReturnOperationRefused("EX_DIRECT_RETURN_SCOPE_REFUSED")
    asset = authority.asset
    if (type(asset) is not Asset or asset.chain_id != binding["chainId"]
            or asset.contract != binding["contract"]
            or str(asset.token_id) != binding["tokenId"]
            or authority.receipt_id != binding["receiptId"]
            or authority.refused_leg_index != binding["globalLegId"]):
        raise DirectReturnOperationRefused("EX_DIRECT_RETURN_IDENTITY_REFUSED")
    # Preserve the exact original interval ordering and members; do not sort,
    # truncate or reconstruct them from current wallet addresses.
    interval = deepcopy(list(affected_legs))
    if authority.binding != rollback_binding(asset, authority.receipt_id,
            authority.refused_leg_index, authority.boundary_account, interval):
        raise DirectReturnOperationRefused("EX_DIRECT_RETURN_BOUNDARY_REFUSED")
    owner = address(from_account, "EX_DIRECT_RETURN_OWNER_REFUSED")
    holder = authority.boundary_account
    if (owner == "0x" + "0" * 40 or holder == "0x" + "0" * 40
            or owner == holder):
        raise DirectReturnOperationRefused("EX_DIRECT_RETURN_OWNER_REFUSED")
    expected = {"kind": "erc721-transfer", "chainId": str(asset.chain_id),
                "actor": owner, "contract": asset.contract,
                "recipient": holder, "tokenId": str(asset.token_id)}
    if (type(original_operation) is not dict
            or set(original_operation) != set(expected)
            or any(type(original_operation[key]) is not str
                   or original_operation[key] != value
                   for key, value in expected.items())):
        raise DirectReturnOperationRefused("EX_DIRECT_RETURN_OPERATION_REFUSED")
    return {"scope": binding, "operation": deepcopy(original_operation),
            "authorityId": authority.authority_id,
            "rollbackBinding": authority.binding, "affectedLegs": interval,
            "assetControlOperations": 1, "walkedIntermediateWallets": False,
            "dispatchAuthorized": False, "nativeOutcomeVerified": False}
