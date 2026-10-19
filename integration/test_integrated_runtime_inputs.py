"""Approved-server HTTP definitions with synthetic source/controller bindings.

No live feed, Wallet session, Oracle or financial acceptance is asserted.
"""
import json
import threading
import unittest
from urllib.request import urlopen

from exchange.gas_confirmation_ui import GasConfirmationPage
from exchange.integrated_workbench import IntegratedWorkbenchServer
from exchange.workbench import RuntimeBinding
from integration.test_gas_budget import quote
from integration.test_integrated_workbench_http import COMMIT, TREE
from integration.test_nft_detail import OriginalReadOnlyDomain
from integration import test_reference_feed as reference_fixtures
from integration import test_registration_source_workbench as source_fixtures


class IntegratedRuntimeInputsTests(unittest.TestCase):
    def server(self, **inputs):
        sources = source_fixtures.RegistrationSourceWorkbenchContracts("runTest")
        sources.setUp()
        self.wallet_calls = []
        def wallet(*args):
            self.wallet_calls.append(args)
            raise AssertionError("read-only routes must not confirm gas")
        gas = GasConfirmationPage(lambda: quote(), wallet, "fixture-buyer",
            "fixture-action", "fixture-grant", "/gas/confirm", lambda token: False)
        server = IntegratedWorkbenchServer(
            RuntimeBinding(OriginalReadOnlyDomain(), "receipt-1"), gas_page=gas,
            registration_sources=sources.workbench, current_time=lambda: 110,
            commit=COMMIT, tree=TREE, port=0, **inputs)
        self.addCleanup(server.server_close)
        return server

    def start(self, server):
        worker = threading.Thread(target=server.serve_forever,
                                  kwargs={"poll_interval": 0.02}, daemon=True)
        worker.start()
        def stop():
            server.shutdown()
            worker.join(timeout=3)
        self.addCleanup(stop)

    def get(self, server, path):
        with urlopen(server.origin + path, timeout=3) as response:
            return json.load(response)

    def test_integrated_routes_expose_each_explicit_nft_binding(self):
        other = RuntimeBinding(OriginalReadOnlyDomain(), "receipt-2")
        server = self.server(detail_bindings=(other,))
        self.start(server)
        rows = self.get(server, "/api/nfts")["nfts"]
        keys = {row["nftKey"] for row in rows}
        self.assertEqual(len(keys), 2)
        other_key = server.nft_directory.key_for(other)
        self.assertIn(other_key, keys)
        detail = self.get(server, "/api/nft-detail?nft=" + other_key)
        self.assertEqual(detail["nftKey"], other_key)
        self.assertEqual(self.wallet_calls, [])

    def test_integrated_lifecycle_uses_supplied_feed_for_both_market_api_routes(self):
        fixture = reference_fixtures.ReferenceFeedTests("runTest")
        fixture.setUp()
        observed = threading.Event()
        feed = fixture.feed(read=lambda policy: (observed.set(), dict(fixture.row))[1])
        server = self.server(reference_feed=feed)
        self.start(server)
        self.assertTrue(observed.wait(timeout=2))
        reference = self.get(server, "/api/reference")
        catalogue = self.get(server, "/api/catalogue")
        self.assertIs(server.reference_feed, feed)
        for value in (reference, catalogue["reference"]):
            self.assertEqual(value["series"], fixture.policy["series"])
            self.assertEqual(value["price"], fixture.row["price"])
            self.assertFalse(value["executableOrder"])
        server.shutdown()
        server.server_close()
        self.assertFalse(feed._thread.is_alive())
        self.assertEqual(self.wallet_calls, [])

    def test_omitted_inputs_preserve_unconnected_reference_and_one_nft(self):
        server = self.server()
        self.start(server)
        self.assertEqual(self.get(server, "/api/reference")["status"], "not-connected")
        self.assertEqual(len(self.get(server, "/api/nfts")["nfts"]), 1)
        self.assertEqual(self.wallet_calls, [])
