"""The secret scan must be clean here and still catch planted content."""
import unittest
from pathlib import Path

from scenarios import observations
from scenarios.demos import DEMOS
from scenarios.harness import run_all

ROOT = str(Path(__file__).resolve().parents[2])


class SecretScan(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.scan = observations.secret_scan(ROOT)

    def test_the_repository_is_clean(self):
        self.assertTrue(self.scan["clean"], self.scan["findings"])
        self.assertEqual(self.scan["findings"], [])

    def test_it_scanned_the_tracked_text(self):
        self.assertGreater(self.scan["filesScanned"], 20)
        self.assertEqual(self.scan["cases"], ["T-39"])

    def test_it_does_not_claim_to_be_a_security_review(self):
        self.assertIn("not a substitute for an independent security review", self.scan["scope"])

    def test_the_patterns_catch_planted_credential_content(self):
        planted = {
            "private key block": "-----BEGIN RSA PRIVATE KEY-----",
            "mnemonic marker": "mnemonic: pretend words here",
            "api or access token": 'api_key = "ABCD1234EFGH5678"',
            "bearer credential": "Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123",
            "password assignment": 'password = "hunter2345"',
            "hex private key": 'private_key = "0x' + "ab" * 32 + '"',
            "aws key id": "AKIAZZZZZZZZZZZZZZZZ",
            "ssh private marker": "ssh-rsa AAAAB3NzaC1yc2E",
        }
        by_label = dict(observations.SECRET_PATTERNS)
        for label, sample in planted.items():
            with self.subTest(pattern=label):
                self.assertIsNotNone(by_label[label].search(sample))

    def test_an_ordinary_identifier_is_not_a_credential(self):
        by_label = dict(observations.SECRET_PATTERNS)
        for benign in ("bearer = self.leg(receipt_id, 0).buyer",
                       "the bearer of that leg's gas", "password handling is documented"):
            with self.subTest(text=benign):
                self.assertIsNone(by_label["bearer credential"].search(benign))

    def test_non_english_prose_is_detected_but_typography_is_not(self):
        self.assertIsNotNone(observations.NON_ENGLISH_PROSE.search("内部说明"))
        for benign in ("A->B->C", "an em dash — here", "an arrow → here",
                       "a quote “x”"):
            with self.subTest(text=benign):
                self.assertIsNone(observations.NON_ENGLISH_PROSE.search(benign))

    def test_private_material_patterns_are_defined(self):
        labels = {label for label, _ in observations.PRIVATE_CONTENT_PATTERNS}
        self.assertIn("private requirements link", labels)
        self.assertIn("private requirements digest", labels)


class ResourceObservation(unittest.TestCase):

    def test_a_measurement_reports_real_numbers_and_no_target(self):
        result, measured = observations.measure(lambda: run_all(list(DEMOS)))
        self.assertTrue(result["allPassed"])
        self.assertEqual(measured["cases"], ["T-40"])
        for key in ("elapsedMs", "userCpuMs", "systemCpuMs", "peakResidentKib"):
            self.assertIsInstance(measured[key], int)
            self.assertGreaterEqual(measured[key], 0)
        self.assertIn("no throughput or latency target", measured["note"])

    def test_the_workload_size_is_recorded_for_later_comparison(self):
        report = run_all(list(DEMOS))
        workload = observations.workload_observation(report)
        self.assertEqual(workload["scenarios"], 6)
        self.assertGreater(workload["recordedExpectations"], 40)
        self.assertGreater(workload["recordedSteps"], 10)
        self.assertEqual(workload["outcomeTotals"]["failed"], 0)


if __name__ == "__main__":
    unittest.main()
