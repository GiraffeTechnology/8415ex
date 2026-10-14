"""A command record must come from an execution, or say it did not run.

These are the regressions for the fabricated-success defect: a command that
failed, timed out, was killed, could not start, or was never executed must not
be able to produce an exit-0 "passed" record, directly or through the bundle.
"""
import os
import unittest
from pathlib import Path

from scenarios import cli, execution, validation

ROOT = str(Path(__file__).resolve().parents[2])


class RealExecution(unittest.TestCase):

    def test_a_successful_command_records_its_real_output(self):
        record = execution.run_command(("python3", "-c", "print('hello from the real run')"))
        self.assertEqual(record["outcome"], "passed")
        self.assertEqual(record["exitCode"], 0)
        self.assertTrue(record["executed"])
        self.assertIn("hello from the real run", record["stdout"]["tail"])
        self.assertRegex(record["stdout"]["sha256"], r"\A[0-9a-f]{64}\Z")
        self.assertRegex(record["startedAt"], r"\AZ?\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ\Z")
        self.assertEqual(validation.validate_command_record(record), ())

    def test_a_failing_command_cannot_be_recorded_as_a_pass(self):
        record = execution.run_command(("python3", "-c", "import sys; sys.exit(3)"))
        self.assertEqual(record["outcome"], "failed")
        self.assertEqual(record["exitCode"], 3)
        self.assertEqual(validation.validate_command_record(record), ())
        forged = dict(record, outcome="passed")
        self.assertIn("EX_EVIDENCE_OUTCOME_MISMATCH",
                      validation.validate_command_record(forged))

    def test_a_failing_suite_reaches_the_record_as_failed(self):
        program = ("import unittest\n"
                   "class T(unittest.TestCase):\n"
                   "    def test_it(self):\n"
                   "        self.assertTrue(False)\n"
                   "unittest.main()\n")
        record = execution.run_command(("python3", "-c", program))
        self.assertEqual(record["outcome"], "failed")
        self.assertNotEqual(record["exitCode"], 0)
        self.assertIn("FAILED", record["stderr"]["tail"])

    def test_a_timeout_is_not_a_failure_and_carries_no_exit_code(self):
        record = execution.run_command(("python3", "-c", "import time; time.sleep(30)"),
                                       timeout=1)
        self.assertEqual(record["outcome"], "timeout")
        self.assertIsNone(record["exitCode"])
        self.assertEqual(record["timeoutSeconds"], 1)

    def test_a_signalled_command_is_not_an_ordinary_failure(self):
        record = execution.run_command(
            ("python3", "-c", "import os, signal; os.kill(os.getpid(), signal.SIGKILL)"))
        self.assertEqual(record["outcome"], "signalled")
        self.assertLess(record["exitCode"], 0)
        self.assertEqual(record["signal"], 9)

    def test_a_command_that_cannot_start_is_an_error_not_a_pass(self):
        record = execution.run_command(("no-such-command-for-this-test",))
        self.assertEqual(record["outcome"], "error")
        self.assertIsNone(record["exitCode"])
        self.assertIn("could not be started", record["detail"])

    def test_the_four_unexecuted_and_failed_shapes_stay_distinct(self):
        self.assertEqual(len({execution.run_command(("python3", "-c", "import sys;sys.exit(1)"))
                              ["outcome"],
                              execution.run_command(("python3", "-c", "import time;"
                                                     "time.sleep(30)"), timeout=1)["outcome"],
                              execution.run_command(("no-such-command-for-this-test",))
                              ["outcome"],
                              execution.not_run("x", "y")["outcome"]}), 4)


class UnexecutedRecords(unittest.TestCase):

    def test_a_not_run_record_carries_no_result_at_all(self):
        record = execution.not_run("python3 -B -m unittest discover", "not executed here")
        self.assertEqual(record["outcome"], "not-run")
        self.assertIsNone(record["exitCode"])
        self.assertIsNone(record["startedAt"])
        self.assertIsNone(record["finishedAt"])
        self.assertFalse(record["executed"])
        self.assertEqual(validation.validate_command_record(record), ())

    def test_a_pending_record_is_not_a_result_either(self):
        record = execution.pending("python3 -B -m unittest discover", "queued")
        self.assertEqual(record["outcome"], "pending")
        self.assertIsNone(record["exitCode"])
        self.assertEqual(validation.validate_command_record(record), ())

    def test_a_not_run_record_with_a_success_code_is_refused(self):
        forged = dict(execution.not_run("x", "y"), exitCode=0)
        self.assertIn("EX_EVIDENCE_UNEXECUTED_EXIT_CODE",
                      validation.validate_command_record(forged))

    def test_a_self_record_cannot_be_written_before_the_exit_code_is_known(self):
        with self.assertRaises(ValueError):
            execution.self_record("x", None, "2026-10-14T00:00:00Z", "2026-10-14T00:00:01Z")


class BundleRecords(unittest.TestCase):
    """The bundle must not invent a result for a command it did not run."""

    @classmethod
    def setUpClass(cls):
        cls.bundle = cli._bundle(ROOT)

    def test_the_bundle_records_no_command_result_before_it_is_sealed(self):
        for record in self.bundle["commands"]:
            with self.subTest(command=record["command"]):
                self.assertNotEqual(record.get("outcome"), "passed")
                self.assertIsNone(record.get("exitCode"))

    def test_the_unit_suites_are_not_run_unless_they_are_executed(self):
        suites = [record for record in self.bundle["commands"] if "unittest" in record["command"]]
        self.assertEqual(len(suites), 2)
        for record in suites:
            with self.subTest(command=record["command"]):
                self.assertEqual(record["outcome"], "not-run")
                self.assertIsNone(record["exitCode"])
                self.assertFalse(record["executed"])
                self.assertIn("--execute-suites", record["reason"])

    def test_a_not_run_suite_is_reported_as_an_outstanding_obligation(self):
        obligations = {entry["obligation"] for entry in self.bundle["notRun"]}
        self.assertIn("scenario preparation suite", obligations)
        self.assertIn("domain suite", obligations)

    def test_sealing_takes_the_outcome_from_the_real_exit_status(self):
        failed = cli.seal(cli._bundle(ROOT), 1)
        self.assertEqual(failed["commands"][0]["outcome"], "failed")
        self.assertEqual(failed["commands"][0]["exitCode"], 1)
        self.assertTrue(failed["commands"][0]["selfReported"])

    def test_every_command_record_passes_the_evidence_validator(self):
        sealed = cli.seal(cli._bundle(ROOT), 0)
        for record in sealed["commands"]:
            with self.subTest(command=record["command"]):
                self.assertEqual(validation.validate_command_record(record), ())

    def test_an_executed_suite_records_its_real_status(self):
        """Stand-in suites, so the proof does not re-run the whole repository.

        One passes and one fails. The point is that the bundle reports what each
        one actually did, in a run where a real command did fail.
        """
        passing = ("python3", "-c", "import sys; print('OK', file=sys.stderr)")
        failing = ("python3", "-c",
                   "import sys; print('FAILED', file=sys.stderr); sys.exit(1)")
        original = cli.UNIT_SUITES
        cli.UNIT_SUITES = (("passing stand-in", passing), ("failing stand-in", failing))
        try:
            bundle = cli._bundle(ROOT, execute_suites=True)
        finally:
            cli.UNIT_SUITES = original
        executed = [record for record in bundle["commands"] if record["executed"]]
        self.assertEqual([record["outcome"] for record in executed], ["passed", "failed"])
        self.assertEqual([record["exitCode"] for record in executed], [0, 1])
        for record in executed:
            with self.subTest(command=record["command"]):
                self.assertIn(record["outcome"], validation.EXECUTED_OUTCOMES)
                self.assertGreater(record["stderr"]["bytes"], 0)
                self.assertEqual(validation.validate_command_record(record), ())
        # A command that really failed must take the run down with it.
        self.assertFalse(bundle["allLocalPassed"])
        self.assertTrue(any("failed" in reason for reason in bundle["blocking"]))

    def test_a_nested_run_refuses_to_execute_the_suites_again(self):
        """The scenario suite exercises this bundle, so nesting must stop."""
        previous = os.environ.get(cli.NESTING_GUARD_ENV)
        os.environ[cli.NESTING_GUARD_ENV] = "1"
        try:
            bundle = cli._bundle(ROOT, execute_suites=True)
        finally:
            if previous is None:
                del os.environ[cli.NESTING_GUARD_ENV]
            else:
                os.environ[cli.NESTING_GUARD_ENV] = previous
        for record in bundle["commands"]:
            with self.subTest(command=record["command"]):
                self.assertEqual(record["outcome"], "not-run")
                self.assertIsNone(record["exitCode"])
                self.assertIn("re-enter the run", record["reason"])


if __name__ == "__main__":
    unittest.main()
