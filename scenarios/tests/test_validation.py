"""The validators must refuse a guess and a fabricated result."""
import unittest

from scenarios import validation


class ConfigValidation(unittest.TestCase):

    def test_the_template_is_accepted_with_everything_external_unresolved(self):
        outcome = validation.validate_config(validation.local_config_template())
        self.assertTrue(outcome["accepted"])
        self.assertEqual(sorted(outcome["unresolved"]),
                         sorted(validation.MUST_REMAIN_UNRESOLVED))

    def test_every_synthetic_case_is_refused_for_its_own_reason(self):
        for name, config, expected in validation.synthetic_rejection_cases():
            with self.subTest(case=name):
                outcome = validation.validate_config(config)
                self.assertFalse(outcome["accepted"])
                self.assertIn(expected, outcome["reasons"])

    def test_a_concrete_external_value_is_treated_as_unverified(self):
        config = {**validation.local_config_template(),
                  "deploymentTarget": "/srv" + "/somewhere"}
        outcome = validation.validate_config(config)
        self.assertFalse(outcome["accepted"])
        self.assertIn("EX_CONFIG_NOT_VERIFIED_HERE:deploymentTarget", outcome["reasons"])

    def test_acceptance_claims_nothing_about_approval(self):
        outcome = validation.validate_config(validation.local_config_template())
        self.assertIn("no deployment is authorized", outcome["meaning"])


class EvidenceValidation(unittest.TestCase):
    """A result record must stand on real identity and real execution."""

    def _command(self, **changes):
        entry = {"command": "python3 -B -m scenarios.cli run-all",
                 "outcome": "passed", "exitCode": 0,
                 "startedAt": "2026-10-14T16:00:00Z",
                 "finishedAt": "2026-10-14T16:00:01Z"}
        entry.update(changes)
        return entry

    def _record(self, **changes):
        record = {"schema": "8415ex-local-delivery/1", "runId": "local-1",
                  "commit": "a" * 40, "tree": "b" * 40, "worktreeClean": True,
                  "commands": [self._command()],
                  "startedAt": "2026-10-14T16:00:00Z",
                  "finishedAt": "2026-10-14T16:00:01Z",
                  "scenarioDigest": "0x" + "c" * 64,
                  "notRun": [{"obligation": "T-35", "status": "NOT_RUN"}]}
        record.update(changes)
        return record

    def test_a_complete_record_is_accepted(self):
        outcome = validation.validate_result(self._record())
        self.assertTrue(outcome["accepted"], outcome["reasons"])

    def test_a_missing_identity_is_refused(self):
        for key in ("runId", "commit", "tree", "scenarioDigest"):
            with self.subTest(missing=key):
                record = self._record()
                del record[key]
                outcome = validation.validate_result(record)
                self.assertFalse(outcome["accepted"])
                self.assertIn(f"EX_EVIDENCE_MISSING:{key}", outcome["reasons"])

    def test_a_present_null_identity_is_refused_on_its_own_terms(self):
        """Null is not an absence and must not reach the format check."""
        for key in ("runId", "commit", "tree", "scenarioDigest"):
            with self.subTest(null=key):
                outcome = validation.validate_result(self._record(**{key: None}))
                self.assertFalse(outcome["accepted"])
                self.assertIn(f"EX_EVIDENCE_NULL_REFUSED:{key}", outcome["reasons"])

    def test_a_non_string_hash_is_refused_by_type(self):
        for value in (True, 5, [], {}, 0.5):
            with self.subTest(value=value):
                outcome = validation.validate_result(self._record(commit=value))
                self.assertFalse(outcome["accepted"])
                self.assertIn("EX_EVIDENCE_TYPE_REFUSED:commit", outcome["reasons"])

    def test_an_abbreviated_commit_is_refused(self):
        outcome = validation.validate_result(self._record(commit="9af9213"))
        self.assertFalse(outcome["accepted"])
        self.assertIn("EX_EVIDENCE_IDENTITY_REFUSED:commit", outcome["reasons"])

    def test_a_dirty_worktree_is_refused(self):
        outcome = validation.validate_result(self._record(worktreeClean=False))
        self.assertFalse(outcome["accepted"])
        self.assertIn("EX_EVIDENCE_DIRTY_WORKTREE", outcome["reasons"])

    def test_a_record_without_bound_commands_is_refused(self):
        for commands in ([], "python3", None, {}):
            with self.subTest(commands=commands):
                outcome = validation.validate_result(self._record(commands=commands))
                self.assertFalse(outcome["accepted"])
                self.assertIn("EX_EVIDENCE_COMMANDS_REFUSED", outcome["reasons"])

    def test_a_command_without_a_recorded_outcome_is_refused(self):
        entry = self._command()
        del entry["outcome"]
        outcome = validation.validate_result(self._record(commands=[entry]))
        self.assertFalse(outcome["accepted"])
        self.assertIn("EX_EVIDENCE_COMMAND_REFUSED:outcome", outcome["reasons"])

    def test_an_unexecuted_command_cannot_carry_a_success_exit_code(self):
        """The central fabrication: exit 0 for something that never ran."""
        for status in validation.UNEXECUTED_OUTCOMES:
            with self.subTest(outcome=status):
                entry = self._command(outcome=status, exitCode=0)
                outcome = validation.validate_result(self._record(commands=[entry]))
                self.assertFalse(outcome["accepted"])
                self.assertIn("EX_EVIDENCE_UNEXECUTED_EXIT_CODE", outcome["reasons"])

    def test_an_unexecuted_command_cannot_carry_execution_timing(self):
        for status in validation.UNEXECUTED_OUTCOMES:
            with self.subTest(outcome=status):
                entry = self._command(outcome=status, exitCode=None)
                outcome = validation.validate_result(self._record(commands=[entry]))
                self.assertFalse(outcome["accepted"])
                self.assertIn("EX_EVIDENCE_UNEXECUTED_TIMING", outcome["reasons"])

    def test_a_not_run_command_is_accepted_without_any_result(self):
        entry = {"command": "python3 -B -m scenarios.cli run-all",
                 "outcome": "not-run", "exitCode": None,
                 "startedAt": None, "finishedAt": None,
                 "reason": "no deployed environment is authorized here"}
        outcome = validation.validate_result(self._record(commands=[entry]))
        self.assertTrue(outcome["accepted"], outcome["reasons"])

    def test_a_declared_pass_must_agree_with_its_exit_code(self):
        entry = self._command(outcome="passed", exitCode=1)
        outcome = validation.validate_result(self._record(commands=[entry]))
        self.assertFalse(outcome["accepted"])
        self.assertIn("EX_EVIDENCE_OUTCOME_MISMATCH", outcome["reasons"])

    def test_a_declared_failure_cannot_report_exit_zero(self):
        entry = self._command(outcome="failed", exitCode=0)
        outcome = validation.validate_result(self._record(commands=[entry]))
        self.assertFalse(outcome["accepted"])
        self.assertIn("EX_EVIDENCE_OUTCOME_MISMATCH", outcome["reasons"])

    def test_an_executed_command_must_report_real_timing(self):
        for key in ("startedAt", "finishedAt"):
            with self.subTest(missing=key):
                entry = self._command(**{key: None})
                outcome = validation.validate_result(self._record(commands=[entry]))
                self.assertFalse(outcome["accepted"])
                self.assertIn(f"EX_EVIDENCE_COMMAND_REFUSED:{key}", outcome["reasons"])

    def test_an_executed_command_must_report_an_integer_exit_code(self):
        for value in (None, True, "0", 0.0):
            with self.subTest(value=value):
                entry = self._command(exitCode=value)
                outcome = validation.validate_result(self._record(commands=[entry]))
                self.assertFalse(outcome["accepted"])
                self.assertIn("EX_EVIDENCE_COMMAND_REFUSED:exitCode", outcome["reasons"])

    def test_failure_shapes_stay_distinguishable(self):
        """error, timeout and signalled are not collapsed into failed.

        Each one also carries the exit status its real process actually had: a
        launch error and a timeout never reported one, so the truthful record is
        null, and a signalled process reports a negative status whose magnitude
        is the signal.
        """
        for status in validation.NO_EXIT_OUTCOMES:
            with self.subTest(outcome=status):
                entry = self._command(outcome=status, exitCode=None)
                outcome = validation.validate_result(self._record(commands=[entry]))
                self.assertTrue(outcome["accepted"], outcome["reasons"])
                self.assertFalse(outcome["runPassed"])
        signalled = self._command(outcome="signalled", exitCode=-15, signal=15)
        outcome = validation.validate_result(self._record(commands=[signalled]))
        self.assertTrue(outcome["accepted"], outcome["reasons"])
        self.assertFalse(outcome["runPassed"])
        self.assertEqual(sorted(validation.COMMAND_OUTCOMES),
                         sorted(validation.EXECUTED_OUTCOMES
                                + validation.UNEXECUTED_OUTCOMES))
        self.assertEqual(sorted(validation.EXECUTED_OUTCOMES),
                         sorted(validation.NO_EXIT_OUTCOMES
                                + validation.EXIT_CODE_OUTCOMES))

    def test_a_fabricated_transaction_hash_is_refused(self):
        for value in (["0x" + "00" * 32], ["0xdeadbeef"], "all good", ["not-a-hash"]):
            with self.subTest(value=value):
                outcome = validation.validate_result(self._record(transactionHashes=value))
                self.assertFalse(outcome["accepted"])
                self.assertIn("EX_EVIDENCE_FABRICATED:transactionHashes", outcome["reasons"])

    def test_a_not_run_slot_is_accepted_for_an_unexecuted_obligation(self):
        outcome = validation.validate_result(self._record(transactionHashes="NOT_RUN"))
        self.assertTrue(outcome["accepted"], outcome["reasons"])

    def test_an_empty_or_whitespace_identity_is_refused(self):
        """A string is not an identity: it has to carry content."""
        for key in validation.NON_EMPTY_IDENTITY:
            for value in ("", "   ", "\t\n"):
                with self.subTest(key=key, value=repr(value)):
                    outcome = validation.validate_result(self._record(**{key: value}))
                    self.assertFalse(outcome["accepted"])
                    self.assertIn(f"EX_EVIDENCE_EMPTY_REFUSED:{key}", outcome["reasons"])

    def test_a_shape_valid_but_impossible_instant_is_refused(self):
        """The regex admits instants that name no real moment."""
        for value in ("2026-13-01T04:00:00Z", "2026-10-32T04:00:00Z",
                      "2026-10-15T25:00:00Z", "2026-10-15T04:61:00Z",
                      "2026-10-15T04:00:61Z", "2026-02-29T04:00:00Z",
                      "2026-00-10T04:00:00Z", "2026-10-00T04:00:00Z"):
            with self.subTest(value=value):
                self.assertIsNotNone(validation.UTC_INSTANT.match(value),
                                     "the case must be shape-valid to be meaningful")
                self.assertIsNone(validation.parse_instant(value))
                outcome = validation.validate_result(
                    self._record(startedAt=value, finishedAt=value))
                self.assertFalse(outcome["accepted"])
                self.assertIn("EX_EVIDENCE_INSTANT_REFUSED:startedAt", outcome["reasons"])

    def test_a_leap_day_that_exists_is_accepted(self):
        """2028 is a leap year, so the same shape is a real instant there."""
        self.assertIsNotNone(validation.parse_instant("2028-02-29T04:00:00Z"))
        # The command moves with the window: a record whose own command ran
        # outside it would be refused for that instead, which is not what this
        # case is about.
        outcome = validation.validate_result(self._record(
            startedAt="2028-02-29T04:00:00Z", finishedAt="2028-02-29T04:00:01Z",
            commands=[self._command(startedAt="2028-02-29T04:00:00Z",
                                    finishedAt="2028-02-29T04:00:01Z")]))
        self.assertTrue(outcome["accepted"], outcome["reasons"])

    def test_a_run_cannot_finish_before_it_started(self):
        outcome = validation.validate_result(
            self._record(startedAt="2026-10-15T04:00:05Z",
                         finishedAt="2026-10-15T04:00:01Z"))
        self.assertFalse(outcome["accepted"])
        self.assertIn("EX_EVIDENCE_TIME_ORDER_REFUSED", outcome["reasons"])

    def test_equal_start_and_end_instants_are_accepted(self):
        """A sub-second run is ordinary, not a time-order defect."""
        instant = "2026-10-15T04:00:01Z"
        outcome = validation.validate_result(self._record(
            startedAt=instant, finishedAt=instant,
            commands=[self._command(startedAt=instant, finishedAt=instant)]))
        self.assertTrue(outcome["accepted"], outcome["reasons"])

    def test_a_command_cannot_finish_before_it_started(self):
        entry = self._command(startedAt="2026-10-15T04:00:05Z",
                              finishedAt="2026-10-15T04:00:01Z")
        outcome = validation.validate_result(self._record(commands=[entry]))
        self.assertFalse(outcome["accepted"])
        self.assertIn("EX_EVIDENCE_TIME_ORDER_REFUSED", outcome["reasons"])

    def test_a_command_instant_must_be_a_real_calendar_moment(self):
        entry = self._command(startedAt="2026-02-29T04:00:00Z",
                              finishedAt="2026-02-29T04:00:01Z")
        outcome = validation.validate_result(self._record(commands=[entry]))
        self.assertFalse(outcome["accepted"])
        self.assertIn("EX_EVIDENCE_INSTANT_REFUSED:startedAt", outcome["reasons"])

    def test_the_valid_control_still_passes_every_added_check(self):
        """The added refusals must not make an honest record unusable."""
        outcome = validation.validate_result(self._record())
        self.assertTrue(outcome["accepted"], outcome["reasons"])
        self.assertGreater(outcome["canonicalBytes"], 0)

    def test_a_command_must_have_run_inside_the_run_that_reports_it(self):
        """A record whose commands sit outside its own window is not its own."""
        for label, changes in (
                ("years before", {"startedAt": "2020-01-01T00:00:00Z",
                                  "finishedAt": "2020-01-01T00:00:01Z"}),
                ("years after", {"startedAt": "2030-01-01T00:00:00Z",
                                 "finishedAt": "2030-01-01T00:00:01Z"}),
                ("starts too early", {"startedAt": "2026-10-14T15:59:59Z",
                                      "finishedAt": "2026-10-14T16:00:01Z"}),
                ("ends too late", {"startedAt": "2026-10-14T16:00:00Z",
                                   "finishedAt": "2026-10-14T16:00:02Z"})):
            with self.subTest(case=label):
                entry = self._command(**changes)
                outcome = validation.validate_result(self._record(commands=[entry]))
                self.assertFalse(outcome["accepted"])
                self.assertIn("EX_EVIDENCE_COMMAND_OUTSIDE_RUN", outcome["reasons"])

    def test_a_command_exactly_at_the_run_bounds_is_accepted(self):
        record = self._record()
        entry = self._command(startedAt=record["startedAt"],
                              finishedAt=record["finishedAt"])
        outcome = validation.validate_result(self._record(commands=[entry]))
        self.assertTrue(outcome["accepted"], outcome["reasons"])

    def test_an_unexecuted_command_is_not_judged_against_the_window(self):
        """It carries no timing at all, so there is nothing to compare."""
        entry = {"command": "later", "outcome": "not-run", "exitCode": None,
                 "startedAt": None, "finishedAt": None, "executed": False}
        outcome = validation.validate_result(self._record(commands=[entry]))
        self.assertTrue(outcome["accepted"], outcome["reasons"])

    def test_a_historical_run_name_is_not_source_provenance(self):
        """Validate historical evidence independently under its own source/run."""
        earlier = self._command(startedAt="2026-10-01T00:00:00Z",
                                finishedAt="2026-10-01T00:00:01Z",
                                observedInRun="local-20261001T000000Z-aaaaaaaaaaaa")
        outcome = validation.validate_result(self._record(commands=[earlier]))
        self.assertFalse(outcome["accepted"])
        self.assertIn("EX_EVIDENCE_HISTORICAL_COMMAND_UNSUPPORTED", outcome["reasons"])

    def test_historical_citations_are_accepted_only_as_unverified_references(self):
        citation = {"scope": "historical-citation", "verification": "unverified",
                    "observedInRun": "prior-run", "evidenceLocator": "prior-run.json",
                    "sourceIdentity": {"commit": "d" * 40, "tree": "e" * 40}}
        result = validation.validate_result(self._record(historicalCitations=[citation]))
        self.assertTrue(result["accepted"], result["reasons"])
        self.assertFalse(result["historicalCitationsVerified"])
        self.assertEqual(result["historicalCitationCount"], 1)
        self.assertEqual(result["commandOutcomes"], ["passed"])
        result = validation.validate_result(self._record(commands=[], historicalCitations=[citation]))
        self.assertFalse(result["accepted"])
        self.assertFalse(result["runPassed"])
        result = validation.validate_result(self._record(historicalCitations=[
            {**citation, "observedInRun": self._record()["runId"]}]))
        self.assertIn("EX_EVIDENCE_HISTORICAL_CITATION_CURRENT_RUN", result["reasons"])

    def test_a_citation_that_names_this_run_is_held_to_this_window(self):
        record = self._record()
        earlier = self._command(startedAt="2026-10-01T00:00:00Z",
                                finishedAt="2026-10-01T00:00:01Z",
                                observedInRun=record["runId"])
        outcome = validation.validate_result(self._record(commands=[earlier]))
        self.assertFalse(outcome["accepted"])
        self.assertIn("EX_EVIDENCE_COMMAND_OUTSIDE_RUN", outcome["reasons"])

    def test_a_citation_without_a_run_identity_is_refused(self):
        for origin in ("", "   ", 5, True, []):
            with self.subTest(origin=origin):
                earlier = self._command(startedAt="2026-10-01T00:00:00Z",
                                        finishedAt="2026-10-01T00:00:01Z",
                                        observedInRun=origin)
                outcome = validation.validate_result(self._record(commands=[earlier]))
                self.assertFalse(outcome["accepted"])
                self.assertIn("EX_EVIDENCE_REFERENCED_RUN_REFUSED", outcome["reasons"])

    def test_an_obligation_name_must_carry_content(self):
        for blank in ("", "   ", "\t"):
            with self.subTest(obligation=repr(blank)):
                outcome = validation.validate_result(
                    self._record(notRun=[{"obligation": blank, "status": "NOT_RUN"}]))
                self.assertFalse(outcome["accepted"])
                self.assertIn("EX_EVIDENCE_NOT_RUN_REFUSED", outcome["reasons"])

    def test_a_malformed_not_run_list_is_refused(self):
        for value in ("none", None, [{"obligation": "T-35"}], [{"status": "NOT_RUN"}]):
            with self.subTest(value=value):
                outcome = validation.validate_result(self._record(notRun=value))
                self.assertFalse(outcome["accepted"])
                self.assertIn("EX_EVIDENCE_NOT_RUN_REFUSED", outcome["reasons"])


if __name__ == "__main__":
    unittest.main()
