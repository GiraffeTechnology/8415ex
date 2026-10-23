"""Native page reachability definitions; approved remote Linux execution only."""
import unittest
from html import escape
from urllib.request import urlopen

from exchange import fixtures as F
from exchange.workbench import WorkbenchHandler
from exchange.queue_status_page import CONTROLS, WORDS as QUEUE
from exchange.authorization_page import WORDS as AUTH
from exchange.timeline_page import WORDS as TIMELINE
from exchange.rollback_page import WORDS as ROLLBACK
from integration import test_integrated_runtime_inputs as mounted


class NativeNavigationTests(unittest.TestCase):
    def test_every_native_destination_preserves_each_supported_locale(self):
        for locale, words in CONTROLS.items():
            suffix = '' if locale == 'en' else '?lang=' + locale
            labels = {'receipt': words['receipt'], 'market': words['market'],
                      'evidence': words['evidence'], 'queue': QUEUE[locale]['heading'],
                      'authorization': AUTH[locale]['heading'],
                      'timeline': TIMELINE[locale]['heading'],
                      'rollback': ROLLBACK[locale]['heading']}
            with self.subTest(locale=locale):
                value = WorkbenchHandler.native_navigation(locale)
                self.assertEqual(value.count('<a '), len(labels))
                for path, label in labels.items():
                    self.assertIn('href="/' + path + suffix + '">' + escape(label), value)
                self.assertNotIn('<form', value)
                self.assertNotIn('/operation', value)
                self.assertNotIn('advance-exit', value)

    def test_unsupported_locale_cannot_become_a_navigation_url(self):
        for locale in ('de', '', 'ja&buyer=private', '<script>'):
            with self.subTest(locale=locale), self.assertRaises(ValueError):
                WorkbenchHandler.native_navigation(locale)

    def test_mounted_pages_reach_other_native_views_without_dispatch(self):
        fixture = mounted.IntegratedRuntimeInputsTests('runTest')
        self.addCleanup(fixture.doCleanups)
        server = fixture.server()
        detail = server.binding.public_detail()
        server.binding.exchange, _ = F.minted()
        server.binding.receipt_id = 'rcpt-8415-0001'
        server.binding.authorization_ids = ()
        server.binding.public_detail = lambda: detail
        fixture.start(server)
        pages = ('receipt', 'queue', 'authorization', 'timeline', 'rollback', 'evidence')
        for locale in CONTROLS:
            suffix = '' if locale == 'en' else '?lang=' + locale
            for page in pages:
                with self.subTest(locale=locale, page=page):
                    with urlopen(server.origin + '/' + page + '?lang=' + locale,
                                 timeout=3) as response:
                        self.assertEqual(response.status, 200)
                        html = response.read().decode('utf-8')
                    self.assertEqual(html.count('data-native-navigation="1"'), 1)
                    for destination in pages:
                        self.assertIn('href="/' + destination + suffix + '"', html)
        self.assertEqual(fixture.wallet_calls, [])
