"""Real temporary SQLite recovery definitions; native replies are synthetic."""
from copy import deepcopy
from pathlib import Path
import sqlite3
import tempfile
import unittest

from exchange.durable_operation import DurableEXOperationJournal, DurableOperationRefused
from exchange.operation_recovery import enquire_pending_operations


class RestartEnquiryContracts(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = str(Path(directory.name) / "claims.sqlite")
        self.connection = self.connect()
        DurableEXOperationJournal.initialize(self.connection)
        self.journal = DurableEXOperationJournal(self.connection)
        self.scope = {"receiptId": "receipt-1", "chainId": 11155111,
            "contract": "0x" + "1" * 40, "tokenId": "19", "globalLegId": 3,
            "action": "refund", "nativeOperationId": "native-1",
            "intentDigest": "a" * 64, "journalReference": "original-journal-1"}

    def connect(self):
        connection = sqlite3.connect(self.path)
        self.addCleanup(connection.close)
        return connection

    def test_restart_discovers_original_identity_without_old_in_memory_declarations(self):
        self.journal.claim(self.scope, 0)
        self.connection.close()
        reopened = DurableEXOperationJournal(self.connect())
        seen = []
        def enquire(scope):
            seen.append(deepcopy(scope))
            scope["intentDigest"] = "b" * 64
            return {"status": "submitted"}
        page = enquire_pending_operations(reopened, enquire)
        self.assertEqual(seen, [self.scope])
        self.assertFalse(page["nativeGateInvoked"])
        self.assertFalse(page["replayAllowed"])
        self.assertEqual(reopened.lookup("native-1")["scope"], self.scope)
        self.assertEqual(reopened.lookup("native-1")["status"], "UNKNOWN")
        self.assertEqual(reopened.revision("receipt-1"), 1)

    def test_bounded_pages_skip_terminal_claim_and_do_not_change_revisions(self):
        for index in range(1, 4):
            self.journal.claim(dict(self.scope, nativeOperationId="native-" + str(index)), index - 1)
        terminal = dict(self.scope, nativeOperationId="native-2")
        self.journal.reconcile(terminal, "not-applied", "proof-2", lambda *args: True)
        seen = []
        first = enquire_pending_operations(self.journal, lambda s: seen.append(s["nativeOperationId"]), limit=1)
        second = enquire_pending_operations(self.journal, lambda s: seen.append(s["nativeOperationId"]),
                                            limit=1, after=first["nextCursor"])
        self.assertEqual(seen, ["native-1", "native-3"])
        self.assertEqual(first["nextCursor"], "native-1")
        self.assertIsNone(second["nextCursor"])
        self.assertTrue(second["newSweepsStartAtBeginning"])
        self.assertEqual(self.journal.revision("receipt-1"), 3)

    def test_native_enquiry_failure_does_not_block_independent_claim_or_leak_error(self):
        self.journal.claim(self.scope, 0)
        self.journal.claim(dict(self.scope, nativeOperationId="native-2"), 1)
        seen = []
        def enquire(scope):
            seen.append(scope["nativeOperationId"])
            if scope["nativeOperationId"] == "native-1":
                raise TimeoutError("private synthetic transport detail")
            return {"status": "outcome-unknown"}
        page = enquire_pending_operations(self.journal, enquire)
        self.assertEqual(seen, ["native-1", "native-2"])
        self.assertEqual(page["operations"][0]["status"], "ORIGINAL_ENQUIRY_UNAVAILABLE")
        self.assertEqual(page["operations"][1]["status"], "ORIGINAL_ENQUIRY_RETURNED")
        self.assertNotIn("private synthetic", repr(page))
        self.assertEqual(self.journal.lookup("native-1")["status"], "UNKNOWN")

    def test_corrupt_index_refuses_before_any_original_query(self):
        self.journal.claim(self.scope, 0)
        self.connection.execute("UPDATE ex_operation_claims SET receipt_id='another-receipt'")
        self.connection.commit()
        seen = []
        with self.assertRaisesRegex(DurableOperationRefused, "^Stored operation binding is inconsistent$"):
            enquire_pending_operations(self.journal, lambda scope: seen.append(scope))
        self.assertEqual(seen, [])

    def test_invalid_bounds_and_owned_transaction_are_refused(self):
        for parameters in ({"limit": True}, {"limit": 0}, {"limit": 101}, {"after": "bad cursor"}):
            with self.subTest(parameters=parameters), self.assertRaises(DurableOperationRefused):
                enquire_pending_operations(self.journal, lambda scope: None, **parameters)
        self.connection.execute("BEGIN")
        try:
            with self.assertRaises(DurableOperationRefused):
                enquire_pending_operations(self.journal, lambda scope: None)
            self.assertTrue(self.connection.in_transaction)
        finally:
            self.connection.rollback()
