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


class _WithoutNestingGuard(unittest.TestCase):
    """Tests about the outermost behaviour, run with the guard cleared.

    The scenario suite is itself one of the suites a bundle can execute, so this
    file may run inside a bundle's own subprocess with the guard set. These
    cases are about what the outer run does, so they clear it and put it back.
    """

    def setUp(self):
        self._guard = os.environ.pop(cli.NESTING_GUARD_ENV, None)

    def tearDown(self):
        if self._guard is None:
            os.environ.pop(cli.NESTING_GUARD_ENV, None)
        else:
            os.environ[cli.NESTING_GUARD_ENV] = self._guard


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


class GeneratedRecordsThroughTheValidator(_WithoutNestingGuard):
    """Item 2: real process records, not hand-written fixtures, validated.

    Every record in this class comes from an actual subprocess, or from an
    actual refusal to launch one. The point is that what the runner really
    produces is what the validator really accepts, and that a genuine failure
    stays a failure all the way through.
    """

    PROGRAMS = {
        "passed": ("python3", "-c", "import sys; print('ok'); sys.exit(0)"),
        "failed": ("python3", "-c", "import sys; print('bad', file=sys.stderr); sys.exit(7)"),
        "error": ("no-such-binary-for-this-test",),
        "timeout": ("python3", "-c", "import time; time.sleep(30)"),
        "signalled": ("python3", "-c",
                      "import os, signal; os.kill(os.getpid(), signal.SIGTERM)"),
    }

    @classmethod
    def setUpClass(cls):
        cls.generated = {}
        for outcome, argv in cls.PROGRAMS.items():
            cls.generated[outcome] = execution.run_command(
                argv, timeout=1 if outcome == "timeout" else 60)
        cls.generated["pending"] = execution.pending("later", "queued")
        cls.generated["not-run"] = execution.not_run("later", "owner supplies it")

    def _record(self, commands):
        """A record wrapper for the generated command records."""
        return {"schema": "8415ex-local-delivery-evidence/1", "runId": "generated-1",
                "commit": "a" * 40, "tree": "b" * 40, "worktreeClean": True,
                "commands": commands, "startedAt": "2026-10-15T10:00:00Z",
                "finishedAt": "2026-10-15T10:00:05Z",
                "scenarioDigest": "0x" + "c" * 64, "notRun": []}

    def test_every_generated_record_is_structurally_valid(self):
        for outcome, entry in sorted(self.generated.items()):
            with self.subTest(outcome=outcome):
                self.assertEqual(entry["outcome"], outcome)
                self.assertEqual(validation.validate_command_record(entry), (),
                                 f"the runner produced a record its own validator "
                                 f"rejects: {entry}")
                self.assertTrue(
                    validation.validate_result(self._record([entry]))["accepted"])

    def test_a_process_with_no_exit_status_keeps_a_null_exit_code(self):
        """A launch failure and a timeout never reported an exit status."""
        for outcome in validation.NO_EXIT_OUTCOMES:
            with self.subTest(outcome=outcome):
                self.assertIsNone(self.generated[outcome]["exitCode"])
                self.assertEqual(validation.validate_command_record(
                    self.generated[outcome]), ())

    def test_an_invented_exit_code_is_refused_for_those_outcomes(self):
        """124 is a shell convention, not something the process reported."""
        for outcome in validation.NO_EXIT_OUTCOMES:
            for invented in (124, 0, 1):
                with self.subTest(outcome=outcome, exitCode=invented):
                    forged = dict(self.generated[outcome], exitCode=invented)
                    self.assertIn("EX_EVIDENCE_INVENTED_EXIT_CODE",
                                  validation.validate_command_record(forged))

    def test_the_real_exit_codes_match_their_outcomes(self):
        self.assertEqual(self.generated["passed"]["exitCode"], 0)
        self.assertEqual(self.generated["failed"]["exitCode"], 7)
        self.assertLess(self.generated["signalled"]["exitCode"], 0)

    def test_the_signal_field_matches_the_real_process_result(self):
        signalled = self.generated["signalled"]
        self.assertEqual(signalled["signal"], -signalled["exitCode"])
        self.assertEqual(signalled["signal"], 15)
        for forged, expected in (
                (dict(signalled, signal=None), "EX_EVIDENCE_SIGNAL_REFUSED"),
                (dict(signalled, signal=9), "EX_EVIDENCE_SIGNAL_MISMATCH"),
                (dict(self.generated["failed"], signal=9),
                 "EX_EVIDENCE_SIGNAL_REFUSED")):
            with self.subTest(expected=expected):
                self.assertIn(expected, validation.validate_command_record(forged))

    def test_executed_false_cannot_substantiate_a_pass(self):
        for outcome in validation.UNEXECUTED_OUTCOMES:
            with self.subTest(outcome=outcome):
                forged = dict(self.generated[outcome], outcome="passed", exitCode=0,
                              startedAt="2026-10-15T10:00:00Z",
                              finishedAt="2026-10-15T10:00:01Z")
                self.assertIn("EX_EVIDENCE_EXECUTED_MISMATCH",
                              validation.validate_command_record(forged))

    def test_an_executed_record_cannot_claim_nothing_ran(self):
        forged = dict(self.generated["failed"], executed=False)
        self.assertIn("EX_EVIDENCE_EXECUTED_MISMATCH",
                      validation.validate_command_record(forged))

    def test_valid_failure_evidence_never_makes_the_run_pass(self):
        """Structural validity is not the result."""
        for outcome in ("failed", "error", "timeout", "signalled"):
            with self.subTest(outcome=outcome):
                checked = validation.validate_result(
                    self._record([self.generated["passed"], self.generated[outcome]]))
                self.assertTrue(checked["accepted"], checked["reasons"])
                self.assertFalse(checked["runPassed"])
                self.assertTrue(any(outcome in reason
                                    for reason in checked["notPassing"]))

    def test_a_pending_command_also_stops_the_run_from_passing(self):
        checked = validation.validate_result(
            self._record([self.generated["passed"], self.generated["pending"]]))
        self.assertTrue(checked["accepted"])
        self.assertFalse(checked["runPassed"])

    def test_a_not_run_obligation_does_not_stop_the_run_from_passing(self):
        """NOT_RUN is an owned obligation, reported, never counted as a pass."""
        checked = validation.validate_result(
            self._record([self.generated["passed"], self.generated["not-run"]]))
        self.assertTrue(checked["accepted"])
        self.assertTrue(checked["runPassed"], checked["notPassing"])

    def test_an_all_passed_run_passes(self):
        checked = validation.validate_result(
            self._record([self.generated["passed"]]))
        self.assertTrue(checked["accepted"])
        self.assertTrue(checked["runPassed"])
        self.assertEqual(checked["notPassing"], ())

    def test_the_bundle_blocks_on_a_real_command_failure(self):
        original = cli.UNIT_SUITES
        cli.UNIT_SUITES = (("failing stand-in", self.PROGRAMS["failed"]),)
        try:
            bundle = cli._bundle(ROOT, execute_suites=True)
        finally:
            cli.UNIT_SUITES = original
        self.assertFalse(bundle["allLocalPassed"])
        self.assertFalse(bundle["evidenceValidation"]["runPassed"])
        self.assertTrue(any("ended failed" in reason for reason in bundle["blocking"]))
        # The failure record itself is valid evidence: nothing about the command
        # record was refused. A dirty worktree may legitimately be refused here
        # when this suite runs against uncommitted work, so only command-record
        # reasons are asserted against.
        self.assertEqual([reason for reason in bundle["evidenceValidation"]["reasons"]
                          if "COMMAND" in reason or "SIGNAL" in reason
                          or "EXECUTED" in reason or "EXIT" in reason], [])


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


class BundleRecords(_WithoutNestingGuard):
    """The bundle must not invent a result for a command it did not run."""

    def setUp(self):
        super().setUp()
        self.bundle = cli._bundle(ROOT)

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
