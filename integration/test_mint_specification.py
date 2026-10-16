"""Authored metadata contracts; fixtures are not actual mint/storage evidence."""
import json
import unittest
from dataclasses import replace
from exchange.model import Asset, WarehouseReceipt
from exchange.mint_specification import (CommodityTemplate, RegistrationFormat,
    MintSpecification, MintDeclarationBook, MintSpecificationRefused)


def specification(path='REG_DIRECT'):
    receipt = WarehouseReceipt('receipt-1', Asset(11155111, '0x' + '1' * 40, 7),
        'Fixture grain', 100, 'kg', 'warehouse-1', path, 200, '0x' + '2' * 40, 10)
    template = CommodityTemplate('fixture-template', '1', 'fixture-grain',
        'fixture-equivalent-standard', ('grade', 'packing'), ('grade',))
    fmt = RegistrationFormat('fixture-voucher', '1', ('asset', 'segment', 'holder'), path)
    return MintSpecification(receipt, template, 'bill-1', 'issuer-1', 'registrar-1',
        'fixture-location', (('grade', 'fixture-grade'),),
        'Pickup terms retained as document text; EX transfers the bill only.',
        'document-map-1', 'controlled-map-1', 180, 'LTE', fmt)


class MintSpecificationContracts(unittest.TestCase):
    def setUp(self):
        self.spec = specification()
        self.book = MintDeclarationBook(lambda kind, evidence: True)

    def test_complete_whole_receipt_preserves_goods_terms_and_time(self):
        result = self.book.admit(self.spec)
        meta = result['canonicalDeclaration']
        self.assertEqual(meta['wholeReceiptUnits'], 1)
        self.assertEqual(meta['receipt']['commodity_quantity'], 100)
        self.assertEqual(meta['receipt']['commodity_unit'], 'kg')
        self.assertEqual(meta['billTerms'], self.spec.bill_terms)
        self.assertEqual(meta['time']['tradeComparison'], 'LT')
        self.assertEqual(meta['time']['registrationComparison'], 'LTE')
        self.assertEqual(meta['scope'], 'bill-of-lading-transfer-only')
        self.assertEqual(result['mint'], 'NOT_RUN')
        self.assertEqual(result['assetValidity'], 'NOT_ATTESTED')
        self.assertFalse(meta['legalOrInstitutionalEndorsementClaimed'])

    def test_applicable_template_is_not_a_universal_commodity_rule(self):
        other = replace(self.spec.template, template_id='other-template',
            commodity_scope='fixture-metal', applicable_fields=('assay',), required_fields=('assay',))
        valid = replace(self.spec, template=other, public_attributes=(('assay', 'fixture-assay'),))
        self.book.admit(valid)
        with self.assertRaises(MintSpecificationRefused):
            replace(self.spec, template=other)
        with self.assertRaises(MintSpecificationRefused):
            replace(self.spec, public_attributes=())

    def test_missing_or_unlisted_fields_are_refused(self):
        for changes in ({'issuer': ''}, {'bill_terms': ' '}, {'storage_location': ''},
                        {'public_attributes': (('unlisted', 'value'),)},
                        {'public_attributes': (('grade', 'a'), ('grade', 'b'))}):
            with self.subTest(changes=changes), self.assertRaises(MintSpecificationRefused):
                replace(self.spec, **changes)

    def test_same_declaration_is_idempotent_but_deadline_change_is_not(self):
        first = self.book.admit(self.spec)
        self.assertEqual(self.book.admit(self.spec), first)
        with self.assertRaises(MintSpecificationRefused):
            self.book.admit(replace(self.spec, registration_deadline=179))

    def test_duplicate_underlying_document_cannot_mint_another_nft(self):
        self.book.admit(self.spec)
        other_receipt = replace(self.spec.receipt, receipt_id='receipt-2',
            asset=replace(self.spec.receipt.asset, token_id=8))
        with self.assertRaises(MintSpecificationRefused):
            self.book.admit(replace(self.spec, receipt=other_receipt))

    def test_trade_and_registration_equality_are_explicit(self):
        self.assertTrue(self.spec.trade_eligible_at(199))
        self.assertFalse(self.spec.trade_eligible_at(200))
        self.assertTrue(self.spec.registration_time_eligible(180))
        self.assertFalse(self.spec.registration_time_eligible(181))
        strict = replace(self.spec, registration_comparison='LT')
        self.assertFalse(strict.registration_time_eligible(180))
        longer = replace(self.spec, registration_deadline=300)
        self.assertTrue(longer.registration_time_eligible(200))
        self.assertFalse(longer.registration_time_eligible(201))
        self.assertFalse(longer.registration_time_eligible(9))

    def test_no_float_bool_or_implicit_time_policy(self):
        for changes in ({'registration_deadline': True}, {'registration_deadline': 180.5},
                        {'registration_deadline': 10}, {'registration_comparison': 'implicit'}):
            with self.subTest(changes=changes), self.assertRaises(MintSpecificationRefused):
                replace(self.spec, **changes)

    def test_three_paths_share_the_declared_voucher_contract(self):
        for path in ('REG_DIRECT', 'REG_ELECTRONIC', 'REG_INTERMEDIARY'):
            spec = specification(path)
            result = MintDeclarationBook(lambda k, e: True).admit(spec)
            self.assertEqual(result['canonicalDeclaration']['voucherFormat']['path'], path)
            self.assertEqual(result['canonicalDeclaration']['registrationAuthority'],
                             'existing Oracle record only')
        with self.assertRaises(MintSpecificationRefused):
            replace(self.spec, voucher_format=replace(self.spec.voucher_format, path='REG_ELECTRONIC'))

    def test_mapping_is_opaque_and_external_storage_evidence_is_required(self):
        with self.assertRaises(MintSpecificationRefused):
            replace(self.spec, controlled_access_mapping='https://secret-store/?token=fixture')
        seen = []
        def verifier(kind, evidence):
            seen.append(kind)
            return kind != 'controlled-encrypted-access-mapping'
        with self.assertRaises(MintSpecificationRefused):
            MintDeclarationBook(verifier).admit(self.spec)
        self.assertIn('controlled-encrypted-access-mapping', seen)
        self.assertNotIn('privateKey', json.dumps(self.spec.metadata(lambda k, e: True)))

    def test_privacy_scan_and_mutating_verifier_fail_without_echoing_input(self):
        private_fixture = replace(self.spec, bill_terms='fixture-secret-marker')
        def scan(kind, evidence):
            return kind != 'non-secret-metadata-scan' or 'fixture-secret-marker' not in json.dumps(evidence)
        with self.assertRaises(MintSpecificationRefused) as caught:
            MintDeclarationBook(scan).admit(private_fixture)
        self.assertNotIn('fixture-secret-marker', str(caught.exception))
        def mutate(kind, evidence):
            if kind == 'existing-asset-template-schema':
                evidence['issuer'] = 'altered'
            return True
        with self.assertRaises(MintSpecificationRefused):
            self.spec.metadata(mutate)
