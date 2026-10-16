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


if __name__ == "__main__":
    unittest.main()
