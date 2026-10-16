"""A scenario can pass every check and still not record what a demo must carry.

These tests check the dossier on both sides: that it really finds an item the
scenarios do not record, and that it never offers a local stand-in for an item
no local run can discharge.
"""
import unittest

from scenarios import dossier, handoff
from scenarios.demos import DEMOS, MAIN_PATHS
from scenarios.harness import run_all


class Dossier(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.report = run_all(list(DEMOS))
        cls.built = dossier.build(cls.report)
        cls.by_scenario = {entry["scenarioId"]: entry
                           for entry in cls.built["dossiers"]}

    def test_it_covers_every_scenario_and_declares_nine_items(self):
        self.assertEqual(sorted(self.by_scenario), sorted(MAIN_PATHS))
        self.assertEqual(self.built["scenariosNotCovered"], [])
        self.assertEqual(self.built["declaredItemCount"], 9)
        for scenario_id, entry in sorted(self.by_scenario.items()):
            with self.subTest(scenario=scenario_id):
                self.assertEqual(entry["itemCount"], 9)

    def test_every_scenario_carries_every_item_it_can(self):
        self.assertEqual(self.built["gapsByScenario"], {})
        self.assertTrue(self.built["allItemsCarried"])

    def test_each_scenario_records_its_per_segment_escrow_result(self):
        # This item was the one the rollback and deadline scenarios did not
        # record, so it is asserted by name rather than only through the total.
        for scenario_id, entry in sorted(self.by_scenario.items()):
            item = {row["item"]: row for row in entry["items"]}[
                "per-segment escrow result"]
            with self.subTest(scenario=scenario_id):
                self.assertEqual(item["status"], "recorded")
                self.assertTrue(item["resolvedFrom"])

    def test_an_item_no_local_run_can_discharge_stays_not_run(self):
        for scenario_id, entry in sorted(self.by_scenario.items()):
            statuses = {row["item"]: row for row in entry["items"]}
            with self.subTest(scenario=scenario_id):
                for name in ("transaction hashes", "page state"):
                    row = statuses[name]
                    self.assertEqual(row["status"], handoff.NOT_RUN)
                    self.assertTrue(row["reason"])
                    self.assertTrue(row["slot"])

    def test_a_not_run_item_names_a_slot_that_really_exists(self):
        slots = {name for name, _ in handoff.EVIDENCE_SLOTS}
        self.assertTrue(self.built["notRunSlotsAreDeclared"])
        for slot in self.built["notRunSlots"]:
            with self.subTest(slot=slot):
                self.assertIn(slot, slots)

    def test_a_rendered_page_is_not_offered_as_the_page_state(self):
        page = {row["item"]: row for row in
                self.by_scenario["DEMO-01"]["items"]}["page state"]
        self.assertEqual(page["status"], handoff.NOT_RUN)
        self.assertIn("development and diagnosis only", page["renderedBy"],
                      "the renderer is named, and named as not being evidence")
        self.assertIn("no browser ran", page["reason"])

    def test_an_item_held_elsewhere_names_where_rather_than_reading_as_missing(self):
        events = {row["item"]: row for row in
                  self.by_scenario["DEMO-01"]["items"]}["recorded events"]
        self.assertEqual(events["status"], "resolved-elsewhere")
        self.assertIn("scenarios/events.py", events["resolvedFrom"])
        self.assertTrue(events["reason"])
        self.assertNotIn("recorded events",
                         self.by_scenario["DEMO-01"]["gaps"])

    def test_a_gap_names_exactly_which_keys_were_missing(self):
        stripped = dict(self.report)
        stripped["scenarios"] = [
            dict(self.report["scenarios"][0],
                 setup={key: value
                        for key, value in self.report["scenarios"][0]["setup"].items()
                        if key != "prices"})]
        built = dossier.build(stripped)
        entry = built["dossiers"][0]
        item = {row["item"]: row for row in entry["items"]}[
            "test prices and gas conditions"]
        self.assertEqual(item["status"], "gap")
        self.assertEqual(item["missingKeys"], ["prices"])
        self.assertIn("test prices and gas conditions", entry["gaps"])
        self.assertFalse(built["allItemsCarried"])

    def test_an_item_resolves_from_the_cases_asserted_when_the_facts_do_not_name_it(self):
        scenario = dict(self.report["scenarios"][0])
        scenario["steps"] = [dict(step, facts={key: value
                                               for key, value in step["facts"].items()
                                               if key not in dossier.DOSSIER_ITEMS[4]["stepFacts"]})
                             for step in scenario["steps"]]
        scenario["expectations"] = [dict(expectation, cases=["T-11"])
                                    for expectation in scenario["expectations"]]
        item = {row["item"]: row for row in
                dossier.for_scenario(scenario)["items"]}["per-segment escrow result"]
        self.assertEqual(item["status"], "recorded")
        self.assertIn("T-11", item["resolvedFrom"])

    def test_rephrasing_a_check_cannot_turn_an_item_into_a_gap(self):
        scenario = dict(self.report["scenarios"][0])
        scenario["expectations"] = [dict(expectation, name="renamed entirely")
                                    for expectation in scenario["expectations"]]
        rebuilt = dossier.for_scenario(scenario)
        self.assertEqual(rebuilt["gaps"], [],
                         "rules match on structure and case ids, never on wording")

    def test_an_empty_report_covers_nothing_rather_than_claiming_completeness(self):
        built = dossier.build(None)
        self.assertEqual(built["scenarioCount"], 0)
        self.assertFalse(built["allItemsCarried"])
        self.assertEqual(built["scenariosNotCovered"], sorted(MAIN_PATHS))

    def test_it_claims_neither_a_demonstration_nor_ui_nor_chain_evidence(self):
        said = " ".join(self.built["isNot"])
        self.assertIn("not a demonstration", said)
        self.assertIn("not UI evidence", said)
        self.assertIn("not a chain result", said)


if __name__ == "__main__":
    unittest.main()
