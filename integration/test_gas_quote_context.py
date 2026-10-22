"""Authored quote-context contracts; no live wallet, feed or network."""
import unittest
from dataclasses import replace
from html import escape
from html.parser import HTMLParser

from exchange.gas_budget import GasBudgetRefused
from exchange.gas_confirmation_ui import GasConfirmationPage
from exchange.gas_disclosure_locales import WORDS
from integration.test_gas_budget import quote


class DefinitionReader(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.tag = None
        self.buffer = []
        self.label = None
        self.values = {}

    def handle_starttag(self, tag, attrs):
        if tag == 'dl':
            self.depth += 1
        if self.depth and tag in ('dt', 'dd'):
            self.tag, self.buffer = tag, []

    def handle_data(self, data):
        if self.tag:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == self.tag:
            value = ''.join(self.buffer)
            if tag == 'dt':
                self.label = value
            else:
                self.values[self.label] = value
            self.tag = None
        if tag == 'dl':
            self.depth -= 1


class GasQuoteContextContracts(unittest.TestCase):
    def setUp(self):
        self.quote = quote()
        self.calls = []
        self.page = GasConfirmationPage(
            lambda: self.quote, lambda *args: self.calls.append(args),
            'fixture-buyer', 'fixture-action', 'fixture-grant',
            '/existing-gas-confirmation', lambda token: token == 'fixture-csrf')

    def definitions(self, locale='en'):
        document = self.page.render(self.quote.quoted_at, 'fixture-csrf', locale)
        reader = DefinitionReader()
        reader.feed(document)
        return document, reader.values

    def test_all_locales_show_exact_quote_context_outside_collapsed_evidence(self):
        for locale, words in WORDS.items():
            with self.subTest(locale=locale):
                document, values = self.definitions(locale)
                self.assertEqual(values[words['quotedAt']], str(self.quote.quoted_at))
                self.assertEqual(values[words['scope']], self.quote.scope)
                self.assertEqual(values[words['sampleCount']], str(len(self.quote.samples)))
                self.assertEqual(values[words['window']],
                    str(self.quote.window_start) + ' ' + words['to'] + ' ' + str(self.quote.window_end))
                self.assertEqual(values[words['algorithm']], self.quote.disclosure()['algorithm'])
                self.assertLess(document.index('</dl>'), document.index('<details>'))
                self.assertEqual(self.calls, [])

    def test_context_uses_distinct_quote_window_and_expiry_times(self):
        _, values = self.definitions()
        self.assertEqual(values[WORDS['en']['quotedAt']], str(self.quote.quoted_at))
        self.assertEqual(values[WORDS['en']['expires']], str(self.quote.valid_until))
        self.assertNotEqual(self.quote.quoted_at, self.quote.valid_until)
        self.assertEqual(values[WORDS['en']['fxTime']], str(self.quote.rate_observed_at))

    def test_scope_is_original_text_not_inferred_aggregate_or_per_action(self):
        scope = 'fixture-conditional-return-only'
        self.quote = replace(self.quote, scope=scope,
            samples=tuple(replace(sample, scope=scope) for sample in self.quote.samples))
        _, values = self.definitions()
        self.assertEqual(values[WORDS['en']['scope']], scope)
        self.assertEqual(values[WORDS['en']['actions']], ', '.join(self.quote.actions))

    def test_untrusted_scope_is_text_and_cannot_inject_confirmation_inputs(self):
        scope = '<input name="capWei" value="999"><script>scope</script>'
        self.quote = replace(self.quote, scope=scope,
            samples=tuple(replace(sample, scope=scope) for sample in self.quote.samples))
        document, values = self.definitions()
        self.assertEqual(values[WORDS['en']['scope']], scope)
        self.assertNotIn('<script>', document)
        self.assertNotIn('<input name="capWei"', document)
        self.assertIn(escape(scope, quote=True), document)
        self.assertEqual(self.calls, [])

    def test_even_sample_population_preserves_exact_existing_median(self):
        self.quote = quote((10, 11))
        data = self.quote.disclosure()
        document, values = self.definitions()
        self.assertEqual(values[WORDS['en']['sampleCount']], str(data['sampleCount']))
        self.assertIn(data['median']['ETH'] + ' ETH', document)
        self.assertIn(data['median']['USD'] + ' USD', document)
        self.assertIn(data['cap']['ETH'] + ' ETH', document)
        self.assertIn(data['cap']['USD'] + ' USD', document)

    def test_render_does_not_change_signed_quote_or_confirmation_fields(self):
        digest = self.quote.digest
        data = self.quote.disclosure()
        for locale in WORDS:
            document, _ = self.definitions(locale)
            self.assertIn('name="quoteDigest" value="' + digest + '"', document)
            self.assertNotIn('name="quotedAt"', document)
            self.assertNotIn('name="scope"', document)
            self.assertNotIn('name="sampleCount"', document)
        self.assertEqual(self.quote.digest, digest)
        self.assertEqual(self.quote.disclosure(), data)
        self.assertEqual(self.calls, [])

    def test_expired_and_future_quotes_still_refuse_without_confirmation(self):
        for now in (self.quote.quoted_at - 1, self.quote.valid_until):
            with self.subTest(now=now), self.assertRaises(GasBudgetRefused):
                self.page.render(now, 'fixture-csrf')
        self.assertEqual(self.calls, [])

    def test_browser_cannot_post_display_context_as_new_authority(self):
        fields = {'csrf': 'fixture-csrf', 'quoteId': self.quote.quote_id,
                  'version': str(self.quote.version), 'quoteDigest': self.quote.digest,
                  'accepted': 'yes'}
        for key in ('scope', 'quotedAt', 'sampleCount', 'algorithm'):
            with self.subTest(key=key), self.assertRaises(GasBudgetRefused):
                self.page.submit(dict(fields, **{key: 'browser-value'}), self.quote.quoted_at)
        self.assertEqual(self.calls, [])
