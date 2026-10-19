"""Synthetic original ports only; definitions await permitted remote QA."""
from dataclasses import replace
import sqlite3
import unittest

from exchange.durable_operation import DurableNativeOutcomeUnknown
from exchange.remint_execution import observe_remint
from exchange.remint_history import RemintHistoryStore
from exchange.remint_terms import prepare_remint_terms
from exchange.checkpointed_operation import CheckpointedOperationRefused
from exchange.checkpointed_remint import invoke_checkpointed_remint
from integration import test_checkpointed_operation as original_fixture
from integration.test_remint_execution import bill


class CheckpointedRemintTests(unittest.TestCase):
    def setUp(self):
        # Reuse the existing file-backed original claim/snapshot fixture without
        # inheriting its test methods or creating another product implementation.
        self.fixture = original_fixture.CheckpointedOperationTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        from integration.test_mint_specification_codec import specification
        self.old = specification()
        self.new = replace(self.old, bill_terms="Changed original bill terms",
            receipt=replace(self.old.receipt, asset=replace(self.old.receipt.asset, token_id=8)))
        self.verify = lambda kind, evidence: True
        digest = prepare_remint_terms(self.old, self.new, self.verify, bill)["historyDigest"]
        self.scope = dict(self.fixture.scope, intentDigest=digest)
        RemintHistoryStore.initialize(self.fixture.claim_db)
        self.history = RemintHistoryStore(self.fixture.claim_db)
        self.calls = []

    def invoke(self, execute=None, enquire=None):
        return invoke_checkpointed_remint(self.fixture.bridge, self.scope, 0,
            self.old, self.new, self.verify, bill, enquire or (lambda scope: None),
            execute or self.execute, history_store=self.history)

    def execute(self, scope, history):
        self.assertEqual(self.fixture.journal.lookup(scope["nativeOperationId"])["status"], "UNKNOWN")
        self.assertEqual(self.history.read(scope)["history"], history)
        saved = self.fixture.checkpoint.read(self.fixture.bridge.pre_effect_scope(scope))
        self.assertEqual(saved["generation"], 1)
        self.calls.append(scope)
        return {"status": "pending"}

    def test_original_claim_history_and_snapshot_precede_one_native_call(self):
        result = self.invoke()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result["preEffectCheckpoint"]["generation"], 1)
        self.assertFalse(result["executionAuthorized"])
        self.assertFalse(result["completeRecovery"])
        self.assertFalse(result["replayAllowed"])

    def test_same_receipt_id_is_allowed_for_new_nft_identity(self):
        self.assertEqual(self.old.receipt.receipt_id, self.new.receipt.receipt_id)
        self.assertNotEqual(self.old.receipt.asset, self.new.receipt.asset)
        self.invoke()
        self.assertEqual(len(self.calls), 1)

    def test_existing_unknown_enquires_without_another_snapshot_or_effect(self):
        self.invoke()
        result = self.invoke(enquire=lambda scope: {"status": "unknown"})
        self.assertIsNone(result["preEffectCheckpoint"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.fixture.checkpoint.read(
            self.fixture.bridge.pre_effect_scope(self.scope))["generation"], 1)

    def test_history_failure_cannot_create_snapshot_or_native_effect(self):
        class FailingHistory(RemintHistoryStore):
            def save(self, scope, history):
                raise sqlite3.OperationalError("synthetic history write failure")
        self.history = FailingHistory(self.fixture.claim_db)
        with self.assertRaises(DurableNativeOutcomeUnknown):
            self.invoke()
        self.assertEqual(self.calls, [])
        self.assertIsNone(self.fixture.checkpoint.read(self.fixture.bridge.pre_effect_scope(self.scope)))
        self.assertEqual(self.fixture.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")

    def test_snapshot_lost_ack_retains_history_and_claim_without_native_effect(self):
        from exchange.aggregate_checkpoint import CheckpointCommitUnknown
        self.fixture.snapshot_db.fail_ack = True
        with self.assertRaises(CheckpointCommitUnknown):
            self.invoke()
        self.assertEqual(self.calls, [])
        self.assertIsNotNone(self.history.read(self.scope))
        self.assertEqual(self.fixture.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")

    def test_native_timeout_retains_both_preimages_and_never_replays(self):
        def timeout(scope, history):
            self.execute(scope, history)
            raise TimeoutError("synthetic lost native response")
        with self.assertRaises(DurableNativeOutcomeUnknown):
            self.invoke(execute=timeout)
        result = self.invoke(enquire=lambda scope: {"status": "unknown"})
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(result["operation"]["nativeGateInvoked"])
        self.assertIsNotNone(self.history.read(self.scope))

    def test_different_live_receipt_cannot_reach_native_gateway(self):
        self.old = replace(self.old, receipt=replace(self.old.receipt, commodity_quantity=101))
        self.new = replace(self.new, receipt=replace(self.new.receipt, commodity_quantity=101))
        self.scope["intentDigest"] = prepare_remint_terms(
            self.old, self.new, self.verify, bill)["historyDigest"]
        with self.assertRaises(CheckpointedOperationRefused):
            self.invoke()
        self.assertEqual(self.calls, [])

    def test_readonly_original_observation_does_not_need_current_snapshot_schema(self):
        self.fixture.journal.claim(self.scope, 0)
        self.fixture.exchange.unrecognized_future_field = "unsupported"
        result = observe_remint(self.fixture.journal, self.scope,
            lambda scope: {"status": "unknown"}, history_store=self.history)
        self.assertEqual(result["localClaim"]["status"], "UNKNOWN")
        self.assertEqual(self.calls, [])
