"""Synthetic host wiring definitions; no installed provider or chain execution."""
from dataclasses import replace
import http.client
import threading
import unittest

from exchange.ledger import Exchange
from exchange.gas_confirmation_ui import GasConfirmationPage
from exchange.serialized_exchange_access import SerializedExchangeAccess
from exchange.serialized_workbench_composition import compose_serialized_workbench
from exchange.remint_review import RemintReviewBinding
from integration.test_mint_specification_codec import specification
from integration.test_gas_budget import quote
from integration.test_remint_review_workbench import public_detail
from integration import test_registration_source_workbench as original_sources


class SerializedWorkbenchCompositionTests(unittest.TestCase):
    def setUp(self):
        self.exchange = Exchange(lambda: 20, mint_verifier=lambda kind, evidence: True)
        first = specification()
        second = replace(first, receipt=replace(first.receipt, receipt_id="receipt-2",
            receipt_number="warehouse-2", asset=replace(first.receipt.asset, token_id=8)), bill_of_lading_number="bill-2",
            original_document_mapping="document-map-2", controlled_access_mapping="controlled-map-2")
        self.exchange.mint(first.receipt, first)
        self.exchange.mint(second.receipt, second)
        self.access = SerializedExchangeAccess(self.exchange)
        sources = original_sources.RegistrationSourceWorkbenchContracts("runTest")
        sources.setUp()
        self.calls = []
        def wallet(*args):
            self.calls.append(args)
            raise AssertionError("read-only test must not invoke wallet")
        self.gas = GasConfirmationPage(lambda: quote(), wallet, "fixture-buyer",
            "fixture-action", "fixture-grant", "/gas/confirm", lambda token: token == self.server.csrf)
        self.review = RemintReviewBinding("receipt-1", "receipt-2", lambda old, new:
            (public_detail(old, "Original terms"), public_detail(new, "Replacement terms")))
        self.server = compose_serialized_workbench(self.access, "receipt-1",
            gas_page=self.gas, registration_sources=sources.workbench,
            current_time=lambda: 110, commit="a" * 40, tree="b" * 40,
            detail_receipts=(("receipt-2", {}),), remint_review=self.review, port=0)
        self.addCleanup(self.server.server_close)

    def request(self, path):
        worker = threading.Thread(target=self.server.serve_forever,
            kwargs={"poll_interval": 0.02}, daemon=True)
        worker.start()
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            return response.status, response.read().decode()
        finally:
            connection.close()
            self.server.shutdown()
            worker.join(3)

    def test_primary_and_every_directory_binding_use_same_existing_access(self):
        self.assertIs(self.server.binding.exchange, self.access)
        for binding in self.server.nft_directory._bindings.values():
            self.assertIs(binding.exchange, self.access)
            self.assertEqual(binding.run, self.server.binding.run)
            self.assertEqual(binding.snapshot()["source"], self.server.binding.snapshot()["source"])

    def test_constructing_server_does_not_dispatch_or_start_serving(self):
        self.assertEqual(self.calls, [])
        self.assertIs(self.server.gas_page, self.gas)
        self.assertIsNot(self.server.remint_review, self.review)
        self.assertEqual(self.server.server_address[0], "127.0.0.1")

    def test_original_gas_route_survives_composition_without_wallet_call(self):
        status, body = self.request("/gas")
        self.assertEqual(status, 200)
        self.assertIn("<form", body)
        self.assertEqual(self.calls, [])

    def test_original_six_language_remint_route_uses_bound_pair(self):
        for locale in ("en", "zh-Hans", "zh-Hant", "fr", "es", "ja"):
            with self.subTest(locale=locale):
                body = self.server.remint_review.render(locale)
                self.assertIn("Original terms", body)
                self.assertIn("Replacement terms", body)
        status, body = self.request("/remint-review?lang=en")
        self.assertEqual(status, 200)
        self.assertIn("Original terms", body)
        self.assertNotIn("<form", body)

    def test_paired_review_observation_holds_same_lock_against_writer(self):
        entered, release, writer_started, writer_done = (threading.Event() for _ in range(4))
        failures = []
        original_reader = self.review.read_original_pair
        def read_pair(old_id, new_id):
            entered.set()
            if not release.wait(2):
                raise RuntimeError("synthetic blocked read")
            return original_reader(old_id, new_id)
        # Install only the synthetic original reader before constructing another
        # server; the factory detaches the paired projection inside its lock.
        self.review.read_original_pair = read_pair
        other = compose_serialized_workbench(self.access, "receipt-1", gas_page=self.gas,
            registration_sources=self.server.registration_sources, current_time=lambda: 110,
            commit="a" * 40, tree="b" * 40, remint_review=self.review, port=0)
        self.addCleanup(other.server_close)
        def observe():
            try: other.remint_review.render("en")
            except Exception as error: failures.append(error)
        def write():
            writer_started.set()
            try:
                self.access.connect_wallet("0x" + "3" * 40, "fixture-session")
                writer_done.set()
            except Exception as error: failures.append(error)
        observer, writer = threading.Thread(target=observe), threading.Thread(target=write)
        observer.start()
        try:
            self.assertTrue(entered.wait(1))
            writer.start()
            self.assertTrue(writer_started.wait(1))
            self.assertFalse(writer_done.wait(0.05))
        finally:
            release.set()
            observer.join(3)
            if writer.ident is not None: writer.join(3)
        self.assertEqual(failures, [])
        self.assertTrue(writer_done.is_set())

    def test_original_unknown_command_is_enquired_without_dispatch(self):
        class Gateway:
            enquiries = 0
            def enquire(inner, key, context):
                inner.enquiries += 1
                return {"status": "unknown"}
            def dispatch(inner, *args):
                raise AssertionError("original UNKNOWN must not replay")
        gateway = Gateway()
        other = compose_serialized_workbench(self.access, "receipt-1", gas_page=self.gas,
            registration_sources=self.server.registration_sources, current_time=lambda: 110,
            commit="a" * 40, tree="b" * 40, runtime_options={"gateway": gateway}, port=0)
        self.addCleanup(other.server_close)
        result = other.binding.command("resume-payment", "original-key",
            other.binding.snapshot()["revision"], {})
        self.assertTrue(result["enquired"])
        self.assertEqual(gateway.enquiries, 1)
