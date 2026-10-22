"""Synthetic approved-Linux HTTP definitions; no live receipt queries."""
from copy import deepcopy
import http.client
import json
import threading
import unittest
from exchange.gas_confirmation_ui import GasConfirmationPage
from exchange.workbench import RuntimeBinding
from exchange.remint_receipt_workbench import (
    WORDS, RemintReceiptViewBinding, RemintReceiptWorkbenchServer,
)
from integration.test_gas_budget import quote
import integration.test_registration_source_workbench as sources
import integration.test_remint_receipt_observation as receipts


class RemintReceiptWorkbenchContracts(unittest.TestCase):
    def setUp(self):
        self.fixture = receipts.RemintReceiptObservationContracts("runTest")
        self.fixture.setUp()
        self.raw = json.dumps(self.fixture.receipt).encode()
        self.read_calls, self.wallet_calls = [], []
        self.mode = "ok"
        def read():
            self.read_calls.append("read")
            if self.mode == "fail":
                raise RuntimeError("PRIVATE_READER_SENTINEL")
            return self.raw
        context = {"attempt_id":"fixture-attempt", "transaction_hash":receipts.TX,
                   "proof_reference":"private-original-proof", "contract":receipts.CONTRACT,
                   "operation_id":receipts.OP, "old_token_id":"2", "actor":receipts.ACTOR,
                   "replacement":deepcopy(receipts.REPLACEMENT)}
        self.context = context
        self.view = RemintReceiptViewBinding("receipt-1", self.fixture.observer, read, context)
        registration = sources.RegistrationSourceWorkbenchContracts("runTest")
        registration.setUp()
        def wallet(*args):
            self.wallet_calls.append(args)
            raise AssertionError("Receipt view cannot call wallet")
        gas = GasConfirmationPage(lambda: quote(), wallet, "fixture-buyer", "fixture-action",
            "fixture-grant", "/gas/confirm", lambda token: token == self.server.csrf)
        self.server = RemintReceiptWorkbenchServer(RuntimeBinding(None,"receipt-1"),
            remint_receipt=self.view, gas_page=gas, registration_sources=registration.workbench,
            current_time=lambda:110, commit="a"*40, tree="b"*40, port=0)
        self.worker = threading.Thread(target=self.server.serve_forever,
                                      kwargs={"poll_interval":0.02}, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.worker.join(3)
        self.server.server_close()

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method,path,body=body)
            response = connection.getresponse()
            return response.status,dict(response.getheaders()),response.read().decode()
        finally:
            connection.close()

    def test_six_locales_show_actual_new_id_and_exact_consumed_eth_without_private_fields(self):
        for locale, words in WORDS.items():
            status, headers, body = self.request("GET","/remint-result?lang="+locale)
            self.assertEqual(status,200)
            self.assertIn(words[4],body)
            self.assertIn("<code>2</code>",body)
            self.assertIn("<code>9</code>",body)
            self.assertIn("0.000000000000042000 ETH",body)
            self.assertEqual(headers["Cache-Control"],"no-store")
            self.assertIn("/remint-result?lang=ja",body)
            for private in (receipts.ACTOR,receipts.CONTRACT,"private-original-proof","fixture-"):
                self.assertNotIn(private,body)
            self.assertNotIn("<form",body)
        self.assertEqual(self.wallet_calls,[])

    def test_pending_failed_and_no_matching_event_have_distinct_localized_statuses(self):
        self.raw = b"null"
        body = self.request("GET","/remint-result?lang=ja")[2]
        self.assertIn(WORDS["ja"][1],body)
        self.assertNotIn("0.000000000000000000 ETH",body)
        failed = deepcopy(self.fixture.receipt)
        failed["status"] = "0x0"
        self.raw = json.dumps(failed).encode()
        body = self.request("GET","/remint-result?lang=fr")[2]
        self.assertIn(WORDS["fr"][2],body)
        self.assertIn("0.000000000000042000 ETH",body)
        no_event = deepcopy(self.fixture.receipt)
        no_event["logs"] = []
        self.raw = json.dumps(no_event).encode()
        self.assertIn(WORDS["es"][3],self.request("GET","/remint-result?lang=es")[2])

    def test_queries_cannot_select_transactions_operations_actors_or_receipts(self):
        for query in ("tx="+receipts.TX,"operation=other","receipt=other","actor=other",
                      "lang=en&lang=ja","lang=","lang=bad","reader=other"):
            self.assertEqual(self.request("GET","/remint-result?"+query)[0],400)
        self.assertEqual(self.read_calls,[])

    def test_post_refuses_without_receipt_read_or_any_dispatch(self):
        status,headers,_ = self.request("POST","/remint-result","action=retry")
        self.assertEqual(status,405)
        self.assertEqual(headers["Allow"],"GET")
        self.assertEqual(self.read_calls,[])
        self.assertEqual(self.wallet_calls,[])

    def test_reader_or_original_verifier_failure_hides_partial_and_private_data(self):
        for mode in ("reader","verifier"):
            self.mode = "fail" if mode == "reader" else "ok"
            self.fixture.verified = mode != "verifier"
            status,_,body = self.request("GET","/remint-result?lang=ja")
            self.assertEqual(status,503)
            self.assertIn(WORDS["ja"][5],body)
            self.assertNotIn("PRIVATE_READER_SENTINEL",body)
            self.assertNotIn(receipts.TX,body)

    def test_conflicting_native_event_is_unavailable_not_success_or_retry(self):
        self.fixture.events[3]["oldTokenId"] = "8"
        status,_,body = self.request("GET","/remint-result")
        self.assertEqual(status,503)
        self.assertNotIn(WORDS["en"][4],body)
        self.assertNotIn("<form",body)

    def test_missing_receipt_view_preserves_original_gas_and_review_routes(self):
        self.server.remint_receipt = None
        self.assertEqual(self.request("GET","/remint-result")[0],503)
        self.assertEqual(self.request("GET","/gas")[0],200)
        self.assertEqual(self.request("GET","/remint-review")[0],503)
        self.assertEqual(self.wallet_calls,[])

    def test_context_is_detached_and_observation_does_not_change_original_history(self):
        self.context["old_token_id"] = "7"
        before = deepcopy((self.fixture.receipt,self.fixture.events,receipts.REPLACEMENT))
        self.assertEqual(self.request("GET","/remint-result")[0],200)
        self.assertEqual((self.fixture.receipt,self.fixture.events,receipts.REPLACEMENT),before)
        self.assertEqual(self.wallet_calls,[])
