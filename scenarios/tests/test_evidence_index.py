"""Item 7: the index must let a reviewer start anywhere and verify.

It is assembled from artefacts the run already produced, so these tests check
that it agrees with them rather than inventing a second opinion.
"""
import unittest
from pathlib import Path

from scenarios import evidence_index, handoff, matrix
from scenarios.demos import DEMOS, MAIN_PATHS
from scenarios.harness import run_all
from scenarios.paths import PATH_CONTRACTS

ROOT = str(Path(__file__).resolve().parents[2])


class Index(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.scenario_report = run_all(list(DEMOS))
        cls.path_report = run_all(list(PATH_CONTRACTS))
        cls.index = evidence_index.build(cls.scenario_report, cls.path_report, ROOT,
                                         {"runId": "index-test"})
        cls.rows = {row["case"]: row for row in cls.index["rows"]}

    def test_it_covers_the_six_scenarios_and_the_three_routes(self):
        runners = {entry["runner"] for entry in self.index["runners"]}
        self.assertEqual(runners, set(MAIN_PATHS) |
                         {contract.scenario_id for contract in PATH_CONTRACTS})
        self.assertEqual(self.index["runnerCount"], 9,
                         "nine runners exist; the index must not multiply them")

    def test_every_case_has_a_row_and_no_case_is_invented(self):
        self.assertEqual(sorted(self.rows), sorted(matrix.CASE_REQUIREMENTS))
        self.assertEqual(self.index["caseCount"], len(matrix.CASE_REQUIREMENTS))

    def test_each_row_carries_the_whole_chain(self):
        for case, row in sorted(self.rows.items()):
            with self.subTest(case=case):
                self.assertTrue(row["requirements"], "approved requirement")
                self.assertTrue(row["implementation"], "implementation")
                self.assertTrue(row["unitCoverage"], "test coverage")
                self.assertIn("commit", row["sourceIdentity"])
                self.assertIn("runId", row["runIdentity"])
                self.assertTrue(row["localOutcome"], "observed result")
                self.assertTrue(row["artifactReferences"], "where the row lands")

    def test_a_covered_case_carries_its_raw_expected_and_observed_values(self):
        row = self.rows["T-19"]
        self.assertGreater(row["assertionCount"], 0)
        for entry in row["assertions"]:
            with self.subTest(assertion=entry["assertion"]):
                self.assertIn("expected", entry)
                self.assertIn("observed", entry)
                self.assertIn(entry["outcome"],
                              ("passed", "failed", "blocked", "not-run"))
                # The scenarios are taken from the row itself rather than
                # guessed: the index must agree with its own coverage list.
                self.assertIn(entry["scenarioId"], row["scenarios"])

    def test_it_agrees_with_the_acceptance_matrix(self):
        built = matrix.build({}, {}, self.scenario_report, self.path_report)
        from_matrix = {row["case"]: row["localOutcome"] for row in built["rows"]}
        from_index = {case: row["localOutcome"] for case, row in self.rows.items()}
        self.assertEqual(from_index, from_matrix)
        self.assertEqual(self.index["allCasesSound"], built["allCasesSound"])
        self.assertEqual(self.index["unsoundCases"], built["unsoundCases"])

    def test_the_outcome_grouping_accounts_for_every_case(self):
        grouped = self.index["casesByOutcome"]
        total = sum(len(cases) for cases in grouped.values())
        self.assertEqual(total, self.index["caseCount"])
        for cases in grouped.values():
            self.assertEqual(sorted(cases), cases, "each group is ordered")

    def test_an_obligation_names_the_owner_that_owes_it(self):
        for case in ("T-35", "T-36", "T-37", "T-38"):
            with self.subTest(case=case):
                row = self.rows[case]
                self.assertTrue(row["remainingRealEvidence"])
                self.assertTrue(row["remainingOwner"])
                self.assertNotEqual(row["localOutcome"], "passed")

    def test_a_case_with_nothing_owed_names_no_owner(self):
        self.assertIsNone(self.rows["T-17"]["remainingOwner"])

    def test_all_thirteen_evidence_slots_stay_not_run(self):
        slots = self.index["evidenceSlots"]
        self.assertEqual(len(slots), 13)
        for slot in slots:
            with self.subTest(slot=slot["slot"]):
                self.assertEqual(slot["status"], handoff.NOT_RUN)

    def test_the_existing_owner_dependencies_are_named(self):
        dependencies = self.index["existingOwnerDependencies"]
        self.assertTrue(dependencies)
        ledger = next(entry for entry in dependencies
                      if "ledger" in entry["where"])
        self.assertIn("netToOriginalBuyer", ledger["where"])
        self.assertIn("no single unit", ledger["detail"])
        self.assertIn("changes no domain code", ledger["thisPackageDoes"])
        self.assertTrue(ledger["owner"])

    def test_it_records_failed_and_blocked_cases_on_the_same_terms(self):
        broken = {"scenarios": [{
            "scenarioId": "DEMO-X", "mainPath": "REG_DIRECT", "cases": ["T-17"],
            "passed": False, "error": None,
            "counts": {"passed": 1, "failed": 0, "blocked": 1, "not-run": 0},
            "steps": [], "scope": "local",
            "expectations": [
                {"name": "an early check", "cases": ["T-17"], "outcome": "passed",
                 "expected": 1, "observed": 1, "detail": None},
                {"name": "a check that could not run", "cases": ["T-17"],
                 "outcome": "blocked", "expected": "executed",
                 "observed": "blocked", "detail": "a reason"}]}]}
        index = evidence_index.build(broken, None, ROOT, {"runId": "broken"})
        row = {entry["case"]: entry for entry in index["rows"]}["T-17"]
        self.assertEqual(row["localOutcome"], "blocked")
        self.assertEqual(row["assertionCount"], 2)
        self.assertEqual([entry["outcome"] for entry in row["assertions"]],
                         ["passed", "blocked"])
        self.assertFalse(index["allCasesSound"])

    def test_it_tells_a_reviewer_how_to_reproduce_the_candidate(self):
        steps = self.index["reproduce"]
        self.assertTrue(any("scenarios/tests" in step for step in steps))
        self.assertTrue(any("exchange/tests" in step for step in steps))
        self.assertTrue(any("run-all" in step for step in steps))

    def test_it_claims_nothing_beyond_model_evidence(self):
        self.assertIn("model evidence", self.index["note"])
        for entry in self.index["runners"]:
            with self.subTest(runner=entry["runner"]):
                self.assertIn("no deployment", entry["scope"])


if __name__ == "__main__":
    unittest.main()


class ArtifactLeg(unittest.TestCase):
    """The last leg: which file carries a row, and where inside it.

    The index is built before the outputs are written, so the one thing these
    tests insist on is that it never claims the writing happened.
    """

    @classmethod
    def setUpClass(cls):
        cls.scenario_report = run_all(list(DEMOS))
        cls.path_report = run_all(list(PATH_CONTRACTS))
        cls.planned = evidence_index.build(
            cls.scenario_report, cls.path_report, ROOT, {"runId": "artifact-test"},
            artifacts=["/out/run.json", "/out/run.txt"])
        cls.unplanned = evidence_index.build(
            cls.scenario_report, cls.path_report, ROOT, {"runId": "artifact-test"})

    def test_a_declared_artifact_is_never_reported_as_delivered(self):
        self.assertEqual(self.planned["artifactDeliveryStatus"],
                         evidence_index.ARTIFACT_NOT_OBSERVED)
        for slot in self.planned["artifacts"]:
            with self.subTest(path=slot["path"]):
                self.assertEqual(slot["deliveryStatus"],
                                 evidence_index.ARTIFACT_NOT_OBSERVED)
                self.assertIn("outputDelivery", slot["deliveryReportedBy"])

    def test_every_row_names_each_declared_artifact_once(self):
        paths = [slot["path"] for slot in self.planned["artifacts"]]
        self.assertEqual(paths, ["/out/run.json", "/out/run.txt"])
        for row in self.planned["rows"]:
            with self.subTest(case=row["case"]):
                self.assertEqual([ref["path"] for ref in row["artifactReferences"]],
                                 paths)

    def test_a_row_pointer_resolves_this_row_inside_the_delivered_record(self):
        for position, row in enumerate(self.planned["rows"]):
            reference = row["artifactReferences"][0]
            with self.subTest(case=row["case"]):
                self.assertEqual(reference["pointerInIndex"], "#/rows/%d" % position)
                self.assertEqual(reference["pointerInArtifact"],
                                 "%s/rows/%d" % (evidence_index.BUNDLE_POINTER,
                                                 position))

    def test_the_text_output_does_not_claim_to_carry_the_row_verbatim(self):
        text = self.planned["rows"][0]["artifactReferences"][1]
        self.assertEqual(text["path"], "/out/run.txt")
        self.assertIsNone(text["pointerInArtifact"],
                          "a summary has no pointer to the row")
        self.assertIn("summary", text["note"])

    def test_no_declared_output_is_reported_as_no_artifact_not_as_a_failure(self):
        self.assertEqual(self.unplanned["artifacts"], [])
        self.assertEqual(self.unplanned["artifactCount"], 0)
        for row in self.unplanned["rows"]:
            with self.subTest(case=row["case"]):
                reference, = row["artifactReferences"]
                self.assertEqual(reference["deliveryStatus"], "NO_ARTIFACT_DECLARED")
                self.assertIsNone(reference["path"])
                self.assertIsNone(reference["pointerInArtifact"])
                self.assertEqual(reference["pointerInIndex"],
                                 "#/rows/%d" % self.unplanned["rows"].index(row))

    def test_the_artifact_leg_is_a_schema_change(self):
        self.assertEqual(self.planned["schema"], "8415ex-evidence-index/3")
        self.assertEqual(self.planned["bundlePointer"], "/evidenceIndex")
