"""Synthetic renderer/HTTP definitions; no live evidence or local execution."""
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from exchange import fixtures as F
from exchange.evidence_page import render_evidence, WORDS
from exchange.workbench import RuntimeBinding, WorkbenchServer
from integration import test_integrated_runtime_inputs as mounted
from integration.test_integrated_workbench_http import COMMIT, TREE


class EvidenceDomain:
    def __init__(self):
        self.calls = 0

    def receipt_view(self, receipt_id):
        self.calls += 1
        return {'asset': {'chainId': 11155111, 'contract': F.A},
                'owner': {'position': 2, 'account': F.B},
                'holder': {'position': 1, 'account': F.C},
                'registeredPrefixLegs': 1, 'observedAt': 1700000000,
                'privateJournal': '<script>private-proof</script>'}


class EvidenceLocaleTests(unittest.TestCase):
    def test_all_six_locales_keep_original_evidence_values_and_boundaries(self):
        run = {'scenario': 'DEMO-01', 'runId': 'demo-' + 'a' * 32,
               'commit': COMMIT, 'tree': TREE, 'transactionHashes': ['0x' + 'b' * 64]}
        for locale, words in WORDS.items():
            with self.subTest(locale=locale):
                domain = EvidenceDomain()
                page = render_evidence(domain, 'receipt-1', run, locale=locale)
                self.assertIn('<html lang="' + locale + '">', page)
                self.assertIn(words['heading'], page)
                self.assertIn(words['boundary'], page)
                self.assertIn(COMMIT, page)
                self.assertIn(TREE, page)
                self.assertIn('0x' + 'b' * 64, page)
                self.assertIn('<td>11155111</td>', page)
                self.assertIn('<td>2</td>', page)
                self.assertEqual(domain.calls, 1)
                for secret in (F.A, F.B, F.C, 'private-proof'):
                    self.assertNotIn(secret, page)
                self.assertNotIn('<form', page)

    def test_malformed_or_opaque_source_values_do_not_enter_html(self):
        run = {'scenario': '<script>scenario</script>', 'runId': F.A,
               'commit': 'x' * 40, 'tree': '<img src=x>',
               'transactionHashes': [F.B, '<script>transaction</script>'],
               'walletName': 'PRIVATE-WALLET', 'proof': 'PRIVATE-PROOF'}
        page = render_evidence(EvidenceDomain(), 'receipt-1', run, locale='ja',
                               gateway_configured=True)
        self.assertIn(WORDS['ja']['configured'], page)
        for value in ('<script>', '<img', 'PRIVATE-WALLET', 'PRIVATE-PROOF', F.A, F.B):
            self.assertNotIn(value, page)
        self.assertIn(WORDS['ja']['missing'], page)

    def test_unsupported_locale_refuses_before_domain_read(self):
        domain = EvidenceDomain()
        with self.assertRaises(ValueError):
            render_evidence(domain, 'receipt-1', {}, locale='de')
        self.assertEqual(domain.calls, 0)

    def server(self, integrated):
        fixture = mounted.IntegratedRuntimeInputsTests('runTest')
        self.addCleanup(fixture.doCleanups)
        if integrated:
            server = fixture.server()
        else:
            exchange, _ = F.minted()
            server = WorkbenchServer(RuntimeBinding(exchange, 'rcpt-8415-0001'),
                                     port=0, commit=COMMIT, tree=TREE)
            self.addCleanup(server.server_close)
        server.binding.exchange = EvidenceDomain()
        fixture.start(server)
        return fixture, server

    def test_standalone_and_integrated_evidence_routes_preserve_locale(self):
        for integrated in (False, True):
            fixture, server = self.server(integrated)
            for locale in WORDS:
                with self.subTest(integrated=integrated, locale=locale):
                    with urlopen(server.origin + '/evidence?lang=' + locale, timeout=3) as response:
                        page = response.read().decode('utf-8')
                        self.assertEqual(response.headers['Cache-Control'], 'no-store')
                    suffix = '' if locale == 'en' else '?lang=' + locale
                    self.assertIn('<html lang="' + locale + '">', page)
                    self.assertIn('href="/receipt' + suffix + '"', page)
                    if integrated:
                        self.assertIn('href="/gas' + suffix + '"', page)
            if integrated:
                self.assertEqual(fixture.wallet_calls, [])

    def test_invalid_native_queries_refuse_without_reading_domain(self):
        fixture, server = self.server(True)
        domain = server.binding.exchange
        for query in ('lang=de', 'lang=', 'lang=ja&lang=en', 'lang=ja&id=demo-x',
                      'lang=' + 'a' * 65):
            with self.subTest(query=query), self.assertRaises(HTTPError) as raised:
                urlopen(server.origin + '/evidence?' + query, timeout=3)
            self.assertEqual(raised.exception.code, 400)
        self.assertEqual(domain.calls, 0)
        self.assertEqual(fixture.wallet_calls, [])

    def test_default_native_page_and_separate_unknown_demo_run(self):
        fixture, server = self.server(True)
        domain = server.binding.exchange
        with urlopen(server.origin + '/evidence', timeout=3) as response:
            self.assertIn('<html lang="en">', response.read().decode('utf-8'))
        self.assertEqual(domain.calls, 1)
        with self.assertRaises(HTTPError) as raised:
            urlopen(server.origin + '/evidence?id=demo-' + '0' * 32, timeout=3)
        self.assertEqual(raised.exception.code, 404)
        self.assertEqual(domain.calls, 1)
        self.assertEqual(fixture.wallet_calls, [])
