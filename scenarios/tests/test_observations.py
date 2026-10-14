"""The scan must fail closed, cover what it claims, and police its own source.

Every credential-shaped sample here is assembled at runtime from harmless
fragments, so this test file contains no credential-shaped literal of its own
and is subject to the same scan as the rest of the source.
"""
import os
import subprocess
import unittest
from pathlib import Path

from scenarios import observations
from scenarios.demos import DEMOS
from scenarios.harness import run_all

ROOT = str(Path(__file__).resolve().parents[2])


def _sample(kind):
    """Build a detection sample without writing a credential-shaped literal."""
    dash = "-" * 5
    joiner = {"colon": ": ", "equals": " = "}
    if kind == "private key block":
        return f"{dash}BEGIN RSA PRIVATE KEY{dash}"
    if kind == "mnemonic marker":
        return "mnemonic" + joiner["colon"] + "alpha bravo charlie"
    if kind == "api or access token":
        return "api" + "_" + "key" + joiner["equals"] + "A" * 12
    if kind == "bearer credential":
        return "Bearer " + "b" * 24
    if kind == "password assignment":
        return "pass" + "word" + joiner["equals"] + "x" * 9
    if kind == "hex private key":
        return "private" + "_" + "key" + joiner["equals"] + "0x" + "a" * 64
    if kind == "cloud access key id":
        return "ABCD" + "E" * 16
    if kind == "ssh private marker":
        return "ssh" + "-rsa " + "AAAA" + "B3Nza"
    if kind == "document sharing link":
        return "https://drive." + "google.com/file/d/" + "n" * 8
    if kind == "internal operational path":
        return "/srv" + "/somewhere/private"
    raise AssertionError(kind)


class Enumeration(unittest.TestCase):
    """A file list that could not be established is never a clean source."""

    def test_the_repository_enumerates_tracked_paths(self):
        enumeration = observations.tracked_files(ROOT)
        self.assertTrue(enumeration["ok"])
        self.assertEqual(enumeration["state"], "enumerated")
        self.assertGreater(len(enumeration["files"]), 20)
        self.assertIn("scenarios/observations.py", enumeration["files"])

    def test_a_non_repository_is_an_explicit_failure(self):
        enumeration = observations.tracked_files("/tmp")
        self.assertFalse(enumeration["ok"])
        self.assertEqual(enumeration["state"], "not-a-repository")
        self.assertEqual(enumeration["files"], ())

    def test_a_missing_directory_is_an_explicit_failure(self):
        enumeration = observations.tracked_files("/nonexistent-directory-for-this-test")
        self.assertFalse(enumeration["ok"])
        self.assertIn(enumeration["state"], ("git-unavailable", "not-a-repository"))

    def test_an_empty_enumeration_is_a_failure_not_a_clean_result(self):
        empty = subprocess.run(("git", "init", "--quiet",
                                "/tmp/ex-empty-repo-for-this-test"), check=False)
        self.assertEqual(empty.returncode, 0)
        enumeration = observations.tracked_files("/tmp/ex-empty-repo-for-this-test")
        self.assertFalse(enumeration["ok"])
        self.assertEqual(enumeration["state"], "empty-enumeration")

    def test_a_filename_with_spaces_survives_enumeration(self):
        """NUL-delimited enumeration keeps a path with spaces in one piece."""
        root = "/tmp/ex-spaced-repo-for-this-test"
        subprocess.run(("rm", "-rf", root), check=False)
        subprocess.run(("git", "init", "--quiet", root), check=False)
        target = Path(root) / "a file with spaces.md"
        target.write_text("plain english text\n", encoding="utf-8")
        subprocess.run(("git", "-C", root, "add", "--", target.name), check=False)
        enumeration = observations.tracked_files(root)
        self.assertTrue(enumeration["ok"])
        self.assertIn("a file with spaces.md", enumeration["files"])
        scan = observations.secret_scan(root)
        self.assertTrue(scan["ok"])
        self.assertEqual(scan["coverage"]["scanned"], 1)
        self.assertTrue(scan["clean"])


class ScanIntegrity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.scan = observations.secret_scan(ROOT)

    def test_the_repository_is_clean(self):
        self.assertTrue(self.scan["ok"])
        self.assertTrue(self.scan["clean"], self.scan["findings"])
        self.assertEqual(self.scan["findings"], [])

    def test_coverage_is_reported_rather_than_implied(self):
        coverage = self.scan["coverage"]
        self.assertGreater(coverage["enumerated"], 20)
        self.assertGreater(coverage["scanned"], 20)
        self.assertEqual(coverage["unreadable"], [])
        for entry in coverage["skipped"]:
            self.assertTrue(entry["reason"])
        self.assertEqual(coverage["enumerated"],
                         coverage["scanned"] + len(coverage["skipped"])
                         + len(coverage["unreadable"]))

    def test_the_scanners_own_source_is_scanned(self):
        """There is no self-exemption: this file and the scanner are both read."""
        enumeration = observations.tracked_files(ROOT)
        self.assertIn("scenarios/observations.py", enumeration["files"])
        self.assertIn("scenarios/tests/test_observations.py", enumeration["files"])
        skipped = {entry["path"] for entry in self.scan["coverage"]["skipped"]}
        self.assertNotIn("scenarios/observations.py", skipped)
        self.assertNotIn("scenarios/tests/test_observations.py", skipped)

    def test_the_scanner_source_carries_no_private_value(self):
        source = Path(ROOT, "scenarios/observations.py").read_text(encoding="utf-8")
        self.assertTrue(all(ord(character) < 128 for character in source),
                        "the public scanner source stays ASCII")
        self.assertNotIn("drive." + "google.com/file/d/", source)
        self.assertEqual(observations.PRIVATE_MARKER_ENV, "EX_PRIVATE_CONTENT_MARKERS")

    def test_a_planted_sample_is_detected_in_a_synthetic_tree(self):
        root = "/tmp/ex-planted-repo-for-this-test"
        for label, _ in observations.SECRET_PATTERNS + observations.PRIVATE_CONTENT_PATTERNS:
            with self.subTest(pattern=label):
                subprocess.run(("rm", "-rf", root), check=False)
                subprocess.run(("git", "init", "--quiet", root), check=False)
                target = Path(root) / "planted.md"
                target.write_text(_sample(label) + "\n", encoding="utf-8")
                subprocess.run(("git", "-C", root, "add", "planted.md"), check=False)
                scan = observations.secret_scan(root)
                self.assertTrue(scan["ok"])
                self.assertFalse(scan["clean"])
                self.assertIn(label, {finding["pattern"] for finding in scan["findings"]})

    def test_a_configured_private_marker_is_detected_without_being_echoed(self):
        root = "/tmp/ex-marker-repo-for-this-test"
        subprocess.run(("rm", "-rf", root), check=False)
        subprocess.run(("git", "init", "--quiet", root), check=False)
        marker = "fingerprint-" + "f" * 10
        (Path(root) / "notes.md").write_text(f"see {marker} here\n", encoding="utf-8")
        subprocess.run(("git", "-C", root, "add", "notes.md"), check=False)
        scan = observations.secret_scan(root, private_markers=(marker,))
        self.assertFalse(scan["clean"])
        self.assertEqual(scan["privateMarkerCount"], 1)
        rendered = str(scan)
        self.assertNotIn(marker, rendered, "a marker is never echoed into the report")

    def test_markers_come_from_the_approved_private_mechanism(self):
        previous = os.environ.get(observations.PRIVATE_MARKER_ENV)
        os.environ[observations.PRIVATE_MARKER_ENV] = "alpha-marker, beta-marker"
        try:
            self.assertEqual(observations._private_markers(),
                             ("alpha-marker", "beta-marker"))
        finally:
            if previous is None:
                del os.environ[observations.PRIVATE_MARKER_ENV]
            else:
                os.environ[observations.PRIVATE_MARKER_ENV] = previous

    def test_an_ordinary_identifier_is_not_a_credential(self):
        by_label = dict(observations.SECRET_PATTERNS)
        for benign in ("bearer = self.leg(receipt_id, 0).buyer",
                       "the bearer of that leg's gas"):
            with self.subTest(text=benign):
                self.assertIsNone(by_label["bearer credential"].search(benign))

    def test_typography_is_not_non_english_prose(self):
        for code_point in (0x2192, 0x2014, 0x201C):
            with self.subTest(code_point=hex(code_point)):
                self.assertIsNone(observations.NON_ENGLISH_PROSE.search(chr(code_point)))
        for code_point in (0x4E2D, 0x0434, 0x05D0):
            with self.subTest(code_point=hex(code_point)):
                self.assertIsNotNone(observations.NON_ENGLISH_PROSE.search(chr(code_point)))

    def test_a_failed_enumeration_never_reports_clean(self):
        for root in ("/tmp", "/nonexistent-directory-for-this-test"):
            with self.subTest(root=root):
                scan = observations.secret_scan(root)
                self.assertFalse(scan["ok"])
                self.assertFalse(scan["clean"])
                self.assertEqual(scan["coverage"]["scanned"], 0)

    def test_an_unreadable_tracked_file_prevents_a_clean_result(self):
        root = "/tmp/ex-unreadable-repo-for-this-test"
        subprocess.run(("rm", "-rf", root), check=False)
        subprocess.run(("git", "init", "--quiet", root), check=False)
        target = Path(root) / "gone.md"
        target.write_text("english text\n", encoding="utf-8")
        subprocess.run(("git", "-C", root, "add", "gone.md"), check=False)
        target.unlink()
        scan = observations.secret_scan(root)
        self.assertTrue(scan["ok"])
        self.assertFalse(scan["clean"])
        self.assertEqual(len(scan["coverage"]["unreadable"]), 1)
        self.assertEqual(scan["coverage"]["scanned"], 0)

    def test_it_does_not_claim_to_be_a_security_review(self):
        self.assertIn("not a substitute for an independent security review", self.scan["scope"])


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
        self.assertEqual(workload["outcomeTotals"]["failed"], 0)


if __name__ == "__main__":
    unittest.main()
