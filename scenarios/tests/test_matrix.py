"""The matrix must never mark an unexecuted obligation as passed."""
import unittest

from scenarios import matrix
from scenarios.demos import DEMOS
from scenarios.harness import run_all
from scenarios.paths import PATH_CONTRACTS


class Matrix(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.scenario_report = run_all(list(DEMOS))
        cls.path_report = run_all(list(PATH_CONTRACTS))
        cls.built = matrix.build({"commit": "a" * 40, "tree": "b" * 40},
                                 {"runId": "local-test"},
                                 cls.scenario_report, cls.path_report)
        cls.rows = {row["case"]: row for row in cls.built["rows"]}

    def test_every_case_in_the_requirement_matrix_has_a_row(self):
        self.assertEqual(len(self.built["rows"]), 40)
        self.assertEqual(sorted(self.rows), sorted(matrix.CASE_REQUIREMENTS))

    def test_every_row_names_requirements_a_stage_and_an_implementation(self):
        for case, row in sorted(self.rows.items()):
            with self.subTest(case=case):
                self.assertTrue(row["requirements"])
                self.assertIn("stage", row)
                self.assertTrue(row["implementation"])
                self.assertTrue(row["unitCoverage"])

    def test_the_stage_five_obligations_are_never_passed(self):
        for case in ("T-35", "T-36", "T-37", "T-38"):
            with self.subTest(case=case):
                self.assertEqual(self.rows[case]["localOutcome"], "not-run")
                self.assertTrue(self.rows[case]["remainingRealEvidence"])

    def test_a_row_with_scenario_coverage_reports_passed(self):
        self.assertEqual(self.rows["T-17"]["localOutcome"], "passed")
        self.assertIn("DEMO-03", self.rows["T-17"]["scenarios"])
        self.assertGreater(self.rows["T-17"]["scenarioAssertionCounts"]["passed"], 0)

    def test_the_partly_local_cases_say_why(self):
        for case in ("T-19", "T-21", "T-22", "T-24", "T-25", "T-32"):
            with self.subTest(case=case):
                self.assertTrue(self.rows[case]["partiallyLocal"])

    def test_the_source_and_run_identity_are_carried(self):
        self.assertEqual(self.built["sourceIdentity"]["commit"], "a" * 40)
        self.assertEqual(self.built["runIdentity"]["runId"], "local-test")

    def test_the_tally_is_consistent_with_the_rows(self):
        counted = {}
        for row in self.built["rows"]:
            counted[row["localOutcome"]] = counted.get(row["localOutcome"], 0) + 1
        self.assertEqual(self.built["localOutcomeCounts"], dict(sorted(counted.items())))

    def test_no_row_claims_a_local_run_is_real_acceptance(self):
        self.assertIn("never marked passed", self.built["note"])
        for row in self.built["rows"]:
            if row["remainingRealEvidence"]:
                self.assertNotEqual(row["localOutcome"], "passed")


if __name__ == "__main__":
    unittest.main()
