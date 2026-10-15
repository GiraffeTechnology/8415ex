"""Independent joining contracts; no producer edits or real execution claims."""
import copy
import unittest
from exchange import stage5
from scenarios import demos, harness, paths, matrix, handoff

class JoinedStage5Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.producer = harness.run_all(demos.DEMOS)
        cls.routes = harness.run_all(paths.PATH_CONTRACTS)
        cls.independent = {name: stage5.run_scenario(name) for name in stage5.SCENARIOS}

    def test_both_packages_complete_the_same_six_scenarios(self):
        self.assertEqual({r["scenarioId"] for r in self.producer["scenarios"]}, set(stage5.SCENARIOS))
        self.assertTrue(self.producer["allPassed"], self.producer)
        self.assertEqual(self.producer["scenariosPassed"], 6)
        for name, record in self.independent.items():
            self.assertEqual(record["status"], "passed", (name, record))
            self.assertTrue(record["simulated"])

    def test_case_and_main_path_contracts_agree(self):
        for scenario in demos.DEMOS:
            with self.subTest(scenario=scenario.scenario_id):
                independent = self.independent[scenario.scenario_id]
                self.assertEqual(set(scenario.cases), set(independent["cases"]))
                self.assertEqual(scenario.main_path, independent["path"])
                self.assertEqual(scenario.main_path, demos.MAIN_PATHS[scenario.scenario_id])

    def test_all_three_routes_have_their_own_completed_contract(self):
        records = self.routes["scenarios"]
        self.assertEqual({r["mainPath"] for r in records}, set(stage5.PATHS))
        self.assertEqual(len(records), 3)
        self.assertTrue(self.routes["allPassed"], self.routes)
        for record in records:
            self.assertTrue(record["passed"])
            self.assertIn("T-10", record["cases"])
            self.assertGreater(record["counts"]["passed"], 0)

    def test_matrix_does_not_promote_real_obligations(self):
        result = matrix.build({"kind": "joined-memory-input"}, {"kind": "actual-integration-test"},
                              self.producer, self.routes)
        by_case = {r["case"]: r for r in result["rows"]}
        self.assertEqual(len(by_case), 40)
        for case in ("T-35", "T-36", "T-37", "T-38"):
            self.assertEqual(by_case[case]["localOutcome"], "not-run")
            self.assertTrue(by_case[case]["remainingRealEvidence"])
        self.assertTrue(result["allCasesSound"])

    def test_partial_producer_failure_invalidates_every_affected_case(self):
        damaged = copy.deepcopy(self.producer)
        damaged["scenarios"][0]["error"] = "Injected joining-contract failure"
        damaged["scenarios"][0]["passed"] = False
        result = matrix.build({}, {}, damaged, self.routes)
        by_case = {r["case"]: r for r in result["rows"]}
        for case in damaged["scenarios"][0]["cases"]:
            self.assertEqual(by_case[case]["localOutcome"], "error")
            self.assertIn(case, result["unsoundCases"])
        self.assertFalse(result["allCasesSound"])

    def test_handoff_retains_all_six_scenarios_and_real_evidence_slots(self):
        delivery = handoff.build()
        self.assertEqual({r["scenarioId"] for r in delivery["scenarios"]}, set(stage5.SCENARIOS))
        for record in delivery["scenarios"]:
            self.assertEqual(record["mainPath"], demos.MAIN_PATHS[record["scenarioId"]])
            self.assertTrue(record["steps"])
            self.assertTrue(record["evidence"])
            self.assertTrue(all(value == "NOT_RUN" for value in record["evidence"].values()))
        for independent in self.independent.values():
            self.assertTrue(all(value == "NOT_RUN" for value in independent["realEvidence"].values()))

    def test_undecided_real_gas_policy_is_not_fabricated_by_join(self):
        for record in self.independent.values():
            self.assertEqual(record["fixtureConditions"]["gasUnit"], "synthetic")
            self.assertIn("D-04", record["fixtureConditions"]["gasDeductionPolicy"])
            self.assertEqual(record["realEvidence"]["realFees"], "NOT_RUN")
