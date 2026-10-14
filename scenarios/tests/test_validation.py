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
        """error, timeout and signalled are not collapsed into failed."""
        for status in ("error", "timeout", "signalled"):
            with self.subTest(outcome=status):
                entry = self._command(outcome=status, exitCode=124)
                outcome = validation.validate_result(self._record(commands=[entry]))
                self.assertTrue(outcome["accepted"], outcome["reasons"])
        self.assertEqual(sorted(validation.COMMAND_OUTCOMES),
                         sorted(validation.EXECUTED_OUTCOMES
                                + validation.UNEXECUTED_OUTCOMES))

    def test_a_fabricated_transaction_hash_is_refused(self):
        for value in (["0x" + "00" * 32], ["0xdeadbeef"], "all good", ["not-a-hash"]):
            with self.subTest(value=value):
                outcome = validation.validate_result(self._record(transactionHashes=value))
                self.assertFalse(outcome["accepted"])
                self.assertIn("EX_EVIDENCE_FABRICATED:transactionHashes", outcome["reasons"])

    def test_a_not_run_slot_is_accepted_for_an_unexecuted_obligation(self):
        outcome = validation.validate_result(self._record(transactionHashes="NOT_RUN"))
        self.assertTrue(outcome["accepted"], outcome["reasons"])

    def test_a_malformed_not_run_list_is_refused(self):
        for value in ("none", None, [{"obligation": "T-35"}], [{"status": "NOT_RUN"}]):
            with self.subTest(value=value):
                outcome = validation.validate_result(self._record(notRun=value))
                self.assertFalse(outcome["accepted"])
                self.assertIn("EX_EVIDENCE_NOT_RUN_REFUSED", outcome["reasons"])


if __name__ == "__main__":
    unittest.main()
