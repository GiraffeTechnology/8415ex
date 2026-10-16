"""The logical operations must land on real code, and reads must move nothing.

The read-only rule is the one part of PRD 10.1 that can be demonstrated rather
than declared, so it is demonstrated here, with a negative control proving the
comparison detects movement when there is some.
"""
import unittest
from pathlib import Path

from exchange import fixtures as F
from exchange.ledger import Exchange
from scenarios import matrix, operations

ROOT = str(Path(__file__).resolve().parents[2])


class OperationMap(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.map = operations.build(ROOT)
        cls.by_logical = {entry["logical"]: entry
                          for entry in cls.map["operations"]}

    def test_all_ten_logical_operations_are_mapped(self):
        self.assertEqual(self.map["operationCount"], 10)
        self.assertEqual(sorted(self.by_logical),
                         sorted(entry["logical"] for entry in operations.OPERATIONS))

    def test_every_logical_operation_lands_on_a_callable_method(self):
        for logical, entry in sorted(self.by_logical.items()):
            with self.subTest(operation=logical):
                self.assertTrue(entry["methods"])
                for method in entry["methods"]:
                    self.assertTrue(method["exists"], method["method"])
                    self.assertTrue(method["callable"], method["method"])
                self.assertTrue(entry["resolved"])
        self.assertEqual(self.map["unresolvedOperations"], [])

    def test_a_renamed_method_would_be_reported(self):
        kept = operations.OPERATIONS
        operations.OPERATIONS = tuple(
            dict(entry, methods=("validate_intent_renamed",))
            if entry["logical"] == "validateIntent" else entry
            for entry in kept)
        try:
            resolved = {entry["logical"]: entry for entry in operations.resolve()}
        finally:
            operations.OPERATIONS = kept
        self.assertFalse(resolved["validateIntent"]["resolved"])
        self.assertFalse(resolved["validateIntent"]["methods"][0]["exists"])

    def test_an_operation_spanning_two_methods_says_so(self):
        rollback = self.by_logical["rollbackSuffix"]
        self.assertTrue(rollback["mapsToSeveralMethods"])
        self.assertEqual(rollback["methodNames"],
                         ["begin_rollback", "advance_rollback"])
        self.assertTrue(rollback["note"], "the split needs its reason on record")

    def test_every_case_an_operation_names_really_exists(self):
        self.assertEqual(self.map["casesNamedThatDoNotExist"], [])
        for logical, entry in sorted(self.by_logical.items()):
            with self.subTest(operation=logical):
                self.assertTrue(entry["cases"])
                for case in entry["cases"]:
                    self.assertIn(case, matrix.CASE_REQUIREMENTS)

    def test_it_claims_nothing_about_return_content_or_idempotency(self):
        said = " ".join(self.map["isNot"])
        self.assertIn("not an ABI", said)
        self.assertIn("not a claim about return content", said)
        self.assertIn("not an idempotency proof", said)
        self.assertIn("acceptance cases", self.map["resultColumnCheckedBy"])


class ReadsMoveNothing(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.check = operations.read_only_moves_nothing()

    def test_every_read_was_really_called(self):
        self.assertEqual(self.check["notCalled"], [],
                         "a read that could not be called proves nothing")
        self.assertEqual(self.check["calledCount"], self.check["readCount"])
        self.assertGreater(self.check["readCount"], len(operations.ADDITIONAL_READS))

    def test_no_read_moved_money_the_asset_or_the_audit_trail(self):
        self.assertEqual(self.check["movedSomething"], [])
        self.assertTrue(self.check["allReadsMovedNothing"])
        for entry in self.check["reads"]:
            with self.subTest(method=entry["method"]):
                self.assertEqual(entry["before"], entry["after"])

    def test_the_counters_cover_money_the_asset_and_the_trail(self):
        self.assertEqual(sorted(self.check["counters"]),
                         ["assetReturns", "holderIndex", "ownerOf",
                          "paymentMovements", "recordedEvents"])

    def test_the_comparison_detects_movement_when_there_is_some(self):
        # The negative control. A release really does move money and append to
        # the trail, so the same counters must differ across it; if they did
        # not, the check above would be vacuous.
        exchange, _ = F.funded_chain_to_d()
        requests = F.submit_all(exchange)
        F.confirm(exchange, requests[0], "res-0")
        before = operations._movement_counters(exchange)
        exchange.release_segment("rcpt-8415-0001", 0,
                                 F.release_authority(exchange, 0, "rel-0"))
        after = operations._movement_counters(exchange)
        self.assertNotEqual(before, after)
        self.assertGreater(after["paymentMovements"], before["paymentMovements"])
        self.assertGreater(after["recordedEvents"], before["recordedEvents"])

    def test_every_additional_read_is_a_real_method(self):
        for name in operations.ADDITIONAL_READS:
            with self.subTest(method=name):
                self.assertTrue(callable(getattr(Exchange, name, None)))

    def test_the_rule_covers_every_classified_read(self):
        """Not a chosen subset: the whole read half of the class.

        This used to exercise the section's own three reads plus eleven
        hand-picked names, with nothing checking that the eleven were all of
        them. A read added to the domain would have been outside the one rule
        here that can be demonstrated.
        """
        self.assertEqual([entry["method"] for entry in self.check["reads"]],
                         list(operations.READS))
        self.assertEqual(self.check["readCount"], len(operations.READS))
        self.assertGreater(self.check["readCount"], 25)

    def test_a_read_that_moved_something_would_be_named(self):
        """The negative control for the rule itself, not just the counters.

        The control above shows the counters notice a release. This one shows
        the check notices when a method it calls as a read moves something: a
        read that quietly recorded an event would otherwise pass.
        """
        original = Exchange.deferred_legs

        def leaky(self, receipt_id):
            # Moving money is the plainest version of what the rule forbids,
            # and unlike recording an event it neither refuses on a repeat nor
            # turns the read into one that could not be called at all.
            self.payments.movements += 1
            return original(self, receipt_id)

        Exchange.deferred_legs = leaky
        try:
            measured = operations.read_only_moves_nothing()
            built = operations.build(ROOT)
        finally:
            Exchange.deferred_legs = original
        self.assertIn("deferred_legs", measured["movedSomething"])
        self.assertFalse(measured["allReadsMovedNothing"])
        self.assertFalse(built["consistent"],
                         "a read that moved something must stop the run")
        # And it is put back, or every later report describes a leaky domain.
        self.assertIs(Exchange.deferred_legs, original)
        self.assertEqual(operations.read_only_moves_nothing()["movedSomething"], [])


class EveryMethodIsClassified(unittest.TestCase):
    """A read nobody classified is a read outside the no-movement rule."""

    @classmethod
    def setUpClass(cls):
        cls.buckets = operations.classification()

    def test_the_two_buckets_account_for_the_whole_class(self):
        self.assertEqual(self.buckets["unclassified"], [])
        self.assertEqual(self.buckets["classifiedButNotOnTheClass"], [])
        self.assertEqual(self.buckets["inBothBuckets"], [])
        self.assertTrue(self.buckets["complete"])
        self.assertEqual(self.buckets["readCount"] + self.buckets["changeCount"],
                         self.buckets["classCount"])

    def test_the_class_list_is_read_from_the_class(self):
        self.assertEqual(operations.public_methods(),
                         tuple(sorted(name for name in dir(Exchange)
                                      if not name.startswith("_")
                                      and callable(getattr(Exchange, name)))))
        self.assertEqual(self.buckets["classCount"],
                         len(operations.public_methods()))

    def test_an_unclassified_method_is_a_finding(self):
        kept = operations.READS
        operations.READS = tuple(name for name in kept if name != "owner_of")
        try:
            broken = operations.classification()
        finally:
            operations.READS = kept
        self.assertEqual(broken["unclassified"], ["owner_of"])
        self.assertFalse(broken["complete"])

    def test_a_method_in_both_buckets_is_a_finding(self):
        kept = operations.CHANGES
        operations.CHANGES = kept + ("owner_of",)
        try:
            broken = operations.classification()
        finally:
            operations.CHANGES = kept
        self.assertEqual(broken["inBothBuckets"], ["owner_of"])
        self.assertFalse(broken["complete"])

    def test_a_classified_name_that_is_not_a_method_is_a_finding(self):
        kept = operations.READS
        operations.READS = kept + ("no_such_read",)
        try:
            broken = operations.classification()
        finally:
            operations.READS = kept
        self.assertEqual(broken["classifiedButNotOnTheClass"], ["no_such_read"])
        self.assertFalse(broken["complete"])

    def test_an_incomplete_classification_stops_the_run(self):
        kept = operations.READS
        operations.READS = tuple(name for name in kept if name != "owner_of")
        try:
            built = operations.build(ROOT)
        finally:
            operations.READS = kept
        self.assertFalse(built["consistent"])
        self.assertEqual(built["methodClassification"]["unclassified"], ["owner_of"])

    def test_every_read_has_arguments_to_be_called_with(self):
        """A read with no argument entry raises rather than being skipped."""
        called = {entry["method"] for entry in
                  operations.read_only_moves_nothing()["reads"]}
        self.assertEqual(called, set(operations.READS))


if __name__ == "__main__":
    unittest.main()
