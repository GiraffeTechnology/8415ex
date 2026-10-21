"""Enter only an existing reserved exact task through the original Wallet client."""
from copy import deepcopy
from threading import RLock

from .durable_operation import _scope
from .wallet_api_client import WalletAPIClient
from .wallet_task_status_reader import WalletTaskStatusReader


class ReservedWalletTaskRefused(ValueError):
    pass


class ReservedWalletTaskGateway:
    """Trusted composition of original immutable task/native correlations.

    No prepare/authorize/reserve route, task policy construction, credential,
    persistence, RPC or signer is created. The original client owns its durable
    execute-attempt guard and the server owns its CAS and execution checks.
    """
    def __init__(self, client, *, scope, task_digest, wallet_operation_id,
                 child_digest, original_operation):
        if not isinstance(client, WalletAPIClient):
            raise ReservedWalletTaskRefused("EX_RESERVED_WALLET_CLIENT_REQUIRED")
        self._client = client
        self._reader = WalletTaskStatusReader(client)
        self._scope = _scope(scope)
        self._task = deepcopy(task_digest)
        self._wallet_operation = deepcopy(wallet_operation_id)
        self._child = deepcopy(child_digest)
        self._operation = deepcopy(original_operation)
        self._lock = RLock()

    def _read(self):
        return self._reader.read(self._scope, self._task, self._wallet_operation,
                                 self._child, self._operation)

    def read(self):
        """Read the SAME original task, including unknown/cancelled/missing rows."""
        with self._lock:
            return self._read()

    def execute(self):
        """Execute a matching already-reserved operation once via existing guards.

        The observed budget revision is the server's existing compare-and-swap
        input, not a locally minted permission. A concurrent change is left to
        that original CAS; this gateway never refreshes and retries execution.
        """
        with self._lock:
            observed = self._read()
            if observed["reservationStatus"] != "reserved":
                raise ReservedWalletTaskRefused("EX_RESERVED_WALLET_RECONCILE_ONLY")
            request = {"taskDigest": self._task,
                       "operationId": self._wallet_operation,
                       "childDigest": self._child,
                       "expectedBudgetRevision": observed["budgetRevision"]}
            # Do not duplicate or reset the client's persistent attempt store.
            # Exceptions propagate; its uncertain/claimed operation stays bound.
            self._client.task("execute", request)
            # Even an accepted/submitted HTTP body cannot prove economic effects.
            return {"scope": deepcopy(self._scope), "taskDigest": self._task,
                    "walletOperationId": self._wallet_operation,
                    "childDigest": self._child,
                    "budgetRevisionAtRequest": observed["budgetRevision"],
                    "status": "unknown", "originalExecuteReturned": True,
                    "nativeOutcomeVerified": False, "replayAllowed": False}
