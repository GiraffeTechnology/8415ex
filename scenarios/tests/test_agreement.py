"""The published record must not contradict itself, and the check must catch it.

A rebuilt report that lost an input produced a self-contradicting published
record twice. Each fix was a parameter, passed more carefully; the second
mistake was made under a comment recording the first. These tests hold the
structural check to the standard those fixes could not meet: it has to catch the
contradiction whatever caused it.
"""
import contextlib
import io
import unittest
from pathlib import Path
from unittest.mock import patch

from scenarios import agreement, cli, evidence_index

ROOT = str(Path(__file__).resolve().parents[2])


def _sealed():
    return cli.seal(cli._bundle(ROOT), 0)


class ASealedRecord(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.bundle = _sealed()
        cls.check = cls.bundle["selfAgreement"]

    def test_the_record_agrees_with_itself(self):
        self.assertEqual(self.check["disagreements"], [])
        self.assertTrue(self.check["consistent"])
        for entry in self.check["comparisons"]:
            with self.subTest(comparison=entry["comparison"]):
                self.assertTrue(entry["agrees"])
                self.assertTrue(entry["meaning"])

    def test_the_comparisons_are_real_and_not_an_empty_pass(self):
        self.assertGreater(self.check["comparisonCount"], 8)
        self.assertEqual(self.check["comparisonCount"],
                         len(self.check["comparisons"]))

    def test_the_reports_are_discovered_not_listed(self):
        """A list of report keys is what the rebuilds got wrong."""
        found = agreement.scenario_reports(self.bundle)
        self.assertEqual(sorted(found),
                         ["guaranteeReport", "pathReport", "scenarioReport"])
        self.assertEqual(self.check["scenarioReportsFound"], sorted(found))
        for key, report in sorted(found.items()):
            with self.subTest(report=key):
                self.assertEqual(report["schema"],
                                 agreement.SCENARIO_REPORT_SCHEMA)
                self.assertTrue(report["scenarios"])

    def test_it_says_what_it_is_not(self):
        joined = " ".join(self.check["isNot"])
        self.assertIn("not a check that the reports are right", joined)
        self.assertIn("not a re-run", joined)

    def test_the_verdict_is_accounted_for_rather_than_reported(self):
        """It cannot be a consistency check, so it has to be named elsewhere."""
        self.assertIn("selfAgreement", cli.HANDLED_AT_SEALING)
        self.assertIn("sealing", cli.HANDLED_AT_SEALING["selfAgreement"])
        self.assertNotIn("selfAgreement", cli.HANDLED_ELSEWHERE,
                         "that record is of reports the bundle carries all "
                         "along, and this one appears only at sealing")
        # The guard was applied to the bundle as built, which left anything
        # added at sealing outside it. The sealed record is scanned too.
        self.assertEqual(self.bundle["unclassifiedVerdicts"], [])


class WhenTheRecordContradictsItself(unittest.TestCase):
    """The negative controls, each one a way the record has gone wrong."""

    def test_the_rebuild_that_lost_a_report_is_caught(self):
        """The defect as it actually happened, reproduced exactly.

        Sealing rebuilt the evidence index without the guarantee report, so the
        published index said ten cases had only unit coverage while the matrix
        beside it said they passed.
        """
        bundle = _sealed()
        bundle["evidenceIndex"] = evidence_index.build(
            bundle["scenarioReport"], bundle["pathReport"],
            bundle["source"]["requestedRoot"],
            {"runId": bundle["runId"], "startedAt": bundle["startedAt"]},
            commands=bundle["commands"],
            observations={key: bundle[key] for key in
                          ("secretScan", "resourceObservation", "workload")},
            source=bundle["source"],
            artifacts=bundle.get("outputArtifacts"))
        found = agreement.check(bundle)
        self.assertFalse(found["consistent"])
        self.assertIn("each case has one local outcome, not two",
                      found["disagreements"])
        self.assertIn("every runner this run recorded is in the published index",
                      found["disagreements"])

    def test_sealing_refuses_a_record_that_contradicts_itself(self):
        """The gate, not just the comparison.

        A check whose failure changed nothing would be the same mistake one
        level up, so sealing has to carry the disagreement into the blocking
        list and the verdict.
        """
        bundle = cli._bundle(ROOT)
        self.assertNotIn("the sealed record contradicts itself",
                         " ".join(bundle["blocking"]))
        # One case disagrees with the index that sealing will rebuild from it.
        bundle["matrix"]["rows"][0]["localOutcome"] = "invented-outcome"
        sealed = cli.seal(bundle, 0)
        self.assertFalse(sealed["selfAgreement"]["consistent"])
        self.assertFalse(sealed["allLocalPassed"])
        self.assertFalse(sealed["calculationPassed"])
        self.assertTrue(any(item.startswith("the sealed record contradicts itself")
                            for item in sealed["blocking"]),
                        sealed["blocking"])

    def test_a_dropped_workload_observation_is_caught(self):
        bundle = _sealed()
        bundle["workload"].pop("guarantees")
        found = agreement.check(bundle)
        self.assertIn("every scenario report has a workload observation",
                      found["disagreements"])

    def test_a_sealed_digest_from_another_run_is_caught(self):
        bundle = _sealed()
        bundle["evidence"]["scenarioDigest"] = "0x" + "0" * 64
        found = agreement.check(bundle)
        self.assertIn("the sealed evidence names this run's scenario digest",
                      found["disagreements"])

    def test_the_verdict_is_not_compared_with_its_own_blocking_list(self):
        """A comparison that cannot fail for the reason it names is not one.

        Both places that set the verdict derive it from the blocking list, so
        comparing the two restates a construction rather than checking it, and
        it fires on a report that fabricates a verdict to exercise its own
        rendering. It was dropped deliberately, and the reason is recorded.
        """
        bundle = _sealed()
        bundle["blocking"] = ["something really did block"]
        bundle["allLocalPassed"] = True
        found = agreement.check(bundle)
        self.assertTrue(found["consistent"])
        self.assertNotIn("verdict", " ".join(
            entry["comparison"] for entry in found["comparisons"]))

    def test_a_runner_count_that_disagrees_with_its_list_is_caught(self):
        bundle = _sealed()
        bundle["evidenceIndex"]["runnerCount"] = 99
        found = agreement.check(bundle)
        self.assertIn("the index counts the runners it lists",
                      found["disagreements"])

    def test_a_commands_list_that_drifted_from_the_manifest_is_caught(self):
        bundle = _sealed()
        bundle["manifest"]["commands"] = []
        found = agreement.check(bundle)
        self.assertIn("the manifest carries the same commands as the bundle",
                      found["disagreements"])

    def test_an_unsound_case_visible_in_only_one_copy_is_caught(self):
        bundle = _sealed()
        bundle["matrix"]["unsoundCases"] = ["T-01"]
        found = agreement.check(bundle)
        self.assertIn("the same cases are unsound in both",
                      found["disagreements"])

    def test_a_case_missing_from_one_copy_is_caught(self):
        bundle = _sealed()
        bundle["evidenceIndex"]["rows"] = bundle["evidenceIndex"]["rows"][1:]
        found = agreement.check(bundle)
        self.assertIn("the index covers the same cases as the matrix",
                      found["disagreements"])

    def test_nothing_to_compare_is_reported_as_that_and_not_as_agreement(self):
        """The third answer, kept apart from the other two.

        A recorded bundle from an earlier run may carry no scenario reports at
        all; a run that just executed them and carries none is wrong in a way
        this module cannot diagnose. Calling the first a contradiction would be
        false, and calling it agreement would be the silent green this whole
        check exists to refuse.
        """
        found = agreement.check({})
        self.assertFalse(found["comparable"])
        self.assertEqual(found["nothingToCompare"],
                         ["no scenario report", "no indexed runners",
                          "no matrix rows"])
        self.assertEqual(found["comparisons"], [],
                         "comparing a report with an absent one is not a "
                         "comparison")
        self.assertEqual(found["disagreements"], [])
        self.assertEqual(found["scenarioReportsFound"], [])
        self.assertIn("not a claim that there was anything to compare",
                      " ".join(found["isNot"]))

    def test_a_real_run_that_carries_nothing_to_compare_is_blocked(self):
        """Where inapplicability is itself wrong, the caller says so.

        run-all has just executed the scenarios, so a sealed record with
        nothing to compare cannot be acceptable there, whatever it may mean for
        a bundle another command sealed.
        """
        real = agreement.check

        def nothing_to_compare(bundle):
            # The original, captured before patching: calling the patched name
            # would call this function again.
            return dict(real(bundle), comparable=False,
                        nothingToCompare=["no scenario report"])

        with patch.object(cli.agreement, "check", side_effect=nothing_to_compare), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = cli.main(["run-all", "--root", ROOT])
        self.assertEqual(code, 1)
        self.assertIn("the sealed record carried nothing to compare",
                      out.getvalue())


if __name__ == "__main__":
    unittest.main()
