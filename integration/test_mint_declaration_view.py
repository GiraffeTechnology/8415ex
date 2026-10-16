"""Authored rendering contracts; no browser, storage or mint execution."""
import unittest
from dataclasses import replace
from exchange.mint_declaration_view import render_mint_declaration
from exchange.mint_specification import MintSpecificationRefused
from integration.test_mint_specification import specification


class MintDeclarationViewContracts(unittest.TestCase):
    def test_complete_fields_terms_and_oracle_format_are_visible(self):
        spec = specification()
        html = render_mint_declaration(spec, lambda k, e: True, 100)
        for value in ('100 kg', 'bill-1', 'issuer-1', 'registrar-1', 'fixture-location',
                      'fixture-grade', 'fixture-template', 'fixture-voucher', 'REG_DIRECT',
                      'controlled-map-1', 'UTC epoch seconds', 'LTE', spec.bill_terms):
            self.assertIn(value, html)
        self.assertIn('Declaration candidate only', html)
        self.assertIn('single authoritative registration fact', html)
        self.assertNotIn('<form', html)
        self.assertNotIn('<button', html)

    def test_terms_attributes_and_labels_are_escaped(self):
        spec = replace(specification(), bill_terms='<script>fixture</script>',
            issuer='issuer<script>', public_attributes=(('grade', '<img src=x>'),))
        html = render_mint_declaration(spec, lambda k, e: True, 100)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('&lt;img src=x&gt;', html)

    def test_failed_privacy_or_mapping_verification_cannot_render(self):
        for refused in ('non-secret-metadata-scan', 'controlled-encrypted-access-mapping'):
            with self.subTest(refused=refused), self.assertRaises(MintSpecificationRefused):
                render_mint_declaration(specification(), lambda k, e: k != refused, 100)

    def test_each_path_uses_the_same_display_contract(self):
        for path in ('REG_DIRECT', 'REG_ELECTRONIC', 'REG_INTERMEDIARY'):
            html = render_mint_declaration(specification(path), lambda k, e: True, 100)
            self.assertIn(path, html)
            self.assertIn('not a second receipt', html)

    def test_unknown_or_non_exact_observation_is_refused(self):
        for now in (True, 100.5, -1, None):
            with self.subTest(now=now), self.assertRaises(MintSpecificationRefused):
                render_mint_declaration(specification(), lambda k, e: True, now)
