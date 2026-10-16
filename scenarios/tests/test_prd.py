"""No section of the requirements may be addressed by nothing at all.

The matrix answers one axis and the stage map another, and a section that
produced no requirement identifier and no stage entry appears in neither. That
is the gap these tests exist for, and each finding has its own negative control.
"""
import unittest
from pathlib import Path

from scenarios import matrix, prd
from scenarios.demos import DEMOS
from scenarios.guarantees import GUARANTEE_CONTRACTS
from scenarios.harness import run_all
from scenarios.paths import PATH_CONTRACTS

ROOT = str(Path(__file__).resolve().parents[2])


def _acceptance():
    """An acceptance matrix from a real run, which is what the evidence axis reads."""
    return matrix.build({"commit": "a" * 40}, {"runId": "test-run"},
                        run_all(list(DEMOS)), run_all(list(PATH_CONTRACTS)),
                        run_all(list(GUARANTEE_CONTRACTS)))


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
                                "handing a section to an owner is not an answer "
                                "on its own")

    def test_the_private_sources_section_publishes_nothing(self):
        entry = self.by_section[20]
        self.assertEqual(entry["delivers"], [])
        self.assertIn("never written into this repository",
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
        self.assertIn("a section is addressed by nothing and owed by nobody",
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
        self.assertIn("a section is handed to an owner without saying what this "
                      "surface does instead", _findings(ledger))


class WhatEstablishesEachSection(unittest.TestCase):
    """Addressed and established are different questions.

    A section was called addressed when its deliverable paths existed. Two
    sections read that way while nothing local established them: one whose three
    requirements all await real network execution, and one carrying a not-run
    obligation. The page a reviewer reads to ask whether the document is covered
    was answering with file existence.
    """

    @classmethod
    def setUpClass(cls):
        cls.acceptance = _acceptance()
        cls.ledger = prd.build(ROOT, cls.acceptance)
        cls.by_section = {entry["section"]: entry
                          for entry in cls.ledger["sections"]}

    def test_the_evidence_comes_from_the_matrix_not_from_the_disk(self):
        self.assertTrue(self.ledger["evidenceSupplied"])
        rows = {row["case"]: row["localOutcome"]
                for row in self.acceptance["rows"]}
        for section, entry in sorted(self.by_section.items()):
            with self.subTest(section=section):
                self.assertEqual(entry["caseOutcomes"],
                                 {case: rows[case] for case in entry["cases"]})

    def test_a_section_backed_only_by_awaited_evidence_is_not_established(self):
        awaiting = {entry["section"]: entry
                    for entry in self.ledger["sectionsAwaitingRealEvidence"]}
        self.assertIn(15, awaiting, "its three requirements are all not-run")
        self.assertEqual(awaiting[15]["weakestOutcome"], "not-run")
        self.assertEqual([item["case"] for item in awaiting[15]["awaiting"]],
                         ["T-35", "T-36", "T-37"])
        self.assertTrue(self.by_section[15]["addressedHere"],
                        "its deliverables are on disk, which is why it read as "
                        "addressed")
        self.assertFalse(self.by_section[15]["locallyEstablished"])
        self.assertNotIn(15, self.ledger["sectionsLocallyEstablished"])

    def test_every_awaited_case_says_what_is_owed(self):
        for entry in self.ledger["sectionsAwaitingRealEvidence"]:
            for item in entry["awaiting"]:
                with self.subTest(case=item["case"]):
                    self.assertEqual(item["requires"],
                                     matrix.REMAINING_EVIDENCE[item["case"]])
                    self.assertTrue(item["requires"])

    def test_awaiting_real_evidence_is_not_a_finding(self):
        self.assertEqual(self.ledger["sectionsWeakWithoutReason"], [])
        self.assertTrue(self.ledger["consistent"])
        self.assertIn("not a local pass for a section awaiting real evidence",
                      " ".join(self.ledger["isNot"]))

    def test_the_established_sections_rest_on_a_local_result(self):
        established = self.ledger["sectionsLocallyEstablished"]
        self.assertTrue(established)
        for section in established:
            with self.subTest(section=section):
                entry = self.by_section[section]
                self.assertIn(entry["weakestOutcome"], prd.ESTABLISHED_OUTCOMES)
                self.assertEqual(entry["awaitingRealEvidence"], [])
                self.assertTrue(entry["cases"])

    def test_a_section_carrying_no_requirement_identifier_is_named(self):
        """Addressed by deliverables and backed by no case is a real state."""
        for section in self.ledger["sectionsWithNoCases"]:
            with self.subTest(section=section):
                entry = self.by_section[section]
                self.assertTrue(entry["addressedHere"])
                self.assertEqual(entry["requirements"], [])
                self.assertFalse(entry["locallyEstablished"])

    def test_without_a_matrix_the_evidence_is_not_supplied_rather_than_passed(self):
        """A result cannot be inferred from a file being present."""
        ledger = prd.build(ROOT)
        self.assertFalse(ledger["evidenceSupplied"])
        self.assertEqual(ledger["sectionsLocallyEstablished"], [])
        self.assertEqual(ledger["sectionsAwaitingRealEvidence"], [])
        self.assertTrue(ledger["consistent"],
                        "not supplying a run is not a defect of the document")
        for entry in ledger["sections"]:
            with self.subTest(section=entry["section"]):
                self.assertEqual(entry["evidence"], "NOT_SUPPLIED")
                self.assertFalse(entry["locallyEstablished"])


class WhenTheEvidenceWeakens(unittest.TestCase):
    """The negative controls for the new axis."""

    def _with_outcome(self, case, outcome):
        acceptance = _acceptance()
        for row in acceptance["rows"]:
            if row["case"] == case:
                row["localOutcome"] = outcome
        return prd.build(ROOT, acceptance)

    def test_a_failed_case_under_a_section_is_a_finding(self):
        # T-01 backs section 3 and has no remaining-evidence record, so a
        # failure there is weakness nothing accounts for.
        ledger = self._with_outcome("T-01", "failed")
        self.assertIn("a section rests on a case that neither passed nor says "
                      "what it is still owed", _findings(ledger))
        self.assertIn(3, ledger["sectionsWeakWithoutReason"])
        self.assertFalse(ledger["consistent"])
        self.assertNotIn(3, ledger["sectionsLocallyEstablished"])

    def test_a_blocked_case_under_a_section_is_a_finding(self):
        ledger = self._with_outcome("T-01", "blocked")
        self.assertIn(3, ledger["sectionsWeakWithoutReason"])
        self.assertFalse(ledger["consistent"])

    def test_the_weakest_outcome_is_what_the_section_rests_on(self):
        """One weak case is enough: a section is no stronger than its floor."""
        ledger = self._with_outcome("T-02", "incomplete")
        section = next(entry for entry in ledger["sections"]
                       if entry["section"] == 4
                       or "T-02" in entry["cases"])
        self.assertEqual(section["weakestOutcome"], "incomplete")
        self.assertFalse(section["locallyEstablished"])

    def test_an_awaited_case_that_stops_being_accounted_for_is_a_finding(self):
        kept = dict(matrix.REMAINING_EVIDENCE)
        matrix.REMAINING_EVIDENCE.pop("T-35")
        try:
            ledger = prd.build(ROOT, _acceptance())
        finally:
            matrix.REMAINING_EVIDENCE.clear()
            matrix.REMAINING_EVIDENCE.update(kept)
        self.assertIn(15, ledger["sectionsWeakWithoutReason"])
        self.assertFalse(ledger["consistent"])


if __name__ == "__main__":
    unittest.main()
