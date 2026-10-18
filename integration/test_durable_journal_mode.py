"""File-SQLite crash-safety policy definitions for approved remote Linux.

These exercise effective journal modes, not a crash or real financial writer.
"""
from pathlib import Path
import sqlite3
import tempfile
import unittest

from exchange.durable_operation import DurableEXOperationJournal, DurableOperationRefused


class DurableJournalModeTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.connection = sqlite3.connect(str(Path(directory.name) / "claims.sqlite"))
        self.addCleanup(self.connection.close)
        self.connection.execute("PRAGMA synchronous=FULL")
        DurableEXOperationJournal.initialize(self.connection)
        self.scope = {"receiptId": "receipt-1", "chainId": 11155111,
            "contract": "0x" + "1" * 40, "tokenId": "19", "globalLegId": 3,
            "action": "refund", "nativeOperationId": "native-1",
            "intentDigest": "a" * 64, "journalReference": "original-journal-1"}

    def mode(self, name):
        # Only these test-owned fixed tokens are interpolated, never user input.
        self.assertIn(name, ("OFF", "MEMORY", "DELETE", "TRUNCATE", "PERSIST", "WAL"))
        observed = self.connection.execute("PRAGMA journal_mode=" + name).fetchone()[0]
        self.assertEqual(observed.lower(), name.lower())

    def test_constructor_refuses_nonpersistent_journals_even_with_full_sync(self):
        for mode in ("OFF", "MEMORY"):
            with self.subTest(mode=mode):
                self.mode(mode)
                self.assertEqual(self.connection.execute("PRAGMA synchronous").fetchone()[0], 2)
                with self.assertRaisesRegex(DurableOperationRefused, "persistent SQLite journal"):
                    DurableEXOperationJournal(self.connection)
                self.assertFalse(self.connection.in_transaction)

    def test_changed_mode_blocks_claim_before_native_dispatch_or_receipt_revision(self):
        journal = DurableEXOperationJournal(self.connection)
        effects = []
        for mode in ("OFF", "MEMORY"):
            with self.subTest(mode=mode):
                self.mode(mode)
                with self.assertRaisesRegex(DurableOperationRefused, "persistent SQLite journal"):
                    journal.invoke_once(self.scope, 0, lambda scope: None,
                                        lambda scope: effects.append(scope))
                self.assertEqual(journal.revision("receipt-1"), 0)
                self.assertIsNone(journal.lookup("native-1"))
                self.assertEqual(effects, [])
                self.assertFalse(self.connection.in_transaction)

    def test_changed_mode_preserves_unknown_and_blocks_terminal_write(self):
        journal = DurableEXOperationJournal(self.connection)
        journal.claim(self.scope, 0)
        verified = []
        for mode in ("OFF", "MEMORY"):
            with self.subTest(mode=mode):
                self.mode(mode)
                with self.assertRaisesRegex(DurableOperationRefused, "persistent SQLite journal"):
                    journal.reconcile(self.scope, "applied", "proof-1",
                                      lambda *args: verified.append(args) or True)
                self.assertEqual(journal.lookup("native-1")["status"], "UNKNOWN")
                self.assertEqual(journal.revision("receipt-1"), 1)
                self.assertEqual(verified, [])
                # Read-only recovery still queries the original operation.
                seen = []
                result = journal.observe(self.scope, lambda scope: seen.append(scope) or {"status": "pending"})
                self.assertEqual(seen, [self.scope])
                self.assertFalse(result["nativeGateInvoked"])
                self.assertFalse(result["replayAllowed"])

    def test_existing_file_journal_modes_and_wal_remain_supported(self):
        journal = DurableEXOperationJournal(self.connection)
        for revision, mode in enumerate(("DELETE", "TRUNCATE", "PERSIST", "WAL")):
            with self.subTest(mode=mode):
                self.mode(mode)
                scope = dict(self.scope, nativeOperationId="native-" + str(revision))
                self.assertEqual(journal.claim(scope, revision)["disposition"], "NEW_DURABLE_CLAIM")
                self.assertEqual(journal.revision("receipt-1"), revision + 1)
                self.assertEqual(journal.lookup(scope["nativeOperationId"])["status"], "UNKNOWN")
