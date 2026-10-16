"""Authored read-only original journal fixtures, not actual mTLS/grant proof."""
from copy import deepcopy
import unittest
from exchange.original_task_journal_reader import (OriginalTaskJournalReader,
    OriginalJournalRefused, OriginalJournalUnavailable)

WALLET = '0x' + '2' * 40
OPERATION = 'native_operation_1234'
PRINCIPAL = {'kind': 'task', 'taskId': 'task-1', 'taskDigest': '0x' + 'a' * 64,
    'executorDigest': '0x' + 'b' * 64, 'grantReference': 'grant:fixture',
    'grantPolicyVersion': '1', 'operationId': 'logical-operation-1'}


def native_operation():
    return {'id': OPERATION, 'wallet': WALLET, 'chainId': 11155111,
        'revision': 1, 'status': 'pending', 'requestHash': 'c' * 64,
        'walletStarted': False, 'updatedAt': '2026-10-17T04:00:00Z',
        'plan': {'operationId': OPERATION, 'chainId': 11155111,
            'taskPrincipal': deepcopy(PRINCIPAL), 'request': {'account': WALLET}}}


class OriginalJournalReaderContracts(unittest.TestCase):
    def setUp(self):
        self.result = native_operation()
        self.calls = []
        def original(principal, action, operation):
            self.calls.append((deepcopy(principal), action, deepcopy(operation)))
            return self.result
        self.reader = OriginalTaskJournalReader(original)

    def read(self):
        return self.reader.read(PRINCIPAL, OPERATION, 11155111, WALLET)

    def test_only_original_get_and_original_digests_are_preserved(self):
        result = self.read()
        self.assertEqual(self.calls, [(PRINCIPAL, 'get', {'id': OPERATION})])
        self.assertEqual(result['sourceInterface'], 'artfi-task-journal/1')
        self.assertEqual(result['nativeOperation']['requestHash'], 'c' * 64)
        self.assertEqual(result['nativeOperation']['plan']['taskPrincipal'], PRINCIPAL)
        self.assertFalse(result['canExecute'])
        self.assertEqual(result['oracleRegistration'], 'NOT_VERIFIED')
        self.assertEqual(result['gasFunding'], 'NOT_VERIFIED')
        result['nativeOperation']['status'] = 'changed-copy'
        self.assertEqual(self.result['status'], 'pending')

    def test_bad_principal_or_missing_scope_is_refused_before_get(self):
        for principal in (dict(PRINCIPAL, sessionId='not-task'),
                          dict(PRINCIPAL, grantPolicyVersion='0'),
                          dict(PRINCIPAL, executorDigest='invalid')):
            with self.assertRaises(OriginalJournalRefused):
                self.reader.read(principal, OPERATION, 11155111, WALLET)
        with self.assertRaises(OriginalJournalRefused):
            self.reader.read(PRINCIPAL, 'short', True, WALLET)
        self.assertEqual(self.calls, [])

    def test_foreign_chain_wallet_principal_and_operation_are_refused(self):
        original = native_operation()
        for key, value in (('id', 'different_operation_1234'), ('chainId', 560048),
                           ('wallet', '0x' + '3' * 40)):
            self.result = dict(original, **{key: value})
            with self.subTest(key=key), self.assertRaises(OriginalJournalRefused):
                self.read()
        self.result = native_operation()
        self.result['plan']['taskPrincipal']['taskDigest'] = '0x' + 'd' * 64
        with self.assertRaises(OriginalJournalRefused):
            self.read()

    def test_nested_signature_or_capability_payload_is_not_exposed(self):
        for key in ('exact_signature', 'rawTransaction', 'accessToken', 'capability'):
            self.result = native_operation()
            self.result['plan']['request']['nested'] = [{key: 'synthetic-private-marker'}]
            with self.subTest(key=key), self.assertRaises(OriginalJournalRefused) as caught:
                self.read()
            self.assertNotIn('synthetic-private-marker', str(caught.exception))

    def test_invalid_revision_status_timestamp_and_hash_are_refused(self):
        for key, value in (('revision', True), ('status', 'invented'), ('status', []),
                           ('updatedAt', 'invalid'), ('updatedAt', '2026-10-17T04:00:00'),
                           ('transactionHash', 'not-a-hash'), ('requestHash', 'missing')):
            self.result = dict(native_operation(), **{key: value})
            with self.subTest(key=key), self.assertRaises(OriginalJournalRefused):
                self.read()

    def test_plan_session_or_foreign_request_account_is_refused(self):
        for change in ('session', 'account', 'chain'):
            self.result = native_operation()
            if change == 'session':
                self.result['plan']['sessionId'] = 'session-1'
            elif change == 'account':
                self.result['plan']['request']['account'] = '0x' + '3' * 40
            else:
                self.result['plan']['chainId'] = True
            with self.assertRaises(OriginalJournalRefused):
                self.read()

    def test_unavailable_original_never_retries_or_falls_back(self):
        calls = []
        def unavailable(*args):
            calls.append(args)
            raise RuntimeError('synthetic-sensitive-marker')
        reader = OriginalTaskJournalReader(unavailable)
        with self.assertRaises(OriginalJournalUnavailable) as caught:
            reader.read(PRINCIPAL, OPERATION, 11155111, WALLET)
        self.assertEqual(len(calls), 1)
        self.assertNotIn('synthetic-sensitive-marker', str(caught.exception))
        with self.assertRaises(OriginalJournalUnavailable):
            OriginalTaskJournalReader(None)

    def test_oversized_or_unsafe_integer_payload_is_refused(self):
        self.result['plan']['extra'] = 'x' * 65536
        with self.assertRaises(OriginalJournalRefused):
            self.read()
        self.result = native_operation()
        self.result['plan']['extra'] = 9007199254740992
        with self.assertRaises(OriginalJournalRefused):
            self.read()
