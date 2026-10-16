"""PR10 item1 validation exercised through the joined delivery producer.

These are synthetic local integration checks, never chain acceptance. Mutations
only affect copies of an actual locally generated evidence record.
"""
import copy
from pathlib import Path
import unittest

from scenarios import cli, validation


ROOT = str(Path(__file__).resolve().parents[1])


class Item1EvidenceJoin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        bundle = cli._bundle(ROOT)
        cls.bundle = cli.seal(bundle, 0 if bundle["allLocalPassed"] else 1)

    def evidence(self):
        return copy.deepcopy(self.bundle["evidence"])

    def assert_refused(self, record, reason):
        result = validation.validate_result(record)
        self.assertFalse(result["accepted"], result)
        self.assertIn(reason, result["reasons"])

    def test_joined_producer_emits_valid_ordered_evidence(self):
        self.assertTrue(self.bundle["allLocalPassed"], self.bundle["blocking"])
        self.assertTrue(self.bundle["evidenceValidation"]["accepted"])
        evidence = self.evidence()
        self.assertEqual(evidence["tree"], self.bundle["source"]["tree"])
        self.assertLessEqual(validation.parse_instant(evidence["startedAt"]),
                             validation.parse_instant(evidence["finishedAt"]))

    def test_generated_identity_cannot_be_replaced_by_whitespace(self):
        for key in ("schema", "runId"):
            for value in ("", " ", "\t\n"):
                with self.subTest(key=key, value=value):
                    record = self.evidence()
                    record[key] = value
                    self.assert_refused(record, f"EX_EVIDENCE_EMPTY_REFUSED:{key}")

    def test_impossible_run_instants_are_refused_after_join(self):
        for key in ("startedAt", "finishedAt"):
            with self.subTest(key=key):
                record = self.evidence()
                record[key] = "2026-02-29T00:00:00Z"
                self.assert_refused(record, f"EX_EVIDENCE_INSTANT_REFUSED:{key}")

    def test_reversed_run_order_is_refused_after_join(self):
        record = self.evidence()
        record.update(startedAt="2026-10-15T00:00:01Z",
                      finishedAt="2026-10-15T00:00:00Z")
        self.assert_refused(record, "EX_EVIDENCE_TIME_ORDER_REFUSED")

    def test_sealed_self_command_retains_calendar_and_order_validation(self):
        for changes, reason in (
            ({"finishedAt": "2026-13-01T00:00:00Z"},
             "EX_EVIDENCE_INSTANT_REFUSED:finishedAt"),
            ({"startedAt": "2026-10-15T00:00:01Z",
              "finishedAt": "2026-10-15T00:00:00Z"},
             "EX_EVIDENCE_TIME_ORDER_REFUSED"),
        ):
            with self.subTest(changes=changes):
                record = self.evidence()
                self.assertTrue(record["commands"][0]["executed"])
                record["commands"][0].update(changes)
                self.assert_refused(record, reason)

    def test_invalid_initial_timestamp_blocks_local_delivery(self):
        bundle = cli._bundle(ROOT, started_at="2026-02-29T00:00:00Z")
        self.assertFalse(bundle["allLocalPassed"])
        self.assertIn("EX_EVIDENCE_INSTANT_REFUSED:startedAt",
                      bundle["evidenceValidation"]["reasons"])
        self.assertTrue(any("evidence record was refused" in reason
                            for reason in bundle["blocking"]))

    def test_unexecuted_suites_and_real_obligations_stay_unexecuted(self):
        suites = self.bundle["commands"][1:]
        self.assertEqual(len(suites), 2)
        for record in suites:
            self.assertEqual(record["outcome"], "not-run")
            for field in ("exitCode", "startedAt", "finishedAt"):
                self.assertIsNone(record[field])
        self.assertEqual(self.bundle["evidence"]["transactionHashes"], "NOT_RUN")
        rows = {row["case"]: row for row in self.bundle["matrix"]["rows"]}
        for case in ("T-35", "T-36", "T-37", "T-38"):
            self.assertEqual(rows[case]["localOutcome"], "not-run")


if __name__ == "__main__":
    unittest.main()
