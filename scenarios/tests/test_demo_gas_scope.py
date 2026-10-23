"""Current DEMO-05 scope: intermediate shortage is not return-budget shortage."""
import unittest
from unittest.mock import patch

from exchange import fixtures as F
from scenarios.demos import DEMOS, GAS_UNIT, RECEIPT
from scenarios.harness import run_all


class NoIncrease(dict):
    def __setitem__(self, key, value):
        if key in self and value > self[key]:
            raise AssertionError("a mid-recovery fixture top-up is not the core scenario")
        super().__setitem__(key, value)


class DemoGasScopeTests(unittest.TestCase):
    def test_core_returns_once_without_increasing_any_fixture_ceiling(self):
        original = F.rollback_chain_to_d
        instances = []
        def create(**options):
            exchange, clock = original(**options)
            exchange._budgets = NoIncrease(exchange._budgets)
            instances.append(exchange)
            return exchange, clock
        scenario = next(row for row in DEMOS if row.scenario_id == "DEMO-05")
        with patch.object(F, "rollback_chain_to_d", side_effect=create):
            result = run_all([scenario])["scenarios"][0]
        self.assertIsNone(result["error"])
        self.assertTrue(result["passed"])
        self.assertEqual(len(instances), 1)
        exchange = instances[0]
        self.assertEqual((exchange._budgets[F.B], exchange._budgets[F.C]), (0, 0))
        self.assertEqual(exchange._budgets[F.D], 100_000)
        self.assertEqual(exchange.owner_of(RECEIPT), F.A)
        self.assertEqual((exchange.payments.movements, exchange.asset_control.returns), (3, 1))
        observed = next(row for row in result["expectations"]
                        if row["name"] == "one direct return needs no intermediate wallet gas")
        self.assertEqual(observed["observed"], [F.D, F.A, 1, False, False])

    def test_actual_return_bearer_shortfall_remains_a_separate_negative_control(self):
        exchange, _ = F.rollback_chain_to_d(
            gas_budgets={F.B: 0, F.C: 0, F.D: 0})
        requests = F.submit_all(exchange)
        F.refuse(exchange, requests[0], "negative-return-budget")
        exchange.begin_rollback(RECEIPT, 0,
            F.rollback_authority(exchange, 0, "negative-budget-authority"))
        first = exchange.advance_rollback(RECEIPT)
        self.assertEqual(first["state"], "blocked")
        blocked = [row for row in first["outstandingSteps"] if row["kind"] == "asset-return"]
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0]["detail"]["reason"], "EX_GAS_BUDGET_EXHAUSTED")
        self.assertEqual(exchange.owner_of(RECEIPT), F.D)
        self.assertEqual((exchange.payments.movements, exchange.asset_control.returns), (3, 0))
        # This deliberate negative fixture's resume is not the primary DEMO-05.
        exchange._budgets[F.D] = 100_000
        second = exchange.advance_rollback(RECEIPT)
        self.assertTrue(second["complete"])
        self.assertEqual((exchange._budgets[F.B], exchange._budgets[F.C]), (0, 0))
        self.assertEqual((exchange.payments.movements, exchange.asset_control.returns), (3, 1))
        exchange.advance_rollback(RECEIPT)
        self.assertEqual((exchange.payments.movements, exchange.asset_control.returns), (3, 1))

    def test_fixture_ceilings_do_not_claim_observed_eth_or_real_execution(self):
        scenario = next(row for row in DEMOS if row.scenario_id == "DEMO-05")
        result = run_all([scenario])["scenarios"][0]
        conditions = result["setup"]["gasConditions"]
        self.assertEqual(conditions["budgetUnit"], GAS_UNIT)
        self.assertEqual(conditions["ordinaryWalletETHBalances"], "NOT_OBSERVED")
        native = next(row for row in result["expectations"]
                      if row["name"] == "actual zero-ETH intermediate-wallet execution")
        self.assertEqual(native["outcome"], "not-run")
        self.assertEqual(native["observed"], "NOT_RUN")
        self.assertIn("buyer-confirmed maximum-gas prepayments", native["detail"])
        self.assertIn("no deployment", result["scope"])


if __name__ == "__main__":
    unittest.main()
