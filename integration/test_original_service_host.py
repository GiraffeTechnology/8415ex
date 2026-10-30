"""Host-entry boundary regressions; synthetic ports are test data only."""
from dataclasses import replace
import inspect
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from exchange.original_service_host import (
    OriginalHostInputs, OriginalHostInputsUnavailable,
    compose_original_host_inputs, create_original_service_binding,
    original_host_requirements,
)
from exchange.production_host import ProductionHostUnbound
from exchange.service_runtime import ServiceRefused
from integration import test_production_host as synthetic_fixture


class OriginalServiceHostTests(unittest.TestCase):
    def setUp(self):
        self.fixture = synthetic_fixture.ProductionHostTests('test_configuration_is_exact_copied_and_does_not_contact_network')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        self.inputs = OriginalHostInputs(
            configuration=f.config, store=f.store,
            runtime_capabilities=f.capabilities, native_authority=f.authority,
            deferred_profile=SimpleNamespace(checkpoint_scope='unit-case'),
            deferred_verifier=SimpleNamespace(verify=f.forbidden),
            original_mint_verifier=f.verifier, authenticate_caller=f.forbidden,
            journal_transport=f.forbidden, with_journal_capability=f.forbidden,
            gas_page=object(), registration_sources=(),
        )

    def provider(self, loader=None):
        module = ModuleType('exchange.original_provider_bindings')
        module.load_original_host_inputs = loader or (lambda: self.inputs)
        return patch.dict(sys.modules, {'exchange.original_provider_bindings': module})

    def test_zero_argument_export_passes_real_ports_and_configuration_unchanged(self):
        self.assertEqual(len(inspect.signature(create_original_service_binding).parameters), 0)
        with self.provider(), patch('exchange.original_service_host.compose_production_service') as compose:
            result = create_original_service_binding()
        self.assertIs(result, compose.return_value)
        args, kwargs = compose.call_args
        self.assertIs(args[0], self.inputs.configuration)
        for name in ('store', 'runtime_capabilities', 'native_authority', 'original_mint_verifier',
                     'authenticate_caller', 'journal_transport', 'with_journal_capability'):
            self.assertIs(kwargs[name], getattr(self.inputs, name))

    def test_missing_provider_never_creates_store_or_runs_composition(self):
        with patch('exchange.original_service_host.import_module', side_effect=ModuleNotFoundError), \
             patch('exchange.original_service_host.compose_production_service') as compose:
            with self.assertRaises(OriginalHostInputsUnavailable) as caught:
                create_original_service_binding()
        self.assertEqual(caught.exception.names, ('original_provider_bindings',))
        compose.assert_not_called()
        self.assertFalse(self.fixture.directory.joinpath('attempts.sqlite').exists())

    def test_missing_inputs_are_exact_names_and_cannot_be_defaulted(self):
        with self.provider(lambda: replace(self.inputs, authenticate_caller=None, journal_transport=None)):
            with self.assertRaises(OriginalHostInputsUnavailable) as caught:
                create_original_service_binding()
        self.assertEqual(caught.exception.names, ('authenticate_caller', 'journal_transport'))
        self.assertFalse(self.fixture.directory.joinpath('attempts.sqlite').exists())

    def test_provider_failures_do_not_expose_private_details(self):
        def failure():
            raise RuntimeError('synthetic-secret-value')
        with self.provider(failure), self.assertRaises(OriginalHostInputsUnavailable) as caught:
            create_original_service_binding()
        self.assertNotIn('synthetic-secret-value', str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)

    def test_dictionary_or_module_getattr_cannot_supply_implicit_inputs(self):
        with self.provider(lambda: vars(self.inputs)), self.assertRaises(ServiceRefused):
            create_original_service_binding()
        module = ModuleType('exchange.original_provider_bindings')
        module.__getattr__ = lambda name: self.fail('Implicit module attribute evaluation')
        with patch.dict(sys.modules, {'exchange.original_provider_bindings': module}):
            with self.assertRaises(OriginalHostInputsUnavailable):
                create_original_service_binding()

    def test_existing_only_attempt_guard_remains_effective_through_entry(self):
        with self.provider(), self.assertRaisesRegex(ServiceRefused, 'EX_SERVICE_HOST_COMPOSITION_REFUSED'):
            create_original_service_binding()
        self.assertFalse(self.fixture.directory.joinpath('attempts.sqlite').exists())
        self.assertEqual(self.fixture.store.read('unit-case'), self.fixture.row)

    def test_stale_checkpoint_and_foreign_receipt_are_refused_without_attempt_creation(self):
        for key, value in [('generation', 2), ('receiptId', 'foreign-receipt')]:
            from copy import deepcopy
            c = deepcopy(self.inputs.configuration)
            if key == 'generation': c['aggregate'][key] = value
            else: c[key] = value
            with self.provider(lambda: replace(self.inputs, configuration=c)):
                with self.assertRaises(ServiceRefused): create_original_service_binding()
        self.assertFalse(self.fixture.directory.joinpath('attempts.sqlite').exists())

    def test_safe_missing_capability_diagnostics_keep_no_private_provider_names(self):
        with patch('exchange.original_service_host.compose_production_service',
                   side_effect=ProductionHostUnbound(['read_current_sessions', 'synthetic-secret-value'])):
            with self.assertRaises(OriginalHostInputsUnavailable) as caught:
                compose_original_host_inputs(self.inputs)
        self.assertEqual(caught.exception.names, ('read_current_sessions',))

    def test_configuration_cannot_inject_an_arbitrary_provider_module(self):
        from copy import deepcopy
        c = deepcopy(self.inputs.configuration); c['providerModule'] = 'synthetic.arbitrary'
        with self.provider(lambda: replace(self.inputs, configuration=c)):
            with self.assertRaises(ServiceRefused): create_original_service_binding()

    def test_requirements_are_static_and_do_not_load_providers_or_credentials(self):
        with patch('exchange.original_service_host.import_module', side_effect=AssertionError('no provider read')):
            r = original_host_requirements()
        self.assertIn('read_current_sessions', r['currentRuntimeInputs'])
        self.assertIn('verify_prepared_cancel', r['nativeAuthorityInputs'])
        self.assertEqual(r['providerModule'], 'exchange.original_provider_bindings')

    def test_pinned_loader_finds_export_and_reports_real_missing_provider(self):
        import hashlib
        import json
        from exchange.service_runtime import load_host
        host = self.fixture.directory / 'host.py'
        raw = b'from exchange.original_service_host import create_original_service_binding\n'
        host.write_bytes(raw)
        config = self.fixture.directory / 'host.json'
        config.write_text(json.dumps({'schema': '8415ex-host/1', 'hostPath': str(host),
            'hostSha256': hashlib.sha256(raw).hexdigest(), 'commit': 'c'*40, 'tree': 'd'*40}))
        with patch('exchange.service_install.verify_installation') as installation, \
             patch('exchange.original_service_host.import_module', side_effect=ModuleNotFoundError):
            with self.assertRaisesRegex(ServiceRefused, 'EX_SERVICE_HOST_INPUTS_UNAVAILABLE'):
                load_host(config)
        installation.assert_called_once()


if __name__ == '__main__': unittest.main()
