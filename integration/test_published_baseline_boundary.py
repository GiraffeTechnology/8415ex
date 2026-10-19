"""Approved-remote-only definitions; requirement metadata is not product PASS."""
import unittest
from unittest.mock import patch
from scenarios import current_prd


class PublishedBaselineBoundary(unittest.TestCase):
    def test_public_report_explicitly_distinguishes_historical_and_current_contract(self):
        plan = {"version": "1.4", "retiredRequirements": [], "cases": []}
        with patch.object(current_prd, "load", return_value=plan):
            row = current_prd.report("matrix")
        self.assertEqual(row["version"], "1.4")
        self.assertEqual(row["publishedBaselineVersion"], "1.4")
        self.assertEqual(row["currentCompletePRDVersion"], "1.4")
        self.assertTrue(row["completeCurrentContractLoaded"])
        self.assertFalse(row["baselinePassIsCurrentPass"])
        self.assertEqual(row["acceptedCases"], [])
        self.assertFalse(row["historicalPassInherited"])
        self.assertFalse(row["allCasesSound"])

    def test_old_scenario_revision_does_not_bypass_current_semantic_migration(self):
        with patch.object(current_prd, "load", return_value={}):
            for revision in (None, "1.2", "1.3"):
                with self.assertRaisesRegex(ValueError, "complete current v1.4"):
                    current_prd.require_current_scenario("DEMO-01", revision)

    def test_legacy_command_remains_unexecuted_without_global_stop_or_old_pass(self):
        with patch.object(current_prd, "load", return_value={"retiredRequirements": []}):
            row = current_prd.blocked("demo")
        self.assertEqual(row["version"], "1.4")
        self.assertEqual(row["publishedBaselineVersion"], "1.4")
        self.assertEqual(row["status"], "PRD_MIGRATION_REQUIRED")
        self.assertFalse(row["executed"])
        self.assertFalse(row["allPassed"])
        self.assertTrue(row["independentWorkMayContinue"])
