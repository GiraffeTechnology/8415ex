"""Real loopback HTTP component tests with explicit fixture wallet/journal.

These are not installed-session, financial, Oracle or chain acceptance.
The validation owner executes them on the exact candidate.
"""
import http.client
import threading
import unittest
from dataclasses import replace
from urllib.parse import urlencode

from exchange.gas_budget import BuyerConfirmation
from exchange.gas_confirmation_ui import GasConfirmationPage
from exchange.integrated_workbench import IntegratedWorkbenchServer
from exchange.workbench import RuntimeBinding
from integration.test_gas_budget import quote
from integration.test_registration_source_workbench import (
    RegistrationSourceWorkbenchContracts,
)


COMMIT = "7b452b5fa7f3fbcf485fc9fa578ca5e9b94855b7"
TREE = "7d9e2b5f100d7de14c94d0472bb091b966ed7eac"


class IntegratedWorkbenchHTTPTests(unittest.TestCase):
    def setUp(self):
        self.current_quote = quote()
        self.wallet_calls = []
        self.mode = "confirmed"

        def fixture_wallet(q, buyer, action, grant, now):
            self.wallet_calls.append((q.digest, buyer, action, grant))
            if self.mode == "unknown":
                raise TimeoutError("fixture acknowledgement unknown")
            return BuyerConfirmation(q.digest, buyer, action, grant, now,
                                     "fixture-confirmation-only")

        # Reuse existing source-controller fixture setup without inheriting
        # its tests or claiming an installed native journal.
        self.sources = RegistrationSourceWorkbenchContracts("runTest")
        self.sources.setUp()
        page = GasConfirmationPage(
            lambda: self.current_quote, fixture_wallet, "fixture-buyer",
            "fixture-action", "fixture-grant", "/gas/confirm",
            lambda token: token == self.server.csrf)
        binding = RuntimeBinding(None, "receipt-1")
        self.server = IntegratedWorkbenchServer(
            binding, gas_page=page, registration_sources=self.sources.workbench,
            current_time=lambda: 110, commit=COMMIT, tree=TREE, port=0)
        self.worker = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": 0.02}, daemon=True)
        self.worker.start()

    def tearDown(self):
        self.server.shutdown()
        self.worker.join(timeout=3)
        self.server.server_close()

    def fields(self):
        return {"csrf": self.server.csrf, "quoteId": self.current_quote.quote_id,
                "version": str(self.current_quote.version),
                "quoteDigest": self.current_quote.digest, "accepted": "yes"}

    def request(self, method, path, body=None, origin=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            headers = {}
            if method == "POST":
                headers = {"Content-Type": "application/x-www-form-urlencoded",
                           "Origin": self.server.origin if origin is None else origin}
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read().decode()
        finally:
            connection.close()

    def test_get_renders_existing_quote_without_wallet_effect(self):
        status, headers, body = self.request("GET", "/gas")
        self.assertEqual(status, 200)
        self.assertIn(self.current_quote.digest, body)
        self.assertIn(self.server.csrf, body)
        self.assertIn("Statistical median (P50)", body)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(self.wallet_calls, [])

    def test_confirmation_uses_controller_bindings_and_returns_no_proof(self):
        status, headers, body = self.request(
            "POST", "/gas/confirm", urlencode(self.fields()))
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/gas")
        self.assertEqual(body, "")
        self.assertEqual(self.wallet_calls, [
            (self.current_quote.digest, "fixture-buyer", "fixture-action", "fixture-grant")])

    def test_invalid_csrf_and_wrong_origin_do_not_call_wallet(self):
        fields = dict(self.fields(), csrf="other-session")
        self.assertEqual(self.request("POST", "/gas/confirm", urlencode(fields))[0], 400)
        self.assertEqual(self.request("POST", "/gas/confirm", urlencode(self.fields()),
                                      origin="https://foreign.example")[0], 403)
        self.assertEqual(self.wallet_calls, [])

    def test_changed_quote_requires_refresh_before_wallet_call(self):
        fields = self.fields()
        self.current_quote = replace(self.current_quote, version=2)
        self.assertEqual(self.request("POST", "/gas/confirm", urlencode(fields))[0], 400)
        self.assertEqual(self.wallet_calls, [])

    def test_extra_duplicate_and_edited_form_fields_are_refused(self):
        bodies = [urlencode(dict(self.fields(), buyer="untrusted")),
                  urlencode(self.fields()) + "&accepted=yes",
                  urlencode(dict(self.fields(), accepted="no"))]
        for body in bodies:
            with self.subTest(body=body):
                self.assertEqual(self.request("POST", "/gas/confirm", body)[0], 400)
        self.assertEqual(self.wallet_calls, [])

    def test_duplicate_content_length_refused_before_wallet_call(self):
        body = urlencode(self.fields()).encode()
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.putrequest("POST", "/gas/confirm")
            connection.putheader("Origin", self.server.origin)
            connection.putheader("Content-Type", "application/x-www-form-urlencoded")
            connection.putheader("Content-Length", str(len(body)))
            connection.putheader("Content-Length", str(len(body)))
            connection.endheaders(body)
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            response.read()
        finally:
            connection.close()
        self.assertEqual(self.wallet_calls, [])

    def test_unknown_confirmation_has_no_automatic_retry(self):
        self.mode = "unknown"
        status, _, body = self.request("POST", "/gas/confirm", urlencode(self.fields()))
        self.assertEqual(status, 408)
        self.assertIn("enquire original wallet before retry", body)
        self.assertEqual(len(self.wallet_calls), 1)

    def test_three_source_views_use_one_original_fixture_reader(self):
        status, _, choices = self.request("GET", "/registration-source")
        self.assertEqual(status, 200)
        self.assertEqual(self.sources.calls, [])
        for source in ("REG-DIRECT", "REG-ELECTRONIC", "REG-INTERMEDIARY"):
            self.assertIn(source, choices)
            query = urlencode({"receipt": "receipt-1", "source": source})
            status, _, body = self.request("GET", "/registration-source?" + query)
            self.assertEqual(status, 200)
            self.assertIn(source, body)
            self.assertIn("NOT_VERIFIED", body)
            self.assertIn("UNBOUND", body)
        self.assertEqual(len(self.sources.calls), 3)
        self.assertEqual(self.wallet_calls, [])

    def test_other_receipt_and_duplicate_source_refused_before_reader(self):
        paths = [
            "/registration-source?receipt=other&source=REG-DIRECT",
            "/registration-source?receipt=receipt-1&source=REG-DIRECT&source=REG-DIRECT",
        ]
        for path in paths:
            self.assertEqual(self.request("GET", path)[0], 400)
        self.assertEqual(self.sources.calls, [])

    def test_query_is_not_accepted_on_confirmation_route(self):
        self.assertEqual(self.request("GET", "/gas?buyer=other")[0], 400)
        self.assertEqual(self.request("POST", "/gas/confirm?ignored=1",
                                      urlencode(self.fields()))[0], 403)
        self.assertEqual(self.wallet_calls, [])


if __name__ == "__main__":
    unittest.main()
