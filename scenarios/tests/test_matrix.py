"""The matrix must never mark an unexecuted obligation as passed."""
import unittest
from pathlib import Path

from scenarios import matrix
from scenarios.demos import DEMOS
from scenarios.harness import run_all
from scenarios.paths import PATH_CONTRACTS

ROOT = str(Path(__file__).resolve().parents[2])


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

    def test_a_scenario_that_did_not_pass_marks_its_cases_by_its_own_reason(self):
        """Its counts say a check was blocked, so the case is blocked.

        This case previously asserted "failed", which was the defect item 5
        names: a scenario that merely could not run a check was reported the
        same way as one that got a wrong answer.
        """
        report = {"scenarios": [{
            "scenarioId": "DEMO-Y", "cases": ["T-11"], "passed": False, "error": None,
            "counts": {"passed": 1, "failed": 0, "blocked": 1, "not-run": 0},
            "expectations": [{"name": "an early check", "cases": ["T-11"],
                              "outcome": "passed"}]}]}
        rows = {row["case"]: row
                for row in matrix.build({}, {}, report, None)["rows"]}
        self.assertEqual(rows["T-11"]["localOutcome"], "blocked")
        self.assertEqual(rows["T-11"]["scenarioProblems"][0]["status"], "blocked")

    def test_a_scenario_with_a_failed_assertion_marks_its_cases_failed(self):
        report = {"scenarios": [{
            "scenarioId": "DEMO-Y", "cases": ["T-11"], "passed": False, "error": None,
            "counts": {"passed": 1, "failed": 1, "blocked": 0, "not-run": 0},
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

    def _one_scenario(self, expectations, passed, error=None, **counts):
        tally = {"passed": 0, "failed": 0, "blocked": 0, "not-run": 0}
        tally.update(counts)
        return {"scenarios": [{"scenarioId": "DEMO-X", "cases": ["T-17"],
                               "passed": passed, "error": error, "counts": tally,
                               "expectations": expectations}]}

    def _case_outcome(self, report):
        rows = {row["case"]: row for row in matrix.build({}, {}, report, None)["rows"]}
        return rows["T-17"]["localOutcome"]

    def test_a_blocked_only_case_stays_blocked_rather_than_failed(self):
        """The reviewed defect: blocked became failed because passed was false."""
        outcome = self._case_outcome(self._one_scenario(
            [{"name": "b", "cases": ["T-17"], "outcome": "blocked"}],
            passed=False, blocked=1))
        self.assertEqual(outcome, "blocked")

    def test_blocked_beside_passing_assertions_is_still_blocked(self):
        outcome = self._case_outcome(self._one_scenario(
            [{"name": "p", "cases": ["T-17"], "outcome": "passed"},
             {"name": "b", "cases": ["T-17"], "outcome": "blocked"}],
            passed=False, blocked=1))
        self.assertEqual(outcome, "blocked")

    def test_a_real_failure_is_still_failed(self):
        outcome = self._case_outcome(self._one_scenario(
            [{"name": "f", "cases": ["T-17"], "outcome": "failed"}],
            passed=False, failed=1))
        self.assertEqual(outcome, "failed")

    def test_a_failure_outranks_a_block_in_the_same_case(self):
        outcome = self._case_outcome(self._one_scenario(
            [{"name": "f", "cases": ["T-17"], "outcome": "failed"},
             {"name": "b", "cases": ["T-17"], "outcome": "blocked"}],
            passed=False, failed=1, blocked=1))
        self.assertEqual(outcome, "failed")

    def test_a_raised_scenario_is_an_error_not_a_failure(self):
        outcome = self._case_outcome(self._one_scenario(
            [{"name": "p", "cases": ["T-17"], "outcome": "passed"}],
            passed=False, error="RuntimeError: boom"))
        self.assertEqual(outcome, "error")

    def test_a_case_covered_only_by_obligations_is_not_run(self):
        """It has scenario coverage, so it is not merely unit-suite-only."""
        outcome = self._case_outcome(self._one_scenario(
            [{"name": "n", "cases": ["T-17"], "outcome": "not-run"}],
            passed=True, **{"not-run": 1}))
        self.assertEqual(outcome, "not-run")

    def test_a_scenario_that_concluded_nothing_is_incomplete(self):
        """Not a pass, and not a failure either: no answer was recorded."""
        outcome = self._case_outcome(self._one_scenario([], passed=False))
        self.assertEqual(outcome, "incomplete")

    def test_partial_assertions_before_an_exception_are_preserved(self):
        report = self._one_scenario(
            [{"name": "early", "cases": ["T-17"], "outcome": "passed",
              "expected": {"a": 1}, "observed": {"a": 1}}],
            passed=False, error="RuntimeError: stopped half way")
        rows = {row["case"]: row for row in matrix.build({}, {}, report, None)["rows"]}
        row = rows["T-17"]
        self.assertEqual(row["localOutcome"], "error")
        self.assertEqual(row["scenarioAssertionCounts"]["passed"], 1,
                         "the partial assertion is still recorded")
        self.assertIn("stopped half way", row["scenarioProblems"][0]["error"])

    def test_the_four_states_are_never_collapsed(self):
        outcomes = {
            "error": self._one_scenario(
                [{"name": "p", "cases": ["T-17"], "outcome": "passed"}],
                passed=False, error="boom"),
            "failed": self._one_scenario(
                [{"name": "f", "cases": ["T-17"], "outcome": "failed"}],
                passed=False, failed=1),
            "blocked": self._one_scenario(
                [{"name": "b", "cases": ["T-17"], "outcome": "blocked"}],
                passed=False, blocked=1),
            "not-run": self._one_scenario(
                [{"name": "n", "cases": ["T-17"], "outcome": "not-run"}],
                passed=True, **{"not-run": 1}),
        }
        seen = {name: self._case_outcome(report) for name, report in outcomes.items()}
        self.assertEqual(seen, {"error": "error", "failed": "failed",
                                "blocked": "blocked", "not-run": "not-run"})
        self.assertEqual(len(set(seen.values())), 4)

    def test_an_incomplete_or_blocked_case_is_never_sound(self):
        for report in (self._one_scenario([], passed=False),
                       self._one_scenario(
                           [{"name": "b", "cases": ["T-17"], "outcome": "blocked"}],
                           passed=False, blocked=1)):
            built = matrix.build({}, {}, report, None)
            with self.subTest(outcome=self._case_outcome(report)):
                self.assertFalse(built["allCasesSound"])
                self.assertIn("T-17", built["unsoundCases"])

    def test_a_clean_run_reports_every_case_sound(self):
        self.assertTrue(self.built["allCasesSound"])
        self.assertEqual(self.built["unsoundCases"], [])

    def test_no_row_claims_a_local_run_is_real_acceptance(self):
        self.assertIn("never marked passed", self.built["note"])
        for row in self.built["rows"]:
            if row["remainingRealEvidence"]:
                self.assertNotEqual(row["localOutcome"], "passed")


class RequirementCoverage(unittest.TestCase):
    """Every approved requirement is accounted for, one way or the other."""

    def setUp(self):
        self.coverage = matrix.requirement_coverage()

    def test_no_requirement_is_left_unaccounted_for(self):
        self.assertEqual(self.coverage["unclaimed"], [],
                         "a requirement no case claims and no record excuses")
        self.assertTrue(self.coverage["complete"])

    def test_no_case_claims_a_requirement_that_was_never_declared(self):
        self.assertEqual(self.coverage["unknown"], [])

    def test_the_declared_set_and_the_accounted_set_agree(self):
        accounted = (set(self.coverage["claimedByCases"])
                     | set(self.coverage["notLocallyTestable"]))
        self.assertEqual(accounted, set(matrix.DECLARED_REQUIREMENTS))
        self.assertEqual(self.coverage["declared"],
                         len(set(matrix.DECLARED_REQUIREMENTS)))

    def test_every_unproven_requirement_names_a_reason_and_an_owner(self):
        self.assertTrue(matrix.NOT_LOCALLY_TESTABLE)
        for name, entry in sorted(matrix.NOT_LOCALLY_TESTABLE.items()):
            with self.subTest(requirement=name):
                self.assertIn(name, matrix.DECLARED_REQUIREMENTS)
                self.assertTrue(entry["reason"])
                self.assertTrue(entry["owner"])
                self.assertNotIn(name, self.coverage["claimedByCases"],
                                 "it is either shown locally or it is not")

    def test_each_claimed_requirement_names_the_cases_that_claim_it(self):
        for name, cases in sorted(self.coverage["claimedByCases"].items()):
            with self.subTest(requirement=name):
                self.assertTrue(cases)
                for case in cases:
                    self.assertIn(name, matrix.CASE_REQUIREMENTS[case])

    def test_the_built_matrix_carries_the_reconciliation(self):
        built = matrix.build({}, {})
        self.assertTrue(built["requirementCoverage"]["complete"])
        self.assertEqual(built["requirementCoverage"]["declared"], 55)

    def test_no_requirement_text_or_private_locator_is_reproduced(self):
        """Identifiers only: the approved requirements stay private."""
        source = Path(ROOT, "scenarios/matrix.py").read_text(encoding="utf-8")
        self.assertTrue(all(ord(character) < 128 for character in source),
                        "the public source stays ASCII")
        for forbidden in ("drive.google.com", "docs.google.com", "/file/d/"):
            self.assertNotIn(forbidden, source)


class NoMarketMakingSurface(unittest.TestCase):
    """EX-MATCH-02, asserted rather than assumed.

    The default implementation must not carry automated market making, strategy
    yield, platform proprietary trading or a commercial fee rate. These are
    absences, so the test is a negative one over the domain's own surface.
    """

    FORBIDDEN = ("market_maker", "market_making", "strategy_yield", "proprietary",
                 "fee_rate", "maker_fee", "taker_fee", "commission", "spread_bps",
                 "platform_profit")

    def test_the_domain_surface_carries_no_such_feature(self):
        from exchange import ledger, model, settlement
        for module in (ledger, model, settlement):
            names = " ".join(dir(module)).lower()
            for forbidden in self.FORBIDDEN:
                with self.subTest(module=module.__name__, name=forbidden):
                    self.assertNotIn(forbidden, names)

    def test_the_domain_source_names_no_such_feature(self):
        for name in ("ledger.py", "model.py", "settlement.py"):
            source = Path(ROOT, "exchange", name).read_text(encoding="utf-8").lower()
            for forbidden in self.FORBIDDEN:
                with self.subTest(file=name, name=forbidden):
                    self.assertNotIn(forbidden, source)

    def test_matching_uses_deterministic_counterparties_and_test_prices(self):
        from exchange import fixtures
        self.assertEqual(fixtures.QUOTE_ASSET, "local-test-quote")
        self.assertIn("NOT", fixtures.QUOTE_ASSET.upper() + " NOT A DEPLOYED TOKEN")
        for account in (fixtures.A, fixtures.B, fixtures.C, fixtures.D):
            with self.subTest(account=account):
                self.assertRegex(account, r"\A0x[0-9a-f]{40}\Z")

    def test_the_requirement_is_claimed_by_a_case(self):
        self.assertIn("EX-MATCH-02",
                      matrix.requirement_coverage()["claimedByCases"])

if __name__ == "__main__":
    unittest.main()
