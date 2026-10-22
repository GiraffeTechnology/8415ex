"""Compose an original direct-return binding with an existing reserved task.

These application ports remain private. This module creates no task, policy,
grant, reserve, native journal, signer, RPC or financial operation.
"""
from copy import deepcopy

from .reserved_wallet_task_gateway import ReservedWalletTaskGateway
from .wallet_direct_return_operation import bind_wallet_direct_return


class WalletDirectReturnTask:
    """One original ERC-721 return plan; original Wallet execution owns checks.

    The trusted host supplies authenticated task/child/native correlations and
    the original EX rollback authority. This constructor checks the existing EX
    structural binding only; it does not authenticate arbitrary caller IDs or
    prove current holder, finality or native absence. Source correlation and
    execution-time EX/Wallet authority remain original application duties.
    """
    def __init__(self, client, *, scope, authority, from_account, affected_legs,
                 original_operation, task_digest, wallet_operation_id, child_digest):
        binding = bind_wallet_direct_return(scope, authority, from_account,
                                             affected_legs, original_operation)
        self._binding = deepcopy(binding)
        self._gateway = ReservedWalletTaskGateway(
            client, scope=binding['scope'], task_digest=task_digest,
            wallet_operation_id=wallet_operation_id, child_digest=child_digest,
            original_operation=binding['operation'])

    def binding(self):
        """Detached original plan, not a frontend projection or authority proof."""
        return deepcopy(self._binding)

    def read(self):
        """Read original task status without dispatch or native-absence inference."""
        return self._gateway.read()

    def execute(self, expected_budget_revision):
        """Forward the existing exact-task request without a new status preflight.

        The original server validates its task/reservation/CAS and the original
        client keeps its durable single-attempt guard. A lost reply propagates;
        recreating this composition cannot reset that original guard. A returned
        HTTP body still leaves the native economic result unknown.
        """
        result = self._gateway.execute(expected_budget_revision)
        return dict(result, assetControlOperations=1,
                    walkedIntermediateWallets=False,
                    authorityId=self._binding['authorityId'],
                    rollbackBinding=self._binding['rollbackBinding'],
                    nativeOutcomeVerified=False, replayAllowed=False)
