"""Restart/CAS definitions for the EX claim store; no native financial effects."""
from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
import unittest

from exchange.durable_operation import (DurableEXOperationJournal, DurableOperationRefused,
                                        DurableOperationCommitUnknown, DurableNativeOutcomeUnknown)


class LostCommitAcknowledgement(sqlite3.Connection):
    lose_next_ack = False

    def commit(self):
        super().commit()
        if self.lose_next_ack:
            self.lose_next_ack = False
            raise sqlite3.OperationalError("synthetic commit acknowledgement lost")


class DurableOperationContracts(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = str(Path(self.directory.name) / "ex-claims.sqlite")
        self.connection = self.connect()
        DurableEXOperationJournal.initialize(self.connection)
        self.journal = DurableEXOperationJournal(self.connection)
        self.scope = {"receiptId": "synthetic-receipt", "chainId": 11155111,
            "contract": "0x" + "1" * 40, "tokenId": "19", "globalLegId": 3,
            "action": "refund", "nativeOperationId": "original-native-op-3",
            "intentDigest": "a" * 64, "journalReference": "original-journal-3"}

    def connect(self):
        connection = sqlite3.connect(self.path)
        self.addCleanup(connection.close)
        return connection

    def test_closed_process_connection_reopens_unknown_without_replay(self):
        row = self.journal.claim(self.scope, 0)
        self.assertEqual(row["disposition"], "NEW_DURABLE_CLAIM")
        self.assertEqual(row["status"], "UNKNOWN")
        self.connection.close()
        recovered = DurableEXOperationJournal(self.connect())
        self.assertEqual(recovered.revision(self.scope["receiptId"]), 1)
        stored = recovered.lookup(self.scope["nativeOperationId"])
        self.assertEqual(stored["scope"], self.scope)
        self.assertFalse(stored["dispatchAuthorized"])
        self.assertFalse(stored["replayAllowed"])
        self.assertEqual(recovered.claim(self.scope, 0)["disposition"], "EXISTING_RECONCILE_ONLY")

    def test_two_connections_cannot_claim_different_operations_at_same_revision(self):
        other = DurableEXOperationJournal(self.connect())
        self.journal.claim(self.scope, 0)
        changed = dict(self.scope, nativeOperationId="other-native-operation")
        with self.assertRaisesRegex(DurableOperationRefused, "revision changed"):
            other.claim(changed, 0)
        self.assertIsNone(other.lookup(changed["nativeOperationId"]))
        self.assertEqual(other.revision(self.scope["receiptId"]), 1)

    def test_reused_operation_with_changed_intent_is_conflict(self):
        self.journal.claim(self.scope, 0)
        with self.assertRaisesRegex(DurableOperationRefused, "identity conflict"):
            self.journal.claim(dict(self.scope, intentDigest="b" * 64), 1)
        self.assertEqual(self.journal.revision(self.scope["receiptId"]), 1)

    def test_only_original_verified_outcome_can_reconcile(self):
        self.journal.claim(self.scope, 0)
        for verdict in (False, None, 1, "verified"):
            with self.subTest(verdict=verdict), self.assertRaises(DurableOperationRefused):
                self.journal.reconcile(self.scope, "applied", "original-proof", lambda *args: verdict)
        self.assertEqual(self.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")
        observed = []
        def verify(scope, outcome, proof):
            observed.append((deepcopy(scope), outcome, proof))
            scope["intentDigest"] = "c" * 64
            return True
        result = self.journal.reconcile(self.scope, "applied", "original-proof", verify)
        self.assertEqual(observed, [(self.scope, "applied", "original-proof")])
        self.assertEqual(result["scope"], self.scope)
        self.assertFalse(result["dispatchAuthorized"])

    def test_terminal_result_persists_and_does_not_enable_resend(self):
        self.journal.claim(self.scope, 0)
        self.journal.reconcile(self.scope, "not-applied", "original-proof", lambda *args: True)
        self.connection.close()
        reopened = DurableEXOperationJournal(self.connect())
        result = reopened.claim(self.scope, 0)
        self.assertEqual(result["outcome"], "not-applied")
        self.assertFalse(result["replayAllowed"])
        with self.assertRaisesRegex(DurableOperationRefused, "Conflicting terminal"):
            reopened.reconcile(self.scope, "applied", "different-proof", lambda *args: True)

    def test_secret_payloads_and_other_networks_are_not_persisted(self):
        for scope in (dict(self.scope, signature="not-stored"), dict(self.scope, chainId=560048),
                      dict(self.scope, tokenId="01"), dict(self.scope, globalLegId=True)):
            with self.subTest(scope=scope), self.assertRaises(DurableOperationRefused):
                self.journal.claim(scope, 0)
        self.assertEqual(self.journal.revision(self.scope["receiptId"]), 0)

    def test_memory_database_and_weakened_synchronous_mode_refused(self):
        memory = sqlite3.connect(":memory:")
        self.addCleanup(memory.close)
        with self.assertRaises(DurableOperationRefused):
            DurableEXOperationJournal(memory)
        other = self.connect()
        other.execute("PRAGMA synchronous=OFF")
        with self.assertRaises(DurableOperationRefused):
            DurableEXOperationJournal(other)

    def test_other_owners_transaction_is_never_committed(self):
        self.connection.execute("BEGIN")
        try:
            with self.assertRaisesRegex(DurableOperationRefused, "another owner"):
                self.journal.claim(self.scope, 0)
            self.assertTrue(self.connection.in_transaction)
        finally:
            self.connection.rollback()

    def test_synchronous_downgrade_after_construction_refuses_claim_and_dispatch(self):
        self.connection.execute("PRAGMA synchronous=NORMAL")
        sent = []
        with self.assertRaisesRegex(DurableOperationRefused, "Write requires FULL"):
            self.journal.invoke_once(self.scope, 0, lambda scope: None,
                                     lambda scope: sent.append(scope))
        self.assertEqual(sent, [])
        self.assertIsNone(self.journal.lookup(self.scope["nativeOperationId"]))
        self.assertEqual(self.journal.revision(self.scope["receiptId"]), 0)
        self.assertFalse(self.connection.in_transaction)

    def test_enquiry_cannot_downgrade_durability_before_claim(self):
        sent = []
        def enquire(scope):
            self.connection.execute("PRAGMA synchronous=OFF")
            return None
        with self.assertRaisesRegex(DurableOperationRefused, "Write requires FULL"):
            self.journal.invoke_once(self.scope, 0, enquire,
                                     lambda scope: sent.append(scope))
        self.assertEqual(sent, [])
        self.assertIsNone(self.journal.lookup(self.scope["nativeOperationId"]))
        self.assertEqual(self.journal.revision(self.scope["receiptId"]), 0)

    def test_downgrade_blocks_reconciliation_but_preserves_read_only_recovery(self):
        self.journal.claim(self.scope, 0)
        self.connection.execute("PRAGMA synchronous=OFF")
        proofs = []
        with self.assertRaisesRegex(DurableOperationRefused, "Write requires FULL"):
            self.journal.reconcile(self.scope, "applied", "original-proof",
                                   lambda *args: proofs.append(args) or True)
        self.assertEqual(proofs, [])
        observed = self.journal.observe(self.scope, lambda scope: {"status": "submitted"})
        self.assertFalse(observed["nativeGateInvoked"])
        self.assertEqual(observed["localClaim"]["status"], "UNKNOWN")
        self.assertEqual(self.journal.revision(self.scope["receiptId"]), 1)
        self.assertFalse(self.connection.in_transaction)
        self.connection.execute("PRAGMA synchronous=FULL")
        result = self.journal.reconcile(self.scope, "applied", "original-proof", lambda *args: True)
        self.assertEqual(result["status"], "RECONCILED")

    def test_committed_claim_with_lost_ack_is_recovered_without_replay(self):
        path = str(Path(self.directory.name) / "lost-ack.sqlite")
        connection = sqlite3.connect(path, factory=LostCommitAcknowledgement)
        self.addCleanup(connection.close)
        DurableEXOperationJournal.initialize(connection)
        journal = DurableEXOperationJournal(connection)
        connection.lose_next_ack = True
        with self.assertRaisesRegex(DurableOperationCommitUnknown, "Claim commit outcome unknown"):
            journal.claim(self.scope, 0)
        connection.close()
        reopened = sqlite3.connect(path)
        self.addCleanup(reopened.close)
        recovered = DurableEXOperationJournal(reopened)
        result = recovered.claim(self.scope, 0)
        self.assertEqual(result["disposition"], "EXISTING_RECONCILE_ONLY")
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertFalse(result["dispatchAuthorized"])
        self.assertFalse(result["replayAllowed"])
        self.assertEqual(recovered.revision(self.scope["receiptId"]), 1)

    def test_native_gate_observes_committed_unknown_before_effect(self):
        seen = []
        def original_gate(scope):
            independent = DurableEXOperationJournal(self.connect())
            row = independent.lookup(scope["nativeOperationId"])
            self.assertEqual(row["status"], "UNKNOWN")
            self.assertEqual(row["scope"], self.scope)
            seen.append(scope)
            return {"status": "submitted", "meaning": "synthetic only"}
        result = self.journal.invoke_once(self.scope, 0, lambda scope: None, original_gate)
        self.assertEqual(seen, [self.scope])
        self.assertTrue(result["nativeGateInvoked"])
        self.assertEqual(self.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")

    def test_lost_native_reply_never_dispatches_again_after_reopen(self):
        called = []
        def lose_reply(scope):
            called.append(scope)
            raise TimeoutError("synthetic response lost after native effect")
        with self.assertRaises(DurableNativeOutcomeUnknown):
            self.journal.invoke_once(self.scope, 0, lambda scope: None, lose_reply)
        self.connection.close()
        reopened = DurableEXOperationJournal(self.connect())
        result = reopened.invoke_once(self.scope, 0,
            lambda scope: {"status": "outcome-unknown"}, lose_reply)
        self.assertEqual(called, [self.scope])
        self.assertFalse(result["nativeGateInvoked"])
        self.assertEqual(result["disposition"], "EXISTING_RECONCILE_ONLY")

    def test_lookup_failure_never_creates_claim_or_invokes_native_gate(self):
        called = []
        def unavailable(scope):
            raise TimeoutError("synthetic original journal unavailable")
        with self.assertRaises(TimeoutError):
            self.journal.invoke_once(self.scope, 0, unavailable, lambda scope: called.append(scope))
        self.assertEqual(called, [])
        self.assertIsNone(self.journal.lookup(self.scope["nativeOperationId"]))
        self.assertEqual(self.journal.revision(self.scope["receiptId"]), 0)

    def test_preexisting_original_operation_is_never_sent_again(self):
        called = []
        result = self.journal.invoke_once(self.scope, 0,
            lambda scope: {"status": "submitted"}, lambda scope: called.append(scope))
        self.assertEqual(called, [])
        self.assertFalse(result["nativeGateInvoked"])
        self.assertEqual(self.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")

    def test_claim_commit_unknown_cannot_fall_through_to_dispatch(self):
        path = str(Path(self.directory.name) / "invoke-lost-ack.sqlite")
        connection = sqlite3.connect(path, factory=LostCommitAcknowledgement)
        self.addCleanup(connection.close)
        DurableEXOperationJournal.initialize(connection)
        journal = DurableEXOperationJournal(connection)
        called = []
        connection.lose_next_ack = True
        with self.assertRaises(DurableOperationCommitUnknown):
            journal.invoke_once(self.scope, 0, lambda scope: None, lambda scope: called.append(scope))
        self.assertEqual(called, [])
        self.assertEqual(journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")

