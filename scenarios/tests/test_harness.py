"""The harness must record a disagreement rather than lose it."""
import unittest

from scenarios.harness import Scenario, run_all


def _scenario(body, scenario_id="DEMO-TEST", cases=("T-00",)):
    return Scenario(scenario_id, "probe", cases, "REG_DIRECT", body)


class Recording(unittest.TestCase):

    def test_a_match_is_recorded_as_passed(self):
        result = _scenario(lambda r: r.expect("equal", ("T-00",), 4, 4)).run()
        self.assertEqual(result.counts()["passed"], 1)
        self.assertTrue(result.passed)

    def test_a_mismatch_is_recorded_as_a_genuine_failure(self):
        result = _scenario(lambda r: r.expect("unequal", ("T-00",), 5, 4)).run()
        self.assertEqual(result.counts()["failed"], 1)
        self.assertFalse(result.passed)
        self.assertEqual(result.failures[0].expected, 5)
        self.assertEqual(result.failures[0].observed, 4)

    def test_a_blocked_check_fails_the_scenario(self):
        def body(recorder):
            recorder.expect("fine", ("T-00",), 1, 1)
            recorder.blocked("needs something", ("T-00",), "a dependency is missing")
        result = _scenario(body).run()
        self.assertEqual(result.counts()["blocked"], 1)
        self.assertFalse(result.passed)

    def test_a_not_run_obligation_does_not_fail_or_pass_the_scenario(self):
        def body(recorder):
            recorder.expect("fine", ("T-00",), 1, 1)
            recorder.not_run("chain evidence", ("T-35",), "no deployment")
        result = _scenario(body).run()
        self.assertEqual(result.counts()["not-run"], 1)
        self.assertEqual(result.counts()["failed"], 0)
        self.assertTrue(result.passed, "an unmet real obligation is reported, not a local failure")

    def test_an_exception_is_captured_and_fails_the_scenario(self):
        def body(recorder):
            recorder.expect("before", ("T-00",), 1, 1)
            raise ValueError("a real defect")
        result = _scenario(body).run()
        self.assertIn("ValueError: a real defect", result.error)
        self.assertFalse(result.passed)

    def test_a_scenario_with_no_expectation_does_not_pass(self):
        result = _scenario(lambda r: r.step("nothing checked")).run()
        self.assertFalse(result.passed)

    def test_the_setup_and_steps_are_recorded(self):
        def body(recorder):
            recorder.describe_setup(accounts={"A": "0x1"}, prices={"AB": 5})
            recorder.step("first", ok=True)
            recorder.expect("fine", ("T-00",), 1, 1)
        record = _scenario(body).run().as_record()
        self.assertEqual(record["setup"]["prices"], {"AB": 5})
        self.assertEqual(record["steps"][0]["name"], "first")
        self.assertIn("no deployment", record["scope"])


class Determinism(unittest.TestCase):

    def test_two_runs_of_the_same_body_share_a_digest(self):
        body = lambda r: r.expect("fine", ("T-00",), 7, 7)  # noqa: E731
        first = run_all([_scenario(body)])
        second = run_all([_scenario(body)])
        self.assertEqual(first["deterministicDigest"], second["deterministicDigest"])

    def test_a_different_observation_changes_the_digest(self):
        first = run_all([_scenario(lambda r: r.expect("v", ("T-00",), 7, 7))])
        second = run_all([_scenario(lambda r: r.expect("v", ("T-00",), 7, 8))])
        self.assertNotEqual(first["deterministicDigest"], second["deterministicDigest"])

    def test_the_report_totals_cover_every_outcome(self):
        def body(recorder):
            recorder.expect("a", ("T-00",), 1, 1)
            recorder.expect("b", ("T-00",), 1, 2)
            recorder.not_run("c", ("T-35",), "no deployment")
        report = run_all([_scenario(body)])
        self.assertEqual(report["totals"]["passed"], 1)
        self.assertEqual(report["totals"]["failed"], 1)
        self.assertEqual(report["totals"]["not-run"], 1)
        self.assertFalse(report["allPassed"])


if __name__ == "__main__":
    unittest.main()
