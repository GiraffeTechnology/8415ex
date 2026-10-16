"""Focused new amount contracts; synthetic input, no RPC or signing."""
import unittest
from dataclasses import replace
from exchange.gas_disclosure import (ActionGasEstimate, EtherUSDQuote,
    DisclosureUnavailable, require_disclosure, render_disclosure)


class GasDisclosureContracts(unittest.TestCase):
    def setUp(self):
        self.quote = EtherUSDQuote(2500123456, 90, 120, 'fixture-rate')
        self.action = ActionGasEstimate('transfer', 11155111, 21000, 1000000000,
                                       95, 115, 'fixture-gas')

    def test_exact_eth_and_usd_without_float(self):
        result = require_disclosure([self.action], self.quote, 100)
        self.assertEqual(result['actions'][0]['estimatedETH'], '0.000021')
        self.assertEqual(result['usdPerETH'], '2500.123456')
        self.assertEqual(result['actions'][0]['estimatedUSD'], '0.052502592576')
        self.assertEqual(result['validUntil'], 115)
        self.assertEqual(result['principalConversion'], 'not authorized')

    def test_tiny_amount_is_not_rounded_to_zero(self):
        action = replace(self.action, gas_units=1, fee_per_gas_wei=1)
        result = require_disclosure([action], replace(self.quote, micro_usd_per_eth=1), 100)
        self.assertEqual(result['actions'][0]['estimatedUSD'], '0.000000000000000000000001')

    def test_absent_rate_or_estimate_refused(self):
        for actions, quote in (([], self.quote), ([self.action], None), (None, self.quote)):
            with self.assertRaises(DisclosureUnavailable):
                require_disclosure(actions, quote, 100)

    def test_expiry_and_future_boundary_refused(self):
        for now in (89, 115, 120):
            with self.assertRaises(DisclosureUnavailable):
                require_disclosure([self.action], self.quote, now)

    def test_duplicates_mixed_chain_and_coercion_refused(self):
        for actions in ([self.action, self.action],
            [self.action, replace(self.action, action_id='other', chain_id=560048)],
            [replace(self.action, gas_units=True)],
            [replace(self.action, fee_per_gas_wei=1.5)]):
            with self.assertRaises(DisclosureUnavailable):
                require_disclosure(actions, self.quote, 100)

    def test_conditional_coverage_and_escaped_render(self):
        action = replace(self.action, action_id='<refund>', conditional=True)
        result = require_disclosure([action], self.quote, 100)
        html = render_disclosure(result)
        self.assertNotIn('<refund>', html)
        self.assertIn('&lt;refund&gt;', html)
        self.assertIn('0.000021 ETH', html)
        self.assertIn('0.052502592576 USD', html)
        self.assertIn('conditional', html)
        self.assertNotIn('total gas', html)


if __name__ == '__main__':
    unittest.main()
