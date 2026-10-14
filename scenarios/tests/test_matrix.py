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

    def test_a_scenario_that_raised_marks_every_case_it_serves(self):
        """Assertions that passed before the exception are not acceptance."""
        broken = {"scenarios": [{
            "scenarioId": "DEMO-X", "cases": ["T-17", "T-19"], "passed": False,
            "error": "RuntimeError: the scenario stopped half way",
            "counts": {"passed": 2, "failed": 0, "blocked": 0, "not-run": 0},
            "expectations": [{"name": "an early check", "cases": ["T-17"],
                              "outcome": "passed"}]}]}
        built = matrix.build({"commit": "a" * 40}, {"runId": "local-test"}, broken, None)
        rows = {row["case"]: row for row in built["rows"]}
        self.assertEqual(rows["T-17"]["localOutcome"], "error")
        self.assertEqual(rows["T-19"]["localOutcome"], "error")
        self.assertEqual(rows["T-17"]["scenarioAssertionCounts"]["passed"], 1)
        self.assertIn("the scenario stopped half way",
                      rows["T-17"]["scenarioProblems"][0]["error"])
        self.assertFalse(built["allCasesSound"])
        self.assertIn("T-17", built["unsoundCases"])

    def test_a_scenario_that_did_not_pass_marks_its_cases_failed(self):
        report = {"scenarios": [{
            "scenarioId": "DEMO-Y", "cases": ["T-11"], "passed": False, "error": None,
            "counts": {"passed": 1, "failed": 0, "blocked": 1, "not-run": 0},
            "expectations": [{"name": "an early check", "cases": ["T-11"],
                              "outcome": "passed"}]}]}
        rows = {row["case"]: row
                for row in matrix.build({}, {}, report, None)["rows"]}
        self.assertEqual(rows["T-11"]["localOutcome"], "failed")

    def test_a_blocked_assertion_is_not_passed_even_beside_passing_ones(self):
        report = {"scenarios": [{
            "scenarioId": "DEMO-Z", "cases": ["T-12"], "passed": False, "error": None,
            "counts": {"passed": 1, "failed": 0, "blocked": 1, "not-run": 0},
            "expectations": [{"name": "ok", "cases": ["T-12"], "outcome": "passed"},
                             {"name": "blocked", "cases": ["T-12"], "outcome": "blocked"}]}]}
        rows = {row["case"]: row
                for row in matrix.build({}, {}, report, None)["rows"]}
        self.assertIn(rows["T-12"]["localOutcome"], ("failed", "blocked"))

    def test_a_clean_run_reports_every_case_sound(self):
        self.assertTrue(self.built["allCasesSound"])
        self.assertEqual(self.built["unsoundCases"], [])

    def test_no_row_claims_a_local_run_is_real_acceptance(self):
        self.assertIn("never marked passed", self.built["note"])
        for row in self.built["rows"]:
            if row["remainingRealEvidence"]:
                self.assertNotEqual(row["localOutcome"], "passed")


if __name__ == "__main__":
    unittest.main()
