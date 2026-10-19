"""The six scenarios must run, pass, and record what the requirements ask for."""
import unittest

from exchange import fixtures as F
from scenarios.demos import DEMOS, GAS, GAS_UNIT, MAIN_PATHS, PRICES
from scenarios.harness import run_all


class SixScenarios(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.report = run_all(list(DEMOS))
        cls.by_id = {scenario["scenarioId"]: scenario for scenario in cls.report["scenarios"]}

    def test_there_are_exactly_six(self):
        self.assertEqual(len(DEMOS), 6)
        self.assertEqual(sorted(self.by_id), ["DEMO-01", "DEMO-02", "DEMO-03", "DEMO-04",
                                              "DEMO-05", "DEMO-06"])

    def test_every_scenario_passes(self):
        for scenario_id, scenario in sorted(self.by_id.items()):
            with self.subTest(scenario=scenario_id):
                self.assertIsNone(scenario["error"])
                self.assertEqual([e for e in scenario["expectations"]
                                  if e["outcome"] == "failed"], [])
                self.assertEqual([e for e in scenario["expectations"]
                                  if e["outcome"] == "blocked"], [])
                self.assertTrue(scenario["passed"])

    def test_every_scenario_records_its_setup(self):
        for scenario_id, scenario in sorted(self.by_id.items()):
            with self.subTest(scenario=scenario_id):
                setup = scenario["setup"]
                self.assertEqual(sorted(setup["accounts"]), ["A", "B", "C", "D"])
                self.assertIn("receipt", setup)
                self.assertIn("prices", setup)
                self.assertIn("gasConditions", setup)
                self.assertIn("simulatedAdapters", setup)
                self.assertEqual(setup["receipt"]["tradeableUnits"], 1)

    def test_every_scenario_records_steps_and_positions(self):
        for scenario_id, scenario in sorted(self.by_id.items()):
            with self.subTest(scenario=scenario_id):
                self.assertTrue(scenario["steps"], "a scenario records its steps")
                names = {e["name"] for e in scenario["expectations"]}
                self.assertTrue(any("owner" in name or "holder" in name or "position" in name
                                    for name in names),
                                "a scenario records the owner and holder positions")

    def test_every_scenario_names_its_main_path(self):
        for scenario_id, scenario in sorted(self.by_id.items()):
            with self.subTest(scenario=scenario_id):
                self.assertEqual(scenario["mainPath"], MAIN_PATHS[scenario_id])

    def test_the_three_paths_are_covered_across_the_six(self):
        self.assertEqual(sorted(set(MAIN_PATHS.values())),
                         ["REG_DIRECT", "REG_ELECTRONIC", "REG_INTERMEDIARY"])

    def test_every_scenario_keeps_the_real_obligations_as_not_run(self):
        for scenario_id, scenario in sorted(self.by_id.items()):
            with self.subTest(scenario=scenario_id):
                not_run = [e for e in scenario["expectations"] if e["outcome"] == "not-run"]
                self.assertTrue(not_run, "a local scenario still owes real evidence")
                for entry in not_run:
                    self.assertEqual(entry["observed"], "NOT_RUN")

    def test_the_scope_line_denies_deployment_everywhere(self):
        for scenario in self.by_id.values():
            self.assertIn("no deployment", scenario["scope"])
            self.assertIn("simulated", scenario["scope"])

    def test_the_report_is_deterministic(self):
        again = run_all(list(DEMOS))
        self.assertEqual(self.report["deterministicDigest"], again["deterministicDigest"])


class ScenarioContent(unittest.TestCase):
    """Each scenario must actually check the behaviour it claims."""

    @classmethod
    def setUpClass(cls):
        cls.by_id = {scenario["scenarioId"]: scenario
                     for scenario in run_all(list(DEMOS))["scenarios"]}

    def _names(self, scenario_id):
        return " | ".join(e["name"] for e in self.by_id[scenario_id]["expectations"])

    def test_demo_01_covers_release_bill_history_and_retirement(self):
        names = self._names("DEMO-01")
        self.assertIn("released to its own seller", names)
        self.assertIn("redemption request stays retired", names)
        self.assertIn("physical exit advance stays retired", names)
        self.assertIn("history is preserved", names)

    def test_demo_02_covers_deferral_and_independent_release(self):
        names = self._names("DEMO-02")
        self.assertIn("waits for the gap", names)
        self.assertIn("without waiting for C or D", names)
        self.assertIn("never merged", names)

    def test_demo_03_covers_the_full_suffix_return(self):
        names = self._names("DEMO-03")
        self.assertIn("returns to the origin", names)
        self.assertIn("own unreleased funds", names)
        self.assertIn("charged in full twice", names)

    def test_demo_03_keeps_principal_and_gas_in_their_own_units(self):
        """A gas-unit count is never subtracted from a quote-asset principal."""
        scenario = self.by_id["DEMO-03"]
        by_name = {e["name"]: e for e in scenario["expectations"]}
        whole = next(e for name, e in by_name.items() if "whole principal" in name)
        self.assertEqual(whole["outcome"], "passed")
        for leg, (principal, asset, equal) in whole["observed"].items():
            with self.subTest(leg=leg):
                self.assertEqual(asset, F.QUOTE_ASSET)
                self.assertTrue(equal, "the refund returns the whole principal")
        separate = next(e for name, e in by_name.items() if "in gas units, by bearer" in name)
        self.assertEqual(separate["outcome"], "passed")
        for leg, (amount, unit, bearer) in separate["observed"].items():
            with self.subTest(leg=leg):
                self.assertEqual(unit, GAS_UNIT)
                self.assertNotEqual(unit, F.QUOTE_ASSET)
                self.assertEqual(amount, str(GAS["trade"]))
                self.assertIn(bearer, (F.B, F.C, F.D))

    def test_demo_03_quotes_no_principal_reduced_by_a_gas_figure(self):
        scenario = self.by_id["DEMO-03"]
        quoted = next(e for e in scenario["expectations"]
                      if "reduced by a gas figure" in e["name"])
        self.assertEqual(quoted["outcome"], "passed")
        self.assertEqual(set(quoted["observed"].values()),
                         {str(PRICES["AB"]), str(PRICES["BC"]), str(PRICES["CD"])})
        for value in quoted["observed"].values():
            for price in (PRICES["AB"], PRICES["BC"], PRICES["CD"]):
                self.assertNotEqual(value, str(price - GAS["trade"]),
                                    "a net across two units is not an amount")

    def test_demo_03_leaves_the_fee_deduction_policy_unexecuted(self):
        scenario = self.by_id["DEMO-03"]
        owed = [e for e in scenario["expectations"]
                if e["outcome"] == "not-run" and "fee deduction" in e["name"]]
        self.assertEqual(len(owed), 1)
        self.assertIn("D-04", owed[0]["detail"])
        self.assertEqual(owed[0]["observed"], "NOT_RUN")
        self.assertTrue(any("netToOriginalBuyer" in note for note in scenario["notes"]))

    def test_demo_04_protects_the_finalized_prefix(self):
        names = self._names("DEMO-04")
        self.assertIn("returns to B, not to the origin", names)
        self.assertIn("payment to A are unchanged", names)
        self.assertIn("finalized prefix is refused", names)

    def test_demo_05_covers_the_shortfall_without_disposal(self):
        names = self._names("DEMO-05")
        self.assertIn("no custody, forced sale or liquidation", names)
        self.assertIn("needs no intermediate wallet gas", names)
        self.assertIn("nothing was repeated", names)

    def test_demo_06_covers_cutoff_suffix_recovery_without_burn(self):
        names = self._names("DEMO-06")
        self.assertIn("instant before the cutoff", names)
        self.assertIn("cutoff instant itself refuses", names)
        self.assertIn("one direct operation", names)
        self.assertIn("registered prefix and released payment stay unchanged", names)
        self.assertIn("does not burn or reopen", names)


if __name__ == "__main__":
    unittest.main()
