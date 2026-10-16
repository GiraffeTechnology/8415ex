"""The outline must break when it stops describing the code.

A check that only ever passes proves nothing, so every finding here is
provoked: each test rewrites the outline into a temporary tree and asserts that
the exact finding appears.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from scenarios import storyboard
from scenarios.demos import MAIN_PATHS

ROOT = Path(__file__).resolve().parents[2]


class _Rewritten:
    """A throwaway tree holding one edited copy of the outline."""

    def __init__(self, replace, with_):
        self.replace, self.with_ = replace, with_

    def __enter__(self):
        self.directory = tempfile.mkdtemp()
        target = Path(self.directory) / "scenarios"
        target.mkdir()
        text = (ROOT / storyboard.STORYBOARD).read_text(encoding="utf-8")
        if self.replace is not None:
            assert self.replace in text, "the fixture must change something real"
            text = text.replace(self.replace, self.with_)
        (target / "STORYBOARD.md").write_text(text, encoding="utf-8")
        return self.directory

    def __exit__(self, *exception):
        shutil.rmtree(self.directory, ignore_errors=True)
        return False


def _findings(check):
    return {entry["finding"] for entry in check["findings"]}


class AsWritten(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.check = storyboard.check(str(ROOT))

    def test_the_outline_still_describes_the_code(self):
        self.assertEqual(self.check["findings"], [])
        self.assertTrue(self.check["consistent"])

    def test_every_scenario_has_exactly_one_panel_on_its_real_route(self):
        self.assertEqual(self.check["scenariosShown"], sorted(MAIN_PATHS))
        self.assertEqual(self.check["panelCount"], len(MAIN_PATHS))
        for panel in self.check["parsed"]["panels"]:
            with self.subTest(panel=panel["panel"]):
                self.assertEqual(panel["route"], MAIN_PATHS[panel["scenarioId"]])

    def test_the_deck_and_video_sections_are_read(self):
        self.assertGreater(self.check["deckSlideCount"], 0)
        self.assertGreater(self.check["videoSegmentCount"], 0)
        for segment in self.check["parsed"]["videoSegments"]:
            with self.subTest(segment=segment["segment"]):
                self.assertTrue(segment["labelling"])

    def test_every_required_claim_is_present(self):
        for claim in self.check["parsed"]["claims"]:
            with self.subTest(claim=claim["claim"]):
                self.assertTrue(claim["present"])

    def test_it_claims_neither_acceptance_nor_a_review_of_the_prose(self):
        said = " ".join(self.check["isNot"])
        self.assertIn("not acceptance of the outline", said)
        self.assertIn("not a review of the prose", said)


class WhenItDrifts(unittest.TestCase):

    def test_a_wrong_route_is_caught(self):
        with _Rewritten("DEMO-01, route REG_DIRECT",
                        "DEMO-01, route REG_ELECTRONIC") as root:
            check = storyboard.check(root)
        self.assertIn("a panel shows a scenario on the wrong route",
                      _findings(check))
        self.assertFalse(check["consistent"])

    def test_a_scenario_that_does_not_exist_is_caught(self):
        with _Rewritten("| 1 | DEMO-01, route REG_DIRECT",
                        "| 1 | DEMO-99, route REG_DIRECT") as root:
            check = storyboard.check(root)
        findings = _findings(check)
        self.assertIn("a panel names a scenario that does not exist", findings)
        self.assertIn("a scenario has no panel", findings)

    def test_a_missing_panel_is_caught(self):
        with _Rewritten(None, None) as root:
            text = Path(root, "scenarios/STORYBOARD.md").read_text(encoding="utf-8")
            kept = "\n".join(line for line in text.splitlines()
                             if not line.startswith("| 6 |"))
            Path(root, "scenarios/STORYBOARD.md").write_text(kept, encoding="utf-8")
            check = storyboard.check(root)
        self.assertIn("a scenario has no panel", _findings(check))

    def test_a_duplicated_panel_is_caught(self):
        with _Rewritten("| 6 | DEMO-06, route REG_INTERMEDIARY",
                        "| 6 | DEMO-05, route REG_ELECTRONIC") as root:
            check = storyboard.check(root)
        findings = _findings(check)
        self.assertIn("a scenario has more than one panel", findings)
        self.assertIn("a scenario has no panel", findings)

    def test_an_obligation_on_a_case_that_does_not_exist_is_caught(self):
        with _Rewritten("| Local | T-35, T-36: real transactions",
                        "| Local | T-99: real transactions") as root:
            check = storyboard.check(root)
        self.assertIn("a panel owes a case that does not exist", _findings(check))

    def test_claiming_a_discharged_case_is_still_owed_is_caught(self):
        # T-01 is covered locally and owes no remaining real evidence, so a
        # panel naming it as owed is overstating what is outstanding.
        with _Rewritten("| Local | T-35, T-36: real transactions",
                        "| Local | T-01: real transactions") as root:
            check = storyboard.check(root)
        self.assertIn("a panel says a case is still owed when it is not",
                      _findings(check))

    def test_a_panel_owing_nothing_is_caught(self):
        with _Rewritten("| Local | T-35, T-36 |", "| Local | nothing |") as root:
            check = storyboard.check(root)
        self.assertIn("a panel names nothing still owed", _findings(check))

    def test_a_dropped_required_claim_is_caught(self):
        with _Rewritten("simulated business roles", "business roles") as root:
            check = storyboard.check(root)
        self.assertIn("the outline no longer carries a required claim",
                      _findings(check))

    def test_a_video_segment_naming_an_unknown_scenario_is_caught(self):
        with _Rewritten("| Chain and registration | 60 s | DEMO-02 panels",
                        "| Chain and registration | 60 s | DEMO-98 panels") as root:
            check = storyboard.check(root)
        self.assertIn("a video segment names a scenario that does not exist",
                      _findings(check))

    def test_an_unreadable_outline_is_a_finding_not_an_empty_pass(self):
        check = storyboard.check("/nonexistent-root-for-this-test")
        self.assertFalse(check["consistent"])
        self.assertIn("the outline could not be read", _findings(check))


if __name__ == "__main__":
    unittest.main()
