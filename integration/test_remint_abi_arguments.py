"""Authored ABI vectors only; no selector, signer, contract or RPC execution."""
from copy import deepcopy
import unittest

from exchange.remint_abi_arguments import encode_remint_arguments, RemintABIRefused, REMINT_SIGNATURE


REFERENCE_HEX = (
    '1111111111111111111111111111111111111111111111111111111111111111'
    '0000000000000000000000000000000000000000000000000000000000000007'
    '0000000000000000000000000000000000000000000000000000000000000060'
    '3333333333333333333333333333333333333333333333333333333333333333'
    '4444444444444444444444444444444444444444444444444444444444444444'
    '5555555555555555555555555555555555555555555555555555555555555555'
    '0000000000000000000000000000000000000000000000000000000000000080'
    '0000000000000000000000000000000000000000000000000000000000000002'
    '6666666666666666666666666666666666666666666666666666666666666666'
    '7777777777777777777777777777777777777777777777777777777777777777'
)


def declaration():
    return {'billKey': '0x' + '33' * 32, 'termsHash': '0x' + '44' * 32,
            'currencyDeclarationHash': '0x' + '55' * 32,
            'allowedCurrencies': ['0x' + '66' * 32, '0x' + '77' * 32]}


class RemintABIArgumentContracts(unittest.TestCase):
    def test_fixed_solidity_abi_encode_vector_matches_all_320_bytes(self):
        result = encode_remint_arguments('0x' + '11' * 32, 7, declaration())
        self.assertEqual(result, bytes.fromhex(REFERENCE_HEX))
        self.assertEqual(len(result), 320)
        self.assertIs(type(result), bytes)
        self.assertEqual(REMINT_SIGNATURE,
            'remintNFT0(bytes32,uint256,(bytes32,bytes32,bytes32,bytes32[]))')

    def test_currency_array_order_is_preserved_without_sorting(self):
        changed = declaration()
        changed['allowedCurrencies'].reverse()
        result = encode_remint_arguments('0x' + '11' * 32, 7, changed)
        self.assertEqual(result[-64:], bytes.fromhex('77' * 32 + '66' * 32))
        self.assertEqual(result[:-64], bytes.fromhex(REFERENCE_HEX)[:-64])

    def test_one_and_many_currency_arrays_have_exact_lengths_and_no_truncation(self):
        for count in (1, 3, 33):
            declared = declaration()
            declared['allowedCurrencies'] = ['0x' + format(i + 1, '064x') for i in range(count)]
            with self.subTest(count=count):
                result = encode_remint_arguments('0x' + '11' * 32, 7, declared)
                self.assertEqual(len(result), (8 + count) * 32)
                self.assertEqual(int.from_bytes(result[224:256], 'big'), count)
                self.assertEqual(result[256:], b''.join(bytes.fromhex(value[2:])
                                                       for value in declared['allowedCurrencies']))

    def test_uint256_boundaries_do_not_coerce_tokens_or_add_possession_gates(self):
        for token in (0, 2**256 - 1):
            result = encode_remint_arguments('0x' + '11' * 32, token, declaration())
            self.assertEqual(int.from_bytes(result[32:64], 'big'), token)
        for token in (-1, 2**256, True, 7.0, '7'):
            with self.subTest(token=token), self.assertRaises(RemintABIRefused):
                encode_remint_arguments('0x' + '11' * 32, token, declaration())

    def test_business_ids_hash_labels_and_noncanonical_words_are_not_converted(self):
        for value in ('native-operation-1', '11' * 32, '0x' + '0' * 64,
                      '0x' + 'AA' * 32, b'1' * 32, '0x11'):
            with self.subTest(value=value), self.assertRaises(RemintABIRefused):
                encode_remint_arguments(value, 7, declaration())
        for field in ('billKey', 'termsHash', 'currencyDeclarationHash'):
            changed = declaration()
            changed[field] = '0x' + '0' * 64
            with self.subTest(field=field), self.assertRaises(RemintABIRefused):
                encode_remint_arguments('0x' + '11' * 32, 7, changed)

    def test_empty_duplicate_or_label_currencies_do_not_encode(self):
        for values in ([], ['ETH'], ['0x' + '66' * 32] * 2, ['0x' + '0' * 64], None):
            changed = declaration()
            changed['allowedCurrencies'] = values
            with self.subTest(values=values), self.assertRaises(RemintABIRefused):
                encode_remint_arguments('0x' + '11' * 32, 7, changed)

    def test_original_declaration_inputs_are_not_mutated_or_augmented(self):
        declared = declaration()
        before = deepcopy(declared)
        result = encode_remint_arguments('0x' + '11' * 32, 7, declared)
        self.assertEqual(declared, before)
        self.assertEqual(set(declared), set(before))
        self.assertEqual(result, bytes.fromhex(REFERENCE_HEX))

    def test_missing_or_extra_declaration_fields_are_refused(self):
        changed = declaration()
        del changed['termsHash']
        for value in (changed, dict(declaration(), selector='0x12345678'),
                      dict(declaration(), owner='0x' + 'a' * 40), []):
            with self.subTest(value=value), self.assertRaises(RemintABIRefused):
                encode_remint_arguments('0x' + '11' * 32, 7, value)
