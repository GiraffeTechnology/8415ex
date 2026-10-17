"""Authored server-rendered gas confirmation fixtures; no wallet is called."""
import unittest
from dataclasses import replace
from exchange.gas_budget import BuyerConfirmation, GasBudgetRefused
from exchange.gas_confirmation_ui import GasConfirmationPage
from integration.test_gas_budget import quote


class GasConfirmationContracts(unittest.TestCase):
    def setUp(self):
        self.quote = quote()
        self.calls = []
        def adapter(q, buyer, action, grant, now):
            self.calls.append(q.digest)
            return BuyerConfirmation(q.digest, buyer, action, grant, now, 'fixture-proof')
        self.page = GasConfirmationPage(lambda: self.quote, adapter, 'buyer-1',
            'canonical-action-1', 'existing-grant-1', '/existing-route', lambda token: token == 'csrf-1')
        self.fields = {'csrf': 'csrf-1', 'quoteId': self.quote.quote_id,
            'version': str(self.quote.version), 'quoteDigest': self.quote.digest, 'accepted': 'yes'}

    def test_both_eth_usd_values_and_sample_provenance_are_visible(self):
        html = self.page.render(110, 'csrf-1')
        for text in ('Maximum gas fee', 'Statistical median (P50)', 'ETH / $',
                     'fixture-fx', 'fixture-provider', 'Sample', 'Raw SHA-256',
                     'separately from the purchase price', 'failed transactions'):
            self.assertIn(text, html)
        self.assertIn(self.quote.digest, html)
        self.assertEqual(self.calls, [])

    def test_untrusted_labels_and_tokens_are_escaped(self):
        self.quote = replace(self.quote, rate_source='<script>bad</script>')
        html = self.page.render(110, '"/><script>token</script>')
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_confirmation_uses_server_session_binding(self):
        confirmation = self.page.submit(self.fields, 110)
        self.assertEqual(confirmation.buyer, 'buyer-1')
        self.assertEqual(confirmation.wallet_grant, 'existing-grant-1')
        self.assertEqual(confirmation.action_digest, 'canonical-action-1')
        self.assertEqual(self.calls, [self.quote.digest])

    def test_stale_or_edited_quote_cannot_reach_wallet(self):
        for key, value in (('quoteDigest', 'changed'), ('quoteId', 'different'),
                           ('version', '2'), ('accepted', 'no'), ('csrf', 'invalid')):
            fields = dict(self.fields, **{key: value})
            with self.subTest(key=key), self.assertRaises(GasBudgetRefused):
                self.page.submit(fields, 110)
        self.assertEqual(self.calls, [])

    def test_posted_buyer_fee_or_duplicate_value_is_refused(self):
        for fields in (dict(self.fields, buyer='other'), dict(self.fields, capWei='99999'),
                       dict(self.fields, accepted=['yes', 'no'])):
            with self.assertRaises(GasBudgetRefused):
                self.page.submit(fields, 110)
        self.assertEqual(self.calls, [])

    def test_expired_and_updated_quotes_need_redisclosure(self):
        with self.assertRaises(GasBudgetRefused):
            self.page.submit(self.fields, 200)
        self.quote = replace(self.quote, version=2, cap_wei=120)
        with self.assertRaises(GasBudgetRefused):
            self.page.submit(self.fields, 110)
        self.assertEqual(self.calls, [])

    def test_mismatched_wallet_confirmation_is_not_accepted(self):
        self.page.confirm_with_wallet = lambda *args: BuyerConfirmation(
            self.quote.digest, 'wrong-buyer', 'canonical-action-1', 'existing-grant-1', 110, 'proof')
        with self.assertRaises(GasBudgetRefused):
            self.page.submit(self.fields, 110)

    def test_unknown_wallet_result_is_not_a_confirmation(self):
        self.page.confirm_with_wallet = lambda *args: None
        with self.assertRaises(GasBudgetRefused):
            self.page.submit(self.fields, 110)
