"""Synthetic composition definitions; approved remote Linux execution only."""
from dataclasses import replace
import os
import sqlite3
import tempfile
import unittest

from exchange import fixtures as F
from exchange.durable_operation import DurableEXOperationJournal, DurableNativeOutcomeUnknown
from exchange.remint_terms import prepare_remint_terms, RemintTermsRefused
from exchange.remint_execution import invoke_remint, observe_remint


def bill(binding):
    return {"billKey": "0x" + "1" * 64,
            "sourceReference": "synthetic-original-bill", "binding": binding}


class RemintExecutionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.directory.name, "synthetic-ex.sqlite")
        self.connection = sqlite3.connect(self.path)
        DurableEXOperationJournal.initialize(self.connection)
        self.journal = DurableEXOperationJournal(self.connection)
        self.old = F.mint_specification(F.receipt())
        self.new = replace(self.old, receipt=replace(self.old.receipt,
            asset=replace(self.old.receipt.asset, token_id=8416),
            receipt_id="synthetic-reminted-receipt"), bill_terms="New terms")
        digest = prepare_remint_terms(self.old, self.new, F.verify_fixture_mint, bill)["historyDigest"]
        self.scope = {"receiptId": self.old.receipt.receipt_id, "chainId": 11155111,
            "contract": F.CONTRACT, "tokenId": str(F.TOKEN_ID), "globalLegId": 0,
            "action": "remint", "nativeOperationId": "synthetic-remint-op",
            "intentDigest": digest, "journalReference": "synthetic-native-journal"}

    def tearDown(self):
        self.connection.close()
        self.directory.cleanup()

    def invoke(self, execute, enquire=lambda scope: None, scope=None):
        return invoke_remint(self.journal, scope or self.scope, 0, self.old, self.new,
                             F.verify_fixture_mint, bill, enquire, execute)

    def test_original_gateway_receives_exact_history_after_durable_unknown(self):
        calls = []
        def execute(scope, history):
            self.assertEqual(self.journal.lookup(scope["nativeOperationId"])["status"], "UNKNOWN")
            self.assertEqual(history["newDeclaration"]["billTerms"], "New terms")
            calls.append(scope)
            history["newDeclaration"]["billTerms"] = "External mutation"
            return {"transport": "synthetic-ack"}
        result = self.invoke(execute)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["businessAcceptance"], "NOT_ESTABLISHED")
        self.assertEqual(self.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")
        self.assertEqual(self.new.bill_terms, "New terms")

    def test_restart_after_lost_reply_only_enquires_and_never_resends(self):
        calls = []
        def lost(scope, history):
            calls.append(scope)
            raise TimeoutError("synthetic lost acknowledgement")
        with self.assertRaises(DurableNativeOutcomeUnknown):
            self.invoke(lost)
        self.connection.close()
        self.connection = sqlite3.connect(self.path)
        self.journal = DurableEXOperationJournal(self.connection)
        result = self.invoke(lost, enquire=lambda scope: {"state": "synthetic-pending"})
        self.assertEqual(len(calls), 1)
        self.assertFalse(result["operation"]["nativeGateInvoked"])
        self.assertFalse(result["replayAllowed"])

    def test_changed_declaration_digest_or_asset_refused_before_claim(self):
        for field, value in (("intentDigest", "0" * 64), ("tokenId", "999"),
                             ("action", "trade"), ("chainId", 11155111.0)):
            scope = dict(self.scope, **{field: value})
            with self.subTest(field=field), self.assertRaises(RemintTermsRefused):
                self.invoke(lambda *_: self.fail("must not dispatch"), scope=scope)
            self.assertIsNone(self.journal.lookup(self.scope["nativeOperationId"]))

    def test_enquiry_failure_never_creates_claim_or_calls_execution(self):
        def unavailable(scope):
            raise ConnectionError("synthetic original source unavailable")
        with self.assertRaises(ConnectionError):
            self.invoke(lambda *_: self.fail("must not dispatch"), enquire=unavailable)
        self.assertIsNone(self.journal.lookup(self.scope["nativeOperationId"]))

    def test_read_only_recovery_needs_no_old_declaration_or_new_claim(self):
        result = observe_remint(self.journal, self.scope,
                                lambda scope: {"state": "synthetic-original-absent"})
        self.assertIsNone(result["localClaim"])
        self.assertFalse(result["nativeGateInvoked"])
        self.assertIsNone(self.journal.lookup(self.scope["nativeOperationId"]))
        self.assertEqual(self.journal.revision(self.scope["receiptId"]), 0)

    def test_read_only_recovery_preserves_unknown_and_refuses_identity_conflict(self):
        self.journal.claim(self.scope, 0)
        result = observe_remint(self.journal, self.scope,
                                lambda scope: {"state": "synthetic-pending"})
        self.assertEqual(result["localClaim"]["status"], "UNKNOWN")
        self.assertEqual(self.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")
        from exchange.durable_operation import DurableOperationRefused
        with self.assertRaises(DurableOperationRefused):
            observe_remint(self.journal, dict(self.scope, tokenId="999"),
                           lambda scope: self.fail("conflicting identity must not query"))


if __name__ == "__main__":
    unittest.main()
