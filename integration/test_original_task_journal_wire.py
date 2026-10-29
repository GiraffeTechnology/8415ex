"""Local wire/gate contract tests; no live mTLS or grant authority exercised."""
from copy import deepcopy
import hashlib
import json
import unittest
from exchange.original_task_journal_wire import (OriginalTaskJournalWire,
    JournalHTTPResponse, canonical_bytes, PATH)
from exchange.original_task_journal_reader import (OriginalTaskJournalReader,
    OriginalJournalRefused, OriginalJournalUnavailable)
from integration.test_original_task_journal_reader import PRINCIPAL, OPERATION, WALLET, native_operation


class JournalWireTests(unittest.TestCase):
    def setUp(self):
        self.endpoint = 'https://journal.example' + PATH
        self.held = False
        self.scopes, self.requests = [], []
        self.response = JournalHTTPResponse(200, json.dumps(native_operation()).encode(), self.endpoint)
        self.times = iter([10.0, 10.1])
        def gate(scope, use):
            self.scopes.append(deepcopy(scope))
            self.held = True
            try:
                return use('x' * 32)
            finally:
                self.held = False
        self.gate = gate
    def transport(self, endpoint, **options):
        self.assertTrue(self.held)
        self.requests.append((endpoint, options))
        return self.response
    def adapter(self, **changes):
        config = dict(endpoint=self.endpoint, peer_id='spiffe://artfi/ex',
            transport=self.transport, with_capability=self.gate, clock=lambda: next(self.times))
        config.update(changes)
        return OriginalTaskJournalWire(**config)
    def call(self, adapter=None):
        return (adapter or self.adapter())(PRINCIPAL, 'get', {'id': OPERATION})
    def test_canonical_go_js_bytes(self):
        self.assertEqual(canonical_bytes({'z': '\u2028<>&\u2029é😀', 'a': [True, None, -1]}),
            b'{"a":[true,null,-1],"z":"\\u2028\\u003c\\u003e\\u0026\\u2029\xc3\xa9\xf0\x9f\x98\x80"}')
        self.assertEqual(hashlib.sha256(canonical_bytes({'z': '\u2028<>&\u2029é😀', 'a': [True, None, -1]})).hexdigest(),
            '80bb313db7f0060f54266a57f2e62e9a50b2f0f1c8c7ad1d4dd07fbb1312aaec')
        for bad in ({'é': 1}, {'x': 1.0}, {'x': 9007199254740992}, {'x': '\ud800'}):
            with self.assertRaises(OriginalJournalRefused): canonical_bytes(bad)
    def test_real_wire_scope_and_reader_composition(self):
        result = OriginalTaskJournalReader(self.adapter()).read(PRINCIPAL, OPERATION, 11155111, WALLET)
        self.assertFalse(result['canExecute'])
        endpoint, request = self.requests[0]
        expected_body = ('{"action":"get","operation":{"id":"' + OPERATION + '"}}').encode()
        self.assertEqual(request['body'], expected_body)
        canonical = ('{"action":"get","operation":{"id":"' + OPERATION + '"}}').encode()
        self.assertEqual(self.scopes, [dict(principal=PRINCIPAL, action='get', operation={'id': OPERATION},
            peerId='spiffe://artfi/ex', nativeOperationId=OPERATION, planDigest='',
            requestDigest=hashlib.sha256(canonical).hexdigest())])
        self.assertEqual((request['method'],request['timeout'],request['max_bytes'],request['redirect']), ('POST',8.0,65536,'error'))
        self.assertEqual(request['headers']['authorization'], 'Bearer ' + 'x'*32)
        self.assertFalse(self.held)
    def test_mutated_scope_cannot_change_request_or_principal(self):
        def gate(scope, use):
            scope['principal']['taskId'] = 'different'
            scope['operation']['id'] = 'different'
            self.held = True
            return use('a'*32)
        self.assertEqual(self.call(self.adapter(with_capability=gate))['id'], OPERATION)
    def test_unbound_or_redirecting_configuration(self):
        for endpoint in ('http://journal.example'+PATH, self.endpoint+'?x=1',self.endpoint+'#x',
                         'https://a:b@journal.example'+PATH,'https://journal.example/other'):
            with self.assertRaises(OriginalJournalUnavailable): self.adapter(endpoint=endpoint)
        with self.assertRaises(OriginalJournalUnavailable): self.adapter(transport=None)
    def test_get_only_refuses_before_gate(self):
        for action, operation in [('create',{'id':OPERATION}),('get',{'id':OPERATION,'plan':{}}),('get',{'id':'bad'})]:
            with self.assertRaises(OriginalJournalRefused): self.adapter()(PRINCIPAL,action,operation)
        self.assertEqual(self.scopes, [])
    def test_gate_cannot_skip_substitute_or_reuse_callback(self):
        with self.assertRaises(OriginalJournalUnavailable): self.call(self.adapter(with_capability=lambda s,u:native_operation()))
        saved=[]
        def gate(scope,use):
            saved.append(use)
            self.held=True
            result=use('x'*32)
            result['revision']=2
            return result
        with self.assertRaises(OriginalJournalUnavailable): self.call(self.adapter(with_capability=gate))
        with self.assertRaises(OriginalJournalRefused): saved[0]('x'*32)
    def test_double_use_refused_no_second_transport(self):
        def gate(scope,use):
            self.held=True
            use('x'*32)
            return use('x'*32)
        with self.assertRaises(OriginalJournalUnavailable): self.call(self.adapter(with_capability=gate))
        self.assertEqual(len(self.requests),1)
    def test_invalid_capability_never_reaches_transport(self):
        for token in ('short','x'*31+' ',None,'x'*2049):
            with self.assertRaises(OriginalJournalUnavailable): self.call(self.adapter(with_capability=lambda s,u:u(token)))
        self.assertEqual(self.requests,[])
    def test_timeout_redirect_size_status_and_encoding_refused(self):
        cases=[JournalHTTPResponse(302,b'{}',self.endpoint), JournalHTTPResponse(200,b'{}','https://elsewhere'+PATH),
            JournalHTTPResponse(200,b'x'*65537,self.endpoint),JournalHTTPResponse(200,b'\xff',self.endpoint),
            JournalHTTPResponse(200,b'{"id":1,"id":2}',self.endpoint), JournalHTTPResponse(200,b'{"id":NaN}',self.endpoint)]
        for response in cases:
            self.times=iter([10,10.1]); self.response=response
            with self.assertRaises((OriginalJournalUnavailable,OriginalJournalRefused)): self.call()
        self.response=JournalHTTPResponse(200,json.dumps(native_operation()).encode(),self.endpoint)
        self.times=iter([10,18])
        with self.assertRaises(OriginalJournalUnavailable): self.call()
    def test_original_exception_not_echoed_or_retried(self):
        calls=[]
        def transport(*args,**kwargs):
            calls.append(1)
            raise RuntimeError('private-secret')
        with self.assertRaises(OriginalJournalUnavailable) as raised: self.call(self.adapter(transport=transport))
        self.assertNotIn('private-secret',str(raised.exception)); self.assertEqual(calls,[1])
    def test_typed_host_exception_is_also_redacted(self):
        for error in (OriginalJournalUnavailable, OriginalJournalRefused):
            def transport(*args, **kwargs):
                raise error('private-secret')
            with self.assertRaises(OriginalJournalUnavailable) as raised:
                self.call(self.adapter(transport=transport))
            self.assertNotIn('private-secret', str(raised.exception))
            def gate(*args):
                raise error('private-secret')
            with self.assertRaises(OriginalJournalUnavailable) as raised:
                self.call(self.adapter(with_capability=gate))
            self.assertNotIn('private-secret', str(raised.exception))
    def test_foreign_or_secret_response_refused_inside_gate(self):
        for mutate in (lambda r:r['plan']['taskPrincipal'].update(taskId='other'),lambda r:r.update(secret='private')):
            raw=native_operation(); mutate(raw)
            self.response=JournalHTTPResponse(200,json.dumps(raw).encode(),self.endpoint); self.times=iter([10,10.1])
            with self.assertRaises(OriginalJournalUnavailable): self.call()
            self.assertFalse(self.held)
