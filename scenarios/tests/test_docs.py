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
    """A throwaway tree holding the guides and the domain command line."""

    def __enter__(self):
        self.directory = Path(tempfile.mkdtemp())
        for guide in docs.GUIDES + (docs.DOMAIN_CLI,):
            source = ROOT / guide
            target = self.directory / guide
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
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

    def test_every_named_guide_exists(self):
        self.assertEqual(self.check["guidesMissing"], [])
        self.assertEqual(sorted(self.check["guidesRead"]), sorted(docs.GUIDES))

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


if __name__ == "__main__":
    unittest.main()
