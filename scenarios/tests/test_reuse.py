"""Stage 0: what this package reuses, and what is not located yet.

The reuse map is only worth having if it cannot drift. These tests check it
against the imported modules and against the package's own import statements,
so a domain rename or a new dependency breaks a test instead of quietly
leaving the map wrong.
"""
import ast
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        """The mechanism, over a tree built for it.

        This used to point at whichever real module only the suites touched.
        There is no longer one - every domain module a suite reaches is now
        imported by a shipped module too - and a test that depends on that
        coincidence tests nothing once the coincidence ends. So the split is
        exercised over a tree where a test-only import exists by construction.
        """
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "scenarios"
            (package / "tests").mkdir(parents=True)
            (package / "shipped.py").write_text(
                "from exchange.ids import digest\n", encoding="utf-8")
            # A real module the reuse map does not declare, so the test-only
            # bucket is the only place it can legitimately appear.
            (package / "tests" / "test_only.py").write_text(
                "from exchange.views import nothing_here\n", encoding="utf-8")
            found = reuse.source_imports(directory)
            coverage = reuse.declared_coverage(directory)
        self.assertEqual(found["modules"], {"exchange.ids": ["digest"]})
        self.assertEqual(found["tests"], {"exchange.views": ["nothing_here"]})
        self.assertNotIn("exchange.views", coverage["importsFoundInModules"])
        self.assertIn("exchange.views", coverage["importsFoundInTests"])
        self.assertIn("exchange.views", coverage["importedOnlyByTests"])

    def test_the_real_tree_currently_has_no_test_only_domain_import(self):
        """A state, not a requirement.

        Every domain module the suites reach is now imported by a shipped module
        as well. Asserting it keeps the number honest: if it changes, the module
        that became test-only is named here rather than appearing silently in a
        report.
        """
        coverage = reuse.declared_coverage(ROOT)
        self.assertEqual(coverage["importedOnlyByTests"], [])
        for module in coverage["importsFoundInTests"]:
            with self.subTest(module=module):
                self.assertIn(module, coverage["importsFoundInModules"])

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
        self.assertEqual(self.map["schema"], "8415ex-reuse-map/2")


class Consumers(unittest.TestCase):
    """The other direction: what depends on this package.

    The declared half says what this package consumes. This half says what
    would break if this package renamed something, which was unstated until
    another surface had already come to depend on seven of these modules.
    """

    @classmethod
    def setUpClass(cls):
        cls.consumers = reuse.consumers(ROOT)

    def test_the_depending_surface_is_reported_with_what_it_uses(self):
        self.assertTrue(self.consumers["dependedOn"],
                        "another surface really does import this package")
        byname = {entry["module"]: entry for entry in self.consumers["dependedOn"]}
        self.assertIn("scenarios", byname)
        # These are load-bearing for the joined surface: renaming one breaks it.
        for module in ("cli", "demos", "handoff", "harness", "matrix", "paths",
                       "validation"):
            with self.subTest(module=module):
                self.assertIn(module, byname["scenarios"]["names"])

    def test_every_name_it_depends_on_resolves(self):
        self.assertEqual(self.consumers["unresolvedNames"], [])
        self.assertEqual(self.consumers["unreadableFiles"], [])
        self.assertTrue(self.consumers["consistent"])
        for entry in self.consumers["dependedOn"]:
            with self.subTest(module=entry["module"]):
                self.assertIsNone(entry["error"])
                self.assertEqual(entry["unresolvedNames"], [])

    def test_each_dependency_names_the_files_that_make_it(self):
        for entry in self.consumers["dependedOn"]:
            with self.subTest(module=entry["module"]):
                self.assertTrue(entry["importedBy"])
                for where in entry["importedBy"]:
                    self.assertTrue(where.endswith(".py"))

    def test_it_says_what_the_report_is_for(self):
        self.assertIn("break on", self.consumers["meaning"])

    def test_a_name_that_stopped_existing_is_caught(self):
        # The negative control. Without it this only shows that nothing
        # currently depends on a missing name, not that drift is detected.
        with tempfile.TemporaryDirectory() as directory:
            surface = Path(directory) / reuse.CONSUMER_SURFACES[0]
            surface.mkdir()
            (surface / "test_drifted.py").write_text(
                "from scenarios.harness import NoLongerThere\n", encoding="utf-8")
            found = reuse.consumers(directory)
        self.assertIn("scenarios.harness.NoLongerThere", found["unresolvedNames"])
        self.assertFalse(found["consistent"])

    def test_a_module_that_stopped_existing_is_caught(self):
        with tempfile.TemporaryDirectory() as directory:
            surface = Path(directory) / reuse.CONSUMER_SURFACES[0]
            surface.mkdir()
            (surface / "test_gone.py").write_text(
                "from scenarios.no_such_module import thing\n", encoding="utf-8")
            found = reuse.consumers(directory)
        self.assertFalse(found["consistent"])
        entry, = [row for row in found["dependedOn"]
                  if row["module"] == "scenarios.no_such_module"]
        self.assertIsNotNone(entry["error"])
        self.assertEqual(entry["unresolvedNames"], ["thing"])

    def test_a_file_that_cannot_be_parsed_is_reported_not_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            surface = Path(directory) / reuse.CONSUMER_SURFACES[0]
            surface.mkdir()
            (surface / "test_broken.py").write_text(
                "from scenarios import (\n", encoding="utf-8")
            found = reuse.consumers(directory)
        self.assertFalse(found["consistent"])
        self.assertEqual(len(found["unreadableFiles"]), 1)
        self.assertIn("SyntaxError", found["unreadableFiles"][0]["error"])

    def test_no_depending_surface_is_not_a_finding(self):
        with tempfile.TemporaryDirectory() as directory:
            found = reuse.consumers(directory)
        self.assertEqual(found["dependedOn"], [])
        self.assertTrue(found["consistent"],
                        "nothing depending on the package is not a defect")

    def test_the_map_carries_this_half_too(self):
        built = reuse.build(None, ROOT)
        self.assertIn("consumers", built)
        self.assertTrue(built["consumers"]["consistent"])

    def test_the_answer_does_not_depend_on_what_this_run_imported(self):
        # The report is read by a subcommand that imports almost nothing and by
        # a test suite that imports everything. If resolution went through the
        # loaded module, the same source would be consistent in one and a
        # finding in the other, which is worse than no check at all.
        with tempfile.TemporaryDirectory() as directory:
            surface = Path(directory) / reuse.CONSUMER_SURFACES[0]
            surface.mkdir()
            (surface / "test_attribute.py").write_text(
                "from scenarios.demos import DEMOS\n", encoding="utf-8")
            loaded = reuse.consumers(directory)
            kept = sys.modules.pop("scenarios.demos")
            try:
                unloaded = reuse.consumers(directory)
            finally:
                sys.modules["scenarios.demos"] = kept
        for found in (loaded, unloaded):
            entry, = [row for row in found["dependedOn"]
                      if row["module"] == "scenarios.demos"]
            self.assertEqual(entry["resolvedNames"], ["DEMOS"])
        self.assertEqual(loaded, unloaded)

    def test_a_name_that_cannot_be_decided_is_neither_resolved_nor_missing(self):
        # The negative control for the fail-closed branch. A module whose own
        # names cannot be read in full must not make a name look present, and
        # must not accuse it of being absent either.
        with tempfile.TemporaryDirectory() as directory:
            surface = Path(directory) / reuse.CONSUMER_SURFACES[0]
            surface.mkdir()
            (surface / "test_opaque.py").write_text(
                "from scenarios.demos import WhoKnows\n", encoding="utf-8")
            with patch.object(reuse, "_surface", return_value=(set(), True)):
                found = reuse.consumers(directory)
        entry, = [row for row in found["dependedOn"]
                  if row["module"] == "scenarios.demos"]
        self.assertEqual(entry["undecidedNames"], ["WhoKnows"])
        self.assertEqual(entry["unresolvedNames"], [])
        self.assertEqual(found["undecidedNames"], ["scenarios.demos.WhoKnows"])
        self.assertFalse(found["consistent"],
                         "an undecided name is not a pass")


class ReadingAModuleSurface(unittest.TestCase):
    """What a module offers, read from its source instead of by importing it.

    Importing a module to ask what it holds would change the set of loaded
    modules mid-run, which the provenance snapshot reports as the source
    moving. So the names are parsed, and the parse has to be right about which
    names a module actually exports.
    """

    def names(self, source):
        return reuse._bound_names(ast.parse(source))

    def test_module_level_bindings_are_found(self):
        found = self.names("VALUE = 1\n"
                           "def work():\n    pass\n"
                           "class Thing:\n    pass\n"
                           "import json\n"
                           "from pathlib import Path as Where\n"
                           "first, second = 1, 2\n"
                           "annotated: int = 3\n")
        self.assertEqual(found, {"VALUE", "work", "Thing", "json", "Where",
                                 "first", "second", "annotated"})

    def test_a_name_bound_inside_a_function_is_not_importable(self):
        # The negative control: counting these would make a missing name look
        # present, which is the one error this check must not make.
        self.assertEqual(self.names("def work():\n    inner = 1\n    return inner\n"),
                         {"work"})

    def test_a_name_bound_inside_a_class_body_is_not_importable(self):
        self.assertEqual(self.names("class Thing:\n    member = 1\n"), {"Thing"})

    def test_a_star_import_makes_the_set_incomplete(self):
        self.assertTrue(reuse._reads_star(ast.parse("from json import *\n")))
        self.assertFalse(reuse._reads_star(ast.parse("from json import loads\n")))

    def test_a_module_with_no_readable_source_is_reported_incomplete(self):
        offered, incomplete = reuse._surface("sys")
        self.assertEqual(offered, set())
        self.assertTrue(incomplete, "a built-in module has no source to parse")

    def test_a_real_module_is_read_from_its_own_file(self):
        offered, incomplete = reuse._surface("scenarios.demos")
        self.assertFalse(incomplete)
        self.assertIn("DEMOS", offered)


if __name__ == "__main__":
    unittest.main()
