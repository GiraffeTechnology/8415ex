"""Synthetic file-backed observation contracts; remote validation owner runs them."""
from unittest.mock import patch
import unittest

from exchange.durable_operation import DurableOperationRefused
from exchange.remint_history import RemintHistoryStore
from exchange.checkpointed_operation_observation import observe_checkpointed_operation
from integration import test_checkpointed_operation as original_fixture


class CheckpointedOperationObservationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = original_fixture.CheckpointedOperationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.enquiries = []

    def enquire(self, scope):
        self.enquiries.append(scope)
        return {"status": "unknown"}

    def observe(self, **options):
        return observe_checkpointed_operation(self.fixture.bridge,
            self.fixture.scope, self.enquire, **options)

    def test_absent_original_operation_is_queried_without_any_new_write(self):
        before = (self.fixture.claim_db.total_changes, self.fixture.snapshot_db.total_changes)
        result = self.observe()
        self.assertEqual(result["preEffectCheckpointView"]["status"], "ABSENT")
        self.assertIsNone(result["operation"]["localClaim"])
        self.assertEqual(len(self.enquiries), 1)
        self.assertEqual(before, (self.fixture.claim_db.total_changes,
                                  self.fixture.snapshot_db.total_changes))
        self.assertFalse(result["nativeGateInvoked"])
        self.assertFalse(result["replayAllowed"])

    def test_retained_preimage_summary_excludes_raw_bytes_and_private_facts(self):
        self.fixture.invoke()
        result = self.observe()
        view = result["preEffectCheckpointView"]
        self.assertEqual(set(view), {"status", "generation", "digest"})
        self.assertEqual(view["status"], "FOUND")
        self.assertEqual(view["generation"], 1)
        self.assertEqual(result["operation"]["localClaim"]["status"], "UNKNOWN")
        self.assertFalse(result["executionAuthorized"])
        self.assertFalse(result["completeRecovery"])
        self.assertFalse(result["crossStoreAtomicity"])

    def test_legacy_unknown_without_preimage_remains_queryable(self):
        self.fixture.journal.claim(self.fixture.scope, 0)
        result = self.observe()
        self.assertEqual(result["operation"]["localClaim"]["status"], "UNKNOWN")
        self.assertEqual(result["preEffectCheckpointView"]["status"], "ABSENT")
        self.assertEqual(self.fixture.journal.revision(self.fixture.scope["receiptId"]), 1)

    def test_unreadable_preimage_does_not_hide_original_observation(self):
        self.fixture.invoke()
        with patch.object(self.fixture.checkpoint, "read",
                          side_effect=ValueError("private database details")):
            result = self.observe()
        self.assertEqual(result["preEffectCheckpointView"]["status"], "UNAVAILABLE")
        self.assertEqual(result["operation"]["nativeObservation"], {"status": "unknown"})
        self.assertNotIn("private database details", repr(result))
        self.assertEqual(self.fixture.journal.lookup(
            self.fixture.scope["nativeOperationId"])["status"], "UNKNOWN")

    def test_native_enquiry_failure_is_not_rewritten_as_snapshot_absence(self):
        def unavailable(scope):
            raise TimeoutError("synthetic native enquiry timeout")
        with patch.object(self.fixture.checkpoint, "read") as read:
            with self.assertRaises(TimeoutError):
                observe_checkpointed_operation(self.fixture.bridge,
                    self.fixture.scope, unavailable)
            read.assert_not_called()
        self.assertIsNone(self.fixture.journal.lookup(self.fixture.scope["nativeOperationId"]))

    def test_original_scope_conflict_is_not_hidden_as_storage_unavailable(self):
        self.fixture.journal.claim(self.fixture.scope, 0)
        self.fixture.scope = dict(self.fixture.scope, tokenId="999")
        with self.assertRaises(DurableOperationRefused):
            self.observe()
        self.assertEqual(self.enquiries, [])

    def test_new_live_schema_is_not_required_to_read_old_operation_preimage(self):
        self.fixture.invoke()
        self.fixture.exchange.future_unhandled_domain = "new live schema"
        result = self.observe()
        self.assertEqual(result["preEffectCheckpointView"]["status"], "FOUND")
        self.assertEqual(result["operation"]["localClaim"]["status"], "UNKNOWN")
        self.assertEqual(len(self.fixture.calls), 1)

    def test_remint_history_failure_keeps_native_query_and_checkpoint_summary(self):
        self.fixture.invoke()
        RemintHistoryStore.initialize(self.fixture.claim_db)
        class UnavailableHistory(RemintHistoryStore):
            def read(self, scope):
                raise ValueError("synthetic unreadable original history")
        result = self.observe(remint_history=UnavailableHistory(self.fixture.claim_db))
        self.assertEqual(result["operation"]["historyView"]["status"], "UNAVAILABLE")
        self.assertEqual(result["preEffectCheckpointView"]["status"], "FOUND")
        self.assertEqual(len(self.enquiries), 1)
