"""Read original Wallet exact-task budget states; never infer native effects."""
from copy import deepcopy
import re

from .durable_operation import _scope
from .wallet_api_client import WalletAPIClient


class WalletTaskStatusRefused(ValueError):
    pass


def _hash(value):
    return type(value) is str and re.fullmatch(r"0x[0-9a-f]{64}", value) is not None


def _uint(value):
    return (type(value) is str and re.fullmatch(r"0|[1-9][0-9]{0,77}", value) is not None
            and int(value) < 2 ** 256)


class WalletTaskStatusReader:
    """Only the existing authenticated client tasks/status read is invoked.

    The supplied operation and Wallet operation ID come from the original
    trusted task/native mapping, not from an HTTP caller choosing an identity.
    This reader is not artfi-task-journal/1 and cannot authenticate native absence.
    """
    def __init__(self, client):
        if not isinstance(client, WalletAPIClient):
            raise WalletTaskStatusRefused("EX_WALLET_STATUS_CLIENT_REQUIRED")
        self._client = client

    def read(self, scope, task_digest, wallet_operation_id, child_digest,
             original_operation):
        binding = _scope(scope)
        if (not _hash(task_digest) or not _hash(child_digest)
                or type(wallet_operation_id) is not str
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}",
                                wallet_operation_id) is None
                or type(original_operation) is not dict
                or original_operation.get("chainId") != str(binding["chainId"])):
            raise WalletTaskStatusRefused("EX_WALLET_STATUS_BINDING_REFUSED")
        expected = deepcopy(original_operation)
        # No prepare, reserve, execute, recover, observe, capabilities or retry.
        body = self._client.task("status", {"taskDigest": task_digest})
        if type(body) is not dict:
            raise WalletTaskStatusRefused("EX_WALLET_STATUS_RESPONSE_REFUSED")
        task, budget = body.get("task"), body.get("budget")
        if (type(task) is not dict or task.get("digest") != task_digest
                or type(task.get("policy")) is not dict
                or task["policy"].get("schema") != "8415-agent-task/1"
                or task["policy"].get("chainId") != str(binding["chainId"])
                or task["policy"].get("actor") != expected.get("actor")
                or type(task["policy"].get("intent")) is not dict
                or task["policy"]["intent"].get("kind") != "exact-operation"
                or task["policy"]["intent"].get("operation") != expected
                or type(budget) is not dict
                or set(budget) != {"schema", "taskDigest", "revision", "reservations"}
                or budget["schema"] != "8415-task-budget/1"
                or budget["taskDigest"] != task_digest
                or not _uint(budget["revision"])
                or type(budget["reservations"]) is not list):
            raise WalletTaskStatusRefused("EX_WALLET_STATUS_RESPONSE_REFUSED")
        seen, selected = set(), None
        for row in budget["reservations"]:
            if (type(row) is not dict
                    or set(row) != {"operationId", "childDigest", "feeWei", "units",
                                    "status", "transactionHash"}
                    or type(row["operationId"]) is not str
                    or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}",
                                    row["operationId"]) is None
                    or row["operationId"] in seen or not _hash(row["childDigest"])
                    or not _uint(row["feeWei"]) or int(row["feeWei"]) == 0
                    or not _uint(row["units"]) or int(row["units"]) == 0
                    or type(row["status"]) is not str
                    or row["status"] not in ("reserved", "outcome-unknown", "submitted", "cancelled")
                    or ((row["status"] == "submitted") != (row["transactionHash"] is not None))
                    or (row["transactionHash"] is not None and not _hash(row["transactionHash"]))):
                raise WalletTaskStatusRefused("EX_WALLET_STATUS_BUDGET_REFUSED")
            seen.add(row["operationId"])
            if row["operationId"] == wallet_operation_id:
                if row["childDigest"] != child_digest:
                    raise WalletTaskStatusRefused("EX_WALLET_STATUS_CHILD_DIFFERS")
                selected = deepcopy(row)
        return {"source": "original-wallet-tasks/status",
                "scope": binding, "taskDigest": task_digest,
                "walletOperationId": wallet_operation_id, "childDigest": child_digest,
                "budgetRevision": budget["revision"],
                "reservation": selected,
                "reservationStatus": "not-observed" if selected is None else selected["status"],
                "authenticatedNativeAbsence": False, "nativeOutcomeVerified": False,
                "canExecute": False, "replayAllowed": False,
                "oracleRegistration": "NOT_VERIFIED", "principalSettlement": "NOT_VERIFIED"}
