"""Authored synthetic RPC sequences, not live-provider verification."""
import json
import unittest
from exchange.original_gas_receipt_reader import OriginalGasReceiptReader
from exchange.gas_budget import GasBudgetRefused

TX = '0x' + '1' * 64
BLOCK = '0x' + '2' * 64


def encoded(value):
    return json.dumps(value, separators=(',', ':')).encode()


def sequence():
    receipt = dict(transactionHash=TX, blockHash=BLOCK, blockNumber='0x10',
                   gasUsed='0x5208', effectiveGasPrice='0x3', status='0x0', type='0x2')
    block = dict(number='0x10', hash=BLOCK)
    return [encoded(hex(11155111)), encoded(receipt),
            encoded(dict(number='0x20', hash='0x'+'3'*64)), encoded(block),
            encoded(receipt), encoded(block), encoded(hex(11155111))]


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


def read(rpc, verify=lambda evidence: True):
    return OriginalGasReceiptReader(rpc, verify).read(attempt_id='attempt-1',
        transaction_hash=TX, proof_reference='original-proof')


class OriginalGasReceiptReaderCases(unittest.TestCase):
    def test_finalized_stable_failed_receipt_preserves_exact_gas(self):
        rpc = RpcFixture(sequence())
        seen = []
        result = read(rpc, lambda evidence: seen.append(evidence) or True)
        self.assertEqual(result.outcome, 'FAILED')
        self.assertEqual(result.actual_wei, 63000)
        self.assertEqual(len(seen[0]['reads']), 7)
        self.assertEqual(seen[0]['attemptId'], 'attempt-1')
        self.assertEqual(rpc.calls, [('eth_chainId', []),
            ('eth_getTransactionReceipt', [TX]),
            ('eth_getBlockByNumber', ['finalized', False]),
            ('eth_getBlockByNumber', ['0x10', False]),
            ('eth_getTransactionReceipt', [TX]),
            ('eth_getBlockByNumber', ['0x10', False]), ('eth_chainId', [])])

    def test_null_is_unknown_and_no_verifier_or_extra_calls(self):
        rpc = RpcFixture([encoded(hex(11155111)), b'null'])
        seen = []
        self.assertIsNone(read(rpc, lambda evidence: seen.append(evidence)))
        self.assertEqual(len(rpc.calls), 2)
        self.assertEqual(seen, [])

    def test_wrong_chain_stops_before_receipt(self):
        rpc = RpcFixture([encoded(hex(560048))])
        with self.assertRaises(GasBudgetRefused):
            read(rpc)
        self.assertEqual(len(rpc.calls), 1)

    def test_unfinalized_and_changed_canonical_block_refuse(self):
        for index, replacement in ((2, encoded(dict(number='0xf', hash=BLOCK))),
                                   (3, encoded(dict(number='0x10', hash=TX))),
                                   (5, encoded(dict(number='0x10', hash=TX)))):
            values = sequence()
            values[index] = replacement
            with self.subTest(index=index), self.assertRaises(GasBudgetRefused):
                read(RpcFixture(values))

    def test_receipt_or_chain_change_refuses(self):
        for index, replacement in ((4, b'null'), (6, encoded(hex(1)))):
            values = sequence()
            values[index] = replacement
            with self.subTest(index=index), self.assertRaises(GasBudgetRefused):
                read(RpcFixture(values))

    def test_transport_failure_is_bounded_and_private_error_not_echoed(self):
        rpc = RpcFixture([RuntimeError('sensitive-endpoint')])
        with self.assertRaises(GasBudgetRefused) as caught:
            read(rpc)
        self.assertEqual(len(rpc.calls), 1)
        self.assertNotIn('sensitive-endpoint', str(caught.exception))

    def test_original_attempt_verifier_is_required(self):
        with self.assertRaises(GasBudgetRefused):
            read(RpcFixture(sequence()), lambda evidence: False)
        with self.assertRaises(GasBudgetRefused):
            OriginalGasReceiptReader(lambda method, parameters: b'null', None)

    def test_rpc_envelope_and_duplicate_keys_are_refused(self):
        for first in (b'{"result":"0xaa36a7"}', b'{"x":1,"x":2}', b'NaN'):
            with self.subTest(first=first), self.assertRaises(GasBudgetRefused):
                read(RpcFixture([first]))
