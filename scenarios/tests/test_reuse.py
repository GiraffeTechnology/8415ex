"""Stage 0: what this package reuses, and what is not located yet.

The reuse map is only worth having if it cannot drift. These tests check it
against the imported modules and against the package's own import statements,
so a domain rename or a new dependency breaks a test instead of quietly
leaving the map wrong.
"""
import unittest
from pathlib import Path

from scenarios import decisions, reuse
from scenarios.demos import DEMOS
from scenarios.harness import run_all

ROOT = str(Path(__file__).resolve().parents[2])


class DomainReuse(unittest.TestCase):

    def test_every_declared_name_resolves_on_the_module_it_names(self):
        for entry in reuse.observed_domain_modules():
            with self.subTest(module=entry["module"]):
                self.assertIsNone(entry["error"])
                self.assertEqual(entry["unresolvedNames"], [],
                                 "a declared name no longer exists on the module; "
                                 "the domain moved and this map did not")
                self.assertEqual(sorted(entry["uses"]), entry["resolvedNames"])

    def test_the_map_accounts_for_every_domain_import_in_the_shipped_modules(self):
        coverage = reuse.declared_coverage(ROOT)
        self.assertEqual(coverage["undeclaredModules"], [],
                         "a shipped module imports a domain module this map "
                         "does not mention")
        self.assertEqual(coverage["declaredButNotImported"], [],
                         "this map claims a dependency the code no longer has")
        self.assertTrue(coverage["complete"])

    def test_a_test_only_import_is_reported_separately_not_as_package_reuse(self):
        coverage = reuse.declared_coverage(ROOT)
        # The suites import domain modules to assert things about them. That is
        # not this package consuming them, so it must not be counted as reuse,
        # and must not be hidden either.
        self.assertNotIn("exchange.ledger", coverage["importsFoundInModules"])
        self.assertIn("exchange", coverage["importsFoundInTests"])
        self.assertIn("ledger", coverage["importsFoundInTests"]["exchange"])
        self.assertIn("exchange", coverage["importedOnlyByTests"])

    def test_source_imports_are_read_from_the_files_not_from_a_list(self):
        found = reuse.source_imports(ROOT)
        self.assertIn("exchange.ids", found["modules"])
        self.assertEqual(found["modules"]["exchange.ids"],
                         ["canonical_json", "digest"])

    def test_an_undeclared_import_would_be_caught(self):
        # Proving the check can fail: with one declaration removed, the module
        # it covered must be reported as undeclared.
        kept = tuple(entry for entry in reuse.DOMAIN_REUSE
                     if entry["module"] != "exchange.ids")
        original = reuse.DOMAIN_REUSE
        reuse.DOMAIN_REUSE = kept
        try:
            coverage = reuse.declared_coverage(ROOT)
        finally:
            reuse.DOMAIN_REUSE = original
        self.assertIn("exchange.ids", coverage["undeclaredModules"])
        self.assertFalse(coverage["complete"])

    def test_a_local_fixture_is_labelled_simulated_and_a_domain_fact_is_not(self):
        kinds = {entry["module"]: entry for entry in reuse.DOMAIN_REUSE}
        self.assertTrue(kinds["exchange.fixtures"]["simulated"])
        self.assertFalse(kinds["exchange.ids"]["simulated"])
        self.assertFalse(kinds["exchange.model"]["simulated"])


class Adapters(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.report = run_all(list(DEMOS))
        cls.map = reuse.build(cls.report, ROOT)

    def test_every_adapter_role_is_simulated(self):
        self.assertTrue(self.map["allAdaptersSimulated"])
        for entry in self.map["adapterRoles"]:
            with self.subTest(role=entry["role"]):
                self.assertTrue(entry["simulated"])
                self.assertIn("not located", entry["realInterface"])

    def test_the_recorded_adapters_come_from_the_run_not_from_this_module(self):
        recorded = self.map["adaptersRecordedInThisRun"]
        self.assertTrue(recorded, "the scenarios record their simulated adapters")
        declared = {entry["role"] for entry in reuse.ADAPTER_ROLES}
        self.assertTrue(set(recorded) <= declared,
                        "a role was recorded that this map does not declare")

    def test_an_empty_report_records_no_adapter_rather_than_this_modules_list(self):
        self.assertEqual(reuse.adapters_recorded_by(None), {})
        self.assertEqual(reuse.adapters_recorded_by({"scenarios": []}), {})


class Unlocated(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.map = reuse.build(None, ROOT)

    def test_each_unlocated_interface_names_a_real_open_decision(self):
        known = {entry["id"] for entry in decisions.OPEN_DECISIONS}
        for entry in self.map["unlocatedInterfaces"]:
            with self.subTest(interface=entry["interface"]):
                self.assertIn(entry["trackedBy"], known)
                self.assertTrue(entry["decision"],
                                "the tracked decision must be quoted, not just cited")
                self.assertTrue(entry["owner"])
                self.assertTrue(entry["neededFor"])

    def test_it_does_not_present_an_unlocated_interface_as_a_defect(self):
        self.assertEqual(self.map["unlocatedCount"],
                         len(reuse.UNLOCATED_INTERFACES))
        self.assertIn("dependency", self.map["meaning"])

    def test_it_claims_no_real_component_was_exercised(self):
        self.assertIn("no real registrar", self.map["meaning"])
        self.assertEqual(self.map["schema"], "8415ex-reuse-map/1")


if __name__ == "__main__":
    unittest.main()
