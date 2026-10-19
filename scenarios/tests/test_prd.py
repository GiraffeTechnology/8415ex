"""No section of the requirements may be addressed by nothing at all.

The matrix answers one axis and the stage map another, and a section that
produced no requirement identifier and no stage entry appears in neither. That
is the gap these tests exist for, and each finding has its own negative control.
"""
import unittest
from pathlib import Path

from scenarios import matrix, prd

ROOT = str(Path(__file__).resolve().parents[2])


def _findings(ledger):
    return {entry["finding"] for entry in ledger["findings"]}


class SectionLedger(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ledger = prd.build(ROOT)
        cls.by_section = {entry["section"]: entry
                          for entry in cls.ledger["sections"]}

    def test_every_section_number_is_present_with_no_gaps(self):
        self.assertEqual(sorted(self.by_section), list(range(1, 22)))
        self.assertEqual(self.ledger["missingSectionNumbers"], [])
        self.assertEqual(self.ledger["sectionCount"], 21)

    def test_nothing_is_addressed_by_nothing(self):
        self.assertEqual(self.ledger["findings"], [])
        self.assertTrue(self.ledger["consistent"])
        for section, entry in sorted(self.by_section.items()):
            with self.subTest(section=section):
                self.assertTrue(entry["addressedHere"] or entry["owner"],
                                "a section must be addressed here or owed to "
                                "someone by name")

    def test_every_declared_requirement_family_belongs_to_a_section(self):
        families = {name.rsplit("-", 1)[0]
                    for name in matrix.DECLARED_REQUIREMENTS}
        self.assertEqual(self.ledger["requirementFamiliesUnplaced"], [])
        self.assertEqual(set(self.ledger["requirementFamiliesPlaced"]), families)

    def test_every_requirement_a_section_names_really_exists(self):
        for section, entry in sorted(self.by_section.items()):
            for family in entry["requirementFamilies"]:
                with self.subTest(section=section, family=family["family"]):
                    self.assertTrue(family["declared"])
                    self.assertGreater(family["requirementCount"], 0)
                    for name in family["requirements"]:
                        self.assertIn(name, matrix.DECLARED_REQUIREMENTS)

    def test_every_deliverable_a_section_names_is_on_disk(self):
        for section, entry in sorted(self.by_section.items()):
            for delivers in entry["delivers"]:
                with self.subTest(section=section, where=delivers["where"]):
                    self.assertTrue(delivers["exists"])

    def test_a_section_owed_elsewhere_says_what_is_done_here_instead(self):
        owed = self.ledger["sectionsOwedElsewhere"]
        self.assertEqual(owed, [1, 11, 20])
        for section in owed:
            entry = self.by_section[section]
            with self.subTest(section=section):
                self.assertTrue(entry["owner"])
                self.assertTrue(entry["thisSurfaceDoes"],
                                'naming an evidence category is not an answer on its own')

    def test_the_private_sources_section_publishes_nothing(self):
        entry = self.by_section[20]
        self.assertEqual(entry["delivers"], [])
        self.assertIn('PRD.md records the product requirements',
                      entry["thisSurfaceDoes"])

    def test_it_reproduces_none_of_the_document_and_claims_no_acceptance(self):
        said = " ".join(self.ledger["isNot"])
        self.assertIn("not the requirements document", said)
        self.assertIn("not a completeness claim", said)
        self.assertIn("not an acceptance decision", said)


class WhenItDrifts(unittest.TestCase):

    def _rebuilt(self, sections):
        kept = prd.SECTIONS
        prd.SECTIONS = sections
        try:
            return prd.build(ROOT)
        finally:
            prd.SECTIONS = kept

    def test_a_section_addressed_by_nothing_is_caught(self):
        ledger = self._rebuilt(tuple(
            dict(entry, families=(), delivers=(), owner=None, thisSurfaceDoes=None)
            if entry["section"] == 13 else entry for entry in prd.SECTIONS))
        self.assertIn('a section has no implementation or evidence category',
                      _findings(ledger))
        self.assertFalse(ledger["consistent"])

    def test_a_deliverable_that_is_not_there_is_caught(self):
        ledger = self._rebuilt(tuple(
            dict(entry, delivers=("scenarios/not_a_module.py",))
            if entry["section"] == 13 else entry for entry in prd.SECTIONS))
        self.assertIn("a section names a deliverable that is not there",
                      _findings(ledger))

    def test_a_requirement_family_that_does_not_exist_is_caught(self):
        ledger = self._rebuilt(tuple(
            dict(entry, families=("EX-INVENTED",))
            if entry["section"] == 13 else entry for entry in prd.SECTIONS))
        self.assertIn("a section names a requirement family that does not exist",
                      _findings(ledger))

    def test_a_family_left_out_of_every_section_is_caught(self):
        ledger = self._rebuilt(tuple(
            dict(entry, families=tuple(family for family in entry["families"]
                                       if family != "EX-EXIT"))
            for entry in prd.SECTIONS))
        self.assertIn("a declared requirement family belongs to no section",
                      _findings(ledger))
        self.assertIn("EX-EXIT", ledger["requirementFamiliesUnplaced"])

    def test_a_missing_section_number_is_caught(self):
        ledger = self._rebuilt(tuple(entry for entry in prd.SECTIONS
                                     if entry["section"] != 13))
        self.assertIn("a section number is missing from this ledger",
                      _findings(ledger))
        self.assertEqual(ledger["missingSectionNumbers"], [13])

    def test_an_owner_with_no_local_answer_is_caught(self):
        ledger = self._rebuilt(tuple(
            dict(entry, thisSurfaceDoes=None)
            if entry["section"] == 11 else entry for entry in prd.SECTIONS))
        self.assertIn('a section names an evidence category without describing this surface', _findings(ledger))


if __name__ == "__main__":
    unittest.main()
