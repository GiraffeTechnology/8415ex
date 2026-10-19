"""Synthetic original ports and file-backed stores; no actual chain operation."""
from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
import unittest

from exchange.aggregate_checkpoint import AggregateCheckpointStore, CheckpointCommitUnknown
from exchange.durable_operation import (DurableEXOperationJournal, DurableOperationCommitUnknown,
                                        DurableNativeOutcomeUnknown)
from exchange.exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint, ExchangeCheckpointRefused
from exchange.serialized_exchange_access import SerializedExchangeAccess
from exchange.checkpointed_operation import CheckpointedOperationBridge, CheckpointedOperationRefused
from exchange.ledger import Exchange
from integration.test_mint_specification_codec import specification


class LostAcknowledgement(sqlite3.Connection):
    fail_ack = False
    lost_acks = 0
    def commit(self):
        super().commit()
        if self.fail_ack:
            self.lost_acks += 1
            raise sqlite3.OperationalError("synthetic lost acknowledgement")


class CheckpointedOperationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name)
        self.claim_db = self.connect("claims.db", LostAcknowledgement)
        self.snapshot_db = self.connect("snapshot.db", LostAcknowledgement)
        DurableEXOperationJournal.initialize(self.claim_db)
        AggregateCheckpointStore.initialize(self.snapshot_db)
        self.journal = DurableEXOperationJournal(self.claim_db)
        store = AggregateCheckpointStore(self.snapshot_db, components=("owned-facts",),
                                         source_commit="a" * 40, source_tree="b" * 40)
        self.checkpoint = ExchangeSnapshotCheckpoint(store)
        self.exchange = Exchange(lambda: 20, mint_verifier=lambda kind, evidence: True)
        spec = specification()
        self.exchange.mint(spec.receipt, spec)
        self.access = SerializedExchangeAccess(self.exchange)
        self.bridge = CheckpointedOperationBridge(self.access, self.checkpoint, self.journal, "original-instance")
        self.scope = {"receiptId": "receipt-1", "chainId": spec.receipt.asset.chain_id,
            "contract": spec.receipt.asset.contract, "tokenId": str(spec.receipt.asset.token_id),
            "globalLegId": 0, "action": "remint", "nativeOperationId": "original-native-operation",
            "intentDigest": "c" * 64, "journalReference": "original-journal"}
        self.pre_scope = self.bridge.pre_effect_scope(self.scope)
        self.calls = []

    def connect(self, filename, factory=sqlite3.Connection):
        db = sqlite3.connect(self.path / filename, factory=factory)
        self.addCleanup(db.close)
        db.execute("PRAGMA synchronous=FULL")
        return db

    def invoke(self, enquire=None, execute=None, **overrides):
        options = dict(expected_operation_revision=0,
                       enquire_original=enquire or (lambda scope: None),
                       execute_original=execute or self.execute)
        options.update(overrides)
        return self.bridge.invoke(self.scope, **options)

    def execute(self, scope):
        self.assertEqual(self.journal.lookup(scope["nativeOperationId"])["status"], "UNKNOWN")
        self.assertEqual(self.checkpoint.read(self.bridge.pre_effect_scope(scope))["generation"], 1)
        self.calls.append(deepcopy(scope))
        return {"status": "pending", "reference": "synthetic-original-result"}

    def test_claim_and_pre_effect_snapshot_are_durable_before_original_gate(self):
        result = self.invoke()
        self.assertEqual(self.calls, [self.scope])
        self.assertEqual(result["preEffectCheckpoint"]["generation"], 1)
        self.assertTrue(result["operation"]["nativeGateInvoked"])
        self.assertEqual(self.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")
        self.assertFalse(result["executionAuthorized"])
        self.assertFalse(result["completeRecovery"])

    def test_existing_unknown_is_enquired_without_checkpoint_or_native_replay(self):
        self.invoke()
        result = self.invoke(enquire=lambda scope: {"status": "unknown"})
        self.assertIsNone(result["preEffectCheckpoint"])
        self.assertFalse(result["operation"]["nativeGateInvoked"])
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.checkpoint.read(self.pre_scope)["generation"], 1)

    def test_later_original_operation_retains_the_first_operation_preimage(self):
        self.invoke()
        retained = self.checkpoint.read(self.pre_scope)["components"]["owned-facts"]
        self.access.connect_wallet("0x" + "3" * 40, "later-original-session")
        self.scope = dict(self.scope, nativeOperationId="second-original-native-operation")
        result = self.invoke(expected_operation_revision=1)
        self.assertNotEqual(result["preEffectCheckpoint"]["scope"], self.pre_scope)
        self.assertEqual(self.checkpoint.read(self.pre_scope)["components"]["owned-facts"], retained)
        self.assertEqual(self.checkpoint.read(self.pre_scope)["generation"], 1)
        self.assertEqual(len(self.calls), 2)

    def test_native_enquiry_hit_does_not_save_or_dispatch(self):
        result = self.invoke(enquire=lambda scope: {"status": "pending"})
        self.assertIsNone(result["preEffectCheckpoint"])
        self.assertEqual(self.calls, [])
        self.assertIsNone(self.checkpoint.read(self.pre_scope))
        self.assertEqual(self.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")

    def test_stale_snapshot_generation_cannot_enter_native_gate(self):
        self.access.write_checkpoint(self.checkpoint, self.pre_scope, expected_generation=0)
        with self.assertRaises(ExchangeCheckpointRefused): self.invoke()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.checkpoint.read(self.pre_scope)["generation"], 1)
        self.assertEqual(self.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")

    def test_snapshot_lost_ack_retains_exact_error_and_never_dispatches(self):
        self.snapshot_db.fail_ack = True
        with self.assertRaises(CheckpointCommitUnknown): self.invoke()
        self.assertEqual(self.snapshot_db.lost_acks, 1)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.checkpoint.read(self.pre_scope)["generation"], 1)
        self.assertEqual(self.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")

    def test_claim_lost_ack_does_not_attempt_snapshot_or_native_gate(self):
        self.claim_db.fail_ack = True
        with self.assertRaises(DurableOperationCommitUnknown): self.invoke()
        self.assertEqual(self.claim_db.lost_acks, 1)
        self.assertEqual(self.calls, [])
        self.assertIsNone(self.checkpoint.read(self.pre_scope))
        self.assertEqual(self.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")

    def test_native_timeout_keeps_pre_effect_snapshot_and_unknown_without_replay(self):
        def native(scope):
            self.calls.append(deepcopy(scope))
            raise TimeoutError("synthetic native response lost")
        with self.assertRaises(DurableNativeOutcomeUnknown): self.invoke(execute=native)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.checkpoint.read(self.pre_scope)["generation"], 1)
        self.invoke(enquire=lambda scope: {"status": "unknown"})
        self.assertEqual(len(self.calls), 1)

    def test_operation_asset_mismatch_is_refused_before_snapshot_and_native_effect(self):
        self.scope["tokenId"] = "999"
        with self.assertRaises(CheckpointedOperationRefused): self.invoke()
        self.assertEqual(self.calls, [])
        self.assertIsNone(self.checkpoint.read(self.pre_scope))
        self.assertEqual(self.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")

    def test_existing_claim_enquiry_does_not_require_new_snapshot_schema_availability(self):
        self.journal.claim(self.scope, 0)
        self.exchange._new_unhandled_state = {"status": "UNKNOWN"}
        result = self.invoke(enquire=lambda scope: {"status": "unknown"})
        self.assertFalse(result["operation"]["nativeGateInvoked"])
        self.assertIsNone(result["preEffectCheckpoint"])
        self.assertEqual(self.calls, [])
