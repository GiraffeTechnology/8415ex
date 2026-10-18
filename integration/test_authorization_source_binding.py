"""Wrong-scope authorization observation definitions; approved Linux only."""
from dataclasses import fields, replace
from types import SimpleNamespace
import unittest

from exchange.authorization_page import render_authorizations
from integration import test_authorization_locales as fixtures


class AuthorizationSourceBindingTests(unittest.TestCase):
    def fixture(self):
        return fixtures.AuthorizationLocalesTests('runTest').fixture()[0]

    def test_foreign_receipt_observation_refuses_even_with_original_grant(self):
        domain = self.fixture()
        read = domain.receipt_view
        def wrong(*args):
            value = read(*args)
            value['receiptId'] = 'other-receipt'
            return value
        domain.receipt_view = wrong
        with self.assertRaises(ValueError):
            render_authorizations(domain, 'rcpt-8415-0001', ('PRIVATE-GRANT',))

    def test_foreign_asset_and_chain_grants_are_not_shown_under_receipt(self):
        for field in ('asset', 'chain_id'):
            domain = self.fixture()
            grant = domain.authorization('PRIVATE-GRANT')
            changed = SimpleNamespace(**{item.name: getattr(grant, item.name)
                                         for item in fields(grant)})
            if field == 'asset':
                changed.asset = replace(grant.asset, token_id=grant.asset.token_id + 1)
            else:
                changed.chain_id = 1
            domain.authorization = lambda *args: changed
            with self.subTest(field=field), self.assertRaises(ValueError):
                render_authorizations(domain, 'rcpt-8415-0001', ('PRIVATE-GRANT',))

    def test_foreign_or_stale_state_is_not_paired_with_original_grant(self):
        for field, replacement in (('authorizationId', 'OTHER-GRANT'),
                                   ('account', '0x' + 'f' * 40), ('observedAt', 0)):
            domain = self.fixture()
            original = domain.authorization_state
            def changed(*args):
                value = original(*args)
                value[field] = replacement
                return value
            domain.authorization_state = changed
            with self.subTest(field=field), self.assertRaises(ValueError):
                render_authorizations(domain, 'rcpt-8415-0001', ('PRIVATE-GRANT',))
