"""Synthetic file-backed journal definitions for approved Linux execution.

Storage consistency checks are not native proof verification or full recovery.
"""
import unittest

from exchange.durable_operation import DurableEXOperationJournal, DurableOperationRefused
from integration import test_durable_operation as fixtures


class OperationStorageIdentityTests(unittest.TestCase):
    def fixture(self):
        fixture = fixtures.DurableOperationContracts("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.journal.claim(fixture.scope, 0)
        return fixture

    def test_receipt_index_mismatch_refuses_lookup_observe_and_execution_before_callbacks(self):
        fixture = self.fixture()
        fixture.connection.execute(
            "UPDATE ex_operation_claims SET receipt_id=? WHERE native_operation_id=?",
            ("other-receipt", fixture.scope["nativeOperationId"]))
        fixture.connection.commit()
        calls = []
        for read in (
            lambda: fixture.journal.lookup(fixture.scope["nativeOperationId"]),
            lambda: fixture.journal.observe(fixture.scope, lambda scope: calls.append("read")),
            lambda: fixture.journal.invoke_once(fixture.scope, 1,
                lambda scope: calls.append("read"), lambda scope: calls.append("dispatch")),
        ):
            with self.assertRaises(DurableOperationRefused):
                read()
        self.assertEqual(calls, [])
        stored = fixture.connection.execute(
            "SELECT receipt_id,status FROM ex_operation_claims").fetchone()
        self.assertEqual(stored, ("other-receipt", "UNKNOWN"))

    def test_missing_or_older_head_cannot_validate_a_persisted_claim(self):
        fixture = self.fixture()
        for revision in (0, -1, "invalid", 1.5):
            fixture.connection.execute(
                "UPDATE ex_operation_receipt_heads SET revision=? WHERE receipt_id=?",
                (revision, fixture.scope["receiptId"]))
            fixture.connection.commit()
            with self.subTest(revision=revision), self.assertRaises(DurableOperationRefused):
                fixture.journal.lookup(fixture.scope["nativeOperationId"])
        fixture.connection.execute("DELETE FROM ex_operation_receipt_heads")
        fixture.connection.commit()
        with self.assertRaises(DurableOperationRefused):
            fixture.journal.lookup(fixture.scope["nativeOperationId"])

    def test_invalid_revision_is_not_returned_as_a_current_cas_value(self):
        fixture = self.fixture()
        for revision in (-1, "invalid", 1.5):
            fixture.connection.execute(
                "UPDATE ex_operation_receipt_heads SET revision=? WHERE receipt_id=?",
                (revision, fixture.scope["receiptId"]))
            fixture.connection.commit()
            with self.subTest(revision=revision), self.assertRaises(DurableOperationRefused):
                fixture.journal.revision(fixture.scope["receiptId"])
        self.assertEqual(fixture.journal.revision("not-yet-claimed"), 0)

    def test_healthy_earlier_claim_survives_later_receipt_revision_and_reopen(self):
        fixture = self.fixture()
        other = dict(fixture.scope, nativeOperationId="original-native-op-4", globalLegId=4)
        fixture.journal.claim(other, 1)
        fixture.connection.close()
        recovered = DurableEXOperationJournal(fixture.connect())
        for scope, revision in ((fixture.scope, 1), (other, 2)):
            result = recovered.lookup(scope["nativeOperationId"])
            self.assertEqual(result["scope"], scope)
            self.assertEqual(result["claimedRevision"], revision)
            self.assertEqual(result["status"], "UNKNOWN")
            self.assertFalse(result["replayAllowed"])
        self.assertEqual(recovered.revision(fixture.scope["receiptId"]), 2)

