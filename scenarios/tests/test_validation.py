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
                  "deploymentTarget": "/srv/somewhere"}
        outcome = validation.validate_config(config)
        self.assertFalse(outcome["accepted"])
        self.assertIn("EX_CONFIG_NOT_VERIFIED_HERE:deploymentTarget", outcome["reasons"])

    def test_acceptance_claims_nothing_about_approval(self):
        outcome = validation.validate_config(validation.local_config_template())
        self.assertIn("no deployment is authorized", outcome["meaning"])


class EvidenceValidation(unittest.TestCase):

    def _record(self, **changes):
        record = {"schema": "8415ex-local-delivery/1", "runId": "local-1",
                  "commit": "a" * 40, "tree": "b" * 40, "worktreeClean": True,
                  "commands": [{"command": "python3 -B -m scenarios.cli run-all",
                                "exitCode": 0}],
                  "startedAt": "2026-10-14T16:00:00Z", "finishedAt": "2026-10-14T16:00:01Z",
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

    def test_an_abbreviated_commit_is_refused(self):
        outcome = validation.validate_result(self._record(commit="9af9213"))
        self.assertFalse(outcome["accepted"])
        self.assertIn("EX_EVIDENCE_IDENTITY_REFUSED:commit", outcome["reasons"])

    def test_a_dirty_worktree_is_refused(self):
        outcome = validation.validate_result(self._record(worktreeClean=False))
        self.assertFalse(outcome["accepted"])
        self.assertIn("EX_EVIDENCE_DIRTY_WORKTREE", outcome["reasons"])

    def test_a_record_without_bound_commands_is_refused(self):
        for commands in ([], "python3", [{"command": "x"}]):
            with self.subTest(commands=commands):
                outcome = validation.validate_result(self._record(commands=commands))
                self.assertFalse(outcome["accepted"])
                self.assertIn("EX_EVIDENCE_COMMANDS_REFUSED", outcome["reasons"])

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
        for value in ("none", [{"obligation": "T-35"}], [{"status": "NOT_RUN"}]):
            with self.subTest(value=value):
                outcome = validation.validate_result(self._record(notRun=value))
                self.assertFalse(outcome["accepted"])
                self.assertIn("EX_EVIDENCE_NOT_RUN_REFUSED", outcome["reasons"])


if __name__ == "__main__":
    unittest.main()
