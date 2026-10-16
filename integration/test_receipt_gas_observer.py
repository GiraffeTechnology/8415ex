"""Authored receipt fixtures only; no chain or wallet access."""
import json
import unittest
from exchange.receipt_gas_observer import ReceiptGasObserver
from exchange.gas_budget import GasBudgetRefused

TX = '0x' + '1' * 64
BLOCK = '0x' + '2' * 64


def raw(**changes):
    value = dict(transactionHash=TX, blockHash=BLOCK, blockNumber='0x10',
                 gasUsed='0x5208', effectiveGasPrice='0x3', status='0x1', type='0x2')
    value.update(changes)
    return json.dumps(value, separators=(',', ':')).encode()


def observe(data, verify=lambda evidence: True, **changes):
    context = dict(chain_id=11155111, attempt_id='original-attempt',
                   transaction_hash=TX, proof_reference='original-proof')
    context.update(changes)
    return ReceiptGasObserver(verify).observe(data, **context)


class ReceiptGasObserverCases(unittest.TestCase):
    def test_actual_cost_uses_transaction_gas_not_cumulative_or_limit(self):
        seen = []
        result = observe(raw(cumulativeGasUsed='0xffff', gas='0xffffff'),
                         lambda evidence: seen.append(evidence) or True)
        self.assertEqual(result.actual_wei, 21000 * 3)
        self.assertEqual(result.gas_used, 21000)
        self.assertEqual(result.consumption().actual_wei, 63000)
        self.assertEqual(result.consumption().transaction_hash, TX)
        self.assertEqual(seen[0]['rawReceipt'], raw(cumulativeGasUsed='0xffff', gas='0xffffff'))
        self.assertEqual(seen[0]['rawSHA256'], result.raw_sha256)

    def test_failed_execution_still_consumes_gas(self):
        result = observe(raw(status='0x0'))
        self.assertEqual(result.outcome, 'FAILED')
        self.assertEqual(result.consumption().actual_wei, 63000)

    def test_null_remains_unknown_without_verification_or_accounting(self):
        calls = []
        self.assertIsNone(observe(b'null', lambda evidence: calls.append(evidence)))
        self.assertEqual(calls, [])

    def test_pending_missing_fields_and_zero_gas_refused(self):
        for changes in ({'blockHash': None}, {'status': None}, {'gasUsed': '0x0'}):
            with self.subTest(changes=changes), self.assertRaises(GasBudgetRefused):
                observe(raw(**changes))

    def test_wrong_chain_transaction_or_noncanonical_quantity_refused(self):
        for data, context in ((raw(), {'chain_id': 560048}),
                              (raw(transactionHash='0x' + '3'*64), {}),
                              (raw(gasUsed='0x05208'), {}),
                              (raw(effectiveGasPrice=3), {}),
                              (raw(status='0x2'), {})):
            with self.subTest(context=context), self.assertRaises(GasBudgetRefused):
                observe(data, **context)

    def test_blob_or_additional_fee_model_refused(self):
        for changes in ({'type': '0x3'}, {'type': '0x4'},
                        {'blobGasUsed': '0x0'}, {'l1Fee': '0x0'}):
            with self.subTest(changes=changes), self.assertRaises(GasBudgetRefused):
                observe(raw(**changes))

    def test_reorg_or_unverified_attempt_has_no_consumption(self):
        with self.assertRaises(GasBudgetRefused):
            observe(raw(), lambda evidence: False)
        def unavailable(evidence):
            raise RuntimeError('private-provider-token')
        with self.assertRaises(GasBudgetRefused) as caught:
            observe(raw(), unavailable)
        self.assertNotIn('private-provider-token', str(caught.exception))

    def test_duplicate_fields_envelopes_and_oversized_raw_refused(self):
        duplicate = raw()[:-1] + b',"gasUsed":"0x1"}'
        for value in (duplicate, b'{"result":null}', b'[]', b'x' * 262145,
                      b'{"gasUsed":NaN}'):
            with self.subTest(size=len(value)), self.assertRaises(GasBudgetRefused):
                observe(value)
