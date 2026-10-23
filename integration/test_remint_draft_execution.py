"""Synthetic edited-term to original durable-gate contracts; author NOT_RUN."""
import unittest

from exchange.checkpointed_operation import CheckpointedOperationRefused
from exchange.durable_operation import DurableNativeOutcomeUnknown
from exchange.remint_draft_execution import invoke_draft_remint
from exchange.remint_draft_workbench import RemintDraftEditorBinding, RemintDraftUnavailable
from exchange.remint_terms import prepare_remint_terms, RemintTermsRefused
from exchange.serialized_exchange_access import SerializedExchangeAccess
from integration import test_checkpointed_remint as original


class DraftRemintExecutionContracts(unittest.TestCase):
    def setUp(self):
        self.host = original.CheckpointedRemintTests("runTest")
        self.host.setUp()
        self.addCleanup(self.host.doCleanups)
        self.reads = []
        self.unavailable = False
        def specifications(receipt_id):
            self.reads.append(receipt_id)
            if self.unavailable:
                raise RuntimeError("private original declaration error")
            return self.host.old, self.host.new
        self.editor = RemintDraftEditorBinding(self.host.fixture.bridge.access,
            self.host.old.receipt.receipt_id, specifications)
        self.options = {"bill_terms": "Complete edited replacement terms"}
        old, proposed = self.editor.draft_specifications(**self.options)
        digest = prepare_remint_terms(old, proposed, self.host.verify, original.bill)["historyDigest"]
        self.scope = dict(self.host.scope, intentDigest=digest)
        self.reads.clear()

    def invoke(self, *, editor=None, scope=None, execute=None, enquire=None):
        return invoke_draft_remint(self.host.fixture.bridge, editor or self.editor,
            self.scope if scope is None else scope, 0, self.host.verify, original.bill,
            enquire or (lambda scope: None), execute or self.host.execute,
            history_store=self.host.history, draft_options=self.options)

    def test_one_original_read_feeds_exact_edited_history_and_one_native_gate(self):
        result = self.invoke()
        self.assertEqual(self.reads, [self.editor.receipt_id])
        self.assertEqual(len(self.host.calls), 1)
        stored = self.host.history.read(self.scope)["history"]
        self.assertEqual(stored["newDeclaration"]["billTerms"], self.options["bill_terms"])
        self.assertEqual(stored["oldDeclaration"]["billTerms"], self.host.old.bill_terms)
        self.assertEqual(result["historyDigest"], self.scope["intentDigest"])
        self.assertEqual(result["preEffectCheckpoint"]["generation"], 1)
        self.assertFalse(result["executionAuthorized"])
        self.assertFalse(result["replayAllowed"])
        self.assertEqual(self.host.new.bill_terms, "Changed original bill terms")

    def test_old_preview_digest_cannot_authorize_edited_terms(self):
        with self.assertRaises(RemintTermsRefused):
            self.invoke(scope=self.host.scope)
        self.assertEqual(self.host.calls, [])
        self.assertIsNone(self.host.fixture.journal.lookup(self.scope["nativeOperationId"]))
        self.assertIsNone(self.host.history.read(self.scope))

    def test_foreign_access_or_receipt_is_refused_before_draft_source_read(self):
        foreign = RemintDraftEditorBinding(SerializedExchangeAccess(self.host.fixture.exchange),
            self.editor.receipt_id, self.editor.read_original_specifications)
        for editor, scope in ((foreign, self.scope),
                              (self.editor, dict(self.scope, receiptId="another-receipt"))):
            with self.subTest(editor=editor), self.assertRaises(CheckpointedOperationRefused):
                self.invoke(editor=editor, scope=scope)
        self.assertEqual(self.reads, [])
        self.assertEqual(self.host.calls, [])

    def test_lost_reply_preserves_exact_history_and_existing_unknown_without_replay(self):
        def lost(scope, history):
            self.host.execute(scope, history)
            raise TimeoutError("synthetic lost response")
        with self.assertRaises(DurableNativeOutcomeUnknown):
            self.invoke(execute=lost)
        result = self.invoke(enquire=lambda scope: {"status": "unknown"})
        self.assertEqual(len(self.host.calls), 1)
        self.assertFalse(result["operation"]["nativeGateInvoked"])
        self.assertIsNone(result["preEffectCheckpoint"])
        self.assertEqual(self.host.fixture.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")
        self.assertEqual(self.host.history.read(self.scope)["history"]["newDeclaration"]["billTerms"],
                         self.options["bill_terms"])

    def test_unavailable_original_draft_creates_no_claim_history_or_checkpoint(self):
        self.unavailable = True
        with self.assertRaises(RemintDraftUnavailable):
            self.invoke()
        self.assertEqual(self.host.calls, [])
        self.assertIsNone(self.host.fixture.journal.lookup(self.scope["nativeOperationId"]))
        self.assertIsNone(self.host.history.read(self.scope))
        self.assertIsNone(self.host.fixture.checkpoint.read(
            self.host.fixture.bridge.pre_effect_scope(self.scope)))

    def test_preview_remains_unsigned_and_does_not_enter_this_execution_port(self):
        changes = self.host.fixture.claim_db.total_changes
        text = self.editor.render("fixture-csrf", "en", **self.options)
        self.assertIn(self.options["bill_terms"], text)
        self.assertEqual(self.host.fixture.claim_db.total_changes, changes)
        self.assertEqual(self.host.calls, [])
        self.assertIsNone(self.host.fixture.journal.lookup(self.scope["nativeOperationId"]))
