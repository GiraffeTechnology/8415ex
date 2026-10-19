"""Real loopback definitions for identity-excluding read-only comparison."""
from copy import deepcopy
import http.client
import threading
import unittest

from exchange.gas_confirmation_ui import GasConfirmationPage
from exchange.workbench import RuntimeBinding
from exchange.remint_review import RemintReviewBinding, WORDS
from exchange.remint_review_workbench import RemintReviewWorkbenchServer
from integration.test_gas_budget import quote
import integration.test_registration_source_workbench as source_fixtures


def public_detail(receipt_id, text):
    return {"schema": "8415ex-public-nft-detail/1", "receiptId": receipt_id,
            "sourceStatus": "verified-original-reader",
            "terms": {"status": "provided-verified-projection",
                      "clauses": [{"label": "Fixture bill terms", "text": text}]}}


class RemintReviewWorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.pair = (public_detail("receipt-1", "Original fixture business clause."),
                     public_detail("receipt-2", "Proposed fixture business clause."))
        self.read_calls, self.wallet_calls = [], []
        self.mode = "ok"
        def read_pair(old_id, new_id):
            self.read_calls.append((old_id, new_id))
            if self.mode == "unavailable":
                raise RuntimeError("private diagnostic must never be served")
            return deepcopy(self.pair)
        self.review = RemintReviewBinding("receipt-1", "receipt-2", read_pair)
        sources = source_fixtures.RegistrationSourceWorkbenchContracts("runTest")
        sources.setUp()
        def wallet(*args):
            self.wallet_calls.append(args)
            raise AssertionError("read-only route must not call wallet")
        page = GasConfirmationPage(lambda: quote(), wallet, "fixture-buyer", "fixture-action",
                                   "fixture-grant", "/gas/confirm", lambda token: token == self.server.csrf)
        self.server = RemintReviewWorkbenchServer(RuntimeBinding(None, "receipt-1"),
            remint_review=self.review, gas_page=page, registration_sources=sources.workbench,
            current_time=lambda: 110, commit="a" * 40, tree="b" * 40, port=0)
        self.worker = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.02}, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.worker.join(3)
        self.server.server_close()

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method, path, body=body)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode()
        finally:
            connection.close()

    def test_all_six_locales_render_complete_before_and_after_without_effects(self):
        for locale, words in WORDS.items():
            with self.subTest(locale=locale):
                status, headers, body = self.request("GET", "/remint-review?lang=" + locale)
                self.assertEqual(status, 200)
                self.assertIn(words[0], body)
                self.assertIn("Original fixture business clause.", body)
                self.assertIn("Proposed fixture business clause.", body)
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertNotIn("<form", body)
        self.assertEqual(self.wallet_calls, [])

    def test_reader_gets_only_original_bound_versions(self):
        self.request("GET", "/remint-review")
        self.assertEqual(self.read_calls, [("receipt-1", "receipt-2")])
        for path in ("/remint-review?receipt=other", "/remint-review?lang=en&lang=ja",
                     "/remint-review?lang=unsupported", "/remint-review?lang="):
            self.assertEqual(self.request("GET", path)[0], 400)
        self.assertEqual(len(self.read_calls), 1)

    def test_business_clause_html_is_escaped_without_rewriting_text(self):
        self.pair[1]["terms"]["clauses"][0]["text"] = '<script>alert("fixture")</script>'
        status, _, body = self.request("GET", "/remint-review")
        self.assertEqual(status, 200)
        self.assertIn("&lt;script&gt;", body)
        self.assertNotIn('<script>alert("fixture")', body)

    def test_same_bill_receipt_identity_is_not_an_extra_remint_gate(self):
        pair = deepcopy(self.pair)
        pair[1]["receiptId"] = "receipt-1"
        bound = RemintReviewBinding("receipt-1", "receipt-1", lambda old, proposed: pair)
        body = bound.render("en")
        self.assertIn("Original fixture business clause.", body)
        self.assertIn("Proposed fixture business clause.", body)

    def test_identity_or_unexpected_clause_fields_refuse_entire_pair(self):
        for change in ("address", "field"):
            original = deepcopy(self.pair)
            if change == "address": self.pair[1]["terms"]["clauses"][0]["text"] = "0x" + "1" * 40
            else: self.pair[1]["terms"]["clauses"][0]["privateReference"] = "private-fixture"
            status, _, body = self.request("GET", "/remint-review")
            self.assertEqual(status, 503)
            self.assertNotIn("0x" + "1" * 40, body)
            self.assertNotIn("private-fixture", body)
            self.pair = original

    def test_missing_original_verification_or_wrong_version_binding_is_unavailable(self):
        for change in ("source", "receipt", "terms"):
            original = deepcopy(self.pair)
            if change == "source": self.pair[1]["sourceStatus"] = "not-verified"
            if change == "receipt": self.pair[1]["receiptId"] = "wrong-version"
            if change == "terms": self.pair[1]["terms"]["status"] = "unavailable"
            self.assertEqual(self.request("GET", "/remint-review")[0], 503)
            self.pair = original

    def test_reader_failure_is_localized_without_private_error_or_partial_terms(self):
        self.mode = "unavailable"
        status, _, body = self.request("GET", "/remint-review?lang=ja")
        self.assertEqual(status, 503)
        self.assertIn(WORDS["ja"][5], body)
        self.assertNotIn("private diagnostic", body)
        self.assertNotIn("Original fixture business clause.", body)

    def test_post_is_refused_without_reading_or_dispatching_remint_input(self):
        status, headers, _ = self.request("POST", "/remint-review", "action=remint&receipt=other")
        self.assertEqual(status, 405)
        self.assertEqual(headers["Allow"], "GET")
        self.assertEqual(self.read_calls, [])
        self.assertEqual(self.wallet_calls, [])

    def test_missing_review_does_not_disable_existing_gas_route(self):
        self.server.remint_review = None
        self.assertEqual(self.request("GET", "/remint-review")[0], 503)
        status, _, body = self.request("GET", "/gas")
        self.assertEqual(status, 200)
        self.assertIn("Statistical median (P50)", body)
        self.assertEqual(self.wallet_calls, [])
