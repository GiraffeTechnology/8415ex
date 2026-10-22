"""Authored synthetic Hoodi cases, not executed or live-chain evidence.

Fixture verifiers returning True exercise the adapter contract only. They do
not establish EX payer/budget authority or produce deferred settlement Facts.
"""
from dataclasses import replace
import json
import unittest

from exchange.gas_budget import GasBudgetRefused
from exchange.original_gas_receipt_reader import (
    HoodiOriginalGasReceiptReader, OriginalGasReceiptReader)
from exchange.receipt_gas_observer import (
    HoodiReceiptGasObservation, HoodiReceiptGasObserver,
    ReceiptGasObservation, ReceiptGasObserver)


TX = '0x' + '1' * 64
BLOCK = '0x' + '2' * 64
FINALIZED = '0x' + '3' * 64


def encoded(value):
    return json.dumps(value, separators=(',', ':')).encode()


def raw(**changes):
    value = dict(transactionHash=TX, blockHash=BLOCK, blockNumber='0x10',
                 gasUsed='0x5208', effectiveGasPrice='0x3', status='0x1', type='0x2')
    value.update(changes)
    return encoded(value)


def sequence(**changes):
    receipt = raw(**changes)
    block = encoded(dict(number='0x10', hash=BLOCK))
    return [encoded(hex(560048)), receipt,
            encoded(dict(number='0x20', hash=FINALIZED)), block,
            receipt, block, encoded(hex(560048))]


class RpcFixture:
    def __init__(self, values):
        self.values = list(values)
        self.calls = []

    def __call__(self, method, parameters):
        self.calls.append((method, parameters))
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def read(rpc, verify=lambda evidence: True, **changes):
    context = dict(attempt_id='hoodi-attempt', transaction_hash=TX,
                   proof_reference='hoodi-original-proof')
    context.update(changes)
    return HoodiOriginalGasReceiptReader(rpc, verify).read(**context)


def observe(data, verify=lambda evidence: True, **changes):
    context = dict(chain_id=560048, attempt_id='hoodi-attempt',
                   transaction_hash=TX, proof_reference='hoodi-original-proof')
    context.update(changes)
    return HoodiReceiptGasObserver(verify).observe(data, **context)


class HoodiOriginalGasReceiptReaderCases(unittest.TestCase):
    def test_finalized_success_and_failure_keep_native_chain_and_exact_transcript(self):
        for status, outcome in (('0x1', 'SUCCESS'), ('0x0', 'FAILED')):
            with self.subTest(status=status):
                values = sequence(status=status)
                rpc, seen = RpcFixture(values), []
                result = read(rpc, lambda evidence: seen.append(evidence) or True)
                self.assertIs(type(result), HoodiReceiptGasObservation)
                self.assertEqual((result.chain_id, result.actual_wei, result.outcome),
                                 (560048, 63000, outcome))
                self.assertEqual(len(seen), 1)
                proof = seen[0]
                self.assertEqual(proof['chainId'], 560048)
                self.assertEqual(proof['attemptId'], 'hoodi-attempt')
                self.assertEqual(proof['transactionHash'], TX)
                self.assertEqual(proof['proofReference'], 'hoodi-original-proof')
                self.assertEqual(proof['finalizedBlockNumber'], 32)
                self.assertEqual(proof['finalizedBlockHash'], FINALIZED)
                self.assertEqual(proof['receiptEvidence']['chainId'], 560048)
                self.assertEqual(proof['receiptEvidence']['rawReceipt'], values[1])
                self.assertEqual(proof['receiptEvidence']['rawSHA256'], result.raw_sha256)
                self.assertEqual(proof['receiptEvidence']['actualWei'], 63000)
                self.assertEqual([entry['raw'] for entry in proof['reads']], values)
                self.assertEqual([(entry['method'], entry['parameters'])
                                  for entry in proof['reads']], rpc.calls)
                self.assertEqual(rpc.calls, [('eth_chainId', []),
                    ('eth_getTransactionReceipt', [TX]),
                    ('eth_getBlockByNumber', ['finalized', False]),
                    ('eth_getBlockByNumber', ['0x10', False]),
                    ('eth_getTransactionReceipt', [TX]),
                    ('eth_getBlockByNumber', ['0x10', False]), ('eth_chainId', [])])

    def test_hoodi_pending_rechecks_chain_but_emits_no_evidence_or_zero_cost(self):
        rpc = RpcFixture([encoded(hex(560048)), b'null', encoded(hex(560048))])
        seen = []
        self.assertIsNone(read(rpc, lambda evidence: seen.append(evidence)))
        self.assertEqual(rpc.calls, [('eth_chainId', []),
            ('eth_getTransactionReceipt', [TX]), ('eth_chainId', [])])
        self.assertEqual(seen, [])

    def test_pending_chain_change_is_refused_before_unknown_result(self):
        for changed in (encoded(hex(11155111)), b'true'):
            rpc = RpcFixture([encoded(hex(560048)), b'null', changed])
            seen = []
            with self.subTest(changed=changed), self.assertRaises(GasBudgetRefused):
                read(rpc, lambda evidence: seen.append(evidence) or True)
            self.assertEqual(len(rpc.calls), 3)
            self.assertEqual(seen, [])

    def test_each_explicit_reader_refuses_the_other_chain_before_receipt(self):
        for reader, wrong_chain in ((HoodiOriginalGasReceiptReader, 11155111),
                                    (HoodiOriginalGasReceiptReader, 1),
                                    (OriginalGasReceiptReader, 560048)):
            rpc = RpcFixture([encoded(hex(wrong_chain))])
            seen = []
            with self.subTest(reader=reader, chain=wrong_chain), self.assertRaises(GasBudgetRefused):
                reader(rpc, lambda evidence: seen.append(evidence) or True).read(
                    attempt_id='original-attempt', transaction_hash=TX,
                    proof_reference='original-proof')
            self.assertEqual(rpc.calls, [('eth_chainId', [])])
            self.assertEqual(seen, [])

    def test_sepolia_pending_contract_still_uses_two_reads(self):
        rpc = RpcFixture([encoded(hex(11155111)), b'null'])
        seen = []
        self.assertIsNone(OriginalGasReceiptReader(rpc,
            lambda evidence: seen.append(evidence)).read(attempt_id='original-attempt',
                transaction_hash=TX, proof_reference='original-proof'))
        self.assertEqual(len(rpc.calls), 2)
        self.assertEqual(seen, [])

    def test_wrong_finality_reorg_receipt_or_late_chain_has_no_verifier_call(self):
        for index, replacement in (
            (2, encoded(dict(number='0xf', hash=FINALIZED))),
            (2, b'null'),
            (2, encoded(dict(number=True, hash=FINALIZED))),
            (3, encoded(dict(number='0x10', hash=TX))),
            (3, encoded(dict(number='0x11', hash=BLOCK))),
            (4, b'null'),
            (4, raw(gasUsed='0x5209')),
            (5, encoded(dict(number='0x10', hash=TX))),
            (6, encoded(hex(11155111))),
            (6, b'true')):
            values, seen = sequence(), []
            values[index] = replacement
            with self.subTest(index=index, value=replacement), self.assertRaises(GasBudgetRefused):
                read(RpcFixture(values), lambda evidence: seen.append(evidence) or True)
            self.assertEqual(seen, [])

    def test_receipt_transaction_mismatch_refuses_before_finality_reads(self):
        rpc, seen = RpcFixture(sequence(transactionHash=BLOCK)), []
        with self.assertRaises(GasBudgetRefused):
            read(rpc, lambda evidence: seen.append(evidence) or True)
        self.assertEqual(len(rpc.calls), 2)
        self.assertEqual(seen, [])

    def test_original_attempt_and_proof_mismatch_do_not_produce_observation(self):
        seen = []
        def verify(evidence):
            seen.append(evidence)
            return (evidence['chainId'] == 560048 and
                    evidence['attemptId'] == 'hoodi-attempt' and
                    evidence['proofReference'] == 'hoodi-original-proof' and
                    evidence['transactionHash'] == TX and
                    evidence['receiptEvidence']['attemptId'] == evidence['attemptId'])
        for changes in ({'attempt_id': 'another-attempt'},
                        {'proof_reference': 'another-proof'}):
            with self.subTest(changes=changes), self.assertRaises(GasBudgetRefused):
                read(RpcFixture(sequence()), verify, **changes)
        self.assertEqual(len(seen), 2)

    def test_verifier_requires_exact_true_and_hides_callback_failure(self):
        for value in (False, None, 1, 'true'):
            with self.subTest(value=value), self.assertRaises(GasBudgetRefused):
                read(RpcFixture(sequence()), lambda evidence: value)
        def unavailable(evidence):
            raise RuntimeError('private-original-verifier-token')
        with self.assertRaises(GasBudgetRefused) as caught:
            read(RpcFixture(sequence()), unavailable)
        self.assertNotIn('private-original-verifier-token', str(caught.exception))

    def test_rpc_bytes_quantities_and_json_remain_bounded(self):
        for first in (b'true', b'560048', b'"0x088bb0"', b'"0x88BB0"',
                      b'{"result":"0x88bb0"}', b'{"x":1,"x":2}',
                      b'NaN', b'\xff', b'', b'x' * 262145, '"0x88bb0"'):
            rpc, seen = RpcFixture([first]), []
            with self.subTest(first=str(first)[:30]), self.assertRaises(GasBudgetRefused):
                read(rpc, lambda evidence: seen.append(evidence) or True)
            self.assertEqual(len(rpc.calls), 1)
            self.assertEqual(seen, [])

    def test_transport_errors_are_private_and_not_retried(self):
        rpc = RpcFixture([RuntimeError('private-rpc-endpoint')])
        with self.assertRaises(GasBudgetRefused) as caught:
            read(rpc)
        self.assertEqual(len(rpc.calls), 1)
        self.assertNotIn('private-rpc-endpoint', str(caught.exception))

    def test_invalid_original_identities_refuse_before_rpc(self):
        for changes in ({'attempt_id': True}, {'attempt_id': ' '},
                        {'proof_reference': 'x' * 257},
                        {'transaction_hash': '0x' + 'A' * 64}):
            rpc = RpcFixture([])
            with self.subTest(changes=changes), self.assertRaises(GasBudgetRefused):
                read(rpc, **changes)
            self.assertEqual(rpc.calls, [])

    def test_missing_transport_or_verifier_is_refused(self):
        for rpc, verify in ((None, lambda evidence: True),
                            (lambda method, parameters: b'null', None)):
            with self.subTest(rpc=rpc), self.assertRaises(GasBudgetRefused):
                HoodiOriginalGasReceiptReader(rpc, verify)


class HoodiReceiptGasObserverCases(unittest.TestCase):
    def test_supported_receipt_types_use_transaction_gas_and_preserve_hoodi(self):
        for kind in ('0x0', '0x1', '0x2'):
            seen = []
            data = raw(type=kind, cumulativeGasUsed='0xffff', gas='0xffffff')
            result = observe(data, lambda evidence: seen.append(evidence) or True)
            self.assertIs(type(result), HoodiReceiptGasObservation)
            self.assertEqual((result.chain_id, result.gas_used,
                              result.effective_gas_price, result.actual_wei),
                             (560048, 21000, 3, 63000))
            self.assertEqual(seen[0]['chainId'], 560048)
            self.assertEqual(seen[0]['rawReceipt'], data)

    def test_hoodi_cannot_erase_chain_through_either_legacy_conversion(self):
        result = observe(raw())
        with self.assertRaises(GasBudgetRefused):
            result.consumption()
        with self.assertRaises(GasBudgetRefused):
            ReceiptGasObservation.consumption(result)
        for chain in (11155111, True):
            with self.subTest(chain=chain), self.assertRaises(GasBudgetRefused):
                replace(result, chain_id=chain)

    def test_existing_sepolia_observation_still_converts_its_own_chain_only(self):
        result = ReceiptGasObserver(lambda evidence: True).observe(raw(),
            chain_id=11155111, attempt_id='original-attempt',
            transaction_hash=TX, proof_reference='original-proof')
        self.assertIs(type(result), ReceiptGasObservation)
        self.assertEqual(result.consumption().actual_wei, 63000)
        for chain in (560048, True):
            with self.subTest(chain=chain), self.assertRaises(GasBudgetRefused):
                replace(result, chain_id=chain).consumption()

    def test_hoodi_observer_rejects_other_chains_and_boolean_context(self):
        for chain in (11155111, 1, True, False, '560048'):
            seen = []
            with self.subTest(chain=chain), self.assertRaises(GasBudgetRefused):
                observe(raw(), lambda evidence: seen.append(evidence) or True,
                        chain_id=chain)
            self.assertEqual(seen, [])
        with self.assertRaises(GasBudgetRefused):
            ReceiptGasObserver(lambda evidence: True).observe(raw(), chain_id=560048,
                attempt_id='hoodi-attempt', transaction_hash=TX,
                proof_reference='hoodi-original-proof')

    def test_malformed_or_boolean_quantity_hash_and_outcome_are_refused(self):
        for changes in ({'blockHash': None}, {'blockHash': '0x' + 'A' * 64},
                        {'transactionHash': BLOCK}, {'blockNumber': True},
                        {'gasUsed': True}, {'gasUsed': '0x0'},
                        {'gasUsed': '0x05208'}, {'gasUsed': '0x' + '1' * 65},
                        {'effectiveGasPrice': False}, {'effectiveGasPrice': 3},
                        {'status': True}, {'status': '0x2'}, {'type': True}):
            seen = []
            with self.subTest(changes=changes), self.assertRaises(GasBudgetRefused):
                observe(raw(**changes), lambda evidence: seen.append(evidence) or True)
            self.assertEqual(seen, [])

    def test_unsupported_extra_fee_models_are_not_undercounted(self):
        for changes in ({'type': '0x3'}, {'type': '0x4'},
                        {'blobGasUsed': '0x0'}, {'blobGasPrice': '0x0'},
                        {'l1Fee': '0x0'}, {'l1GasUsed': '0x0'}, {'l1GasPrice': '0x0'}):
            with self.subTest(changes=changes), self.assertRaises(GasBudgetRefused):
                observe(raw(**changes))

    def test_null_stays_unknown_without_verification(self):
        seen = []
        self.assertIsNone(observe(b'null', lambda evidence: seen.append(evidence)))
        self.assertEqual(seen, [])

    def test_duplicate_json_envelope_nonbytes_and_size_limits_remain_strict(self):
        duplicate = raw()[:-1] + b',"gasUsed":"0x1"}'
        for value in (duplicate, b'{"result":null}', b'[]', b'true', b'NaN',
                      b'\xff', b'', b'x' * 262145, raw().decode()):
            with self.subTest(value=str(value)[:30]), self.assertRaises(GasBudgetRefused):
                observe(value)

    def test_exact_true_and_original_verifier_are_required(self):
        for value in (False, None, 1, 'true'):
            with self.subTest(value=value), self.assertRaises(GasBudgetRefused):
                observe(raw(), lambda evidence: value)
        with self.assertRaises(GasBudgetRefused):
            HoodiReceiptGasObserver(None)
