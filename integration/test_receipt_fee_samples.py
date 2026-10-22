"""Authored receipt-to-P50 fixtures only; no real chain, network or wallet."""
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
import unittest

from exchange.gas_budget import GasBudgetRefused, GasQuote
from exchange.original_gas_receipt_reader import OriginalGasReceiptReader
from exchange.receipt_fee_samples import receipt_fee_samples
from exchange.receipt_gas_observer import ReceiptGasObservation
from integration.test_original_gas_receipt_reader import RpcFixture, sequence, TX


def observation(number=1, outcome='SUCCESS'):
    return ReceiptGasObservation(11155111, 'private-attempt-' + str(number),
        '0x' + str(number) * 64, '0x' + 'a' * 64, 16,
        21000, number + 2, 21000 * (number + 2), outcome,
        'b' * 64, 'private-proof-' + str(number))


def population():
    return [{'observation': observation(1), 'sampleId': 'sample-1',
             'observedAt': 90, 'source': 'original-receipt-source'},
            {'observation': observation(2, 'FAILED'), 'sampleId': 'sample-2',
             'observedAt': 99, 'source': 'original-receipt-source'}]


def convert(values, verify=lambda binding: True, **changes):
    options = dict(scope='original-transfer-scope', window_start=90, window_end=99,
                   verify_applicability=verify)
    options.update(changes)
    return receipt_fee_samples(values, **options)


class ReceiptFeeSampleContracts(unittest.TestCase):
    def test_exact_total_transaction_fees_feed_existing_even_population_p50(self):
        samples = convert(population())
        self.assertEqual(tuple(sample.fee_wei for sample in samples), (63000, 84000))
        quote = GasQuote('quote-fixture', 1, 'budget-fixture', 'original-transfer-scope',
            ('transfer',), 11155111, 100000, samples, 90, 99, 100, 200,
            3000000000, 100, 'fixture-fx', 'c' * 64)
        self.assertEqual(quote.median_wei, Fraction(73500))
        self.assertEqual(quote.disclosure()['sampleCount'], 2)
        self.assertEqual(samples[0].raw_sha256, 'b' * 64)
        self.assertEqual(samples[0].block_number, 16)

    def test_original_applicability_receives_complete_private_binding_once(self):
        seen = []
        values = population()
        before = deepcopy(values)
        samples = convert(values, lambda binding: seen.append(binding) or True)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]['scope'], 'original-transfer-scope')
        self.assertEqual(seen[0]['windowStart'], 90)
        self.assertEqual(seen[0]['windowEnd'], 99)
        self.assertEqual(len(seen[0]['population']), 2)
        self.assertEqual(seen[0]['population'][1]['observation']['outcome'], 'FAILED')
        self.assertEqual(seen[0]['population'][0]['observation']['proof_reference'], 'private-proof-1')
        self.assertEqual(values, before)
        self.assertFalse(hasattr(samples[0], 'proof_reference'))
        self.assertFalse(hasattr(samples[0], 'transaction_hash'))

    def test_null_one_sample_or_oversized_population_is_not_fake_zero(self):
        for values in (None, [], population()[:1], population() * 257):
            with self.subTest(size=len(values) if values is not None else None):
                seen = []
                with self.assertRaises(GasBudgetRefused):
                    convert(values, lambda binding: seen.append(binding) or True)
                self.assertEqual(seen, [])
        values = population()
        values[0]['observation'] = None
        with self.assertRaises(GasBudgetRefused):
            convert(values)

    def test_duplicate_transaction_or_sample_labels_cannot_weight_the_median_twice(self):
        for key in ('sampleId', 'observation'):
            values = population()
            values[1][key] = values[0][key]
            with self.subTest(key=key), self.assertRaises(GasBudgetRefused):
                convert(values)

    def test_wrong_chain_inconsistent_cost_and_unmined_shapes_refused_before_verifier(self):
        for change in ({'chain_id': 560048}, {'chain_id': True}, {'gas_used': 0},
                       {'gas_used': True}, {'actual_wei': 1}, {'actual_wei': float(63000)},
                       {'block_number': -1}, {'raw_sha256': 'missing'},
                       {'transaction_hash': '0x1'}, {'outcome': 'UNKNOWN'}):
            values = population()
            values[0]['observation'] = replace(values[0]['observation'], **change)
            seen = []
            with self.subTest(change=change), self.assertRaises(GasBudgetRefused):
                convert(values, lambda binding: seen.append(binding) or True)
            self.assertEqual(seen, [])

    def test_times_and_labels_are_original_and_cannot_be_guessed_or_coerced(self):
        for key, value in (('observedAt', 89), ('observedAt', 100), ('observedAt', True),
                           ('sampleId', '0x' + 'a' * 40), ('source', '<private>')):
            values = population()
            values[0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(GasBudgetRefused):
                convert(values)
        with self.assertRaises(GasBudgetRefused):
            convert(population(), window_start=100, window_end=90)

    def test_false_non_boolean_and_failed_applicability_provide_no_samples_or_private_error(self):
        for result in (False, None, 1, 'verified'):
            with self.subTest(result=result), self.assertRaises(GasBudgetRefused):
                convert(population(), lambda binding: result)
        def unavailable(binding):
            raise RuntimeError('private-endpoint-credential')
        with self.assertRaises(GasBudgetRefused) as caught:
            convert(population(), unavailable)
        self.assertNotIn('private-endpoint-credential', str(caught.exception))

    def test_verifier_mutation_cannot_change_returned_amount_scope_or_window(self):
        def verify(binding):
            binding['population'][0]['sample']['fee_wei'] = 0
            binding['scope'] = 'other-scope'
            binding['population'].clear()
            return True
        samples = convert(population(), verify)
        self.assertEqual(samples[0].fee_wei, 63000)
        self.assertEqual(samples[0].scope, 'original-transfer-scope')
        self.assertEqual(samples[0].observed_at, 90)

    def test_existing_original_reader_output_composes_without_new_rpc_or_signer(self):
        rpc = RpcFixture(sequence())
        result = OriginalGasReceiptReader(rpc, lambda evidence: True).read(
            attempt_id='original-fixture-attempt', transaction_hash=TX,
            proof_reference='original-fixture-proof')
        calls = deepcopy(rpc.calls)
        values = population()
        values[0]['observation'] = result
        samples = convert(values)
        self.assertEqual(samples[0].fee_wei, 63000)
        self.assertEqual(result.outcome, 'FAILED')
        self.assertEqual(rpc.calls, calls)
        self.assertEqual(len(rpc.calls), 7)
