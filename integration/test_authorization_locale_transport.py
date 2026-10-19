"""Private route definitions; no actual Wallet session or execution."""
from html import escape
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from exchange import fixtures as F
from exchange.authorization_page import WORDS
from exchange.workbench import RuntimeBinding, WorkbenchServer
from integration import test_integrated_runtime_inputs as mounted
from integration.test_integrated_workbench_http import COMMIT, TREE


class AuthorizationLocaleTransportTests(unittest.TestCase):
    def server(self, integrated=True):
        fixture = mounted.IntegratedRuntimeInputsTests('runTest')
        self.addCleanup(fixture.doCleanups)
        exchange, _ = F.minted()
        exchange.register_authorization(F.authorization(F.A, 'PRIVATE-GRANT', 'session-a'))
        if integrated:
            server = fixture.server()
            server.binding.exchange = exchange
            server.binding.receipt_id = 'rcpt-8415-0001'
            server.binding.authorization_ids = ('PRIVATE-GRANT',)
        else:
            server = WorkbenchServer(RuntimeBinding(exchange, 'rcpt-8415-0001',
                authorization_ids=('PRIVATE-GRANT',)), port=0, commit=COMMIT, tree=TREE)
            self.addCleanup(server.server_close)
        fixture.start(server)
        return server

    def test_standalone_and_integrated_routes_preserve_locale_and_hide_identity(self):
        for integrated in (False, True):
            server = self.server(integrated)
            for locale, words in WORDS.items():
                with self.subTest(integrated=integrated, locale=locale):
                    with urlopen(server.origin + '/authorization?lang=' + locale, timeout=3) as response:
                        page = response.read().decode('utf-8')
                        self.assertEqual(response.headers['Cache-Control'], 'no-store')
                    self.assertIn('<html lang="' + locale + '">', page)
                    self.assertIn(escape(words['heading']), page)
                    self.assertIn(escape(words['boundary']), page)
                    suffix = '' if locale == 'en' else '?lang=' + locale
                    self.assertIn('href="/queue' + suffix + '"', page)
                    if integrated:
                        self.assertIn('href="/gas' + suffix + '"', page)
                    for private in ('PRIVATE-GRANT', 'session-a', F.A):
                        self.assertNotIn(private, page)
                    self.assertNotIn('<form', page)

    def test_invalid_queries_refuse_before_original_grant_reader(self):
        server = self.server()
        calls = []
        server.binding.exchange.authorization_state = lambda *args: calls.append(args)
        for query in ('lang=de', 'lang=', 'lang=ja&lang=en', 'lang=ja&grant=x'):
            with self.subTest(query=query), self.assertRaises(HTTPError) as raised:
                urlopen(server.origin + '/authorization?' + query, timeout=3)
            self.assertEqual(raised.exception.code, 400)
        self.assertEqual(calls, [])
