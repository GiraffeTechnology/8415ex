"""The domain-surface measurement must measure, and must fail closed.

A method appearing in a source file proves nothing about being entered, so the
measurement wraps the real methods and runs the real groups. These tests insist
that it restores the class, that it refuses to call an unexercised method
accounted for, and that its exemption record cannot rot.
"""
import unittest

from exchange.ledger import Exchange

from scenarios import cli, surface
from scenarios.demos import DEMOS
from scenarios.guarantees import GUARANTEE_CONTRACTS
from scenarios.harness import Scenario, run_all
from scenarios.paths import PATH_CONTRACTS

GROUPS = (DEMOS, PATH_CONTRACTS, GUARANTEE_CONTRACTS)


class AsMeasured(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.coverage = surface.coverage(GROUPS, run_all)

    def test_every_counted_method_is_entered_or_accounted_for(self):
        self.assertEqual(self.coverage["notAccountedFor"], [])
        self.assertEqual(self.coverage["staleExemptions"], [])
        self.assertEqual(self.coverage["exemptionsNamingNoMethod"], [])
        # What is left unentered is exactly what is accounted for, and no more.
        self.assertEqual(sorted(self.coverage["notExercised"]),
                         sorted(surface.NOT_EXERCISED_LOCALLY))
        self.assertEqual(self.coverage["exercisedCount"]
                         + len(self.coverage["notExercised"]),
                         self.coverage["methodCount"])
        self.assertTrue(self.coverage["everyMethodAccountedFor"])

    def test_every_adapter_role_is_counted(self):
        """The widening that found the enquiry surface.

        Counting only the ledger said nothing about the adapters, which are what
        a real interface would replace.
        """
        per_subject = {entry["subject"]: entry
                       for entry in self.coverage["perSubject"]}
        self.assertEqual(sorted(per_subject), sorted(surface.SUBJECTS))
        for subject, entry in sorted(per_subject.items()):
            with self.subTest(subject=subject):
                self.assertGreater(entry["methodCount"], 0,
                                   "a subject with no counted method counts nothing")
        for adapter in ("exchange.settlement.SimulatedPaymentAdapter",
                        "exchange.rollback.SimulatedAssetControl",
                        "exchange.exit.SimulatedVoucherDesk"):
            with self.subTest(adapter=adapter):
                self.assertEqual(per_subject[adapter]["notExercised"], [])

    def test_what_cannot_be_measured_says_why(self):
        self.assertEqual(self.coverage["notMeasured"], dict(surface.NOT_MEASURED))
        self.assertIn("module-level functions", self.coverage["notMeasured"])
        self.assertIn("inherited methods", self.coverage["notMeasured"])
        for limit, reason in self.coverage["notMeasured"].items():
            with self.subTest(limit=limit):
                self.assertTrue(reason)

    def test_each_exemption_names_a_counted_method_and_says_why(self):
        for name, reason in surface.NOT_EXERCISED_LOCALLY.items():
            with self.subTest(method=name):
                self.assertIn(name, self.coverage["methods"])
                self.assertTrue(reason)
                self.assertIn(name, self.coverage["notExercised"])

    def test_only_methods_a_class_defines_itself_are_counted(self):
        """An inherited method would be a measurement artifact, not a fact."""
        counted = {name for name, _, _ in surface.methods()}
        self.assertIn("exchange.registration.DirectRegistrar.handover_record",
                      counted)
        # DirectRegistrar inherits submit and result; counting them there would
        # shadow the base and make the base read as unentered.
        self.assertNotIn("exchange.registration.DirectRegistrar.submit", counted)
        self.assertIn("exchange.registration.SimulatedRegistrar.submit", counted)

    def test_the_method_list_comes_from_the_classes(self):
        self.assertEqual(tuple(self.coverage["methods"]),
                         tuple(name for name, _, _ in surface.methods()))
        self.assertGreater(self.coverage["methodCount"], 60)
        for name, subject, attribute in surface.methods():
            with self.subTest(method=name):
                self.assertFalse(attribute.startswith("_"))
                self.assertIn(attribute, subject.__dict__)
                self.assertTrue(callable(getattr(subject, attribute)))

    def test_the_instrumented_run_has_to_pass(self):
        self.assertTrue(self.coverage["instrumentedRunPassed"])
        self.assertEqual(self.coverage["groupsRun"], len(GROUPS))

    def test_it_says_what_it_is_not(self):
        joined = " ".join(self.coverage["isNot"])
        self.assertIn("not the reported run", joined)
        self.assertIn("not a correctness claim", joined)
        self.assertIn("measured", self.coverage["basis"])


class RestoringTheClass(unittest.TestCase):
    """Leaving the domain wrapped would make every later report describe it."""

    def originals(self):
        return {name: getattr(subject, attribute)
                for name, subject, attribute in surface.methods()}

    def test_the_classes_are_the_same_afterwards(self):
        before = self.originals()
        surface.coverage(GROUPS, run_all)
        self.assertEqual(self.originals(), before)

    def test_the_classes_are_restored_even_when_a_group_raises(self):
        before = self.originals()

        def boom(scenarios):
            raise RuntimeError("the runner itself failed")

        with self.assertRaises(RuntimeError):
            surface.coverage(GROUPS, boom)
        self.assertEqual(self.originals(), before,
                         "a failure must not leave the domain instrumented")


class FailingClosed(unittest.TestCase):
    """The negative controls. Each one is a way this could report a false pass."""

    def test_an_unexercised_method_that_nothing_accounts_for_is_a_finding(self):
        def touches_nothing(recorder):
            recorder.expect("a contract that enters no domain method", ("T-01",), 1, 1)

        measured = surface.coverage(
            ((Scenario("SURFACE-EMPTY", "enters nothing", ("T-01",), "REG_DIRECT",
                       touches_nothing),),), run_all)
        self.assertEqual(measured["exercised"], [])
        self.assertEqual(measured["notExercised"], measured["methods"])
        self.assertEqual(measured["notAccountedFor"],
                         [name for name in measured["methods"]
                          if name not in surface.NOT_EXERCISED_LOCALLY])
        self.assertFalse(measured["everyMethodAccountedFor"],
                         "entering nothing is not every method accounted for")

    def test_an_accounted_for_method_is_not_a_finding_but_is_still_named(self):
        kept = dict(surface.NOT_EXERCISED_LOCALLY)
        surface.NOT_EXERCISED_LOCALLY.clear()
        surface.NOT_EXERCISED_LOCALLY.update(
            {name: "a stated reason" for name, _, _ in surface.methods()})
        try:
            def touches_nothing(recorder):
                recorder.expect("a contract that enters no domain method", ("T-01",),
                                1, 1)

            measured = surface.coverage(
                ((Scenario("SURFACE-EMPTY", "enters nothing", ("T-01",), "REG_DIRECT",
                           touches_nothing),),), run_all)
        finally:
            surface.NOT_EXERCISED_LOCALLY.clear()
            surface.NOT_EXERCISED_LOCALLY.update(kept)
        self.assertEqual(measured["notAccountedFor"], [])
        self.assertEqual(measured["notExercised"], measured["methods"],
                         "accounted for is not the same as hidden")
        self.assertTrue(measured["everyMethodAccountedFor"])

    def test_a_stale_exemption_is_a_finding(self):
        """An exemption for a method that is exercised after all must not stand."""
        kept = dict(surface.NOT_EXERCISED_LOCALLY)
        surface.NOT_EXERCISED_LOCALLY["exchange.ledger.Exchange.owner_of"] = (
            "no longer true")
        try:
            measured = surface.coverage(GROUPS, run_all)
        finally:
            surface.NOT_EXERCISED_LOCALLY.clear()
            surface.NOT_EXERCISED_LOCALLY.update(kept)
        self.assertEqual(measured["staleExemptions"],
                         ["exchange.ledger.Exchange.owner_of"])
        self.assertFalse(measured["everyMethodAccountedFor"])

    def test_an_exemption_naming_no_method_is_a_finding(self):
        kept = dict(surface.NOT_EXERCISED_LOCALLY)
        surface.NOT_EXERCISED_LOCALLY["no_such_method"] = "a method that is not there"
        try:
            measured = surface.coverage(GROUPS, run_all)
        finally:
            surface.NOT_EXERCISED_LOCALLY.clear()
            surface.NOT_EXERCISED_LOCALLY.update(kept)
        self.assertEqual(measured["exemptionsNamingNoMethod"], ["no_such_method"])
        self.assertFalse(measured["everyMethodAccountedFor"])

    def test_a_failing_group_is_not_a_measurement(self):
        def fails(recorder):
            recorder.expect("a contract that no longer holds", ("T-01",), "a", "b")

        measured = surface.coverage(
            ((Scenario("SURFACE-FAILING", "does not hold", ("T-01",), "REG_DIRECT",
                       fails),),), run_all)
        self.assertFalse(measured["instrumentedRunPassed"])
        self.assertFalse(measured["everyMethodAccountedFor"],
                         "a scenario that stopped early never reaches what it would have")

    def test_no_group_at_all_is_not_a_pass(self):
        measured = surface.coverage((), run_all)
        self.assertEqual(measured["groupsRun"], 0)
        self.assertFalse(measured["instrumentedRunPassed"])
        self.assertFalse(measured["everyMethodAccountedFor"])

    def test_the_verdict_is_acted_on_rather_than_reported(self):
        gated = [check for check in cli.CONSISTENCY_CHECKS
                 if check["key"] == "domainSurface"]
        self.assertEqual(len(gated), 1)
        self.assertEqual(gated[0]["flag"], ("everyMethodAccountedFor",))
        self.assertTrue(gated[0]["blocks"])


if __name__ == "__main__":
    unittest.main()
