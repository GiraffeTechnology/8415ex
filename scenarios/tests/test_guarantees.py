"""The guarantee contracts must really pass, and must really be able to fail.

Ten acceptance cases were evidenced only by the domain's own suite, so the
delivery report said nothing about them. These contracts close that, which is
only worth anything if a contract that stopped holding would be recorded as
failed rather than quietly recorded as something else.
"""
import unittest
from pathlib import Path

from exchange.errors import DomainError

from scenarios import guarantees, manifest, matrix
from scenarios.harness import Scenario, run_all

ROOT = str(Path(__file__).resolve().parents[2])


class AsRun(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.report = run_all(list(guarantees.GUARANTEE_CONTRACTS))

    def test_every_contract_passes(self):
        for scenario in self.report["scenarios"]:
            with self.subTest(scenario=scenario["scenarioId"]):
                self.assertIsNone(scenario["error"])
                failed = [entry["name"] for entry in scenario["expectations"]
                          if entry["outcome"] == "failed"]
                self.assertEqual(failed, [])
                self.assertTrue(scenario["passed"])
        self.assertTrue(self.report["allPassed"])

    def test_the_report_records_real_assertions_not_an_empty_pass(self):
        self.assertEqual(self.report["scenariosTotal"],
                         len(guarantees.GUARANTEE_CONTRACTS))
        self.assertGreater(self.report["totals"]["passed"], 50)
        for scenario in self.report["scenarios"]:
            with self.subTest(scenario=scenario["scenarioId"]):
                self.assertTrue(scenario["expectations"],
                                "a contract with no expectation passes by saying nothing")
                self.assertTrue(scenario["setup"],
                                "every contract states the fixtures it ran on")

    def test_two_runs_give_the_same_digest(self):
        again = run_all(list(guarantees.GUARANTEE_CONTRACTS))
        self.assertEqual(again["deterministicDigest"],
                         self.report["deterministicDigest"])

    def test_every_expectation_names_a_real_case(self):
        for scenario in self.report["scenarios"]:
            for entry in scenario["expectations"]:
                with self.subTest(expectation=entry["name"]):
                    self.assertTrue(entry["cases"],
                                    "an expectation serving no case evidences nothing")
                    for case in entry["cases"]:
                        self.assertIn(case, matrix.CASE_REQUIREMENTS)

    def test_the_declared_cases_are_the_ones_the_contracts_assert(self):
        asserted = set()
        for scenario in self.report["scenarios"]:
            for entry in scenario["expectations"]:
                if entry["outcome"] == "passed":
                    asserted.update(entry["cases"])
        # The not-run obligations name Stage 5 cases, which these contracts do
        # not claim to cover; only what actually passed counts here.
        self.assertTrue(set(guarantees.COVERED_CASES) <= asserted,
                        sorted(set(guarantees.COVERED_CASES) - asserted))

    def test_the_contracts_say_what_they_are_not(self):
        described = guarantees.coverage_map()
        self.assertEqual(described["coveredCases"], list(guarantees.COVERED_CASES))
        self.assertEqual([entry["scenarioId"] for entry in described["contracts"]],
                         [contract.scenario_id
                          for contract in guarantees.GUARANTEE_CONTRACTS])
        joined = " ".join(described["isNot"])
        self.assertIn("not real execution", joined)
        self.assertIn("not a second copy of the domain suite", joined)

    def test_real_execution_is_still_owed_rather_than_implied(self):
        obligations = [entry for scenario in self.report["scenarios"]
                       for entry in scenario["expectations"]
                       if entry["outcome"] == "not-run"]
        self.assertTrue(obligations, "a local contract cannot discharge real execution")
        for entry in obligations:
            with self.subTest(obligation=entry["name"]):
                self.assertEqual(entry["observed"], "NOT_RUN")
                self.assertTrue(entry["detail"])


class WhatTheMatrixSaysNow(unittest.TestCase):
    """The point of the exercise, stated as the matrix states it."""

    @classmethod
    def setUpClass(cls):
        cls.source = manifest.source_identity(ROOT)
        cls.identity = {"runId": "test-run"}
        cls.report = run_all(list(guarantees.GUARANTEE_CONTRACTS))

    def rows(self, **reports):
        built = matrix.build(self.source, self.identity, **reports)
        return {row["case"]: row for row in built["rows"]}

    def test_the_ten_cases_had_only_the_domain_suite_before(self):
        """The negative control for the whole batch.

        Without the contracts the same ten cases read ``unit-suite-only``, so
        the new outcome comes from assertions that were recorded and not from a
        relabelling of the matrix.
        """
        before = self.rows()
        for case in guarantees.COVERED_CASES:
            with self.subTest(case=case):
                self.assertEqual(before[case]["localOutcome"], "unit-suite-only")
                self.assertEqual(before[case]["scenarios"], [])

    def test_each_case_now_names_the_contract_that_recorded_it(self):
        after = self.rows(guarantee_report=self.report)
        for case in guarantees.COVERED_CASES:
            with self.subTest(case=case):
                self.assertEqual(after[case]["localOutcome"], "passed")
                self.assertTrue(after[case]["scenarios"],
                                "a reviewer has to be able to find the evidence")
                for scenario_id in after[case]["scenarios"]:
                    self.assertTrue(scenario_id.startswith("GUARANTEE-"))
                self.assertGreater(after[case]["scenarioAssertionCounts"]["passed"], 0)

    def test_this_packages_own_checks_stay_unit_suite_only(self):
        """T-39 and T-40 are this package's scan and observations.

        They are asserted by the preparation suite and are not scenario-shaped,
        so a contract claiming them would be a label rather than evidence.
        """
        after = self.rows(guarantee_report=self.report)
        for case in ("T-39", "T-40"):
            with self.subTest(case=case):
                self.assertEqual(after[case]["localOutcome"], "unit-suite-only")

    def test_a_failing_contract_reaches_the_matrix_as_a_failure(self):
        def wrong(recorder):
            recorder.expect("a guarantee that stopped holding", ("T-01",), "expected",
                            "observed")

        broken = run_all([Scenario("GUARANTEE-BROKEN", "a contract that no longer holds",
                                   ("T-01",), guarantees.CONTRACT_PATH, wrong)])
        self.assertFalse(broken["allPassed"])
        after = self.rows(guarantee_report=broken)
        self.assertEqual(after["T-01"]["localOutcome"], "failed")
        built = matrix.build(self.source, self.identity, guarantee_report=broken)
        self.assertIn("T-01", built["unsoundCases"])
        self.assertFalse(built["allCasesSound"])

    def test_a_contract_that_raises_reaches_the_matrix_as_an_error(self):
        def explodes(recorder):
            recorder.expect("something that did hold", ("T-09",), 1, 1)
            raise DomainError("EX_SOMETHING_ELSE", "the fixture moved under the contract")

        raised = run_all([Scenario("GUARANTEE-RAISED", "a contract that raised",
                                   ("T-09",), guarantees.CONTRACT_PATH, explodes)])
        self.assertFalse(raised["allPassed"])
        after = self.rows(guarantee_report=raised)
        self.assertEqual(after["T-09"]["localOutcome"], "error",
                         "an assertion that passed before the exception is not acceptance")


class RecordingARefusal(unittest.TestCase):
    """``_refusal`` is how every refusal in these contracts is recorded."""

    def test_a_domain_refusal_is_recorded_as_its_own_code(self):
        def refuse():
            raise DomainError("EX_SOMETHING_REFUSED", "because")

        self.assertEqual(guarantees._refusal(refuse), "EX_SOMETHING_REFUSED")

    def test_nothing_refused_is_recorded_as_accepted_not_as_a_pass(self):
        """The negative control that matters most.

        If a refusal that stopped happening were recorded as anything that could
        equal the expected code, every refusal expectation in this module would
        pass for the wrong reason.
        """
        self.assertEqual(guarantees._refusal(lambda: None), "accepted")

    def test_another_exception_is_recorded_with_its_type_not_as_a_code(self):
        def wrong_kind():
            raise ValueError("not a domain refusal")

        recorded = guarantees._refusal(wrong_kind)
        self.assertTrue(recorded.startswith("ValueError:"), recorded)
        self.assertNotEqual(recorded, "accepted")


if __name__ == "__main__":
    unittest.main()
