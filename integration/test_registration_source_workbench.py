"""Authored three-source read/UI fixtures; no installed service or Oracle call."""
import unittest
from dataclasses import replace
from exchange.model import Asset, WarehouseReceipt
from exchange.original_task_journal_reader import OriginalTaskJournalReader
from exchange.registration_source_workbench import (RegistrationSourceWorkbench,
    SourceTaskBinding, RegistrationSourceRefused, SOURCES)
from integration.test_original_task_journal_reader import PRINCIPAL, OPERATION, WALLET, native_operation


class RegistrationSourceWorkbenchContracts(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.resolutions = []
        def original(principal, action, operation):
            self.calls.append((action, operation))
            return native_operation()
        self.reader = OriginalTaskJournalReader(original)
        def resolve(source, receipt_id):
            self.resolutions.append((source, receipt_id))
            receipt = WarehouseReceipt(receipt_id, Asset(11155111, '0x' + '1' * 40, 7),
                'Fixture goods', 100, 'kg', 'warehouse-1', SOURCES[source][0],
                200, WALLET, 10)
            return SourceTaskBinding(receipt, 'mint-format-1', '1', ('asset', 'segment', 'holder'),
                                     PRINCIPAL, OPERATION, WALLET)
        self.resolve = resolve
        self.workbench = RegistrationSourceWorkbench(self.reader, resolve)

    def test_all_three_sources_share_one_original_get_backend(self):
        for source, role in SOURCES.items():
            result = self.workbench.read_source(source, 'receipt-1')
            self.assertEqual(result['domainPath'], role[0])
            self.assertTrue(result['simulatedRole'])
            self.assertFalse(result['canExecute'])
            self.assertEqual(result['oracleRecord'], 'UNBOUND')
            self.assertEqual(result['principalFunds'], 'NOT_VERIFIED')
        self.assertIs(self.workbench.reader, self.reader)
        self.assertEqual(self.calls, [('get', {'id': OPERATION})] * 3)

    def test_source_must_match_the_existing_mint_path(self):
        binding = self.resolve('REG-DIRECT', 'receipt-1')
        self.workbench.resolve_binding = lambda source, receipt: binding
        with self.assertRaises(RegistrationSourceRefused):
            self.workbench.read_source('REG-INTERMEDIARY', 'receipt-1')
        self.assertEqual(self.calls, [])

    def test_unknown_source_or_bad_receipt_is_refused_before_resolution(self):
        for source, receipt in (('futures', 'receipt-1'), ('REG_DIRECT', 'receipt-1'),
                                ('REG-DIRECT', 'bad receipt'), ([], 'receipt-1')):
            with self.assertRaises(RegistrationSourceRefused):
                self.workbench.read_source(source, receipt)
        self.assertEqual(self.resolutions, [])
        self.assertEqual(self.calls, [])

    def test_missing_or_duplicate_declared_format_fields_are_refused(self):
        binding = self.resolve('REG-DIRECT', 'receipt-1')
        for changes in ({'voucher_format_id': ''}, {'required_voucher_fields': ()},
                        {'required_voucher_fields': ('asset', 'asset')}):
            self.workbench.resolve_binding = lambda source, receipt: replace(binding, **changes)
            with self.assertRaises(RegistrationSourceRefused):
                self.workbench.read_source('REG-DIRECT', 'receipt-1')
        self.assertEqual(self.calls, [])

    def test_each_source_detail_has_provenance_and_separate_unknown_dimensions(self):
        for source in SOURCES:
            html = self.workbench.render_source(source, 'receipt-1')
            for text in ('Simulated source role', source, 'mint-format-1', OPERATION,
                         'Original task status only', 'pending', 'Oracle chain record',
                         'UNBOUND', 'Principal funds', 'Gas funds', 'NOT_VERIFIED'):
                self.assertIn(text, html)
            self.assertNotIn('registration complete', html.lower())
            self.assertNotIn('payment complete</dd>', html.lower())

    def test_choices_use_explicit_same_origin_read_route(self):
        html = self.workbench.render_choices('receipt-1', '/existing-source-view')
        self.assertIn('method="get"', html)
        for source in SOURCES:
            self.assertIn(source, html)
        for route in ('https://foreign.example/', '//foreign.example/', '/\\foreign'):
            with self.assertRaises(RegistrationSourceRefused):
                self.workbench.render_choices('receipt-1', route)

    def test_source_resolver_failure_does_not_fall_back_or_leak_values(self):
        def unavailable(*args):
            raise RuntimeError('synthetic-sensitive-marker')
        self.workbench.resolve_binding = unavailable
        with self.assertRaises(RegistrationSourceRefused) as caught:
            self.workbench.read_source('REG-DIRECT', 'receipt-1')
        self.assertNotIn('synthetic-sensitive-marker', str(caught.exception))
        self.assertEqual(self.calls, [])
