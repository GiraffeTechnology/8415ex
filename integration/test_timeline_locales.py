"""Private synthetic timeline renderer and HTTP definitions; NOT_RUN."""
from html import escape
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from exchange.timeline_page import WORDS, SIMULATION, render_timeline
from integration import test_timeline_predecessor as history
from integration import test_authorization_locale_transport as mounted


def domain():
    value = history.TimelineDomain()
    original = value.receipt_view
    value.receipt_view = lambda *args: {**original(*args), 'simulatedRegistration': True}
    return value


class TimelineLocaleTests(unittest.TestCase):
    def test_six_locales_keep_branch_positions_with_simulation_and_acceptance_boundaries(self):
        for locale, words in WORDS.items():
            page = render_timeline(domain(), 'receipt-1', locale=locale)
            for key in ('heading', 'basis', 'boundary', 'active', 'withdrawn', 'units'):
                self.assertIn(escape(words[key]), page)
            self.assertIn(escape(SIMULATION[locale]), page)
            self.assertIn('<td>3</td><td>1</td><td>4</td>', page)
            self.assertIn('<td>2</td><td>0</td><td>3</td>', page)
            self.assertNotIn('PRIVATE-BUYER', page)
            self.assertNotIn('private-0', page)
            self.assertNotIn('<form', page)

    def test_missing_original_predecessor_is_localized_unknown_not_adjacent_position(self):
        value = domain()
        value.originals[3].predecessor_transfer_id = 'missing-record'
        for locale, words in WORDS.items():
            page = render_timeline(value, 'receipt-1', locale=locale)
            self.assertIn('<td>3</td><td>' + escape(words['unknown']) + '</td><td>4</td>', page)
            self.assertNotIn('missing-record', page)

    def test_native_and_integrated_routes_keep_language_and_original_branch_positions(self):
        for integrated in (False, True):
            fixture = mounted.AuthorizationLocaleTransportTests('runTest')
            self.addCleanup(fixture.doCleanups)
            server = fixture.server(integrated)
            server.binding.exchange = domain()
            server.binding.receipt_id = 'receipt-1'
            for locale in WORDS:
                with self.subTest(integrated=integrated, locale=locale):
                    with urlopen(server.origin + '/timeline?lang=' + locale, timeout=3) as response:
                        page = response.read().decode('utf-8')
                        self.assertEqual(response.headers['Cache-Control'], 'no-store')
                    self.assertIn('<html lang="' + locale + '">', page)
                    self.assertIn('<td>3</td><td>1</td><td>4</td>', page)
                    suffix = '' if locale == 'en' else '?lang=' + locale
                    self.assertIn('href="/queue' + suffix + '"', page)
                    if integrated:
                        self.assertIn('href="/gas' + suffix + '"', page)

    def test_invalid_queries_refuse_before_original_history_reader(self):
        fixture = mounted.AuthorizationLocaleTransportTests('runTest')
        self.addCleanup(fixture.doCleanups)
        server = fixture.server()
        calls = []
        server.binding.exchange.receipt_view = lambda *args: calls.append(args)
        for query in ('lang=de', 'lang=', 'lang=ja&lang=en', 'lang=ja&position=2'):
            with self.subTest(query=query), self.assertRaises(HTTPError) as raised:
                urlopen(server.origin + '/timeline?' + query, timeout=3)
            self.assertEqual(raised.exception.code, 400)
        self.assertEqual(calls, [])

    def test_bad_locale_refuses_before_read_and_unknown_currency_never_becomes_zero(self):
        value = domain()
        value.receipt_view = lambda *args: self.fail('unsupported locale read')
        with self.assertRaises(ValueError):
            render_timeline(value, 'receipt-1', locale='de')
        value = domain()
        value.entries[3].update(price='invalid', quoteAsset='PRIVATE-CURRENCY')
        page = render_timeline(value, 'receipt-1', locale='ja')
        self.assertIn(WORDS['ja']['unknown'], page)
        self.assertNotIn('PRIVATE-CURRENCY', page)
