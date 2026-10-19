"""Private rollback renderer/HTTP definitions; no native funds or chain execution."""
from html import escape
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from exchange.rollback_page import WORDS, render_rollback
from exchange.timeline_page import WORDS as TIMELINE
from integration import test_rollback_projection as observations
from integration import test_authorization_locale_transport as mounted


class RollbackLocaleTests(unittest.TestCase):
    def test_six_locales_preserve_prefix_and_separate_principal_from_consumed_eth(self):
        for locale, words in WORDS.items():
            page = render_rollback(observations.RollbackDomain(), 'receipt-1', locale=locale)
            for key in ('heading', 'prefix', 'policy', 'nativeBoundary', 'refundStep'):
                self.assertIn(escape(words[key]), page)
            self.assertIn('1000 PYUSD', page)
            self.assertIn('17 ETH wei', page)
            self.assertIn('<td>1</td>', page)
            for private in ('PRIVATE-WALLET', 'PRIVATE-BUYER', 'PRIVATE-JOURNAL', 'PRIVATE-PROOF'):
                self.assertNotIn(private, page)
            self.assertNotIn('<form', page)

    def test_inconsistent_completion_is_unknown_in_every_locale(self):
        domain = observations.RollbackDomain()
        domain.report.update(complete=True, state='complete')
        for locale, words in WORDS.items():
            page = render_rollback(domain, 'receipt-1', locale=locale)
            self.assertIn('<td>' + escape(words['completion']) + '</td><td>'
                          + escape(TIMELINE[locale]['unknown']) + '</td>', page)

    def test_missing_gas_and_principal_values_never_become_zero(self):
        domain = observations.RollbackDomain()
        domain.report['funds'][0].update(principal='invalid', gasTotal='invalid')
        page = render_rollback(domain, 'receipt-1', locale='ja')
        self.assertNotIn('0 ETH wei', page)
        self.assertIn('<td>1</td><td>' + TIMELINE['ja']['unknown'] + '</td>', page)
        self.assertIn(TIMELINE['ja']['unknown'], page)

    def test_bad_locale_refuses_before_original_observation(self):
        domain = observations.RollbackDomain()
        domain.receipt_view = lambda *args: self.fail('unsupported locale read')
        with self.assertRaises(ValueError):
            render_rollback(domain, 'receipt-1', locale='de')

    def server(self, integrated=True):
        fixture = mounted.AuthorizationLocaleTransportTests('runTest')
        self.addCleanup(fixture.doCleanups)
        server = fixture.server(integrated)
        server.binding.exchange = observations.RollbackDomain()
        server.binding.receipt_id = 'receipt-1'
        return server

    def test_native_and_integrated_routes_preserve_language_without_enabling_actions(self):
        for integrated in (False, True):
            server = self.server(integrated)
            for locale in WORDS:
                with self.subTest(integrated=integrated, locale=locale):
                    with urlopen(server.origin + '/rollback?lang=' + locale, timeout=3) as response:
                        page = response.read().decode('utf-8')
                        self.assertEqual(response.headers['Cache-Control'], 'no-store')
                    suffix = '' if locale == 'en' else '?lang=' + locale
                    self.assertIn('<html lang="' + locale + '">', page)
                    self.assertIn('href="/queue' + suffix + '"', page)
                    self.assertIn('17 ETH wei', page)
                    self.assertNotIn('<form', page)
                    if integrated:
                        self.assertIn('href="/gas' + suffix + '"', page)

    def test_invalid_queries_refuse_before_original_rollback_reader(self):
        server = self.server()
        calls = []
        server.binding.exchange.rollback_report = lambda *args: calls.append(args)
        for query in ('lang=de', 'lang=', 'lang=ja&lang=en', 'lang=ja&success=true'):
            with self.subTest(query=query), self.assertRaises(HTTPError) as raised:
                urlopen(server.origin + '/rollback?' + query, timeout=3)
            self.assertEqual(raised.exception.code, 400)
        self.assertEqual(calls, [])
