"""Synthetic HTTP composition; never actual Wallet authority or value movement."""
from contextlib import contextmanager
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest

from exchange.wallet_api_client import WalletAPIRefused
from exchange.reserved_wallet_task_gateway import (
    ReservedWalletTaskGateway, ReservedWalletTaskRefused)
from integration.test_wallet_api_client import original_protocol, ACTOR, EXECUTE
from integration.test_wallet_task_status_reader import body, SCOPE, OPERATION, ROW


@contextmanager
def gateway_fixture(status="reserved", *, durable=True):
    with original_protocol(durable_attempts=durable) as (client, state):
        client.login(lambda *args: "0x" + "1" * 130)
        operation = dict(OPERATION, actor=ACTOR)
        row = dict(ROW, operationId=EXECUTE["operationId"], status=status,
                   transactionHash="0x" + "c" * 64 if status == "submitted" else None)
        value = body([] if status == "missing" else [row])
        value["task"]["policy"]["actor"] = ACTOR
        value["task"]["policy"]["intent"]["operation"] = deepcopy(operation)
        original = client.task

        def task(action, payload):
            result = original(action, payload)
            return deepcopy(value) if action == "status" else result

        client.task = task
        options = {"scope": deepcopy(SCOPE), "task_digest": EXECUTE["taskDigest"],
                   "wallet_operation_id": EXECUTE["operationId"],
                   "child_digest": EXECUTE["childDigest"], "original_operation": operation}
        yield ReservedWalletTaskGateway(client, **options), client, state, value, options


def executes(state):
    return [row for _, path, row in state["calls"] if path == "/auth/tasks/execute"]


class ReservedWalletGatewayContracts(unittest.TestCase):
    def test_existing_budget_revision_and_ids_reach_original_execute(self):
        with gateway_fixture() as (gateway, client, state, value, _):
            result = gateway.execute("4")
            self.assertEqual(executes(state), [dict(EXECUTE, expectedBudgetRevision="4")])
            self.assertEqual(result["status"], "unknown")
            self.assertFalse(result["nativeOutcomeVerified"])
            self.assertFalse(result["replayAllowed"])
            self.assertTrue(result["originalExecuteReturned"])
            self.assertFalse(any(path.endswith(("/prepare", "/authorize", "/reserve", "/recover"))
                                 for _, path, _ in state["calls"]))

    def test_execute_has_no_mandatory_status_or_new_readiness_query(self):
        with gateway_fixture() as (gateway, client, state, value, _):
            original = client.task
            def no_status(action, payload):
                if action == "status":
                    self.fail("extra status query blocked original execution")
                return original(action, payload)
            client.task = no_status
            result = gateway.execute("4")
            self.assertEqual(result["status"], "unknown")
            self.assertEqual(len(executes(state)), 1)
            self.assertFalse(any(path == "/auth/tasks/status"
                                 for _, path, _ in state["calls"]))

    def test_unknown_execute_propagates_and_same_original_client_blocks_resend(self):
        with gateway_fixture() as (gateway, client, state, value, _):
            state["mode"] = "unknown-execute"
            with self.assertRaisesRegex(WalletAPIRefused, "OUTCOME_UNKNOWN"):
                gateway.execute("4")
            with self.assertRaisesRegex(WalletAPIRefused, "RECONCILE_FIRST"):
                gateway.execute("4")
            self.assertEqual(len(executes(state)), 1)
            self.assertEqual(gateway.read()["reservationStatus"], "reserved")
            self.assertEqual(len(executes(state)), 1)

    def test_reconstructed_gateway_cannot_clear_original_durable_attempt(self):
        with gateway_fixture() as (gateway, client, state, value, options):
            gateway.execute("4")
            recreated = ReservedWalletTaskGateway(client, **options)
            with self.assertRaisesRegex(WalletAPIRefused, "RECONCILE_FIRST"):
                recreated.execute("4")
            self.assertEqual(len(executes(state)), 1)

    def test_no_fallback_store_is_created_when_original_attempt_store_is_missing(self):
        with gateway_fixture(durable=False) as (gateway, client, state, value, _):
            with self.assertRaisesRegex(WalletAPIRefused, "DURABLE_ATTEMPT_STORE_REQUIRED"):
                gateway.execute("4")
            self.assertEqual(executes(state), [])

    def test_captured_mapping_does_not_follow_caller_mutation(self):
        with gateway_fixture() as (gateway, client, state, value, options):
            options["scope"]["nativeOperationId"] = "other"
            options["original_operation"]["recipient"] = ACTOR
            result = gateway.execute("4")
            self.assertEqual(result["scope"]["nativeOperationId"], SCOPE["nativeOperationId"])
            self.assertEqual(len(executes(state)), 1)

    def test_read_is_available_without_dispatch_for_all_budget_states(self):
        for status in ("reserved", "outcome-unknown", "submitted", "cancelled", "missing"):
            with self.subTest(status=status), gateway_fixture(status) as (
                    gateway, client, state, value, _):
                observed = gateway.read()
                self.assertEqual(observed["reservationStatus"],
                                 "not-observed" if status == "missing" else status)
                self.assertFalse(observed["canExecute"])
                self.assertEqual(executes(state), [])

    def test_concurrent_entry_keeps_original_single_execute_attempt(self):
        with gateway_fixture() as (gateway, client, state, value, _):
            ready = threading.Barrier(2)
            def call():
                ready.wait(timeout=5)
                try:
                    return gateway.execute("4")["status"]
                except WalletAPIRefused as error:
                    return str(error)
            with ThreadPoolExecutor(max_workers=2) as workers:
                pending = [workers.submit(call) for _ in range(2)]
                results = [future.result(timeout=10) for future in pending]
            self.assertEqual(results.count("unknown"), 1)
            self.assertEqual(sum("RECONCILE_FIRST" in result for result in results), 1)
            self.assertEqual(len(executes(state)), 1)
