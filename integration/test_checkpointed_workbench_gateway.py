"""Synthetic UI/native correlation recovery; no live wallet or chain calls."""
from collections import OrderedDict
from copy import deepcopy
from email.message import Message
from io import BytesIO
from types import SimpleNamespace
from urllib.parse import urlencode
import hashlib
import json
from unittest.mock import patch
import unittest

from exchange.checkpointed_operation import CheckpointedOperationBridge, CheckpointedOperationRefused
from exchange.checkpointed_workbench_gateway import (CheckpointedWorkbenchGateway,
    WorkbenchGatewayRefused, WorkbenchBindingCommitUnknown, WorkbenchOperationUnknown)
from exchange.durable_operation import (DurableEXOperationJournal, DurableOperationRefused,
    DurableOperationCommitUnknown, DurableNativeOutcomeUnknown)
from integration import test_checkpointed_operation as original_bridge


class CheckpointedWorkbenchGatewayTests(unittest.TestCase):
    def setUp(self):
        self.host = original_bridge.CheckpointedOperationTests("runTest")
        self.host.setUp()
        self.addCleanup(self.host.doCleanups)
        CheckpointedWorkbenchGateway.initialize(self.host.journal)
        self.scope = dict(self.host.scope, action="rollback")
        self.resolutions, self.enquiries = [], []
        self.observation = None
        self.gateway = self.make_gateway(self.host.bridge)

    def resolve(self, action, payload, context):
        self.resolutions.append((action, deepcopy(payload), deepcopy(context)))
        return deepcopy(self.scope)

    def enquire_native(self, scope):
        self.enquiries.append(deepcopy(scope))
        return deepcopy(self.observation)

    def make_gateway(self, bridge, *, resolver=None, enquiry=None, execute=None, fallback=None):
        return CheckpointedWorkbenchGateway(bridge, resolve_command=resolver or self.resolve,
            enquire_original=enquiry or self.enquire_native,
            execute_original=execute or self.host.execute, fallback_gateway=fallback)

    def context(self, *, key="original-ui-key", action="advance-rollback", payload=None):
        payload = {} if payload is None else payload
        return {"receiptId": "receipt-1", "source": {"commit": "a" * 40, "tree": "b" * 40},
            "journalKey": key, "observedRevision": "d" * 64, "action": action,
            "payloadDigest": hashlib.sha256(json.dumps(payload, sort_keys=True,
                separators=(",", ":")).encode()).hexdigest()}

    def dispatch(self, *, gateway=None, context=None, payload=None):
        gateway = self.gateway if gateway is None else gateway
        context = self.context() if context is None else context
        payload = {} if payload is None else payload
        return gateway.dispatch(context["action"], payload, context)

    def reopened(self, *, resolver=None, enquiry=None, execute=None):
        connection = self.host.connect("claims.db", original_bridge.LostAcknowledgement)
        journal = DurableEXOperationJournal(connection)
        bridge = CheckpointedOperationBridge(self.host.access, self.host.checkpoint, journal,
                                             self.host.bridge.checkpoint_scope)
        return self.make_gateway(bridge, resolver=resolver, enquiry=enquiry, execute=execute)

    def bindings(self):
        return self.host.claim_db.execute("SELECT journal_key FROM ex_workbench_command_bindings").fetchall()

    def test_real_runtime_binding_enters_original_claim_and_checkpoint_gate_once(self):
        binding = self.host.access.bind_runtime("receipt-1", gateway=self.gateway)
        revision = binding.snapshot()["revision"]
        result = binding.command("advance-rollback", "original-ui-key", revision, {})
        self.assertFalse(result["enquired"])
        self.assertEqual(result["result"], {"status": "pending"})
        self.assertEqual(self.host.calls, [self.scope])
        self.assertEqual(self.host.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")
        self.assertEqual(self.host.checkpoint.read(self.host.bridge.pre_effect_scope(self.scope))["generation"], 1)
        again = binding.command("advance-rollback", "original-ui-key", binding.snapshot()["revision"], {})
        self.assertTrue(again["enquired"])
        self.assertEqual(again["result"], {"status": "unknown"})
        self.assertEqual(self.host.calls, [self.scope])
        self.assertEqual(len(self.resolutions), 1)

    def test_reopen_existing_unknown_does_not_require_resolver_mint_facts_or_snapshot(self):
        self.dispatch()
        def unavailable(*args):
            raise AssertionError("recovery reread declarations or saved another snapshot")
        reopened = self.reopened(resolver=unavailable)
        changes = self.host.claim_db.total_changes
        with patch.object(self.host.access, "snapshot_bytes", side_effect=unavailable), \
                patch.object(self.host.checkpoint, "save", side_effect=unavailable):
            self.assertEqual(reopened.enquire("original-ui-key", self.context()), {"status": "unknown"})
        self.assertEqual(self.host.claim_db.total_changes, changes)
        self.assertEqual(len(self.host.calls), 1)

    def test_mapping_commit_lost_ack_is_pre_effect_and_same_binding_can_continue_once(self):
        self.host.claim_db.fail_ack = True
        with self.assertRaises(WorkbenchBindingCommitUnknown):
            self.dispatch()
        self.host.claim_db.fail_ack = False
        self.assertEqual(self.bindings(), [("original-ui-key",)])
        self.assertIsNone(self.host.journal.lookup(self.scope["nativeOperationId"]))
        self.assertEqual(self.host.calls, [])
        def no_new_resolution(*args):
            raise AssertionError("persisted original scope must be reused")
        reopened = self.reopened(resolver=no_new_resolution)
        self.assertIsNone(reopened.enquire("original-ui-key", self.context()))
        self.assertEqual(self.dispatch(gateway=reopened), {"status": "pending"})
        self.assertEqual(self.host.calls, [self.scope])
        self.assertEqual(len(self.resolutions), 1)

    def test_original_claim_lost_ack_never_enters_checkpoint_or_native_gate(self):
        claim = self.host.journal.claim
        def lost_ack(scope, revision):
            claim(scope, revision)
            raise DurableOperationCommitUnknown("synthetic original claim acknowledgement lost")
        with patch.object(self.host.journal, "claim", side_effect=lost_ack):
            with self.assertRaises(WorkbenchOperationUnknown):
                self.dispatch()
        self.assertIsNone(self.host.checkpoint.read(self.host.bridge.pre_effect_scope(self.scope)))
        self.assertEqual(self.host.calls, [])
        self.assertEqual(self.reopened().enquire("original-ui-key", self.context()), {"status": "unknown"})
        self.assertEqual(self.dispatch(), {"status": "unknown"})
        self.assertEqual(self.host.calls, [])

    def test_key_reuse_for_different_receipt_action_or_payload_refuses_before_native_enquiry(self):
        self.dispatch()
        before = len(self.enquiries)
        for change in ({"receiptId": "different-receipt"}, {"action": "resume-payment"},
                       {"payloadDigest": "e" * 64}):
            with self.subTest(change=change), self.assertRaises(WorkbenchGatewayRefused):
                self.gateway.enquire("original-ui-key", dict(self.context(), **change))
        self.assertEqual(len(self.enquiries), before)
        self.assertEqual(len(self.host.calls), 1)

    def test_changed_payload_is_not_resolved_or_persisted(self):
        with self.assertRaises(WorkbenchGatewayRefused):
            self.dispatch(payload={"legIndex": 2})
        self.assertEqual(self.bindings(), [])
        self.assertEqual(self.resolutions, [])
        self.assertEqual(self.enquiries, [])
        self.assertEqual(self.host.calls, [])

    def test_wrong_native_receipt_or_action_never_creates_a_binding_or_effect(self):
        for change in ({"receiptId": "different-receipt"}, {"action": "remint"}):
            self.scope = dict(self.host.scope, action="rollback", **change) if "action" not in change else dict(self.host.scope, **change)
            with self.subTest(change=change), self.assertRaises(WorkbenchGatewayRefused):
                self.dispatch()
        self.assertEqual(self.bindings(), [])
        self.assertEqual(self.host.calls, [])

    def test_original_bridge_still_refuses_asset_mismatch_and_keeps_unknown_claim(self):
        self.scope = dict(self.scope, contract="0x" + "f" * 40)
        with self.assertRaises(CheckpointedOperationRefused):
            self.dispatch()
        self.assertEqual(self.host.calls, [])
        self.assertEqual(self.host.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")
        self.assertEqual(self.gateway.enquire("original-ui-key", self.context()), {"status": "unknown"})

    def test_unavailable_original_enquiry_is_not_authenticated_absence(self):
        def unavailable(scope):
            raise OSError("synthetic original enquiry unavailable")
        gateway = self.make_gateway(self.host.bridge, enquiry=unavailable)
        with self.assertRaises(OSError):
            self.dispatch(gateway=gateway)
        self.assertEqual(self.bindings(), [("original-ui-key",)])
        self.assertIsNone(self.host.journal.lookup(self.scope["nativeOperationId"]))
        self.assertEqual(self.host.calls, [])
        self.assertEqual(self.dispatch(), {"status": "pending"})
        self.assertEqual(len(self.resolutions), 1)
        self.assertEqual(self.host.calls, [self.scope])

    def test_native_timeout_preserves_same_claim_and_query_returns_only_public_fields(self):
        def execute(scope):
            self.host.calls.append(deepcopy(scope))
            raise TimeoutError("synthetic native response lost")
        gateway = self.make_gateway(self.host.bridge, execute=execute)
        with self.assertRaises(WorkbenchOperationUnknown):
            self.dispatch(gateway=gateway)
        self.observation = {"status": "pending", "account": "private-actor", "scope": self.scope,
                            "transactionHash": "0x" + "1" * 64}
        result = self.reopened().enquire("original-ui-key", self.context())
        self.assertEqual(result, {"status": "pending", "transactionHash": "0x" + "1" * 64})
        self.assertEqual(len(self.host.calls), 1)

    def test_registration_is_forwarded_to_original_fallback_without_financial_mapping(self):
        calls = []
        class OriginalFallback:
            def enquire(self, key, context):
                calls.append(("enquire", key))
                return None
            def dispatch(self, action, payload, context):
                calls.append(("dispatch", action, payload))
                return {"status": "pending"}
        gateway = self.make_gateway(self.host.bridge, fallback=OriginalFallback())
        context = self.context(action="submit-registration", payload={"legIndex": 0})
        self.assertIsNone(gateway.enquire(context["journalKey"], context))
        self.assertEqual(self.dispatch(gateway=gateway, context=context, payload={"legIndex": 0}),
                         {"status": "pending"})
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.resolutions, [])
        self.assertEqual(self.bindings(), [])
        self.assertEqual(self.host.calls, [])

    def test_mapping_requires_original_durable_boundary_and_never_commits_foreign_transaction(self):
        self.host.claim_db.execute("PRAGMA synchronous=OFF")
        with self.assertRaises(DurableOperationRefused):
            self.dispatch()
        self.host.claim_db.execute("PRAGMA synchronous=FULL")
        self.host.claim_db.execute("BEGIN")
        try:
            with self.assertRaises(DurableOperationRefused):
                self.gateway.enquire("original-ui-key", self.context())
            self.assertTrue(self.host.claim_db.in_transaction)
        finally:
            self.host.claim_db.rollback()
        self.assertEqual(self.bindings(), [])
        self.assertEqual(self.host.calls, [])

    def test_stored_scope_corruption_is_not_hidden_as_a_native_outage(self):
        self.dispatch()
        self.host.claim_db.execute("UPDATE ex_workbench_command_bindings SET scope_digest=?", ("0" * 64,))
        self.host.claim_db.commit()
        before = len(self.enquiries)
        with self.assertRaises(WorkbenchGatewayRefused):
            self.gateway.enquire("original-ui-key", self.context())
        self.assertEqual(len(self.enquiries), before)


    def test_fresh_payment_enquiry_never_claims_persists_or_executes(self):
        self.scope = dict(self.host.scope, action="refund")
        payload = {"legIndex": 0}
        context = self.context(action="reconcile-payment", payload=payload)
        before = self.host.claim_db.total_changes
        for observation in (None, {"status": "pending"}, {"status": "refunded"}):
            self.observation = observation
            result = self.dispatch(context=context, payload=payload)
            self.assertEqual(result, {"status": "unknown"} if observation is None else observation)
        self.assertEqual(self.host.claim_db.total_changes, before)
        self.assertEqual(self.bindings(), [])
        self.assertIsNone(self.host.journal.lookup(self.scope["nativeOperationId"]))
        self.assertEqual(self.host.calls, [])

    def test_fresh_payment_enquiry_outage_never_falls_through_to_execution(self):
        self.scope = dict(self.host.scope, action="release")
        def unavailable(scope):
            raise OSError("synthetic enquiry unavailable")
        gateway = self.make_gateway(self.host.bridge, enquiry=unavailable)
        payload = {"legIndex": 0}
        with self.assertRaises(OSError):
            self.dispatch(gateway=gateway, context=self.context(action="reconcile-payment",
                          payload=payload), payload=payload)
        self.assertEqual(self.bindings(), [])
        self.assertEqual(self.host.calls, [])
        self.assertEqual(self.host.journal.revision("receipt-1"), 0)

    def post_original_handler(self, gateway):
        from exchange.workbench import WorkbenchHandler
        binding = self.host.access.bind_runtime("receipt-1", gateway=gateway)
        raw = urlencode({"csrf": "synthetic-csrf", "revision": binding.snapshot()["revision"],
                         "action": "advance-rollback", "key": "original-ui-key", "leg": ""}).encode()
        handler = object.__new__(WorkbenchHandler)
        handler.path = "/operation"
        handler.headers = Message()
        handler.headers["Origin"] = "http://127.0.0.1:18415"
        handler.headers["Content-Type"] = "application/x-www-form-urlencoded"
        handler.headers["Content-Length"] = str(len(raw))
        handler.rfile = BytesIO(raw)
        handler.server = SimpleNamespace(binding=binding, origin="http://127.0.0.1:18415",
                                         csrf="synthetic-csrf", command_observations=OrderedDict())
        handler.host_ok = lambda: True
        replies = []
        handler.send_body = lambda code, body, **kwargs: replies.append((code, body))
        handler.do_POST()
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0][0], 503)
        self.assertNotIn("private", replies[0][1])
        self.assertEqual(handler.server.command_observations, {})

    def test_original_http_handler_reports_native_uncertainty_without_replay(self):
        def execute(scope):
            self.host.calls.append(deepcopy(scope))
            raise TimeoutError("private synthetic provider timeout")
        self.post_original_handler(self.make_gateway(self.host.bridge, execute=execute))
        self.assertEqual(self.host.calls, [self.scope])
        self.assertEqual(self.host.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")
        self.assertEqual(self.dispatch(), {"status": "unknown"})
        self.assertEqual(self.host.calls, [self.scope])

    def test_original_http_handler_reports_claim_commit_uncertainty_without_execution(self):
        claim = self.host.journal.claim
        def lost_ack(scope, revision):
            claim(scope, revision)
            raise DurableOperationCommitUnknown("private synthetic claim commit timeout")
        with patch.object(self.host.journal, "claim", side_effect=lost_ack):
            self.post_original_handler(self.gateway)
        self.assertEqual(self.host.calls, [])
        self.assertEqual(self.host.journal.lookup(self.scope["nativeOperationId"])["status"], "UNKNOWN")
        self.assertEqual(self.dispatch(), {"status": "unknown"})
        self.assertEqual(self.host.calls, [])
