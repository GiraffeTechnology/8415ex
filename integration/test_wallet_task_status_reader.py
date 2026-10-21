"""Synthetic task status responses, not installed Wallet or chain evidence."""
from copy import deepcopy
import unittest

from exchange.wallet_api_client import WalletAPIClient, WalletAPIRefused
from exchange.wallet_task_status_reader import WalletTaskStatusReader, WalletTaskStatusRefused

TASK = "0x" + "a" * 64
CHILD = "0x" + "b" * 64
TX = "0x" + "c" * 64
CONTRACT = "0x" + "d" * 40
OPERATION = {"kind": "erc721-transfer", "chainId": "11155111",
             "actor": "0x" + "e" * 40, "recipient": "0x" + "f" * 40,
             "contract": CONTRACT, "tokenId": "7"}
SCOPE = {"receiptId": "receipt-1", "chainId": 11155111, "contract": CONTRACT,
         "tokenId": "7", "globalLegId": 3, "action": "rollback",
         "nativeOperationId": "native-return-1", "intentDigest": "1" * 64,
         "journalReference": "original-journal"}
ROW = {"operationId": "wallet-operation-1", "childDigest": CHILD,
       "feeWei": "1", "units": "1", "status": "reserved", "transactionHash": None}


class Client(WalletAPIClient):
    # Avoid constructing any network port; the test exercises the consumer only.
    def __init__(self, body):
        self.body, self.calls = body, []

    def task(self, action, payload):
        self.calls.append((action, deepcopy(payload)))
        if isinstance(self.body, Exception):
            raise self.body
        return self.body


def body(rows=None):
    return {"task": {"digest": TASK, "policy": {"schema": "8415-agent-task/1",
            "actor": OPERATION["actor"], "chainId": "11155111",
            "intent": {"kind": "exact-operation", "operation": deepcopy(OPERATION)}}},
            "budget": {"schema": "8415-task-budget/1", "taskDigest": TASK,
                       "revision": "4", "reservations": [deepcopy(ROW)] if rows is None else rows},
            "authorization": {"private": "never-copy"}, "capabilities": {"executable": True}}


class OriginalWalletTaskStatusContracts(unittest.TestCase):
    def read(self, client):
        return WalletTaskStatusReader(client).read(
            SCOPE, TASK, "wallet-operation-1", CHILD, OPERATION)

    def test_only_original_status_and_exact_original_identities_are_returned(self):
        client = Client(body())
        result = self.read(client)
        self.assertEqual(client.calls, [("status", {"taskDigest": TASK})])
        self.assertEqual(result["scope"], SCOPE)
        self.assertEqual(result["walletOperationId"], "wallet-operation-1")
        self.assertEqual(result["reservationStatus"], "reserved")
        self.assertNotIn("authorization", result)
        self.assertNotIn("capabilities", result)
        self.assertNotIn("never-copy", str(result))

    def test_all_original_states_never_authorize_execute_or_prove_finality(self):
        for status in ("reserved", "outcome-unknown", "submitted", "cancelled"):
            row = dict(ROW, status=status, transactionHash=TX if status == "submitted" else None)
            with self.subTest(status=status):
                result = self.read(Client(body([row])))
                self.assertEqual(result["reservationStatus"], status)
                for field in ("canExecute", "replayAllowed", "nativeOutcomeVerified",
                              "authenticatedNativeAbsence"):
                    self.assertIs(result[field], False)

    def test_missing_record_is_not_authenticated_absence_or_permission_to_resend(self):
        result = self.read(Client(body([])))
        self.assertEqual(result["reservationStatus"], "not-observed")
        self.assertIsNone(result["reservation"])
        self.assertFalse(result["authenticatedNativeAbsence"])
        self.assertFalse(result["replayAllowed"])

    def test_foreign_task_chain_operation_or_child_is_refused(self):
        for change in ("digest", "chain", "operation", "child"):
            value = body()
            if change == "digest":
                value["task"]["digest"] = "0x" + "2" * 64
            elif change == "chain":
                value["task"]["policy"]["chainId"] = "560048"
            elif change == "operation":
                value["task"]["policy"]["intent"]["operation"]["recipient"] = OPERATION["actor"]
            else:
                value["budget"]["reservations"][0]["childDigest"] = "0x" + "3" * 64
            with self.subTest(change=change), self.assertRaises(WalletTaskStatusRefused):
                self.read(Client(value))

    def test_duplicate_or_inconsistent_reservations_are_refused(self):
        variants = ([deepcopy(ROW), deepcopy(ROW)],
                    [dict(ROW, status="submitted")],
                    [dict(ROW, transactionHash=TX)],
                    [dict(ROW, feeWei="0")],
                    [dict(ROW, units=True)],
                    [dict(ROW, status="confirmed")])
        for rows in variants:
            with self.subTest(rows=rows), self.assertRaises(WalletTaskStatusRefused):
                self.read(Client(body(rows)))

    def test_unavailable_original_status_is_not_retried_or_converted_to_absence(self):
        client = Client(WalletAPIRefused("EX_WALLET_TRANSPORT_UNAVAILABLE"))
        with self.assertRaises(WalletAPIRefused):
            self.read(client)
        self.assertEqual(client.calls, [("status", {"taskDigest": TASK})])

    def test_returned_scopes_and_reservations_are_detached(self):
        value = body()
        result = self.read(Client(value))
        result["scope"]["nativeOperationId"] = "different"
        result["reservation"]["status"] = "changed"
        self.assertEqual(SCOPE["nativeOperationId"], "native-return-1")
        self.assertEqual(value["budget"]["reservations"][0]["status"], "reserved")
