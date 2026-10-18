"""Failed-observation HTTP definitions; approved remote Linux execution only."""
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from exchange.queue_status_page import CONTROLS
from integration import test_integrated_runtime_inputs as mounted


class NativeErrorLocalesTests(unittest.TestCase):
    def server(self):
        fixture = mounted.IntegratedRuntimeInputsTests('runTest')
        self.addCleanup(fixture.doCleanups)
        server = fixture.server()
        self.reads = []
        def unavailable(*args, **kwargs):
            self.reads.append('read')
            raise ValueError('PRIVATE-PROVIDER-JOURNAL-DETAIL')
        server.binding.exchange.receipt_view = unavailable
        server.binding.public_detail = unavailable
        fixture.start(server)
        return fixture, server

    def refused(self, server, path):
        with self.assertRaises(HTTPError) as caught:
            urlopen(server.origin + path, timeout=3)
        with caught.exception as response:
            self.assertEqual(response.code, 400)
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            return response.read().decode('utf-8')

    def test_failed_native_observation_keeps_each_valid_language_without_private_error(self):
        fixture, server = self.server()
        for locale, words in CONTROLS.items():
            for path in ('receipt', 'queue', 'authorization', 'timeline', 'rollback', 'evidence'):
                with self.subTest(locale=locale, path=path):
                    body = self.refused(server, '/' + path + '?lang=' + locale)
                    self.assertEqual(body, words['inputRefused'])
                    self.assertNotIn('PRIVATE-', body)
        self.assertTrue(self.reads)
        self.assertEqual(fixture.wallet_calls, [])

    def test_unsupported_language_refuses_before_reader_with_bounded_fallback(self):
        fixture, server = self.server()
        for path in ('receipt', 'queue', 'authorization', 'timeline', 'rollback', 'evidence'):
            with self.subTest(path=path):
                body = self.refused(server, '/' + path + '?lang=de')
                self.assertEqual(body, CONTROLS['en']['inputRefused'])
        self.assertEqual(self.reads, [])
        self.assertEqual(fixture.wallet_calls, [])
