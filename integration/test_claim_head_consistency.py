"""Synthetic claim-head consistency definitions; approved Linux execution only."""
import unittest

from exchange.durable_operation import DurableOperationRefused
from integration import test_durable_operation as fixtures


class ClaimHeadConsistencyTests(unittest.TestCase):
    def fixture(self):
        fixture = fixtures.DurableOperationContracts("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.journal.claim(fixture.scope, 0)
        return fixture

    def test_lost_or_rolled_back_head_never_creates_a_new_claim_or_dispatch(self):
        for missing in (False, True):
            with self.subTest(missing=missing):
                fixture = self.fixture()
                if missing:
                    fixture.connection.execute("DELETE FROM ex_operation_receipt_heads")
                else:
                    fixture.connection.execute(
                        "UPDATE ex_operation_receipt_heads SET revision=0")
                fixture.connection.commit()
                other = dict(fixture.scope, nativeOperationId="new-original-operation", globalLegId=4)
                with self.assertRaises(DurableOperationRefused):
                    fixture.journal.revision(fixture.scope["receiptId"])
                with self.assertRaises(DurableOperationRefused):
                    fixture.journal.claim(other, 0)
                dispatched = []
                with self.assertRaises(DurableOperationRefused):
                    fixture.journal.invoke_once(other, 0, lambda scope: None,
                                                lambda scope: dispatched.append(scope))
                self.assertEqual(dispatched, [])
                self.assertIsNone(fixture.journal.lookup(other["nativeOperationId"]))
                head = fixture.connection.execute(
                    "SELECT revision FROM ex_operation_receipt_heads").fetchone()
                self.assertEqual(head, None if missing else (0,))
                self.assertEqual(fixture.connection.execute(
                    "SELECT status FROM ex_operation_claims").fetchall(), [("UNKNOWN",)])

    def test_invalid_retained_claim_revision_refuses_new_cas_without_repair(self):
        fixture = self.fixture()
        other = dict(fixture.scope, nativeOperationId="new-original-operation", globalLegId=4)
        for revision in (0, -1, "invalid", 1.5):
            fixture.connection.execute(
                "UPDATE ex_operation_claims SET claimed_revision=?", (revision,))
            fixture.connection.commit()
            with self.subTest(revision=revision):
                with self.assertRaises(DurableOperationRefused):
                    fixture.journal.revision(fixture.scope["receiptId"])
                with self.assertRaises(DurableOperationRefused):
                    fixture.journal.claim(other, 1)
                self.assertEqual(fixture.connection.execute(
                    "SELECT COUNT(*) FROM ex_operation_claims").fetchone()[0], 1)
                self.assertEqual(fixture.connection.execute(
                    "SELECT revision FROM ex_operation_receipt_heads").fetchone(), (1,))

    def test_healthy_head_allows_only_actual_next_revision(self):
        fixture = self.fixture()
        other = dict(fixture.scope, nativeOperationId="next-original-operation", globalLegId=4)
        with self.assertRaises(DurableOperationRefused):
            fixture.journal.claim(other, 0)
        result = fixture.journal.claim(other, 1)
        self.assertEqual(result["claimedRevision"], 2)
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(fixture.journal.revision(fixture.scope["receiptId"]), 2)
        self.assertEqual(fixture.journal.lookup(
            fixture.scope["nativeOperationId"])["claimedRevision"], 1)

    def test_damaged_receipt_does_not_block_an_independent_valid_receipt(self):
        fixture = self.fixture()
        fixture.connection.execute("DELETE FROM ex_operation_receipt_heads")
        fixture.connection.commit()
        other = dict(fixture.scope, receiptId="independent-receipt", tokenId="20",
                     nativeOperationId="independent-original-operation")
        result = fixture.journal.claim(other, 0)
        self.assertEqual(result["scope"], other)
        self.assertEqual(result["claimedRevision"], 1)
        self.assertEqual(fixture.journal.revision(other["receiptId"]), 1)
        with self.assertRaises(DurableOperationRefused):
            fixture.journal.revision(fixture.scope["receiptId"])

