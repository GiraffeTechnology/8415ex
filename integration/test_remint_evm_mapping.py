"""Authored semantic-to-ABI fixtures; no wallet, provider or chain execution."""
from copy import deepcopy
from dataclasses import replace
import unittest

from exchange import fixtures as F
from exchange.remint_terms import prepare_remint_terms, RemintTermsRefused, _hash
from exchange.remint_evm_mapping import bind_remint_evm_arguments, RemintEVMMappingRefused
from integration.test_remint_terms import original_bill


def prepared():
    old = F.mint_specification(F.receipt())
    new = replace(old, receipt=replace(old.receipt,
        asset=replace(old.receipt.asset, token_id=8416),
        receipt_id='synthetic-replacement-receipt'), bill_terms='Replacement terms')
    result = prepare_remint_terms(old, new, F.verify_fixture_mint, original_bill)
    scope = {'receiptId': old.receipt.receipt_id, 'chainId': 11155111,
             'contract': F.CONTRACT, 'tokenId': str(F.TOKEN_ID), 'globalLegId': 0,
             'action': 'remint', 'nativeOperationId': 'synthetic-native-remint',
             'intentDigest': result['historyDigest'], 'journalReference': 'synthetic-journal'}
    return scope, result['history']


def original_mapping(request, declaration):
    return {'binding': deepcopy(request), 'operationId': '0x' + 'aa' * 32,
            'replacement': {'billKey': request['billKey'], 'termsHash': '0x' + 'bb' * 32,
                'currencyDeclarationHash': '0x' + 'cc' * 32,
                'allowedCurrencies': ['0x' + 'dd' * 32, '0x' + 'ee' * 32]},
            'sourceReference': 'synthetic-original-semantic-mapping'}


class RemintEVMMappingContracts(unittest.TestCase):
    def test_exact_original_mapping_reaches_arguments_without_id_or_hash_derivation(self):
        scope, history = prepared()
        seen = []
        def resolve(request, declaration):
            seen.append((deepcopy(request), deepcopy(declaration)))
            return original_mapping(request, declaration)
        result = bind_remint_evm_arguments(scope, history, resolve)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][1], history['newDeclaration'])
        self.assertEqual(seen[0][0]['scope'], scope)
        self.assertEqual(result['evmOperationId'], '0x' + 'aa' * 32)
        self.assertEqual(result['argumentsHex'][2:66], 'aa' * 32)
        self.assertEqual(result['scope']['nativeOperationId'], 'synthetic-native-remint')
        self.assertEqual(result['historyDigest'], scope['intentDigest'])
        self.assertEqual(result['replacement']['termsHash'], '0x' + 'bb' * 32)
        self.assertFalse(result['selectorIncluded'])
        self.assertFalse(result['walletOperationCreated'])
        self.assertFalse(result['dispatchAuthorized'])
        self.assertFalse(result['nativeOutcomeVerified'])

    def test_scope_and_both_declaration_digests_must_match_exact_original_json_types(self):
        for field, value in (('historyDigest', '0' * 64), ('billKey', '0x' + 'f' * 64),
                             ('oldDeclarationDigest', '0' * 64), ('newDeclarationDigest', '0' * 64)):
            scope, history = prepared()
            def mismatch(request, declaration):
                row = original_mapping(request, declaration)
                row['binding'][field] = value
                return row
            with self.subTest(field=field), self.assertRaises(RemintEVMMappingRefused):
                bind_remint_evm_arguments(scope, history, mismatch)
        scope, history = prepared()
        def float_scope(request, declaration):
            row = original_mapping(request, declaration)
            row['binding']['scope']['chainId'] = 11155111.0
            return row
        with self.assertRaises(RemintEVMMappingRefused):
            bind_remint_evm_arguments(scope, history, float_scope)

    def test_changed_terms_or_history_digest_refuse_before_mapping_lookup(self):
        for resign_digest in (False, True):
            scope, history = prepared()
            history['newDeclaration']['billTerms'] = 'Unbound injected terms'
            if resign_digest:
                scope['intentDigest'] = _hash(history)
            calls = []
            with self.subTest(resign_digest=resign_digest), self.assertRaises(RemintTermsRefused):
                bind_remint_evm_arguments(scope, history, lambda *args: calls.append(args))
            self.assertEqual(calls, [])

    def test_replacement_bill_and_evm_words_cannot_substitute_original_declaration(self):
        for field, value in (('billKey', '0x' + 'ff' * 32), ('termsHash', '0x' + '0' * 64),
                             ('allowedCurrencies', ['ETH'])):
            scope, history = prepared()
            def wrong(request, declaration):
                row = original_mapping(request, declaration)
                row['replacement'][field] = value
                return row
            with self.subTest(field=field), self.assertRaises(ValueError):
                bind_remint_evm_arguments(scope, history, wrong)

    def test_original_native_id_is_not_accepted_as_an_evm_operation_word(self):
        scope, history = prepared()
        def wrong(request, declaration):
            row = original_mapping(request, declaration)
            row['operationId'] = scope['nativeOperationId']
            return row
        with self.assertRaises(ValueError):
            bind_remint_evm_arguments(scope, history, wrong)

    def test_resolver_input_mutation_does_not_change_original_history_or_scope(self):
        scope, history = prepared()
        before = deepcopy((scope, history))
        def resolve(request, declaration):
            row = original_mapping(request, declaration)
            request['scope']['tokenId'] = '999'
            declaration['billTerms'] = 'Resolver mutation'
            return row
        result = bind_remint_evm_arguments(scope, history, resolve)
        self.assertEqual((scope, history), before)
        self.assertEqual(result['scope'], scope)
        result['replacement']['allowedCurrencies'].clear()
        self.assertEqual(len(bind_remint_evm_arguments(scope, history, original_mapping)
                             ['replacement']['allowedCurrencies']), 2)

    def test_unavailable_missing_or_extra_mapping_fields_cannot_encode_or_leak_private_errors(self):
        scope, history = prepared()
        def unavailable(*args):
            raise RuntimeError('private-native-endpoint-token')
        with self.assertRaises(RemintEVMMappingRefused) as caught:
            bind_remint_evm_arguments(scope, history, unavailable)
        self.assertNotIn('private-native-endpoint-token', str(caught.exception))
        for resolve in (lambda *args: None,
                        lambda request, declaration: dict(original_mapping(request, declaration), approval=True)):
            with self.subTest(resolve=resolve), self.assertRaises(RemintEVMMappingRefused):
                bind_remint_evm_arguments(scope, history, resolve)

    def test_another_contract_is_not_silently_encoded_as_this_contract_remint(self):
        scope, history = prepared()
        other = '0x' + 'f' * 40
        history['newDeclaration']['receipt']['asset']['contract'] = other
        history['binding']['newAsset']['contract'] = other
        history['binding']['newDeclarationDigest'] = _hash(history['newDeclaration'])
        scope['intentDigest'] = _hash(history)
        calls = []
        with self.assertRaises(RemintEVMMappingRefused):
            bind_remint_evm_arguments(scope, history, lambda *args: calls.append(args))
        self.assertEqual(calls, [])
