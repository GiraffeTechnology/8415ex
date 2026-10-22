"""Approved-Linux definitions for one integrated original remint workbench."""
from copy import deepcopy
import http.client
import json
import threading
import unittest
from exchange.gas_confirmation_ui import GasConfirmationPage
from exchange.remint_history_workbench import RemintChainHistoryBinding, WORDS as HISTORY_WORDS
from exchange.remint_receipt_workbench import RemintReceiptViewBinding, WORDS as RECEIPT_WORDS
from exchange.remint_review import RemintReviewBinding
from exchange.remint_workbench import RemintWorkbenchServer
from exchange.workbench import RuntimeBinding
from integration.test_gas_budget import quote
import integration.test_registration_source_workbench as sources
import integration.test_remint_receipt_observation as receipts
import integration.test_remint_review_workbench as review_fixtures


def word(value):
    return value.to_bytes(32,"big")


class RemintWorkbenchCompositionContracts(unittest.TestCase):
    def setUp(self):
        self.history_calls, self.receipt_calls, self.wallet_calls = [], [], []
        self.history_failure, self.receipt_failure = False, False
        self.fixture = receipts.RemintReceiptObservationContracts("runTest")
        self.fixture.setUp()
        def history(scope):
            self.history_calls.append(deepcopy(scope))
            if self.history_failure:
                raise RuntimeError("PRIVATE_HISTORY_SENTINEL")
            token = scope["tokenId"]
            before, after = {"1":(0,2),"2":(1,9),"9":(2,0)}[token]
            declared = (word(32)+bytes.fromhex(receipts.REPLACEMENT["billKey"][2:])
                        + word(2)+word(3)+word(128)+word(1)+word(4))
            if token == "9":
                declared = (word(32)+bytes.fromhex(receipts.REPLACEMENT["billKey"][2:])
                    + bytes.fromhex(receipts.REPLACEMENT["termsHash"][2:])
                    + bytes.fromhex(receipts.REPLACEMENT["currencyDeclarationHash"][2:])
                    + word(128)+word(1)+bytes.fromhex(receipts.REPLACEMENT["allowedCurrencies"][0][2:]))
            return {"scope":deepcopy(scope),
                "observedBlock":{"number":32,"hash":receipts.BLOCK,"timestamp":1800},
                "declaration":declared, "predecessor":word(before), "successor":word(after),
                "active":word(9), "predecessorReverse":word(int(token)) if before else None,
                "successorReverse":word(int(token)) if after else None}
        self.history = RemintChainHistoryBinding("receipt-1",receipts.CONTRACT,
            receipts.REPLACEMENT["billKey"],"2",history)
        def raw_receipt():
            self.receipt_calls.append("read")
            if self.receipt_failure:
                raise RuntimeError("PRIVATE_RECEIPT_SENTINEL")
            return json.dumps(self.fixture.receipt).encode()
        context = {"attempt_id":"fixture-attempt","transaction_hash":receipts.TX,
            "proof_reference":"private-original-proof","contract":receipts.CONTRACT,
            "operation_id":receipts.OP,"old_token_id":"2","actor":receipts.ACTOR,
            "replacement":deepcopy(receipts.REPLACEMENT)}
        self.receipt = RemintReceiptViewBinding("receipt-1",self.fixture.observer,
                                               raw_receipt,context)
        self.review = RemintReviewBinding("receipt-1","receipt-2",lambda old,new:(
            review_fixtures.public_detail(old,"Original business clause."),
            review_fixtures.public_detail(new,"Replacement business clause.")))
        registration = sources.RegistrationSourceWorkbenchContracts("runTest")
        registration.setUp()
        def wallet(*args):
            self.wallet_calls.append(args)
            raise AssertionError("Views cannot dispatch a wallet operation")
        gas = GasConfirmationPage(lambda:quote(),wallet,"fixture-buyer","fixture-action",
            "fixture-grant","/gas/confirm",lambda token:token==self.server.csrf)
        self.options = {"gas_page":gas,"registration_sources":registration.workbench,
            "current_time":lambda:110,"commit":"a"*40,"tree":"b"*40,"port":0}
        self.runtime = RuntimeBinding(None,"receipt-1")
        self.server = RemintWorkbenchServer(self.runtime,remint_history=self.history,
            remint_receipt=self.receipt,remint_review=self.review,**self.options)
        self.worker = threading.Thread(target=self.server.serve_forever,
                                      kwargs={"poll_interval":0.02},daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.worker.join(3)
        self.server.server_close()

    def request(self,method,path,body=None):
        connection = http.client.HTTPConnection(*self.server.server_address,timeout=3)
        try:
            connection.request(method,path,body=body)
            response=connection.getresponse()
            return response.status,dict(response.getheaders()),response.read().decode()
        finally:
            connection.close()

    def test_six_locales_share_navigation_without_losing_selected_history_token(self):
        for locale in HISTORY_WORDS:
            for path in ("/remint-history?token=9&lang=","/remint-result?lang="):
                status,headers,body=self.request("GET",path+locale)
                self.assertEqual(status,200)
                self.assertIn(HISTORY_WORDS[locale][0],body)
                self.assertIn(RECEIPT_WORDS[locale][0],body)
                self.assertIn("/remint-review?lang="+locale,body)
                self.assertEqual(headers["Cache-Control"],"no-store")
                self.assertNotIn(receipts.CONTRACT,body)
                self.assertNotIn(receipts.ACTOR,body)
                self.assertNotIn("<form",body)
            body=self.request("GET","/remint-history?token=9&lang="+locale)[2]
            self.assertIn("lang=ja&amp;token=9",body)

    def test_each_route_invokes_only_its_own_original_reader(self):
        self.assertEqual(self.request("GET","/remint-history")[0],200)
        self.assertEqual(len(self.history_calls),1)
        self.assertEqual(self.receipt_calls,[])
        self.assertEqual(self.request("GET","/remint-result")[0],200)
        self.assertEqual(len(self.history_calls),1)
        self.assertEqual(len(self.receipt_calls),1)
        self.assertEqual(self.wallet_calls,[])

    def test_either_optional_reader_can_be_absent_without_blocking_the_other(self):
        self.server.remint_history=None
        self.assertEqual(self.request("GET","/remint-history")[0],503)
        self.assertEqual(self.request("GET","/remint-result")[0],200)
        self.server.remint_history=self.history
        self.server.remint_receipt=None
        self.assertEqual(self.request("GET","/remint-history")[0],200)
        self.assertEqual(self.request("GET","/remint-result")[0],503)

    def test_reader_failures_stay_local_and_never_leak_private_errors(self):
        self.history_failure=True
        status,_,body=self.request("GET","/remint-history")
        self.assertEqual(status,503)
        self.assertNotIn("PRIVATE_HISTORY_SENTINEL",body)
        self.assertEqual(self.request("GET","/remint-result")[0],200)
        self.history_failure=False
        self.receipt_failure=True
        status,_,body=self.request("GET","/remint-result")
        self.assertEqual(status,503)
        self.assertNotIn("PRIVATE_RECEIPT_SENTINEL",body)
        self.assertEqual(self.request("GET","/remint-history")[0],200)

    def test_both_post_paths_refuse_before_reading_or_dispatching(self):
        for path in ("/remint-history","/remint-result"):
            status,headers,_=self.request("POST",path,"action=retry")
            self.assertEqual(status,405)
            self.assertEqual(headers["Allow"],"GET")
        self.assertEqual(self.history_calls,[])
        self.assertEqual(self.receipt_calls,[])
        self.assertEqual(self.wallet_calls,[])

    def test_original_gas_and_complete_terms_review_remain_on_same_server(self):
        self.assertEqual(self.request("GET","/gas")[0],200)
        status,_,body=self.request("GET","/remint-review")
        self.assertEqual(status,200)
        self.assertIn("Original business clause.",body)
        self.assertIn("Replacement business clause.",body)
        self.assertIn("/remint-result?lang=en",body)
        self.assertIn("/remint-history?lang=en",body)
        self.assertEqual(self.history_calls,[])
        self.assertEqual(self.receipt_calls,[])

    def test_cross_contract_or_bill_view_pair_is_refused_without_source_queries(self):
        for key,value in (("contract","0x"+"7"*40),("bill","0x"+"8"*64)):
            other=RemintChainHistoryBinding("receipt-1",
                value if key=="contract" else receipts.CONTRACT,
                value if key=="bill" else receipts.REPLACEMENT["billKey"],"2",lambda scope:None)
            with self.assertRaises(ValueError):
                RemintWorkbenchServer(self.runtime,remint_history=other,
                    remint_receipt=self.receipt,**self.options)
        self.assertEqual(self.history_calls,[])
        self.assertEqual(self.receipt_calls,[])

    def test_route_query_contracts_remain_independent_without_new_selection_controls(self):
        for path in ("/remint-history?transaction=other","/remint-result?token=9",
                     "/remint-result?lang=en&token=2","/remint-history?contract=other"):
            self.assertEqual(self.request("GET",path)[0],400)
        self.assertEqual(self.history_calls,[])
        self.assertEqual(self.receipt_calls,[])
