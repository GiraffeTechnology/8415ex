"""The stage map must be checkable, not decorative.

A stage map reads as authoritative, so these tests insist it cannot claim a
module that is not there, cannot disagree with the acceptance matrix, and cannot
present a stage's local half as the whole of it.
"""
import tempfile
import unittest
from pathlib import Path

from scenarios import cli, handoff, matrix, stages

ROOT = str(Path(__file__).resolve().parents[2])


class StageMap(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.map = stages.build(ROOT)
        cls.by_stage = {entry["stage"]: entry for entry in cls.map["stages"]}

    def test_it_covers_every_stage_once(self):
        self.assertEqual(sorted(self.by_stage), [0, 1, 2, 3, 4, 5])
        self.assertEqual(self.map["stageCount"], 6)

    def test_every_deliverable_names_a_path_that_exists(self):
        for stage, entry in sorted(self.by_stage.items()):
            for deliverable in entry["developedHere"]:
                with self.subTest(stage=stage, where=deliverable["where"]):
                    self.assertTrue(deliverable["whereExists"],
                                    "a deliverable may not claim a module that is "
                                    "not there")
        self.assertEqual(self.map["missingDeliverablePaths"], [])

    def test_a_deliverable_claiming_a_missing_module_would_be_reported(self):
        kept = dict(stages.DEVELOPED_HERE)
        stages.DEVELOPED_HERE[0] = kept[0] + (
            {"deliverable": "a module that does not exist",
             "where": "scenarios/not_a_module.py"},)
        try:
            broken = stages.build(ROOT)
        finally:
            stages.DEVELOPED_HERE[0] = kept[0]
        self.assertEqual(broken["missingDeliverablePaths"],
                         ["scenarios/not_a_module.py"])
        self.assertFalse(broken["agreesWithMatrix"])

    def test_the_case_lists_come_from_the_matrix_not_from_this_module(self):
        grouped = stages.cases_by_stage()
        from_matrix = {}
        for case, stage in matrix.CASE_STAGE.items():
            from_matrix.setdefault(str(stage), []).append(case)
        self.assertEqual({stage: sorted(cases) for stage, cases in grouped.items()},
                         {stage: sorted(cases) for stage, cases in from_matrix.items()})

    def test_every_matrix_case_is_assigned_and_none_is_invented(self):
        self.assertEqual(self.map["casesInNoStage"], [])
        self.assertEqual(self.map["casesInNoMatrixRow"], [])
        self.assertEqual(self.map["duplicatedCases"], [])
        self.assertTrue(self.map["agreesWithMatrix"])

    def test_a_case_belonging_to_every_stage_is_named_not_dropped(self):
        self.assertEqual(self.map["casesNotAssignedToANumberedStage"],
                         ["T-39", "T-40"])

    def test_the_stage_with_no_cases_still_has_deliverables(self):
        baseline = self.by_stage[0]
        self.assertEqual(baseline["cases"], [],
                         "the baseline stage has no acceptance case of its own")
        self.assertGreater(baseline["developedHereCount"], 0)


class EveryShippedModuleIsClaimed(unittest.TestCase):
    """The other direction of the path check, which was missing.

    Checking only that a claimed path exists caught a map pointing at nothing
    and said nothing about a module that is there and claimed by nothing. Three
    shipped modules were absent from the map that way, one of them a whole
    contract group, while the map still read as what is developed here.
    """

    @classmethod
    def setUpClass(cls):
        cls.map = stages.build(ROOT)

    def test_the_package_is_read_from_the_disk(self):
        shipped = stages.shipped_modules(ROOT)
        self.assertTrue(shipped["readable"])
        self.assertIsNone(shipped["error"])
        self.assertEqual(shipped["modules"], self.map["shippedModules"])
        self.assertGreater(self.map["shippedModuleCount"], 20)
        for name in shipped["modules"]:
            with self.subTest(module=name):
                self.assertTrue(name.startswith(stages.PACKAGE + "/"))
                self.assertTrue(Path(ROOT, name).is_file())

    def test_every_shipped_module_is_claimed_by_a_stage(self):
        self.assertEqual(self.map["shippedButClaimedByNoStage"], [])
        self.assertTrue(self.map["everyShippedModuleIsClaimed"])

    def test_a_module_no_stage_claims_is_reported(self):
        """The negative control: dropping a claim must surface its module."""
        kept = stages.DEVELOPED_HERE[1]
        dropped = tuple(entry for entry in kept
                        if entry["where"] != "scenarios/guarantees.py")
        self.assertNotEqual(len(dropped), len(kept), "the fixture must drop a claim")
        stages.DEVELOPED_HERE[1] = dropped
        try:
            broken = stages.build(ROOT)
        finally:
            stages.DEVELOPED_HERE[1] = kept
        # Stages 2 and 3 still claim it, so dropping stage 1's claim alone must
        # not make it unclaimed; that is the point of checking the union.
        self.assertEqual(broken["shippedButClaimedByNoStage"], [])
        for stage in (1, 2, 3):
            kept_stage = stages.DEVELOPED_HERE[stage]
            stages.DEVELOPED_HERE[stage] = tuple(
                entry for entry in kept_stage
                if entry["where"] != "scenarios/guarantees.py")
            self.addCleanup(_restore, stage, kept_stage)
        unclaimed = stages.build(ROOT)
        self.assertEqual(unclaimed["shippedButClaimedByNoStage"],
                         ["scenarios/guarantees.py"])
        self.assertFalse(unclaimed["everyShippedModuleIsClaimed"])

    def test_an_unreadable_package_is_not_a_silent_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            shipped = stages.shipped_modules(directory)
            empty = stages.build(directory)
        self.assertFalse(shipped["readable"])
        self.assertEqual(shipped["error"], "EX_PACKAGE_UNREADABLE")
        self.assertEqual(shipped["modules"], [])
        self.assertFalse(empty["packageReadable"])
        self.assertFalse(empty["everyShippedModuleIsClaimed"],
                         "no modules found is not every module claimed")

    def test_a_test_module_is_not_a_deliverable(self):
        shipped = stages.shipped_modules(ROOT)
        self.assertTrue(Path(ROOT, "scenarios/tests/test_stages.py").is_file())
        for name in shipped["modules"]:
            with self.subTest(module=name):
                self.assertNotIn("tests/", name)
                self.assertFalse(Path(name).name.startswith("test_"))

    def test_each_exemption_says_why_it_is_not_a_deliverable(self):
        self.assertTrue(stages.NOT_A_DELIVERABLE, "an empty record hides nothing")
        self.assertEqual(self.map["notADeliverable"], dict(stages.NOT_A_DELIVERABLE))
        for name, reason in stages.NOT_A_DELIVERABLE.items():
            with self.subTest(module=name):
                self.assertIn(name, self.map["shippedModules"],
                              "an exemption for a module that is not shipped is stale")
                self.assertNotIn(name, self.map["claimedPaths"])
                self.assertTrue(reason)

    def test_the_new_verdict_is_acted_on_rather_than_reported(self):
        gated = [check for check in cli.CONSISTENCY_CHECKS
                 if check["key"] == "stageMap"
                 and check["flag"] == ("everyShippedModuleIsClaimed",)]
        self.assertEqual(len(gated), 1, "a verdict nothing acts on changes nothing")
        self.assertTrue(gated[0]["blocks"])


def _restore(stage, entries):
    stages.DEVELOPED_HERE[stage] = entries


class Ownership(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.map = stages.build(ROOT)
        cls.by_stage = {entry["stage"]: entry for entry in cls.map["stages"]}

    def test_every_stage_names_what_is_accepted_elsewhere(self):
        for stage, entry in sorted(self.by_stage.items()):
            with self.subTest(stage=stage):
                self.assertTrue(entry["acceptedElsewhere"],
                                "this surface develops and records; it does not "
                                "accept its own work")

    def test_no_stage_is_presented_as_complete(self):
        for stage, entry in sorted(self.by_stage.items()):
            with self.subTest(stage=stage):
                self.assertTrue(entry["localHalfOnly"])
        said = " ".join(self.map["isNot"])
        self.assertIn("not a completion claim", said)
        self.assertIn("not an approval", said)

    def test_each_dependency_names_an_owner_a_scope_and_a_next_step(self):
        for entry in stages.REAL_WORLD_DEPENDENCIES:
            with self.subTest(needs=entry["needs"]):
                self.assertIn(entry["stage"], self.by_stage)
                self.assertTrue(entry["owner"])
                self.assertTrue(entry["blocks"])
                self.assertTrue(entry["doesNotBlock"],
                                "a dependency must say what it does not block, or "
                                "it reads as blocking everything")
                self.assertTrue(entry["nextStep"])

    def test_every_dependency_points_at_a_real_evidence_slot(self):
        slots = {name for name, _ in handoff.EVIDENCE_SLOTS}
        for entry in stages.REAL_WORLD_DEPENDENCIES:
            with self.subTest(needs=entry["needs"]):
                self.assertIn(entry["slot"], slots,
                              "a dependency must name a slot that really exists "
                              "in the handoff checklist")
        self.assertTrue(set(self.map["slotsDependedOn"]) <= slots)

    def test_a_dependency_does_not_reassign_the_work(self):
        self.assertIn("dependency labels identify technical evidence categories", " ".join(self.map["isNot"]))
        owners = {entry["owner"] for entry in stages.REAL_WORLD_DEPENDENCIES}
        self.assertTrue(owners)
        for owner in sorted(owners):
            with self.subTest(owner=owner):
                self.assertNotIn("this package", owner)
                self.assertNotIn("this surface", owner)

    def test_the_deployment_dependency_blocks_the_chain_obligations_only(self):
        deployment = [entry for entry in stages.REAL_WORLD_DEPENDENCIES
                      if entry["slot"] == "deployedHead"]
        self.assertEqual(len(deployment), 1)
        self.assertIn("real-chain", deployment[0]["blocks"])
        self.assertIn("local delivery", deployment[0]["doesNotBlock"])


if __name__ == "__main__":
    unittest.main()
