"""Each registrar route needs its own result; one never stands in for another."""
import unittest

from exchange.model import REGISTRATION_PATHS
from scenarios.harness import run_all
from scenarios.paths import PATH_CONTRACTS, coverage_map


class PathContracts(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.report = run_all(list(PATH_CONTRACTS))
        cls.by_id = {scenario["scenarioId"]: scenario for scenario in cls.report["scenarios"]}

    def test_there_is_one_contract_result_per_route(self):
        self.assertEqual(len(PATH_CONTRACTS), 3)
        self.assertEqual(sorted(self.by_id), sorted(f"PATH-{path}" for path in REGISTRATION_PATHS))

    def test_every_route_passes_on_its_own(self):
        for scenario_id, scenario in sorted(self.by_id.items()):
            with self.subTest(route=scenario_id):
                self.assertIsNone(scenario["error"])
                self.assertTrue(scenario["passed"])
                self.assertEqual([e for e in scenario["expectations"]
                                  if e["outcome"] in ("failed", "blocked")], [])

    def test_each_route_records_the_same_contract_checks(self):
        shapes = {scenario_id: tuple(e["name"] for e in scenario["expectations"])
                  for scenario_id, scenario in self.by_id.items()}
        self.assertEqual(len(set(shapes.values())), 1,
                         "the three routes are held to one contract")

    def test_each_route_is_labelled_simulated(self):
        for scenario_id, scenario in sorted(self.by_id.items()):
            with self.subTest(route=scenario_id):
                self.assertTrue(scenario["setup"]["simulated"])
                self.assertIn("simulated", scenario["setup"]["label"])

    def test_a_route_refuses_another_routes_result(self):
        for scenario in self.by_id.values():
            names = [e["name"] for e in scenario["expectations"]]
            self.assertIn("a result from another path advances nothing", names)
            self.assertIn("a request filed to another path's adapter is refused", names)

    def test_each_route_still_owes_real_integration(self):
        for scenario_id, scenario in sorted(self.by_id.items()):
            with self.subTest(route=scenario_id):
                not_run = [e for e in scenario["expectations"] if e["outcome"] == "not-run"]
                self.assertEqual(len(not_run), 1)
                self.assertEqual(not_run[0]["observed"], "NOT_RUN")


class CoverageMap(unittest.TestCase):

    def setUp(self):
        self.map = coverage_map()

    def test_every_route_is_listed_with_its_own_result(self):
        self.assertEqual(sorted(self.map["paths"]), sorted(REGISTRATION_PATHS))
        self.assertEqual(sorted(self.map["contractResultPerPath"]),
                         sorted(f"PATH-{path}" for path in REGISTRATION_PATHS))

    def test_every_scenario_names_exactly_one_main_route(self):
        self.assertEqual(len(self.map["mainPathPerScenario"]), 6)
        for scenario_id, path in self.map["mainPathPerScenario"].items():
            self.assertIn(path, REGISTRATION_PATHS, scenario_id)

    def test_every_route_is_the_main_route_for_at_least_one_scenario(self):
        for path, scenarios in self.map["scenariosPerPath"].items():
            self.assertTrue(scenarios, f"{path} is no scenario's main route")

    def test_the_map_says_one_route_does_not_establish_another(self):
        self.assertIn("does not", self.map["note"])
        self.assertIn("eighteen", self.map["note"])


if __name__ == "__main__":
    unittest.main()
