"""Usage instructions must break when they stop being true.

Both directions matter and they are different mistakes: a documented command
that does not exist is a broken instruction a reader will follow, and a command
no guide mentions is a report nobody will find. Each finding has its own
negative control, so the check is known to fail rather than only known to pass.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from scenarios import cli, docs

ROOT = Path(__file__).resolve().parents[2]


class _Copy:
    """A throwaway tree holding everything the check reads.

    That is every guide it discovers, the domain command line it parses, and
    each runnable module it finds, so a copy behaves like the real tree instead
    of like a subset that happens to pass.
    """

    def __enter__(self):
        self.directory = Path(tempfile.mkdtemp())
        wanted = set(docs.guides(str(ROOT))["read"])
        wanted.add(docs.DOMAIN_CLI)
        wanted.update(docs.TOOL_SOURCES.values())
        wanted.update(entry["path"] for entry in docs.entry_points(str(ROOT)))
        for name in sorted(wanted):
            target = self.directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)
        return self.directory

    def __exit__(self, *exception):
        shutil.rmtree(self.directory, ignore_errors=True)
        return False


def _findings(check):
    return {entry["finding"] for entry in check["findings"]}


class AsWritten(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.check = docs.check(str(ROOT))

    def test_the_guides_and_the_commands_agree(self):
        self.assertEqual(self.check["findings"], [])
        self.assertTrue(self.check["consistent"])

    def test_every_scenario_command_exists_and_is_documented(self):
        tool = self.check["tools"]["scenarios"]
        self.assertEqual(tool["commandsThatExist"], sorted(cli.COMMANDS))
        self.assertEqual(tool["documentedButMissing"], [])
        self.assertEqual(tool["existsButUndocumented"], [])
        for command in cli.COMMANDS:
            with self.subTest(command=command):
                self.assertTrue(tool["whereEachIsShown"][command],
                                "every command names the guide that shows it")

    def test_the_domain_commands_are_read_from_the_domain_source(self):
        source = self.check["domainCommandSource"]
        self.assertTrue(source["readable"])
        self.assertIsNone(source["error"])
        self.assertEqual(source["commands"], ["queue", "timeline", "view"])
        self.assertEqual(self.check["tools"]["exchange"]["commandsThatExist"],
                         ["queue", "timeline", "view"])

    def test_every_required_guide_exists_and_the_folder_is_read_too(self):
        self.assertEqual(self.check["guidesMissing"], [])
        read = set(self.check["guidesRead"])
        self.assertTrue(set(docs.REQUIRED_GUIDES) <= read,
                        "the required guides must all be read")
        # The point of the widening: the guide folder is read as well. Four of
        # the eight entry points are documented only there, and the earlier
        # check reported itself consistent without ever opening those files.
        from_folder = sorted(name for name in read if name.startswith("docs/"))
        self.assertTrue(from_folder, "the guide folder must be read")
        self.assertGreater(len(read), len(docs.REQUIRED_GUIDES))

    def test_it_claims_only_that_a_command_exists_and_is_shown(self):
        said = " ".join(self.check["isNot"])
        self.assertIn("not a check that an instruction works", said)
        self.assertIn("not a review of the explanation", said)


class WhenTheyDrift(unittest.TestCase):

    def test_a_documented_command_that_does_not_exist_is_caught(self):
        with _Copy() as root:
            guide = root / "scenarios/README.md"
            guide.write_text(guide.read_text(encoding="utf-8")
                             + "\n```sh\npython3 -B -m scenarios.cli invented\n```\n",
                             encoding="utf-8")
            check = docs.check(str(root))
        self.assertIn("a guide shows a command that does not exist",
                      _findings(check))
        self.assertIn("invented",
                      check["tools"]["scenarios"]["documentedButMissing"])

    def test_a_command_no_guide_mentions_is_caught(self):
        with _Copy() as root:
            for guide in ("README.md", "scenarios/README.md"):
                path = root / guide
                path.write_text(
                    path.read_text(encoding="utf-8").replace(
                        "scenarios.cli operations", "scenarios.cli run-all"),
                    encoding="utf-8")
            check = docs.check(str(root))
        self.assertIn("a command exists and no guide shows it", _findings(check))
        self.assertIn("operations",
                      check["tools"]["scenarios"]["existsButUndocumented"])

    def test_a_renamed_domain_command_is_caught_from_its_own_source(self):
        with _Copy() as root:
            path = root / docs.DOMAIN_CLI
            path.write_text(path.read_text(encoding="utf-8").replace(
                '"view", "timeline", "queue"', '"view", "timeline", "backlog"'),
                encoding="utf-8")
            check = docs.check(str(root))
        findings = _findings(check)
        self.assertIn("a guide shows a command that does not exist", findings)
        self.assertIn("a command exists and no guide shows it", findings)
        self.assertEqual(check["tools"]["exchange"]["documentedButMissing"],
                         ["queue"])
        self.assertEqual(check["tools"]["exchange"]["existsButUndocumented"],
                         ["backlog"])

    def test_a_missing_guide_is_caught(self):
        with _Copy() as root:
            (root / "ci/README.md").unlink()
            check = docs.check(str(root))
        self.assertIn("a guide named here does not exist", _findings(check))
        self.assertEqual(check["guidesMissing"], ["ci/README.md"])

    def test_an_unreadable_domain_command_list_is_a_finding(self):
        check = docs.check("/nonexistent-root-for-this-test")
        self.assertFalse(check["consistent"])
        self.assertIn("the domain command list could not be read",
                      _findings(check))
        self.assertEqual(check["domainCommandSource"]["error"],
                         "EX_DOMAIN_CLI_UNREADABLE")

    def test_a_command_list_that_cannot_be_found_is_a_finding_not_an_empty_list(self):
        with _Copy() as root:
            path = root / docs.DOMAIN_CLI
            path.write_text(path.read_text(encoding="utf-8").replace(
                'add_argument("command", choices=', 'add_argument("command", values='),
                encoding="utf-8")
            check = docs.check(str(root))
        self.assertEqual(check["domainCommandSource"]["error"],
                         "EX_DOMAIN_CLI_CHOICES_NOT_FOUND")
        self.assertFalse(check["consistent"])


class EntryPoints(unittest.TestCase):
    """Every runnable module, not only the two that have subcommands."""

    @classmethod
    def setUpClass(cls):
        cls.check = docs.check(str(ROOT))

    def test_every_runnable_module_is_discovered_not_listed(self):
        found = {entry["module"] for entry in self.check["entryPoints"]}
        # Discovered from the source, so a new runnable module is covered
        # without anyone remembering to add it here.
        self.assertIn("scenarios.cli", found)
        self.assertIn("exchange.cli", found)
        self.assertIn("ci.smoke", found)
        self.assertGreater(len(found), 2,
                           "the earlier check knew only two command lines")
        self.assertEqual(len(found), self.check["entryPointCount"])

    def test_every_entry_point_is_documented_and_names_where(self):
        self.assertEqual(self.check["entryPointsUndocumented"], [])
        for entry in self.check["entryPoints"]:
            with self.subTest(module=entry["module"]):
                self.assertTrue(entry["documented"])
                self.assertTrue(entry["documentedIn"])
                for guide in entry["documentedIn"]:
                    self.assertIn(guide, self.check["guidesRead"])

    def test_a_module_taking_no_options_still_has_to_be_documented(self):
        byname = {entry["module"]: entry for entry in self.check["entryPoints"]}
        noopts = [entry for entry in byname.values() if not entry["takesOptions"]]
        self.assertTrue(noopts, "at least one runnable module takes no options")
        for entry in noopts:
            with self.subTest(module=entry["module"]):
                self.assertTrue(entry["documented"])

    def test_a_test_module_is_not_treated_as_an_entry_point(self):
        found = {entry["module"] for entry in self.check["entryPoints"]}
        for module in found:
            with self.subTest(module=module):
                self.assertNotIn(".tests.", module)
                self.assertFalse(module.split(".")[-1].startswith("test_"))

    def test_a_foreign_module_in_a_guide_is_not_a_finding(self):
        invoked = self.check["modulesInvokedByGuides"]
        self.assertIn("unittest", invoked,
                      "the guides really do invoke the test runner")
        self.assertEqual(self.check["guideInvocationsNotRunnable"], [])


class WhenEntryPointsDrift(unittest.TestCase):

    def test_an_undocumented_entry_point_is_caught(self):
        with _Copy() as root:
            extra = root / "exchange" / "newtool.py"
            extra.parent.mkdir(parents=True, exist_ok=True)
            extra.write_text("import argparse\n\n\n"
                             "def main():\n"
                             "    argparse.ArgumentParser()\n\n\n"
                             'if __name__ == "__main__":\n'
                             "    main()\n", encoding="utf-8")
            check = docs.check(str(root))
        self.assertIn("a runnable entry point is documented nowhere",
                      _findings(check))
        self.assertIn("exchange.newtool", check["entryPointsUndocumented"])
        self.assertFalse(check["consistent"])

    def test_a_guide_invoking_a_module_that_is_not_runnable_is_caught(self):
        with _Copy() as root:
            guide = root / "ci/README.md"
            guide.write_text(guide.read_text(encoding="utf-8")
                             + "\n```sh\npython3 -B -m ci.not_a_tool\n```\n",
                             encoding="utf-8")
            check = docs.check(str(root))
        self.assertIn("a guide invokes a module that is not runnable",
                      _findings(check))
        self.assertIn("ci.not_a_tool", check["guideInvocationsNotRunnable"])

    def test_dropping_the_guide_folder_makes_entry_points_undocumented(self):
        # The regression this widening fixes, stated as a test: without the
        # guide folder, the modules documented only there look undocumented.
        with _Copy() as root:
            for path in sorted((root / "docs").glob("*.md")):
                path.unlink()
            check = docs.check(str(root))
        self.assertIn("a runnable entry point is documented nowhere",
                      _findings(check))
        self.assertIn("exchange.demo_package", check["entryPointsUndocumented"])
        self.assertIn("exchange.demo_ui", check["entryPointsUndocumented"])


class Options(unittest.TestCase):
    """One level below a subcommand, and it was not being checked.

    A renamed option breaks every documented instruction that carries it, and
    an option no guide shows is a capability nobody will use. Neither made
    anything go red: the check knew the subcommands existed and nothing about
    what they accept.
    """

    @classmethod
    def setUpClass(cls):
        cls.check = docs.check(str(ROOT))

    def test_the_scenario_options_and_the_guides_agree(self):
        tool = self.check["options"]["scenarios"]
        self.assertTrue(tool["gatedHere"])
        self.assertEqual(tool["documentedButNotAccepted"], [])
        self.assertEqual(tool["acceptedButUndocumented"], [])
        self.assertTrue(tool["consistent"])
        for option in tool["optionsAccepted"]:
            with self.subTest(option=option):
                self.assertTrue(tool["whereEachIsShown"][option],
                                "every option names the guide that shows it")

    def test_the_accepted_options_are_read_from_the_command_line_source(self):
        self.assertEqual(self.check["optionSources"], dict(docs.TOOL_SOURCES))
        self.assertEqual(self.check["optionSourcesUnreadable"], [])
        self.assertEqual(self.check["options"]["scenarios"]["optionsAccepted"],
                         ["--execute-suites", "--json", "--json-out", "--root",
                          "--text-out"])

    def test_the_domain_options_are_observed_and_say_why_they_are_not_gated(self):
        """A one-sided finding is kept visible without being claimed as ours.

        The domain command line's guide is not written from this package, so an
        option undocumented there is reported rather than asserted as this
        package's defect. Reporting it as nothing at all would be the quiet
        version of the same mistake.
        """
        self.assertFalse(self.check["options"]["exchange"]["gatedHere"])
        observed = self.check["optionsObservedNotGated"]
        self.assertTrue(observed)
        for entry in observed:
            with self.subTest(option=entry["option"]):
                self.assertEqual(entry["tool"], "exchange")
                self.assertTrue(entry["notGatedBecause"])
                self.assertIn(entry["observation"],
                              ("accepted but shown in no guide",
                               "shown in a guide but not accepted"))
        self.assertNotIn("an option exists and no guide shows it",
                         _findings(self.check))

    def test_a_copy_of_the_tree_is_consistent_too(self):
        with _Copy() as directory:
            self.assertTrue(docs.check(str(directory))["consistent"])


class WhenOptionsDrift(unittest.TestCase):
    """The negative controls. A check that only passes proves nothing."""

    def test_an_option_no_guide_shows_is_caught(self):
        with _Copy() as directory:
            source = directory / docs.TOOL_SOURCES["scenarios"]
            source.write_text(
                source.read_text(encoding="utf-8").replace(
                    'parser.add_argument("--root", default=".")',
                    'parser.add_argument("--root", default=".")\n'
                    '    parser.add_argument("--undocumented-switch")'),
                encoding="utf-8")
            check = docs.check(str(directory))
        self.assertIn("an option exists and no guide shows it", _findings(check))
        self.assertIn("--undocumented-switch",
                      check["options"]["scenarios"]["acceptedButUndocumented"])
        self.assertFalse(check["consistent"])

    def test_an_option_the_command_line_does_not_accept_is_caught(self):
        with _Copy() as directory:
            guide = directory / "scenarios/README.md"
            guide.write_text(
                guide.read_text(encoding="utf-8").replace(
                    "python3 -B -m scenarios.cli run-all --execute-suites",
                    "python3 -B -m scenarios.cli run-all --no-such-option"),
                encoding="utf-8")
            check = docs.check(str(directory))
        self.assertIn("a guide shows an option the command line does not accept",
                      _findings(check))
        self.assertIn("--no-such-option",
                      check["options"]["scenarios"]["documentedButNotAccepted"])

    def test_an_unreadable_command_line_source_is_a_finding_not_an_empty_set(self):
        with _Copy() as directory:
            (directory / docs.TOOL_SOURCES["scenarios"]).unlink()
            check = docs.check(str(directory))
        self.assertIn("a command line's option list could not be read",
                      _findings(check))
        self.assertEqual([entry["tool"] for entry in check["optionSourcesUnreadable"]],
                         ["scenarios"])
        self.assertFalse(check["consistent"])

    def test_an_option_on_its_own_line_is_attributed_to_the_invocation(self):
        """Without joining continuations, exactly these would be missed."""
        joined = docs._logical_lines(
            "python3 -B -m scenarios.cli run-all \\\n"
            "  --json-out /tmp/one.json \\\n"
            "  --text-out /tmp/one.txt\n"
            "unrelated --flag\n")
        self.assertEqual(len(joined), 2)
        self.assertIn("--json-out", joined[0])
        self.assertIn("--text-out", joined[0])
        self.assertEqual(joined[1], "unrelated --flag")

    def test_an_option_outside_an_invocation_is_not_attributed_to_a_tool(self):
        with _Copy() as directory:
            guide = directory / "scenarios/README.md"
            guide.write_text(
                guide.read_text(encoding="utf-8")
                + "\n\nProse mentioning --not-an-option on its own line.\n",
                encoding="utf-8")
            check = docs.check(str(directory))
        self.assertEqual(check["options"]["scenarios"]["documentedButNotAccepted"],
                         [])
        self.assertTrue(check["consistent"])


if __name__ == "__main__":
    unittest.main()
