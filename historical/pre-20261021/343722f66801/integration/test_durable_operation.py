"""Restart/CAS definitions for the EX claim store; no native financial effects."""
from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
import unittest

from exchange.durable_operation import (DurableEXOperationJournal, DurableOperationRefused,
                                        DurableOperationCommitUnknown)


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

