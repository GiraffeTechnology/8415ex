"""Published section metadata integrity and explicit current-acceptance limits."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from scenarios import current_prd, prd

ROOT = str(Path(__file__).resolve().parents[2])


class SectionLedger(unittest.TestCase):
    def test_every_published_section_is_present_once(self):
        row = prd.build(ROOT)
        self.assertEqual(row["sections"], list(range(1, 22)))
        self.assertEqual(row["sectionCount"], 21)
        self.assertEqual(row["findings"], [])
        self.assertTrue(row["consistent"])

    def test_exact_published_baseline_is_distinct_from_current_complete_contract(self):
        row = prd.build(ROOT)
        self.assertEqual(row["publishedBaselineVersion"], "1.3")
        self.assertEqual(row["currentCompletePRDVersion"], "1.4.1")
        self.assertFalse(row["completeCurrentContractLoaded"])
        self.assertFalse(row["baselinePassIsCurrentPass"])
        self.assertFalse(row["historicalPassInherited"])

    def test_all_published_requirement_identifiers_remain_distinct(self):
        row = prd.build(ROOT)
        ids = [item["id"] for item in row["requirements"]]
        self.assertEqual(len(ids), 91)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, [item["id"] for item in current_prd.load(ROOT)["requirements"]])

    def test_metadata_never_promotes_cases_or_product_acceptance(self):
        row = prd.build(ROOT)
        self.assertEqual(row["acceptedCases"], [])
        self.assertEqual(row["productStatus"], "OPEN")
        self.assertEqual(row["currentSemanticAcceptance"], "OPEN")

    def test_no_metadata_rewrite_changes_the_original_loaded_report(self):
        before = current_prd.report("sections", ROOT)
        prd.build(ROOT)
        self.assertEqual(current_prd.report("sections", ROOT), before)


class WhenItDrifts(unittest.TestCase):
    def changed(self, change):
        report = copy.deepcopy(current_prd.report("sections", ROOT))
        change(report)
        with patch.object(prd, "report", return_value=report):
            return prd.build(ROOT)

    def test_missing_section_is_a_named_failure(self):
        row = self.changed(lambda x: x["sections"].remove(13))
        self.assertEqual(row["missingSectionNumbers"], [13])
        self.assertFalse(row["consistent"])

    def test_duplicate_section_is_not_complete_coverage(self):
        row = self.changed(lambda x: x["sections"].append(13))
        self.assertEqual(row["duplicatedSectionNumbers"], [13])
        self.assertFalse(row["consistent"])

    def test_unexpected_section_is_refused(self):
        row = self.changed(lambda x: x["sections"].append(22))
        self.assertEqual(row["unexpectedSectionNumbers"], [22])
        self.assertFalse(row["consistent"])

    def test_duplicate_requirement_is_not_more_coverage(self):
        row = self.changed(lambda x: x["requirements"].append(dict(x["requirements"][0])))
        self.assertFalse(row["consistent"])
        self.assertIn("duplicated published requirement identifier", [x["finding"] for x in row["findings"]])

    def test_empty_requirements_do_not_become_a_clean_report(self):
        row = self.changed(lambda x: x["requirements"].clear())
        self.assertFalse(row["consistent"])
        self.assertIn("published requirements are empty", [x["finding"] for x in row["findings"]])

    def test_failed_pin_is_not_replaced_by_structural_success(self):
        with patch.object(prd, "report", side_effect=ValueError("pin mismatch")):
            with self.assertRaisesRegex(ValueError, "pin mismatch"):
                prd.build(ROOT)
