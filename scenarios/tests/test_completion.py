"""The definition of done, and the half of it that is easiest to lose.

Completion cannot be established from here, so the tests insist it is never
claimed, that every clause names who owes the rest, and that the things this
round explicitly does not mean are checked where they can be and labelled
declared-only where they cannot.
"""
import unittest
from pathlib import Path

from scenarios import cli, completion, handoff

ROOT = str(Path(__file__).resolve().parents[2])


class Ledger(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.bundle = cli._bundle(ROOT)
        cls.ledger = cls.bundle["completion"]

    def test_completion_is_never_established_from_here(self):
        self.assertFalse(self.ledger["completionEstablished"])
        self.assertIn("another owner", self.ledger["whyNot"])
        for clause in self.ledger["clauses"]:
            with self.subTest(clause=clause["clause"]):
                self.assertFalse(clause["completeHere"])

    def test_every_clause_is_resolved_against_the_run(self):
        self.assertTrue(self.ledger["runRead"])
        self.assertEqual(self.ledger["clauseCount"], len(completion.CLAUSES))
        for clause in self.ledger["clauses"]:
            with self.subTest(clause=clause["clause"]):
                self.assertNotEqual(clause["localStatus"], "not-resolved")

    def test_a_locally_evidenced_clause_still_names_what_is_owed(self):
        evidenced = [clause for clause in self.ledger["clauses"]
                     if clause["localStatus"] == "evidenced-locally"]
        self.assertTrue(evidenced, "this run really does evidence clauses locally")
        for clause in evidenced:
            with self.subTest(clause=clause["clause"]):
                self.assertGreater(clause["awaitsCount"], 0,
                                   "a finished local half is not a finished clause")

    def test_each_outstanding_item_names_an_owner_and_a_real_slot(self):
        slots = {name for name, _ in handoff.EVIDENCE_SLOTS}
        self.assertGreater(self.ledger["outstandingCount"], 0)
        for owed in self.ledger["outstanding"]:
            with self.subTest(needs=owed["needs"]):
                self.assertTrue(owed["owner"])
                self.assertTrue(owed["clause"])
                self.assertIn(owed["slot"], slots)
        self.assertTrue(set(self.ledger["slotsOwed"]) <= slots)

    def test_no_owner_is_this_surface(self):
        for owner in self.ledger["owners"]:
            with self.subTest(owner=owner):
                self.assertNotIn("this package", owner)
                self.assertNotIn("this surface", owner)

    def test_a_signal_reads_the_report_it_names(self):
        for clause in self.ledger["clauses"]:
            for signal in clause["signals"]:
                with self.subTest(report=signal["report"], flag=signal["flag"]):
                    self.assertIn(signal["report"], self.bundle)
                    self.assertIs(signal["value"], True)

    def test_a_stage_clause_resolves_through_the_acceptance_matrix(self):
        staged = [clause for clause in self.ledger["clauses"]
                  if clause["stageCoverage"]]
        self.assertEqual(len(staged), 2, "funding and rollback, and the exit path")
        for clause in staged:
            coverage = clause["stageCoverage"]
            with self.subTest(stages=coverage["stages"]):
                self.assertTrue(coverage["cases"])
                self.assertEqual(coverage["casesNotStanding"], [])
                self.assertTrue(coverage["met"])
                for case, outcome in sorted(coverage["outcomes"].items()):
                    self.assertIn(outcome, completion.LOCAL_OUTCOMES_THAT_STAND,
                                  case)

    def test_a_missing_report_does_not_read_as_a_met_signal(self):
        bare = completion.build({"scenarioReport": {"allPassed": True}})
        clause = bare["clauses"][0]
        self.assertIs(clause["signals"][0]["value"], True)
        self.assertIsNone(clause["signals"][1]["value"],
                          "an absent report is absent, not passing")
        self.assertEqual(clause["localStatus"], "partly-evidenced")

    def test_with_no_run_nothing_is_resolved_and_it_says_so(self):
        empty = completion.build()
        self.assertFalse(empty["runRead"])
        self.assertIsNone(empty["notMeantHolds"])
        for clause in empty["clauses"]:
            with self.subTest(clause=clause["clause"]):
                self.assertEqual(clause["localStatus"], "not-resolved")
                self.assertTrue(clause["awaits"])

    def test_it_claims_neither_acceptance_nor_a_percentage(self):
        said = " ".join(self.ledger["isNot"])
        self.assertIn("not an acceptance decision", said)
        self.assertIn("not a percentage", said)


class WhatItDoesNotMean(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.bundle = cli._bundle(ROOT)
        cls.ledger = cls.bundle["completion"]

    def test_each_item_is_phrased_as_what_is_not_the_case(self):
        for entry in self.ledger["notMeant"]:
            with self.subTest(item=entry["notTheCase"]):
                self.assertTrue(entry["notTheCase"].startswith(("no ", "the project has not ")),
                                "a skimmed list must not read as confirming the "
                                "opposite of what is meant")

    def test_the_checkable_ones_are_confirmed_against_the_run(self):
        self.assertEqual(len(self.ledger["notMeantConfirmedByThisRun"]), 3)
        for entry in self.ledger["notMeant"]:
            if entry["declaredOnly"]:
                continue
            with self.subTest(item=entry["notTheCase"]):
                self.assertTrue(entry["checkedBy"])
                self.assertIs(entry["confirmedByThisRun"], True)

    def test_the_rest_say_they_are_declared_only(self):
        declared = self.ledger["notMeantDeclaredOnly"]
        self.assertEqual(len(declared), 3)
        for entry in self.ledger["notMeant"]:
            if entry["notTheCase"] in declared:
                with self.subTest(item=entry["notTheCase"]):
                    self.assertIsNone(entry["checkedBy"])
                    self.assertIsNone(entry["confirmedByThisRun"])

    def test_the_run_is_on_a_test_chain_and_never_the_main_network(self):
        checked = self.ledger["notMeantChecked"]
        self.assertTrue(checked["noMainnet"])
        self.assertNotIn(completion.MAINNET_CHAIN_ID, checked["chainIdsObserved"])
        self.assertTrue(checked["chainIdsObserved"])

    def test_all_reports_are_read_not_only_the_first(self):
        expected = sum(len(self.bundle[key]["scenarios"])
                       for key in ("scenarioReport", "pathReport", "guaranteeReport"))
        self.assertEqual(self.ledger["notMeantChecked"]["scenariosRead"], expected)

    def test_every_adapter_the_run_used_is_a_simulated_one(self):
        checked = self.ledger["notMeantChecked"]
        self.assertTrue(checked["everyAdapterSimulated"])
        self.assertTrue(checked["adapterLabelsObserved"])
        for label in checked["adapterLabelsObserved"]:
            with self.subTest(adapter=label):
                self.assertIn("simulated", label.lower())

    def test_the_quote_asset_is_a_local_test_label(self):
        checked = self.ledger["notMeantChecked"]
        self.assertTrue(checked["quoteAssetIsATestLabel"])
        self.assertEqual(checked["quoteAssetsObserved"],
                         [completion.TEST_QUOTE_ASSET])

    def test_a_violated_non_claim_would_stop_the_run(self):
        # The negative control, and the reason this verdict is gated at all: a
        # run against a main network is not an observation to report, it is a
        # stop. Nothing in the fixtures can reach the main network, so the
        # violation is constructed.
        mainnet = completion.build({
            "scenarioReport": {"scenarios": [{"setup": {
                "receipt": {"chainId": completion.MAINNET_CHAIN_ID},
                "quoteAsset": completion.TEST_QUOTE_ASSET,
                "simulatedAdapters": {"registrar": "simulated"},
                "gasConditions": {"note": "fixture"}}}]},
            "reuse": {"allAdaptersSimulated": True}})
        self.assertFalse(mainnet["notMeantChecked"]["noMainnet"])
        self.assertFalse(mainnet["notMeantHolds"])
        check = next(entry for entry in cli.CONSISTENCY_CHECKS
                     if entry["key"] == "completion")
        self.assertTrue(check["blocks"])
        self.assertIs(cli._verdict({"completion": mainnet}, check), False)

    def test_a_real_adapter_would_stop_the_run_too(self):
        real = completion.build({
            "scenarioReport": {"scenarios": [{"setup": {
                "receipt": {"chainId": 11155111},
                "quoteAsset": completion.TEST_QUOTE_ASSET,
                "simulatedAdapters": {"registrar": "LiveRegistrarGateway"},
                "gasConditions": {"note": "fixture"}}}]},
            "reuse": {"allAdaptersSimulated": False}})
        self.assertFalse(real["notMeantChecked"]["everyAdapterSimulated"])
        self.assertFalse(real["notMeantHolds"])


if __name__ == "__main__":
    unittest.main()
