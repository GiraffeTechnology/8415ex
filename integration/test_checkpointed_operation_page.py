"""Synthetic HTTP enquiry of retained original operations; author NOT_RUN."""
import http.client
import threading
import unittest
from unittest.mock import patch

from exchange.checkpointed_operation_page import (
    CheckpointedOperationObservationBinding, mount_checkpointed_operation_observation, WORDS)
from exchange.remint_history import RemintHistoryStore
from exchange.remint_workbench import RemintWorkbenchServer
from integration import test_checkpointed_operation as original
from integration import test_serialized_workbench_composition as original_ui


class OriginalOperationObservationHTTPTests(unittest.TestCase):
    def setUp(self):
        self.host = original.CheckpointedOperationTests()
        self.host.setUp()
        self.addCleanup(self.host.doCleanups)
        self.ui = original_ui.SerializedWorkbenchCompositionTests("runTest")
        self.ui.setUp()
        self.addCleanup(self.ui.doCleanups)
        self.enquiries = []
        self.native = {"status": "unknown", "private": "PRIVATE_NATIVE_DETAILS"}
        self.fail = False
        self.server = self.make_server()

    def make_server(self):
        server = RemintWorkbenchServer(
            self.host.access.bind_runtime(self.host.scope["receiptId"]),
            gas_page=self.ui.gas, registration_sources=self.ui.server.registration_sources,
            current_time=lambda: 110, commit="c" * 40, tree="d" * 40, port=0)
        self.addCleanup(server.server_close)
        return server

    def enquire(self, scope):
        self.enquiries.append(scope)
        if self.fail:
            raise TimeoutError("PRIVATE_NATIVE_ERROR")
        return self.native

    def mount(self, **options):
        self.view = CheckpointedOperationObservationBinding(self.host.bridge,
            self.host.scope, self.enquire, **options)
        mount_checkpointed_operation_observation(self.server, self.view)

    def request(self, path, method="GET", body=None, **headers):
        response, errors = [], []
        def client():
            connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
            try:
                connection.request(method, path, body=body, headers=headers)
                result = connection.getresponse()
                response.append((result.status, result.read().decode()))
            except BaseException as error:
                errors.append(error)
            finally:
                connection.close()
        worker = threading.Thread(target=client, daemon=True)
        worker.start()
        self.server.timeout = 3
        self.server.handle_request()
        worker.join(4)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        return response[0]

    def test_six_locale_reads_query_same_scope_without_writes_or_private_values(self):
        self.mount()
        before = (self.host.claim_db.total_changes, self.host.snapshot_db.total_changes)
        for locale, words in WORDS.items():
            status, body = self.request("/operation-observation?lang=" + locale)
            self.assertEqual(status, 200)
            self.assertIn(words["absent"], body)
            self.assertIn(words["unknown"], body)
            for private in (self.host.scope["contract"], self.host.scope["nativeOperationId"],
                            self.host.scope["journalReference"], self.host.scope["intentDigest"],
                            "PRIVATE_NATIVE_DETAILS"):
                self.assertNotIn(private, body)
        self.assertEqual(self.enquiries, [self.host.scope] * 6)
        self.assertEqual(self.host.calls, [])
        self.assertEqual(before, (self.host.claim_db.total_changes, self.host.snapshot_db.total_changes))

    def test_old_unknown_enquiry_survives_unavailable_preimage_history_and_new_live_schema(self):
        self.host.invoke()
        RemintHistoryStore.initialize(self.host.claim_db)
        class UnavailableHistory(RemintHistoryStore):
            def read(self, scope):
                raise ValueError("PRIVATE_HISTORY_ERROR")
        self.mount(remint_history=UnavailableHistory(self.host.claim_db))
        self.host.exchange.future_unhandled_domain = "current declaration no longer available"
        before = (self.host.claim_db.total_changes, self.host.snapshot_db.total_changes)
        with patch.object(self.host.checkpoint, "read", side_effect=ValueError("PRIVATE_DB_ERROR")):
            status, body = self.request("/operation-observation")
        self.assertEqual(status, 200)
        self.assertIn(WORDS["en"]["unknown"], body)
        self.assertIn(WORDS["en"]["unavailable"], body)
        self.assertNotIn("PRIVATE_", body)
        self.assertEqual(self.enquiries, [self.host.scope])
        self.assertEqual(len(self.host.calls), 1)
        self.assertEqual(before, (self.host.claim_db.total_changes, self.host.snapshot_db.total_changes))
        self.assertEqual(self.host.journal.lookup(self.host.scope["nativeOperationId"])["status"], "UNKNOWN")

    def test_native_failure_is_unavailable_without_raw_error_or_new_effect_and_market_survives(self):
        self.mount()
        self.fail = True
        status, body = self.request("/operation-observation?lang=ja")
        self.assertEqual(status, 503)
        self.assertIn(WORDS["ja"]["unavailable"], body)
        self.assertNotIn("PRIVATE_NATIVE_ERROR", body)
        self.assertEqual(self.request("/market")[0], 200)
        self.assertIsNone(self.host.journal.lookup(self.host.scope["nativeOperationId"]))
        self.assertEqual(self.host.calls, [])

    def test_post_or_http_selected_operation_is_refused_before_enquiry(self):
        self.mount()
        self.assertEqual(self.request("/operation-observation", "POST", "nativeOperationId=other")[0], 405)
        for suffix in ("?nativeOperationId=other", "?lang=en&lang=fr", "?lang=xx"):
            self.assertEqual(self.request("/operation-observation" + suffix)[0], 400)
        self.assertEqual(self.request("/operation-observation", Host="other.invalid")[0], 421)
        self.assertEqual(self.enquiries, [])
        self.assertEqual(self.host.calls, [])

    def test_absent_configuration_is_route_local_and_same_binding_mount_is_idempotent(self):
        mount_checkpointed_operation_observation(self.server)
        handler = self.server.RequestHandlerClass
        mount_checkpointed_operation_observation(self.server)
        self.assertIs(self.server.RequestHandlerClass, handler)
        self.assertEqual(self.request("/operation-observation")[0], 503)
        self.assertEqual(self.request("/market")[0], 200)
        self.assertEqual(self.enquiries, [])
        other = self.make_server()
        view = CheckpointedOperationObservationBinding(self.host.bridge, self.host.scope, self.enquire)
        mount_checkpointed_operation_observation(other, view)
        handler = other.RequestHandlerClass
        mount_checkpointed_operation_observation(other, view)
        self.assertIs(other.RequestHandlerClass, handler)
        with self.assertRaises(ValueError):
            mount_checkpointed_operation_observation(other)

    def test_stored_scope_conflict_never_reaches_original_native_enquiry(self):
        self.host.journal.claim(self.host.scope, 0)
        scope = dict(self.host.scope, tokenId="999")
        view = CheckpointedOperationObservationBinding(self.host.bridge, scope, self.enquire)
        mount_checkpointed_operation_observation(self.server, view)
        self.assertEqual(self.request("/operation-observation")[0], 503)
        self.assertEqual(self.enquiries, [])
        self.assertEqual(self.host.calls, [])
        self.assertEqual(self.host.journal.lookup(self.host.scope["nativeOperationId"])["status"], "UNKNOWN")

    def test_local_reconciliation_and_empty_native_reply_remain_separate_observations(self):
        self.host.journal.claim(self.host.scope, 0)
        self.host.journal.reconcile(self.host.scope, "applied", "original-proof",
                                    lambda *args: True)
        self.mount()
        self.native = None
        status, body = self.request("/operation-observation")
        self.assertEqual(status, 200)
        self.assertIn(WORDS["en"]["reconciled"], body)
        self.assertIn(WORDS["en"]["noRecord"], body)
        self.assertNotIn("original-proof", body)
        self.assertEqual(self.host.calls, [])
