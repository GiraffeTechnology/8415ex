"""Synthetic unit checks; these do not prove host isolation or remote CI."""

import copy
import hashlib
import unittest

from ci.evidence import EvidenceError, validate_identity, validate_result, verify_sha256


def identity():
    return {
        "repository": "GiraffeTechnology/8415ex",
        "commit_sha": "a" * 40,
        "tree_sha": "b" * 40,
        "config_sha256": "c" * 64,
        "run_id": "synthetic-run-1",
    }


def object_ref(key):
    return {
        "bucket": "giraffe",
        "key": "synthetic-test-only/" + key,
        "object_id": "synthetic-version-1",
        "sha256": "d" * 64,
    }


def result():
    return {
        "schema_version": 1,
        "check_name": "8415ex/bootstrap",
        "identity": identity(),
        "outcome": "success",
        "started_at": "2026-01-01T00:00:00Z",
        "finished_at": "2026-01-01T00:00:01Z",
        "source_object": object_ref("source.tar"),
        "log_object": object_ref("run.log"),
        "stages": {
            "unit-tests": {"outcome": "passed", "exit_code": 0},
            "smoke": {"outcome": "passed", "exit_code": 0},
        },
        "artifacts": [object_ref("smoke.txt")],
    }


class EvidenceTests(unittest.TestCase):
    def validate(self, value, expected=None, current_run_id="synthetic-run-1",
                 expected_prefix="synthetic-test-only"):
        validate_result(value, expected_identity=expected or identity(),
                        current_run_id=current_run_id, expected_prefix=expected_prefix)

    def test_complete_success_is_valid(self):
        self.validate(result())

    def test_each_identity_field_must_match(self):
        for field, replacement in (
            ("repository", "other/repository"), ("commit_sha", "e" * 40),
            ("tree_sha", "e" * 40), ("config_sha256", "e" * 64),
            ("run_id", "synthetic-run-2"),
        ):
            with self.subTest(field=field):
                value = result()
                value["identity"][field] = replacement
                with self.assertRaises(EvidenceError):
                    self.validate(value)

    def test_current_run_gate_rejects_older_retry(self):
        with self.assertRaises(EvidenceError):
            self.validate(result(), current_run_id="synthetic-run-2")

    def test_identity_rejects_abbreviated_or_malformed_hash(self):
        for field in ("commit_sha", "tree_sha", "config_sha256"):
            for invalid in ("abc123", "", "z" * 64, None):
                with self.subTest(field=field, invalid=invalid):
                    value = identity()
                    value[field] = invalid
                    with self.assertRaises(EvidenceError):
                        validate_identity(value)

    def test_all_required_stages_must_be_present(self):
        value = result()
        del value["stages"]["smoke"]
        with self.assertRaises(EvidenceError):
            self.validate(value)

    def test_incomplete_or_negative_stage_cannot_pass(self):
        for state, code in (("not_run", None), ("failed", 1),
                            ("timeout", None), ("cancelled", None)):
            with self.subTest(state=state):
                value = result()
                value["stages"]["smoke"] = {"outcome": state, "exit_code": code}
                with self.assertRaises(EvidenceError):
                    self.validate(value)

    def test_negative_outcomes_can_be_recorded_truthfully(self):
        for outcome, state, code in (("failure", "failed", 1),
                                     ("timeout", "timeout", None),
                                     ("cancelled", "cancelled", None)):
            with self.subTest(outcome=outcome):
                value = result()
                value["outcome"] = outcome
                value["stages"]["smoke"] = {"outcome": state, "exit_code": code}
                value["artifacts"] = []
                self.validate(value)

    def test_terminal_outcome_needs_matching_stage(self):
        for outcome in ("failure", "timeout", "cancelled"):
            with self.subTest(outcome=outcome):
                value = result()
                value["outcome"] = outcome
                with self.assertRaises(EvidenceError):
                    self.validate(value)

    def test_pending_is_not_terminal_evidence(self):
        value = result()
        value["outcome"] = "pending"
        with self.assertRaises(EvidenceError):
            self.validate(value)

    def test_missing_artifact_cannot_pass(self):
        value = result()
        value["artifacts"] = []
        with self.assertRaises(EvidenceError):
            self.validate(value)

    def test_wrong_or_missing_exit_code_is_rejected(self):
        for state, code in (("passed", 1), ("passed", True), ("failed", 0),
                            ("not_run", 0), ("passed", None)):
            with self.subTest(state=state, code=code):
                value = result()
                value["stages"]["smoke"] = {"outcome": state, "exit_code": code}
                with self.assertRaises(EvidenceError):
                    self.validate(value)

    def test_timestamps_must_be_ordered_and_utc(self):
        for timestamp in ("2025-12-31T23:59:59Z", "2026-01-01T00:00:01+00:00",
                          "not-a-timeZ"):
            with self.subTest(timestamp=timestamp):
                value = result()
                value["finished_at"] = timestamp
                with self.assertRaises(EvidenceError):
                    self.validate(value)

    def test_object_references_must_be_complete_and_canonical(self):
        for field in ("source_object", "log_object"):
            for mutation in ({"bucket": "public"}, {"key": "../source"},
                             {"object_id": ""}, {"sha256": "short"}):
                with self.subTest(field=field, mutation=mutation):
                    value = result()
                    value[field].update(mutation)
                    with self.assertRaises(EvidenceError):
                        self.validate(value)

    def test_bucket_name_matches_verified_case_sensitive_identity(self):
        self.validate(result())
        for field in ("source_object", "log_object"):
            with self.subTest(field=field):
                value = result()
                value[field]["bucket"] = "Giraffe"
                with self.assertRaises(EvidenceError):
                    self.validate(value)
        value = result()
        value["artifacts"][0]["bucket"] = "Giraffe"
        with self.assertRaises(EvidenceError):
            self.validate(value)

    def test_expected_project_prefix_accepts_trailing_separator(self):
        self.validate(result(), expected_prefix="synthetic-test-only/")

    def test_source_log_and_artifact_must_use_expected_project_prefix(self):
        for field in ("source_object", "log_object", "artifacts"):
            for key in ("other-project/object", "synthetic-test-only-copy/object",
                        "synthetic-test-only"):
                with self.subTest(field=field, key=key):
                    value = result()
                    reference = value[field][0] if field == "artifacts" else value[field]
                    reference["key"] = key
                    with self.assertRaises(EvidenceError):
                        self.validate(value)

    def test_missing_or_noncanonical_project_prefix_is_rejected(self):
        for prefix in (None, "", "/", "../project", "project//run", "project/../run"):
            with self.subTest(prefix=prefix):
                with self.assertRaises(EvidenceError):
                    self.validate(result(), expected_prefix=prefix)

    def test_unknown_schema_or_fields_are_rejected(self):
        for mutation in ({"schema_version": 2}, {"schema_version": True},
                         {"unexpected": "value"}):
            with self.subTest(mutation=mutation):
                value = result()
                value.update(mutation)
                with self.assertRaises(EvidenceError):
                    self.validate(value)

    def test_artifact_checksum_matches_independently_read_bytes(self):
        data = b"synthetic artifact"
        verify_sha256(data, hashlib.sha256(data).hexdigest())
        with self.assertRaises(EvidenceError):
            verify_sha256(data + b"modified", hashlib.sha256(data).hexdigest())

    def test_validation_does_not_mutate_evidence(self):
        value = result()
        before = copy.deepcopy(value)
        self.validate(value)
        self.assertEqual(value, before)


if __name__ == "__main__":
    unittest.main()
