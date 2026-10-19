"""Private read-only domain definitions; no Wallet enforcement acceptance."""
from dataclasses import replace
from html import escape
from types import SimpleNamespace
import unittest

from exchange import fixtures as F
from exchange.authorization_page import WORDS, render_authorizations


class AuthorizationLocalesTests(unittest.TestCase):
    def fixture(self):
        exchange, clock = F.minted()
        exchange.register_authorization(F.authorization(
            F.A, 'PRIVATE-GRANT', 'session-a', counterparties=(F.B,)))
        return exchange, clock

    def test_six_locales_keep_original_constraints_without_identities(self):
        exchange, _ = self.fixture()
        grant = exchange.authorization('PRIVATE-GRANT')
        for locale, words in WORDS.items():
            page = render_authorizations(exchange, 'rcpt-8415-0001', ('PRIVATE-GRANT',),
                                         locale=locale)
            for key in ('heading', 'applies', 'actions', 'amount', 'restricted', 'boundary'):
                self.assertIn(escape(words[key]), page)
            self.assertIn('<td>' + str(grant.max_amount) + '</td>', page)
            self.assertIn('<td>' + str(grant.expires_at) + '</td>', page)
            self.assertIn('<td>' + escape(words['unknown']) + '</td>', page)
            self.assertNotIn(F.QUOTE_ASSET, page)
            for private in ('PRIVATE-GRANT', 'session-a', F.A, F.B):
                self.assertNotIn(private, page)
            self.assertNotIn('<form', page)

    def test_revoked_and_session_loss_reasons_are_localized_not_permission_proofs(self):
        exchange, _ = self.fixture()
        exchange.revoke_authorization('PRIVATE-GRANT')
        exchange.disconnect_wallet(F.A)
        for locale, words in WORDS.items():
            page = render_authorizations(exchange, 'rcpt-8415-0001', ('PRIVATE-GRANT',),
                                         locale=locale)
            self.assertIn(escape(words['revoked']), page)
            self.assertIn(escape(words['sessionLost']), page)
            self.assertIn('<td>' + escape(words['no']) + '</td>', page)
        self.assertEqual(exchange.legs('rcpt-8415-0001'), ())

    def test_unknown_actions_reasons_and_currency_are_not_echoed(self):
        exchange, _ = self.fixture()
        grant = replace(exchange.authorization('PRIVATE-GRANT'),
                        allowed_actions=('PRIVATE-ACTION',), quote_asset='PRIVATE-CURRENCY')
        domain = SimpleNamespace(
            receipt_view=lambda *args: {'receiptId': 'receipt-1', 'observedAt': 1700000000},
            receipt=lambda *args: SimpleNamespace(receipt_id='receipt-1', asset=grant.asset),
            authorization=lambda *args: grant,
            authorization_state=lambda *args: {'authorizationId': grant.authorization_id,
                'observedAt': 1700000000, 'account': grant.account,
                'applies': None, 'reasons': ['PRIVATE-REASON']})
        page = render_authorizations(domain, 'receipt-1', ('PRIVATE-GRANT',), locale='ja')
        self.assertIn(WORDS['ja']['otherAction'], page)
        self.assertIn(WORDS['ja']['unknown'], page)
        for private in ('PRIVATE-ACTION', 'PRIVATE-REASON', 'PRIVATE-CURRENCY', F.A, F.B):
            self.assertNotIn(private, page)

    def test_empty_scope_and_bad_locale_do_not_fabricate_a_grant(self):
        exchange, _ = self.fixture()
        self.assertIn(WORDS['ja']['none'], render_authorizations(
            exchange, 'rcpt-8415-0001', (), locale='ja'))
        domain = SimpleNamespace(receipt_view=lambda *args: self.fail('invalid locale read'))
        with self.assertRaises(ValueError):
            render_authorizations(domain, 'receipt-1', (), locale='de')
