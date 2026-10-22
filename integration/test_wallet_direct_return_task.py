"""Authored synthetic original-task composition; no value or chain execution."""
from contextlib import contextmanager
from copy import deepcopy
import unittest

from exchange.wallet_api_client import WalletAPIRefused
from exchange.wallet_direct_return_operation import DirectReturnOperationRefused
from exchange.wallet_direct_return_task import WalletDirectReturnTask
from integration.test_wallet_api_client import original_protocol, ACTOR, EXECUTE
from integration.test_wallet_direct_return_operation import fixture, HOLDER
from integration.test_wallet_task_status_reader import body, ROW


@contextmanager
def direct_task(status='reserved'):
    with original_protocol(durable_attempts=True) as (client, state):
        client.login(lambda *args: '0x' + '1' * 130)
        scope, authority, legs, operation = fixture()
        operation['actor'] = ACTOR
        row = dict(ROW, operationId=EXECUTE['operationId'],
                   childDigest=EXECUTE['childDigest'], status=status,
                   transactionHash='0x' + 'c' * 64 if status == 'submitted' else None)
        value = body([] if status == 'missing' else [row])
        value['task']['digest'] = EXECUTE['taskDigest']
        value['budget']['taskDigest'] = EXECUTE['taskDigest']
        value['task']['policy']['actor'] = ACTOR
        value['task']['policy']['chainId'] = str(scope['chainId'])
        value['task']['policy']['intent']['operation'] = deepcopy(operation)
        original = client.task
        def task(action, payload):
            result = original(action, payload)
            return deepcopy(value) if action == 'status' else result
        client.task = task
        options = dict(scope=scope, authority=authority, from_account=ACTOR,
            affected_legs=legs, original_operation=operation,
            task_digest=EXECUTE['taskDigest'], wallet_operation_id=EXECUTE['operationId'],
            child_digest=EXECUTE['childDigest'])
        yield WalletDirectReturnTask(client, **options), client, state, value, options


def executes(state):
    return [row for _, path, row in state['calls'] if path == '/auth/tasks/execute']


class DirectReturnTaskContracts(unittest.TestCase):
    def test_original_task_fields_and_budget_revision_reach_single_execute(self):
        with direct_task() as (task, client, state, value, options):
            result = task.execute('4')
            self.assertEqual(executes(state), [dict(EXECUTE, expectedBudgetRevision='4')])
            self.assertEqual(result['scope'], options['scope'])
            self.assertEqual(result['walletOperationId'], EXECUTE['operationId'])
            self.assertEqual(result['assetControlOperations'], 1)
            self.assertFalse(result['walkedIntermediateWallets'])
            self.assertEqual(result['status'], 'unknown')
            self.assertFalse(result['nativeOutcomeVerified'])
            self.assertFalse(result['replayAllowed'])
            self.assertEqual(task.binding()['operation']['recipient'], HOLDER)

    def test_constructor_and_execute_add_no_status_prepare_reserve_or_approval_request(self):
        with direct_task() as (task, client, state, value, options):
            before = len(state['calls'])
            recreated = WalletDirectReturnTask(client, **options)
            self.assertEqual(len(state['calls']), before)
            original = client.task
            def only_execute(action, payload):
                self.assertEqual(action, 'execute')
                return original(action, payload)
            client.task = only_execute
            recreated.execute('4')
            paths = [path for _, path, _ in state['calls'][before:]]
            self.assertEqual(paths, ['/auth/tasks/execute'])

    def test_different_recipient_or_return_hop_refuses_before_wallet_calls(self):
        with direct_task() as (task, client, state, value, options):
            before = deepcopy(state['calls'])
            for operation in (dict(options['original_operation'], recipient=ACTOR),
                              dict(options['original_operation'], kind='return-hop'),
                              dict(options['original_operation'], tokenId='8')):
                with self.subTest(operation=operation), self.assertRaises(DirectReturnOperationRefused):
                    WalletDirectReturnTask(client, **dict(options, original_operation=operation))
            self.assertEqual(state['calls'], before)

    def test_original_interval_and_leg_binding_cannot_be_reordered_or_changed(self):
        with direct_task() as (task, client, state, value, options):
            before = deepcopy(state['calls'])
            for changes in (dict(affected_legs=list(reversed(options['affected_legs']))),
                            dict(affected_legs=options['affected_legs'][:1]),
                            dict(scope=dict(options['scope'], globalLegId=4))):
                with self.subTest(changes=changes), self.assertRaises(DirectReturnOperationRefused):
                    WalletDirectReturnTask(client, **dict(options, **changes))
            self.assertEqual(state['calls'], before)

    def test_captured_scope_operation_and_interval_ignore_caller_mutation(self):
        with direct_task() as (task, client, state, value, options):
            expected = task.binding()
            options['scope']['nativeOperationId'] = 'other-operation'
            options['original_operation']['recipient'] = ACTOR
            options['affected_legs'].clear()
            detached = task.binding()
            detached['operation']['recipient'] = ACTOR
            self.assertEqual(task.binding(), expected)
            self.assertEqual(task.execute('4')['scope'], expected['scope'])
            self.assertEqual(len(executes(state)), 1)

    def test_missing_or_unknown_task_read_never_means_native_absence_or_execution(self):
        for status in ('missing', 'outcome-unknown', 'cancelled', 'submitted'):
            with self.subTest(status=status), direct_task(status) as (task, client, state, value, _):
                result = task.read()
                self.assertEqual(result['reservationStatus'], 'not-observed' if status == 'missing' else status)
                self.assertFalse(result['authenticatedNativeAbsence'])
                self.assertFalse(result['canExecute'])
                self.assertFalse(result['nativeOutcomeVerified'])
                self.assertEqual(executes(state), [])

    def test_unknown_reply_keeps_original_attempt_and_reconstruction_cannot_resend(self):
        with direct_task() as (task, client, state, value, options):
            state['mode'] = 'unknown-execute'
            with self.assertRaisesRegex(WalletAPIRefused, 'OUTCOME_UNKNOWN'):
                task.execute('4')
            recreated = WalletDirectReturnTask(client, **options)
            with self.assertRaisesRegex(WalletAPIRefused, 'RECONCILE_FIRST'):
                recreated.execute('4')
            self.assertEqual(len(executes(state)), 1)
            self.assertFalse(recreated.read()['authenticatedNativeAbsence'])
            self.assertEqual(len(executes(state)), 1)

    def test_native_and_wallet_ids_remain_distinct_without_hashing_or_reset(self):
        with direct_task() as (task, client, state, value, options):
            original_native = options['scope']['nativeOperationId']
            original_wallet = options['wallet_operation_id']
            self.assertNotEqual(original_native, original_wallet)
            result = task.execute('4')
            self.assertEqual(result['scope']['nativeOperationId'], original_native)
            self.assertEqual(result['walletOperationId'], original_wallet)
            self.assertEqual(result['taskDigest'], options['task_digest'])
            self.assertEqual(result['childDigest'], options['child_digest'])
            self.assertFalse(task.binding()['dispatchAuthorized'])
