"""Private synthetic HTTP definitions; command spy is not native execution."""
import http.client
import unittest
from html import escape
from urllib.parse import urlencode

from exchange import fixtures as F
from exchange.queue_status_page import CONTROLS, WORDS
from integration import test_integrated_runtime_inputs as mounted


class QueueLocaleTransportTests(unittest.TestCase):
    def server(self, configured=True):
        fixture = mounted.IntegratedRuntimeInputsTests('runTest')
        self.addCleanup(fixture.doCleanups)
        server = fixture.server()
        server.binding.exchange, _ = F.minted()
        server.binding.receipt_id = 'rcpt-8415-0001'
        server.binding.gateway = object() if configured else None
        self.calls = []
        def command(*args):
            self.calls.append(args)
            return {'enquired': True, 'result': {'status': 'unknown'}}
        server.binding.command = command
        fixture.start(server)
        return server

    def request(self, server, method, path, fields=None, origin=None):
        body = None if fields is None else urlencode(fields).encode('ascii')
        headers = {'Origin': server.origin if origin is None else origin}
        if body is not None:
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        connection = http.client.HTTPConnection(*server.server_address, timeout=3)
        try:
            connection.request(method, path, body, headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode('utf-8')
        finally:
            connection.close()

    def fields(self, server, **changes):
        value = {'csrf': server.csrf, 'revision': '0' * 64, 'action': 'advance-rollback',
                 'key': 'synthetic-queue-operation', 'leg': ''}
        value.update(changes)
        return value

    def test_all_locales_mount_status_controls_and_existing_private_safe_detail(self):
        server = self.server()
        for locale, words in CONTROLS.items():
            with self.subTest(locale=locale):
                status, headers, page = self.request(server, 'GET', '/queue?lang=' + locale)
                suffix = '' if locale == 'en' else '?lang=' + locale
                self.assertEqual(status, 200)
                self.assertEqual(headers['Cache-Control'], 'no-store')
                self.assertIn('<html lang="' + locale + '">', page)
                self.assertIn('<form action="/operation' + suffix + '"', page)
                self.assertIn(escape(words['submit']), page)
                self.assertIn(escape(WORDS[locale]['none']), page)
                self.assertIn('href="/gas' + suffix + '"', page)
                for key in ('funds', 'rollback', 'overdue'):
                    self.assertIn(key, page)
                for party in (F.A, F.B, F.C):
                    self.assertNotIn(party, page)
        self.assertEqual(self.calls, [])

    def test_unconfigured_gateway_stays_disabled_in_every_locale(self):
        server = self.server(configured=False)
        for locale, words in CONTROLS.items():
            status, _, page = self.request(server, 'GET', '/queue?lang=' + locale)
            self.assertEqual(status, 200)
            self.assertIn(escape(words['disabled']), page)
            self.assertNotIn('<form', page)
        self.assertEqual(self.calls, [])

    def test_post_preserves_locale_and_exact_original_command_fields(self):
        server = self.server()
        for locale in CONTROLS:
            status, headers, body = self.request(server, 'POST', '/operation?lang=' + locale,
                                                  self.fields(server))
            self.assertEqual(status, 303)
            self.assertEqual(headers['Location'], '/queue' + ('' if locale == 'en' else '?lang=' + locale))
            self.assertEqual(body, '')
        self.assertEqual(self.calls, [('advance-rollback', 'synthetic-queue-operation',
                                      '0' * 64, {})] * len(CONTROLS))
        self.assertEqual(server.command_observations['synthetic-queue-operation']['result'],
                         {'status': 'unknown'})

    def test_invalid_locale_queries_never_enter_original_command(self):
        server = self.server()
        for query in ('lang=de', 'lang=', 'lang=ja&lang=en', 'lang=ja&success=yes'):
            for method, path in (('GET', '/queue'), ('POST', '/operation')):
                with self.subTest(method=method, query=query):
                    status, _, _ = self.request(server, method, path + '?' + query,
                                                self.fields(server) if method == 'POST' else None)
                    self.assertEqual(status, 400)
        self.assertEqual(self.calls, [])

    def test_origin_csrf_and_exact_body_guards_remain_localized(self):
        server = self.server()
        status, _, body = self.request(server, 'POST', '/operation?lang=ja',
                                       self.fields(server), origin='https://other.invalid')
        self.assertEqual(status, 403)
        self.assertEqual(body, CONTROLS['ja']['originRefused'])
        for changes, expected, key in (({'csrf': 'wrong'}, 403, 'csrfRefused'),
                                       ({'success': 'yes'}, 400, 'inputRefused'),
                                       ({'leg': '1'}, 400, 'inputRefused')):
            status, _, body = self.request(server, 'POST', '/operation?lang=fr',
                                           self.fields(server, **changes))
            self.assertEqual(status, expected)
            self.assertEqual(body, CONTROLS['fr'][key])
        self.assertEqual(self.calls, [])
