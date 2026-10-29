"""The scan must fail closed, cover what it claims, and police its own source.

Every credential-shaped sample here is assembled at runtime from harmless
fragments, so this test file contains no credential-shaped literal of its own
and is subject to the same scan as the rest of the source.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


def _repository(name):
    """An empty repository under /tmp, rebuilt from nothing on every call."""
    root = "/tmp/" + name
    subprocess.run(("rm", "-rf", root), check=False)
    subprocess.run(("git", "init", "--quiet", root), check=False)
    return root


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
                         + len(coverage["unreadable"])
                         + len(coverage["notReadInFull"]))

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

    def test_the_coverage_statement_counts_this_candidate(self):
        """Item 6: the numbers come from this scan, not carried forward."""
        statement = self.scan["coverageStatement"]
        coverage = self.scan["coverage"]
        self.assertEqual(statement["inventoryTotal"], coverage["enumerated"])
        self.assertEqual(statement["scannedCount"], coverage["scanned"])
        self.assertEqual(statement["skippedCount"], len(coverage["skipped"]))
        self.assertEqual(statement["unreadableCount"], len(coverage["unreadable"]))
        self.assertEqual(statement["notReadInFullCount"],
                         len(coverage["notReadInFull"]))
        self.assertTrue(statement["accountedFor"])
        self.assertEqual(statement["enumerationState"], "enumerated")
        # Re-reading must produce the same counts for the same tree, and they
        # must be the live ones rather than a remembered pair.
        again = observations.secret_scan(ROOT)["coverageStatement"]
        self.assertEqual(again["inventoryTotal"], statement["inventoryTotal"])
        self.assertGreater(statement["inventoryTotal"], 0)

    def test_a_credential_in_a_file_with_no_suffix_is_read(self):
        """The gap this closes: the names a credential uses were exempt.

        While text was decided by file name, a ``.env`` and an extensionless
        key file were skipped with a tidy reason and the scan still reported
        clean - over the two files most likely to hold the thing being looked
        for.
        """
        for name in (".env", "credentials", "Dockerfile", "key.pem"):
            with self.subTest(name=name):
                root = _repository("ex-unsuffixed-repo-for-this-test")
                (Path(root) / name).write_text(
                    _sample("password assignment") + "\n", encoding="utf-8")
                subprocess.run(("git", "-C", root, "add", "--", name), check=False)
                scan = observations.secret_scan(root)
                self.assertTrue(scan["ok"])
                self.assertEqual(scan["coverage"]["scanned"], 1)
                self.assertFalse(scan["clean"])
                self.assertEqual({finding["path"] for finding in scan["findings"]},
                                 {name})

    def test_non_english_prose_is_caught_in_every_file_read(self):
        """It used to be checked in three suffixes, and the rule is not three."""
        for name in ("notes.json", "notes.txt", "run.sh", "NOTICE"):
            with self.subTest(name=name):
                root = _repository("ex-prose-repo-for-this-test")
                (Path(root) / name).write_text(
                    "a line with %s in it\n" % chr(0x4E2D), encoding="utf-8")
                subprocess.run(("git", "-C", root, "add", "--", name), check=False)
                scan = observations.secret_scan(root)
                self.assertFalse(scan["clean"])
                self.assertEqual([finding["kind"] for finding in scan["findings"]],
                                 ["non-english"])

    def test_a_binary_file_is_skipped_as_binary_and_is_not_a_finding(self):
        root = _repository("ex-binary-repo-for-this-test")
        (Path(root) / "blob.bin").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
        (Path(root) / "notes.md").write_text("english text\n", encoding="utf-8")
        subprocess.run(("git", "-C", root, "add", "--", "blob.bin", "notes.md"),
                       check=False)
        scan = observations.secret_scan(root)
        self.assertTrue(scan["ok"])
        self.assertEqual(scan["coverage"]["scanned"], 1)
        skipped, = scan["coverage"]["skipped"]
        self.assertEqual(skipped["path"], "blob.bin")
        self.assertIn("binary", skipped["reason"])
        self.assertTrue(scan["clean"],
                        "a text pattern certifies nothing over binary, so "
                        "skipping it is not a finding")

    def test_a_file_that_is_not_read_in_full_prevents_a_clean_result(self):
        """The negative control for the one skip that is a hole, not a reason."""
        root = _repository("ex-oversized-repo-for-this-test")
        (Path(root) / "large.md").write_text("english text\n" * 40, encoding="utf-8")
        subprocess.run(("git", "-C", root, "add", "--", "large.md"), check=False)
        with patch.object(observations, "SCAN_BYTE_LIMIT", 8):
            scan = observations.secret_scan(root)
        self.assertTrue(scan["ok"])
        self.assertEqual(scan["coverage"]["scanned"], 0)
        self.assertEqual(scan["coverage"]["skipped"], [])
        entry, = scan["coverage"]["notReadInFull"]
        self.assertEqual(entry["path"], "large.md")
        self.assertIn("scan limit", entry["reason"])
        self.assertFalse(scan["clean"], "an unread tracked file is not a pass")
        self.assertTrue(scan["coverageStatement"]["accountedFor"])

    def test_the_report_says_the_bytes_decided_not_the_name(self):
        coverage = self.scan["coverage"]
        self.assertIn("utf-8", coverage["textDecidedBy"])
        self.assertIn("never by file name", coverage["textDecidedBy"])
        self.assertEqual(coverage["byteLimit"], observations.SCAN_BYTE_LIMIT)

    def test_every_skip_is_named_with_its_reason(self):
        for entry in self.scan["coverage"]["skipped"]:
            with self.subTest(path=entry["path"]):
                self.assertTrue(entry["path"])
                self.assertTrue(entry["reason"])
        for entry in self.scan["coverage"]["unreadable"]:
            with self.subTest(path=entry["path"]):
                self.assertTrue(entry["reason"])
        for entry in self.scan["coverage"]["notReadInFull"]:
            with self.subTest(path=entry["path"]):
                self.assertTrue(entry["reason"])

    def test_zero_markers_is_stated_as_generic_scanning_only(self):
        statement = self.scan["coverageStatement"]
        self.assertEqual(statement["suppliedPrivateMarkers"], 0)
        self.assertTrue(any("generic" in line for line in statement["isNot"]))

    def test_supplied_markers_certify_nothing_beyond_themselves(self):
        scan = observations.secret_scan(ROOT, private_markers=("marker-a", "marker-b"))
        statement = scan["coverageStatement"]
        self.assertEqual(statement["suppliedPrivateMarkers"], 2)
        self.assertTrue(any("certifies" in line for line in statement["isNot"]))
        rendered = str(scan)
        for marker in ("marker-a", "marker-b"):
            self.assertNotIn(marker, rendered, "a marker is never echoed")

    def test_the_statement_denies_fingerprint_and_history_certification(self):
        joined = " ".join(self.scan["coverageStatement"]["isNot"])
        self.assertIn("not a private-fingerprint certification", joined)
        self.assertIn("not a historical-repository certification", joined)
        self.assertIn("not an independent security review", joined)

    def test_a_failed_enumeration_still_states_its_coverage(self):
        scan = observations.secret_scan("/tmp")
        statement = scan["coverageStatement"]
        self.assertFalse(scan["clean"])
        self.assertEqual(statement["inventoryTotal"], 0)
        self.assertEqual(statement["scannedCount"], 0)
        self.assertEqual(statement["enumerationState"], "not-a-repository")

    def test_the_bounded_coverage_sentence_matches_the_counts(self):
        statement = self.scan["coverageStatement"]
        self.assertIn(f"{statement['scannedCount']} of "
                      f"{statement['inventoryTotal']}", statement["boundedCoverage"])

    def test_it_does_not_claim_to_be_a_security_review(self):
        self.assertIn("not a substitute for an independent security review", self.scan["scope"])



class LocalizedUIClassification(unittest.TestCase):
    """UI translation data does not exempt a file from any secret check."""

    @staticmethod
    def _locale_source(value=None):
        value = value if value is not None else chr(0x4E2D)
        entries = [repr(locale) + ":{label:" + repr(value) + ",names:[" + repr(value) + "]}"
                   for locale in sorted(observations.DISPLAY_LOCALES)]
        return "'use strict';\nwindow.EX_LOCALES = {\n" + ",\n".join(entries) + "\n};\n"

    def _scan(self, files, markers=None):
        with tempfile.TemporaryDirectory(prefix="ex-localized-ui-scan-") as root:
            subprocess.run(("git", "init", "--quiet", root), check=True)
            for name, text in files.items():
                target = Path(root) / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(text, encoding="utf-8")
            subprocess.run(("git", "-C", root, "add", "--", "."), check=True)
            return observations.secret_scan(root, private_markers=markers)

    def test_localized_values_are_fully_scanned_product_data(self):
        scan = self._scan({"ui/commodity-market/locales.js": self._locale_source()})
        self.assertTrue(scan["clean"], scan["findings"])
        self.assertEqual(scan["coverage"]["scanned"], 1)
        self.assertEqual(scan["coverage"]["skipped"], [])

    def test_native_language_option_labels_are_product_data(self):
        html = '<select id="language"><option value="ja">' + chr(0x65E5) + '</option></select>'
        scan = self._scan({"ui/commodity-market/index.html": html})
        self.assertTrue(scan["clean"], scan["findings"])
        self.assertEqual(scan["coverage"]["scanned"], 1)

    def test_non_english_outside_the_language_selector_remains_a_finding(self):
        html = ('<select id="language"><option value="ja">' + chr(0x65E5)
                + '</option></select><p>' + chr(0x4E2D) + '</p>')
        scan = self._scan({"ui/commodity-market/index.html": html})
        self.assertEqual([finding["kind"] for finding in scan["findings"]], ["non-english"])

    def test_unrecognized_language_options_are_not_exempt(self):
        html = '<select id="language"><option value="other">' + chr(0x4E2D) + '</option></select>'
        scan = self._scan({"ui/commodity-market/index.html": html})
        self.assertFalse(scan["clean"])
        self.assertEqual(scan["findings"][0]["kind"], "non-english")

    def test_a_locale_filename_elsewhere_does_not_exempt_technical_prose(self):
        scan = self._scan({"docs/locales.js": self._locale_source()})
        self.assertFalse(scan["clean"])
        self.assertTrue(all(finding["kind"] == "non-english" for finding in scan["findings"]))

    def test_comments_and_executable_suffixes_are_not_translation_values(self):
        for suffix in ("// " + chr(0x4E2D), "run(" + repr(chr(0x4E2D)) + ");"):
            with self.subTest(suffix=suffix):
                scan = self._scan({"ui/commodity-market/locales.js": self._locale_source() + suffix})
                self.assertFalse(scan["clean"])
                self.assertTrue(any(finding["kind"] == "non-english" for finding in scan["findings"]))

    def test_unknown_locales_duplicate_keys_and_nested_objects_are_not_whitelisted(self):
        source = self._locale_source()
        variants = (
            source.replace("'ja':", "'other':"),
            source.replace("'ja':", "'en':"),
            source.replace("label:", "nested:{label:", 1).replace(",names:", "},names:", 1),
        )
        for value in variants:
            with self.subTest(value=value):
                scan = self._scan({"ui/commodity-market/locales.js": value})
                self.assertFalse(scan["clean"])
                self.assertTrue(any(finding["kind"] == "non-english" for finding in scan["findings"]))

    def test_every_credential_and_private_pattern_still_scans_translation_literals(self):
        for label, _ in observations.SECRET_PATTERNS + observations.PRIVATE_CONTENT_PATTERNS:
            with self.subTest(pattern=label):
                value = chr(0x4E2D) + " " + _sample(label)
                scan = self._scan({"ui/commodity-market/locales.js": self._locale_source(value)})
                self.assertFalse(scan["clean"])
                self.assertIn(label, {finding["pattern"] for finding in scan["findings"]})

    def test_configured_private_fingerprints_remain_private_inside_translations(self):
        marker = "fingerprint-" + "q" * 10
        scan = self._scan(
            {"ui/commodity-market/locales.js": self._locale_source(chr(0x4E2D) + marker)},
            markers=(marker,))
        self.assertFalse(scan["clean"])
        self.assertIn("configured private fingerprint",
                      {finding["pattern"] for finding in scan["findings"]})
        self.assertNotIn(marker, str(scan))


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


class WorkloadBaseline(unittest.TestCase):
    """EX-NFR-08 asks for load, time, backlog and failure rate, and no SLA."""

    @classmethod
    def setUpClass(cls):
        cls.report = run_all(list(DEMOS))
        cls.workload = observations.workload_observation(cls.report)

    def test_it_records_the_load_and_the_time_it_took(self):
        self.assertEqual(self.workload["scenarios"], 6)
        self.assertGreater(self.workload["recordedSteps"], 0)
        self.assertGreaterEqual(self.workload["totalScenarioMs"],
                                self.workload["slowestScenarioMs"])

    def test_the_rates_are_integers_over_a_stated_denominator(self):
        rates = self.workload["ratesPerThousand"]
        self.assertEqual(sorted(rates), ["blocked", "failed", "notRun", "passed"])
        for name, value in sorted(rates.items()):
            with self.subTest(rate=name):
                self.assertIsInstance(value, int,
                                      "no floating point appears in these records")
        self.assertEqual(self.workload["rateDenominator"],
                         sum(self.workload["outcomeTotals"][outcome] for outcome in
                             ("passed", "failed", "blocked", "not-run")))
        self.assertEqual(sum(rates.values()), 1000)

    def test_a_not_run_obligation_is_not_counted_as_a_failure(self):
        self.assertTrue(self.workload["failureRateExcludesNotRun"])
        self.assertGreater(self.workload["outcomeTotals"]["not-run"], 0,
                           "this run really does carry outstanding obligations")
        self.assertEqual(self.workload["ratesPerThousand"]["failed"], 0)
        self.assertGreater(self.workload["ratesPerThousand"]["notRun"], 0)

    def test_a_rate_over_nothing_is_null_rather_than_zero(self):
        empty = observations.workload_observation(
            {"scenarios": [], "scenariosTotal": 0,
             "totals": {"passed": 0, "failed": 0, "blocked": 0, "not-run": 0}})
        for name, value in sorted(empty["ratesPerThousand"].items()):
            with self.subTest(rate=name):
                self.assertIsNone(value, "zero would read as a measurement")

    def test_the_backlog_is_read_from_the_facts_the_scenarios_record(self):
        backlog = self.workload["backlog"]
        self.assertEqual(sorted(backlog), sorted(observations.BACKLOG_FACTS))
        outstanding = backlog["outstandingLegs"]
        self.assertEqual(outstanding["observedIn"],
                         sorted(scenario["scenarioId"]
                                for scenario in self.report["scenarios"]))
        self.assertGreater(outstanding["peak"], 0)

    def test_the_deferral_backlog_peaks_and_then_clears(self):
        deferred = self.workload["backlog"]["deferredLegs"]
        self.assertEqual(deferred["observedIn"], ["DEMO-02"],
                         "only the out-of-order scenario buffers a result")
        self.assertEqual(deferred["peak"], 1)
        self.assertEqual(deferred["clearedWhereLastRecorded"], ["DEMO-02"])
        self.assertEqual(deferred["stillCountedWhenLastRecorded"], [])

    def test_the_last_recorded_backlog_is_not_called_the_end_state(self):
        for fact, entry in sorted(self.workload["backlog"].items()):
            if entry is None:
                continue
            with self.subTest(fact=fact):
                self.assertTrue(entry["lastRecordedIsNotTheEndState"])
                self.assertIn("lastRecordedByScenario", entry)
                self.assertNotIn("finalByScenario", entry,
                                 "a scenario stops recording a fact once it is "
                                 "no longer what a step is about")
                self.assertIn("lastRecordedStepByScenario", entry)

    def test_a_fact_no_scenario_recorded_is_null_rather_than_an_empty_reading(self):
        backlog = observations.workload_observation(
            {"scenarios": [{"scenarioId": "X", "expectations": [], "steps": [],
                            "elapsedMs": 0}],
             "scenariosTotal": 1,
             "totals": {"passed": 0, "failed": 0, "blocked": 0, "not-run": 0}})["backlog"]
        for fact in observations.BACKLOG_FACTS:
            with self.subTest(fact=fact):
                self.assertIsNone(backlog[fact])

    def test_it_sets_no_service_level_and_names_no_defect(self):
        said = " ".join(self.workload["isNot"])
        self.assertIn("not a service level", said)
        self.assertIn("not a defect count", said)
        self.assertIn("not a backlog problem", said)


if __name__ == "__main__":
    unittest.main()


class PythonLocalizedUIClassification(unittest.TestCase):
    _scan = LocalizedUIClassification._scan
    @staticmethod
    def _python_source(value=None):
        value = value if value is not None else chr(0x4E2D)
        return "TEXT = " + repr({key: (value,) for key in sorted(observations.DISPLAY_LOCALES)}) + "\n"

    def test_python_display_values_are_scanned_data(self):
        scan = self._scan({"exchange/authorization_page.py": self._python_source()})
        self.assertTrue(scan["clean"], scan["findings"])
        self.assertEqual(scan["coverage"]["scanned"], 1)

    def test_python_comments_and_other_assignments_are_not_translation_data(self):
        for suffix in ("# " + chr(0x4E2D), "other = " + repr(chr(0x4E2D))):
            with self.subTest(suffix=suffix):
                scan = self._scan({"exchange/authorization_page.py": self._python_source() + suffix})
                self.assertFalse(scan["clean"])
                self.assertTrue(any(item["kind"] == "non-english" for item in scan["findings"]))

    def test_python_code_and_incomplete_tables_are_not_exempt(self):
        for source in (self._python_source().replace("'ja':", "'other':"),
                       "TEXT = make(" + repr(chr(0x4E2D)) + ")\n"):
            with self.subTest(source=source):
                scan = self._scan({"exchange/authorization_page.py": source})
                self.assertFalse(scan["clean"])

    def test_python_translation_filename_elsewhere_has_no_exemption(self):
        scan = self._scan({"docs/authorization_page.py": self._python_source()})
        self.assertFalse(scan["clean"])

    def test_all_secret_patterns_still_read_python_translations(self):
        for label, _ in observations.SECRET_PATTERNS + observations.PRIVATE_CONTENT_PATTERNS:
            with self.subTest(pattern=label):
                source = self._python_source(chr(0x4E2D) + " " + _sample(label))
                scan = self._scan({"exchange/authorization_page.py": source})
                self.assertFalse(scan["clean"])
                self.assertIn(label, {item["pattern"] for item in scan["findings"]})



class QueueDeadlineLocalizedUIClassification(unittest.TestCase):
    """Only the fixed six-locale request-window display table is UI data."""
    _scan = LocalizedUIClassification._scan

    @staticmethod
    def _source(value=None):
        value = chr(0x4E2D) if value is None else value
        return "WINDOW_TEXT = " + repr({
            locale: (value, value, value)
            for locale in sorted(observations.DISPLAY_LOCALES)
        }) + "\n"

    def test_complete_window_table_is_display_data_with_full_scan_coverage(self):
        scan = self._scan({"exchange/queue_status_page.py": self._source()})
        self.assertTrue(scan["clean"], scan["findings"])
        self.assertEqual(scan["coverage"]["scanned"], 1)
        self.assertEqual(scan["coverage"]["skipped"], [])
        self.assertEqual(scan["coverage"]["notReadInFull"], [])

    def test_comments_and_unrelated_assignments_remain_findings(self):
        for suffix in ("# " + chr(0x4E2D), "other = " + repr(chr(0x4E2D))):
            with self.subTest(suffix=suffix):
                scan = self._scan({"exchange/queue_status_page.py": self._source() + suffix})
                self.assertFalse(scan["clean"])
                self.assertTrue(any(row["kind"] == "non-english"
                                    for row in scan["findings"]))

    def test_incomplete_dynamic_or_wrong_file_window_tables_are_not_classified(self):
        for path, source in (
            ("exchange/queue_status_page.py", self._source().replace("'ja':", "'other':")),
            ("exchange/queue_status_page.py", "WINDOW_TEXT = make(" + repr(chr(0x4E2D)) + ")\n"),
            ("exchange/queue_status_page.py", self._source().replace("WINDOW_TEXT =", "OTHER_TEXT =")),
            ("docs/queue_status_page.py", self._source()),
        ):
            with self.subTest(path=path, source=source):
                scan = self._scan({path: source})
                self.assertFalse(scan["clean"])
                self.assertTrue(any(row["kind"] == "non-english"
                                    for row in scan["findings"]))

    def test_credentials_and_private_fingerprints_still_scan_window_literals(self):
        for label, _ in observations.SECRET_PATTERNS + observations.PRIVATE_CONTENT_PATTERNS:
            with self.subTest(pattern=label):
                source = self._source(chr(0x4E2D) + " " + _sample(label))
                scan = self._scan({"exchange/queue_status_page.py": source})
                self.assertFalse(scan["clean"])
                self.assertIn(label, {row["pattern"] for row in scan["findings"]})
        marker = "fingerprint-" + "w" * 10
        scan = self._scan({"exchange/queue_status_page.py": self._source(marker)},
                          markers=(marker,))
        self.assertFalse(scan["clean"])
        self.assertIn("configured private fingerprint",
                      {row["pattern"] for row in scan["findings"]})
        self.assertNotIn(marker, str(scan))


class RemintActionLocalizedDataClassification(LocalizedUIClassification):
    """Only exact literal UI data is classified; raw security scans remain."""

    def test_original_action_translation_values_keep_full_scan_coverage(self):
        name = "exchange/remint_draft_action.py"
        words = {locale: (chr(0x4E2D),) for locale in observations.DISPLAY_LOCALES}
        source = "WORDS = " + repr(words) + "\n"
        scan = self._scan({name: source})
        self.assertTrue(scan["clean"], scan["findings"])
        self.assertEqual(scan["coverage"]["scanned"], 1)
        self.assertEqual(scan["coverage"]["skipped"], [])
        scan = self._scan({name: source + "# " + chr(0x4E2D) + "\n"})
        self.assertTrue(any(row["kind"] == "non-english" for row in scan["findings"]))
        for label, _ in observations.SECRET_PATTERNS + observations.PRIVATE_CONTENT_PATTERNS:
            with self.subTest(pattern=label):
                words["en"] = (_sample(label),)
                unsafe = self._scan({name: "WORDS = " + repr(words) + "\n"})
                self.assertIn(label, {row["pattern"] for row in unsafe["findings"]})


class CheckpointedOperationLocalizedDataClassification(LocalizedUIClassification):
    """Literal display resources retain full security scanning."""

    def test_bound_operation_display_table_is_data_and_not_a_file_exemption(self):
        name = "exchange/checkpointed_operation_page.py"
        words = {locale: (chr(0x4E2D),) for locale in observations.DISPLAY_LOCALES}
        source = "TEXT = " + repr(words) + "\n"
        scan = self._scan({name: source})
        self.assertTrue(scan["clean"], scan["findings"])
        self.assertEqual(scan["coverage"]["scanned"], 1)
        self.assertEqual(scan["coverage"]["skipped"], [])
        outside = self._scan({name: source + "# " + chr(0x4E2D) + "\n"})
        self.assertTrue(any(row["kind"] == "non-english" for row in outside["findings"]))
        for label, _ in observations.SECRET_PATTERNS + observations.PRIVATE_CONTENT_PATTERNS:
            with self.subTest(pattern=label):
                words["en"] = (_sample(label),)
                unsafe = self._scan({name: "TEXT = " + repr(words) + "\n"})
                self.assertIn(label, {row["pattern"] for row in unsafe["findings"]})


class LinkedOperationLocalizedDataClassification(unittest.TestCase):
    _scan = LocalizedUIClassification._scan
    name = "exchange/linked_operation_locales.py"
    tables = ("WORDS", "TASK_LABELS", "RECOVERY_LABELS", "ECONOMIC_LABELS",
              "RECOVERY_CONFIRM_LABELS", "ASSET_RETURN_CONFIRM_LABELS")

    def source(self, table, value=None):
        value = chr(0x4E2D) if value is None else value
        return table + " = " + repr({locale: (value,) for locale in observations.DISPLAY_LOCALES}) + "\n"

    def test_exact_complete_literal_tables_remain_fully_scanned(self):
        for table in self.tables:
            with self.subTest(table=table):
                scan = self._scan({self.name: self.source(table)})
                self.assertTrue(scan["clean"], scan["findings"])
                self.assertEqual(scan["coverage"]["scanned"], 1)
                self.assertEqual(scan["coverage"]["skipped"], [])

    def test_prose_dynamic_values_and_missing_locales_are_not_exempt(self):
        for source in (self.source("WORDS") + "# " + chr(0x4E2D),
                       self.source("WORDS").replace("'ja':", "'other':"),
                       "WORDS = make(" + repr(chr(0x4E2D)) + ")\n",
                       "OTHER = " + repr(chr(0x4E2D)) + "\n"):
            scan = self._scan({self.name: source})
            self.assertTrue(any(x["kind"] == "non-english" for x in scan["findings"]))

    def test_every_secret_pattern_and_private_fingerprint_still_checks_raw_data(self):
        for label, _ in observations.SECRET_PATTERNS + observations.PRIVATE_CONTENT_PATTERNS:
            scan = self._scan({self.name: self.source("WORDS", _sample(label))})
            self.assertIn(label, {row["pattern"] for row in scan["findings"]})
        marker = "linked-fingerprint-" + "x" * 12
        scan = self._scan({self.name: self.source("WORDS", marker)}, markers=(marker,))
        self.assertIn("configured private fingerprint", {row["pattern"] for row in scan["findings"]})
        self.assertNotIn(marker, str(scan))
