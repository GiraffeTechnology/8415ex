"""New production-host logic against synthetic unit data, never live acceptance.

Tests use actual Exchange/checkpoint/attempt implementations in isolated temporary
databases. Authority callbacks below are test doubles, never production defaults.
"""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from exchange.aggregate_checkpoint import AggregateCheckpointStore
from exchange.exchange_fact_snapshot import encode_exchange_snapshot
from exchange.ledger import Exchange
from exchange.model import AuthorizationReference
from exchange.linked_operation_controller import OriginalLinkedCaller
from exchange.original_task_journal_reader import OriginalTaskJournalReader
from exchange.original_task_journal_wire import OriginalTaskJournalWire
from exchange.production_host import (AggregateBinding, OriginalRuntimeFactory,
    RuntimeCapabilities, NativeAuthorityPorts, ScopedCaller,
    ProductionHostRefused, ProductionHostUnbound, validate_production_configuration,
    parse_production_configuration, compose_production_service)
from exchange.wallet_execution_attempts import WalletExecutionAttempts
from integration.test_mint_specification_codec import specification

A = '0x' + 'a' * 40


class ProductionHostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.db = sqlite3.connect(self.directory / 'aggregate.sqlite')
        self.addCleanup(self.db.close)
        self.db.execute('PRAGMA synchronous=FULL')
        AggregateCheckpointStore.initialize(self.db)
        self.store = AggregateCheckpointStore(self.db,
            components=('deferred-settlement', 'owned-facts'), source_commit='a'*40, source_tree='b'*40)
        self.verifier = lambda kind, evidence: True  # synthetic unit authority
        original = Exchange(lambda: 20, mint_verifier=self.verifier)
        spec = specification(); original.mint(spec.receipt, spec)
        original.connect_wallet(A, 'stored-old-session')
        self.receipt = spec.receipt.receipt_id
        self.components = {'owned-facts': encode_exchange_snapshot(original), 'deferred-settlement': b'{}'}
        self.store.save('unit-case', self.components, expected_generation=0)
        self.row = self.store.read('unit-case')
        self.pin = AggregateBinding('unit-case', self.store.components, 'a'*40, 'b'*40)
        self.contexts = []
        def current_sessions(context):
            self.contexts.append(context); return {}
        self.capabilities = RuntimeCapabilities(clock=lambda:20, payment_adapter=object(),
            asset_control=object(), registrars=object(), voucher_desk=object(), eth_gas_gate=object(),
            price_balance_gate=object(), priority_store=object(), release_sources=('original-release',),
            rollback_sources=('original-rollback',), funding_required=True,
            read_current_sessions=current_sessions, read_current_authorizations=lambda context:(),
            read_current_gas_budgets=lambda context:{A:1000})
        def forbidden(*args, **kwargs):
            raise AssertionError('No authority effect or network request during construction')
        self.forbidden = forbidden
        self.authority = NativeAuthorityPorts(*(forbidden for _ in range(6)))
        self.attempt_path = str(self.directory / 'attempts.sqlite')
        self.config = {'schema':'8415ex-production-host/1','source':{'commit':'c'*40,'tree':'d'*40},
            'aggregate':{'scope':'unit-case','components':list(self.store.components),
                'sourceCommit':'a'*40,'sourceTree':'b'*40,'generation':1,'digest':self.row['digest']},
            'receiptId':self.receipt,
            'wallet':{'origin':'https://wallet.example.invalid','tenant':'unit-tenant','account':A,
                'basePath':'/unit-tenant','attemptPath':self.attempt_path},
            'journal':{'endpoint':'https://artfi.example.invalid/internal/v1/nft/operations','peerId':'original-unit-peer'},
            'oracle':{'origin':'https://oracle.example.invalid','source':{'chainId':'11155111',
                'projectionContract':'0x'+'1'*40,'settlementContract':'0x'+'2'*40,
                'registerId':'0x'+'3'*64,'verificationProfile':'0x'+'4'*64,
                'verifier':'0x'+'5'*40,'attestor':'0x'+'6'*40,
                'codeHashes':{'projection':'0x'+'7'*64,'settlement':'0x'+'8'*64,'verifier':'0x'+'9'*64}},
                'finalityPolicy':'rpc-finalized-tag'},
            'executionMode':'observe-only','service':{'port':18881}}

    def compose(self, **overrides):
        arguments = dict(store=self.store, runtime_capabilities=self.capabilities,
            native_authority=self.authority, deferred_profile=SimpleNamespace(checkpoint_scope='unit-case'),
            deferred_verifier=SimpleNamespace(verify=self.forbidden), original_mint_verifier=self.verifier,
            authenticate_caller=self.forbidden, journal_transport=self.forbidden,
            with_journal_capability=self.forbidden, gas_page=object(), registration_sources=())
        arguments.update(overrides)
        return compose_production_service(self.config, **arguments)

    def test_fresh_runtime_uses_current_ports_not_snapshot_sessions_or_history(self):
        before = deepcopy(self.row)
        current = replace(self.capabilities, read_current_sessions=lambda context:{A:'current-live-session'})
        factory = OriginalRuntimeFactory(self.store, self.pin, current)
        runtime = factory(self.row, mint_verifier=self.verifier)
        self.assertIs(type(runtime), Exchange)
        self.assertIs(runtime._mint_book.verify, self.verifier)
        self.assertIs(runtime.payments, current.payment_adapter)
        self.assertIs(runtime.registrars, current.registrars)
        self.assertEqual(runtime._sessions, {A:'current-live-session'})
        self.assertEqual(runtime._receipts, {})
        self.assertEqual(runtime._authorizations, {})
        self.assertIsNot(runtime, factory(self.row, mint_verifier=self.verifier))
        self.assertEqual(self.store.read('unit-case'), before)

    def test_saved_session_is_not_reconnected_when_live_reader_is_empty(self):
        runtime = OriginalRuntimeFactory(self.store,self.pin,self.capabilities)(self.row,mint_verifier=self.verifier)
        self.assertEqual(runtime._sessions,{})
        self.assertEqual(self.contexts[0].digest,self.row['digest'])
        self.assertEqual(self.contexts[0].source_tree,'b'*40)
        self.assertFalse(hasattr(self.contexts[0],'components'))

    def test_stale_row_is_refused_before_authority_reads(self):
        self.store.save('unit-case',self.components,expected_generation=1)
        with self.assertRaises(ProductionHostRefused):
            OriginalRuntimeFactory(self.store,self.pin,self.capabilities)(self.row,mint_verifier=self.verifier)
        self.assertEqual(self.contexts,[])

    def test_concurrent_generation_change_during_authority_read_is_preserved_and_refused(self):
        def budgets(context):
            self.store.save('unit-case',self.components,expected_generation=1)
            return {A:1000}
        caps=replace(self.capabilities,read_current_gas_budgets=budgets)
        with self.assertRaises(ProductionHostRefused):
            OriginalRuntimeFactory(self.store,self.pin,caps)(self.row,mint_verifier=self.verifier)
        self.assertEqual(self.store.read('unit-case')['generation'],2)

    def test_wrong_source_scope_components_or_digest_cannot_invoke_current_readers(self):
        variants=[replace(self.pin,source_tree='e'*40),replace(self.pin,scope='foreign-case')]
        for pin in variants:
            with self.subTest(pin=pin),self.assertRaises(ProductionHostRefused):
                OriginalRuntimeFactory(self.store,pin,self.capabilities)(self.row,mint_verifier=self.verifier)
        altered=deepcopy(self.row);altered['digest']='f'*64
        with self.assertRaises(ProductionHostRefused):
            OriginalRuntimeFactory(self.store,self.pin,self.capabilities)(altered,mint_verifier=self.verifier)
        self.assertEqual(self.contexts,[])

    def test_missing_real_runtime_capabilities_are_unbound(self):
        with self.assertRaises(ProductionHostUnbound) as caught:
            OriginalRuntimeFactory(self.store,self.pin,replace(self.capabilities,payment_adapter=None))
        self.assertIn('payment_adapter',caught.exception.names)

    def test_malformed_current_sessions_and_missing_mint_verifier_refuse(self):
        factory=OriginalRuntimeFactory(self.store,self.pin,replace(self.capabilities,read_current_sessions=lambda c:[]))
        with self.assertRaises(ProductionHostRefused):factory(self.row,mint_verifier=self.verifier)
        with self.assertRaises(ProductionHostRefused):
            OriginalRuntimeFactory(self.store,self.pin,self.capabilities)(self.row,mint_verifier=None)

    def test_configuration_is_exact_copied_and_does_not_contact_network(self):
        with patch('socket.create_connection',side_effect=AssertionError('no network')):
            c=validate_production_configuration(self.config)
        c['aggregate']['components'].append('changed')
        self.assertEqual(self.config['aggregate']['components'],list(self.store.components))
        self.assertFalse(Path(self.attempt_path).exists())

    def test_configuration_rejects_callback_injection_false_generation_and_wrong_chain(self):
        variants=[]
        c=deepcopy(self.config);c['provider']='arbitrary.module';variants.append(c)
        c=deepcopy(self.config);c['aggregate']['generation']=True;variants.append(c)
        c=deepcopy(self.config);c['oracle']['finalityPolicy']='optimistic';variants.append(c)
        c=deepcopy(self.config);c['oracle']['source']['chainId']='560048';variants.append(c)
        c=deepcopy(self.config);c['aggregate']['generation']=2**63;variants.append(c)
        c=deepcopy(self.config);c['wallet']['basePath']='/foreign';variants.append(c)
        c=deepcopy(self.config);c['wallet']['attemptPath']='file:other?mode=rwc';variants.append(c)
        for c in variants:
            with self.subTest(config=c),self.assertRaises(ProductionHostRefused):validate_production_configuration(c)
        raw=json.dumps(self.config).encode()
        self.assertEqual(parse_production_configuration(raw)['receiptId'],self.receipt)
        with self.assertRaises(ProductionHostRefused):
            parse_production_configuration(b'{"schema":1,"schema":2}')

    def test_missing_native_or_caller_capability_does_not_create_attempt_store(self):
        with self.assertRaises(ProductionHostUnbound):
            self.compose(native_authority=replace(self.authority,verify_prepared_cancel=None))
        with self.assertRaises(ProductionHostUnbound):self.compose(authenticate_caller=None)
        self.assertFalse(Path(self.attempt_path).exists())

    def test_missing_existing_attempt_database_never_creates_file_or_schema(self):
        with self.assertRaises(ValueError):self.compose()
        self.assertFalse(Path(self.attempt_path).exists())
        self.assertEqual(self.store.read('unit-case'),self.row)

    def test_host_rejects_stale_startup_and_foreign_receipt_before_attempt_open(self):
        self.config['aggregate']['generation']=2
        with self.assertRaises(ProductionHostRefused):self.compose()
        self.config['aggregate']['generation']=1;self.config['receiptId']='foreign-receipt'
        with self.assertRaises(ProductionHostRefused):self.compose()
        self.assertFalse(Path(self.attempt_path).exists())

    def test_host_composition_uses_existing_attempt_and_real_get_only_bridge_without_effects(self):
        WalletExecutionAttempts(self.attempt_path)  # explicit isolated UNIT setup
        before=hashlib.sha256(Path(self.attempt_path).read_bytes()).hexdigest()
        sentinel=object()
        def assemble(**k):
            self.assertIsInstance(k['original_journal'],OriginalTaskJournalReader)
            wire=k['original_journal'].original_journal
            self.assertIs(type(wire),OriginalTaskJournalWire)
            self.assertIs(wire.transport,self.forbidden)
            self.assertIs(wire.with_capability,self.forbidden)
            self.assertTrue(hasattr(k['settlement'].execution_attempts,'_original_file'))
            runtime=k['create_original_runtime'](self.row,mint_verifier=self.verifier)
            self.assertIs(runtime._mint_book.verify,self.verifier)
            self.assertIs(k['ports'].read_admission,self.authority.read_admission)
            self.assertIsNone(k['ports'].read_registration)  # installed by original Oracle composition
            return sentinel
        with patch('exchange.production_host.compose_cross_product_service',side_effect=assemble),\
             patch('exchange.production_host.validate_binding') as final_check,\
             patch('socket.create_connection',side_effect=AssertionError('no network')):
            self.assertIs(self.compose(),sentinel)
            final_check.assert_called_once_with(sentinel,commit='c'*40,tree='d'*40)
        self.assertEqual(hashlib.sha256(Path(self.attempt_path).read_bytes()).hexdigest(),before)
        self.assertEqual(self.store.read('unit-case'),self.row)

    def test_caller_is_reauthenticated_each_request_and_never_replaced_by_service_login(self):
        requests=[]
        expected=OriginalLinkedCaller('unit-case',self.receipt,'unit-tenant',A,frozenset({'observe'}))
        caller=ScopedCaller(lambda request:(requests.append(request) or expected),scope='unit-case',
            receipt_id=self.receipt,tenant='unit-tenant',account=A)
        first,second=object(),object();self.assertIs(caller(first),expected);self.assertIs(caller(second),expected)
        self.assertEqual(requests,[first,second])
        for bad in [None,replace(expected,account='0x'+'b'*40),replace(expected,scope='foreign'),
                    replace(expected,allowed_actions=frozenset({'invented-authority'})),
                    replace(expected,allowed_actions=['observe'])]:
            wrapped=ScopedCaller(lambda request:bad,scope='unit-case',receipt_id=self.receipt,tenant='unit-tenant',account=A)
            with self.subTest(caller=bad),self.assertRaises(ProductionHostRefused):wrapped(first)

    def test_authenticator_failure_is_sanitized_and_has_no_service_login_fallback(self):
        def fails(request):raise RuntimeError('synthetic-private-auth-detail')
        caller=ScopedCaller(fails,scope='unit-case',receipt_id=self.receipt,tenant='unit-tenant',account=A)
        with self.assertRaises(ProductionHostRefused) as caught:caller(object())
        self.assertNotIn('synthetic-private-auth-detail',str(caught.exception))
        self.assertEqual(self.store.read('unit-case'),self.row)

    def test_current_authority_failure_is_sanitized_without_state_change(self):
        def fails(context):raise RuntimeError('synthetic-private-source-detail')
        caps=replace(self.capabilities,read_current_sessions=fails)
        with self.assertRaises(ProductionHostRefused) as caught:
            OriginalRuntimeFactory(self.store,self.pin,caps)(self.row,mint_verifier=self.verifier)
        self.assertNotIn('synthetic-private-source-detail',str(caught.exception))
        self.assertEqual(self.store.read('unit-case'),self.row)

    def checkpoint_authorization(self, *, revoked=False):
        spec=specification()
        auth=AuthorizationReference('unit-auth',A,spec.receipt.asset.chain_id,spec.receipt.asset,
            ('trade',),(),1000,'unit-currency',0,100,'stored-old-session',revoked)
        original=Exchange(lambda:20,mint_verifier=self.verifier)
        original.mint(spec.receipt,spec);original.register_authorization(auth)
        original.connect_wallet(A,'stored-old-session')
        self.components={**self.components,'owned-facts':encode_exchange_snapshot(original)}
        self.store.save('unit-case',self.components,expected_generation=1)
        self.row=self.store.read('unit-case')
        return auth

    def test_omitted_saved_grant_is_unknown_not_silently_valid(self):
        self.checkpoint_authorization()
        caps=replace(self.capabilities,read_current_sessions=lambda c:{A:'stored-old-session'})
        with self.assertRaisesRegex(ProductionHostRefused,'CURRENT_AUTHORIZATION_COVERAGE_REFUSED'):
            OriginalRuntimeFactory(self.store,self.pin,caps)(self.row,mint_verifier=self.verifier)
        self.assertEqual(self.store.read('unit-case'),self.row)

    def test_current_revocation_is_applied_and_context_identifies_required_grants(self):
        auth=self.checkpoint_authorization();contexts=[]
        def read(context):contexts.append(context);return (auth.revoke(),)
        caps=replace(self.capabilities,read_current_authorizations=read)
        runtime=OriginalRuntimeFactory(self.store,self.pin,caps)(self.row,mint_verifier=self.verifier)
        self.assertTrue(runtime.authorization('unit-auth').revoked)
        self.assertEqual(contexts[0].authorization_ids,('unit-auth',))
        self.assertEqual(self.store.read('unit-case'),self.row)

    def test_recorded_revocation_cannot_be_undone_by_current_reader(self):
        auth=self.checkpoint_authorization(revoked=True)
        caps=replace(self.capabilities,read_current_authorizations=lambda c:(replace(auth,revoked=False),))
        with self.assertRaisesRegex(ProductionHostRefused,'AUTHORIZATION_REVOCATION_REFUSED'):
            OriginalRuntimeFactory(self.store,self.pin,caps)(self.row,mint_verifier=self.verifier)

    def test_same_grant_id_cannot_rewrite_signed_constraints(self):
        auth=self.checkpoint_authorization()
        caps=replace(self.capabilities,read_current_authorizations=lambda c:(replace(auth,max_amount=1001),))
        with self.assertRaisesRegex(ProductionHostRefused,'AUTHORIZATION_CONSTRAINTS_REFUSED'):
            OriginalRuntimeFactory(self.store,self.pin,caps)(self.row,mint_verifier=self.verifier)


if __name__=='__main__':unittest.main()
