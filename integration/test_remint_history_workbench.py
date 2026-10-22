"""Approved-Linux test definitions for the original read-only history route."""
from copy import deepcopy
import http.client
import threading
import unittest
from exchange.gas_confirmation_ui import GasConfirmationPage
from exchange.workbench import RuntimeBinding
from exchange.remint_history_workbench import (
    WORDS, RemintChainHistoryBinding, RemintHistoryUnavailable,
    RemintHistoryWorkbenchServer,
)
from integration.test_gas_budget import quote
import integration.test_registration_source_workbench as source_fixtures

CONTRACT = "0x" + "1" * 40
BILL = "0x" + "0" * 63 + "1"


def word(value):
    return value.to_bytes(32, "big")


def original(scope):
    token = int(scope["tokenId"])
    # Three replacements demonstrate both directions and a non-adjacent active NFT.
    previous = {1: 0, 2: 1, 3: 2}[token]
    following = {1: 2, 2: 3, 3: 0}[token]
    return {"scope": deepcopy(scope),
        "observedBlock": {"number": 900, "hash": "0x"+"a"*64, "timestamp": 1800},
        "declaration": b"".join(word(n) for n in (32, 1, 2, 3, 128, 1, 4)),
        "predecessor": word(previous), "successor": word(following), "active": word(3),
        "predecessorReverse": word(token) if previous else None,
        "successorReverse": word(token) if following else None}


class RemintHistoryWorkbenchContracts(unittest.TestCase):
    def setUp(self):
        self.calls, self.wallet_calls = [], []
        self.change = lambda row: row
        def read(scope):
            self.calls.append(deepcopy(scope))
            return self.change(original(scope))
        self.history = RemintChainHistoryBinding("receipt-1", CONTRACT, BILL, "2", read)
        sources = source_fixtures.RegistrationSourceWorkbenchContracts("runTest")
        sources.setUp()
        def wallet(*args):
            self.wallet_calls.append(args)
            raise AssertionError("History cannot execute a wallet operation")
        gas = GasConfirmationPage(lambda: quote(), wallet, "fixture-buyer", "fixture-action",
            "fixture-grant", "/gas/confirm", lambda token: token == self.server.csrf)
        self.server = RemintHistoryWorkbenchServer(RuntimeBinding(None, "receipt-1"),
            remint_history=self.history, gas_page=gas, registration_sources=sources.workbench,
            current_time=lambda: 110, commit="a"*40, tree="b"*40, port=0)
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

    def test_six_locales_show_real_links_and_keep_selection_in_language_navigation(self):
        for locale, words in WORDS.items():
            status, headers, body = self.request("GET", "/remint-history?token=2&lang="+locale)
            self.assertEqual(status, 200)
            for label in words[:5]:
                self.assertIn(label, body)
            self.assertIn("token=1", body)
            self.assertIn("token=3", body)
            self.assertIn('lang=ja&amp;token=2', body)
            self.assertIn("900", body)
            self.assertEqual(headers["Cache-Control"], "no-store")
            self.assertNotIn(CONTRACT, body)
            self.assertNotIn("<form", body)
        self.assertEqual(self.wallet_calls, [])

    def test_navigation_reads_only_requested_original_bill_and_reciprocal_links(self):
        for token in ("1", "2", "3"):
            self.assertEqual(self.request("GET", "/remint-history?token="+token)[0], 200)
        self.assertEqual([row["tokenId"] for row in self.calls], ["1", "2", "3"])
        for scope in self.calls:
            self.assertEqual(scope, {"chainId": 11155111, "contract": CONTRACT,
                                     "billKey": BILL, "tokenId": scope["tokenId"]})
        first = self.history.read("1")
        self.assertEqual(first["predecessor"], "0")
        self.assertEqual(first["successor"], "2")
        self.assertEqual(first["active"], "3")
        self.assertNotIn("burned", first)
        self.assertNotIn("replayAllowed", first)

    def test_queries_cannot_select_another_contract_chain_bill_or_callback(self):
        for query in ("token=0", "token=01", "token=-1", "token=1.0", "token=",
                      "token="+str(2**256), "token=1&token=2", "lang=bad",
                      "lang=", "contract="+CONTRACT, "chainId=1", "billKey=other",
                      "reader=other", "lang=en&token=1&extra=1"):
            self.assertEqual(self.request("GET", "/remint-history?"+query)[0], 400)
        self.assertEqual(self.calls, [])

    def test_wrong_response_scope_or_block_is_unavailable_without_raw_errors(self):
        def corrupt(kind):
            def change(row):
                if kind == "token": row["scope"]["tokenId"] = "3"
                if kind == "float": row["scope"]["chainId"] = 11155111.0
                if kind == "contract": row["scope"]["contract"] = "0x"+"2"*40
                if kind == "block": row["observedBlock"]["number"] = True
                if kind == "hash": row["observedBlock"]["hash"] = "private-diagnostic"
                if kind == "bill": row["declaration"] = row["declaration"][:32]+word(8)+row["declaration"][64:]
                return row
            return change
        for kind in ("token", "float", "contract", "block", "hash", "bill"):
            self.change = corrupt(kind)
            status, _, body = self.request("GET", "/remint-history?lang=fr")
            self.assertEqual(status, 503)
            self.assertIn(WORDS["fr"][6], body)
            self.assertNotIn("private-diagnostic", body)
            self.assertNotIn(CONTRACT, body)

    def test_malformed_or_conflicting_link_results_never_become_no_history(self):
        for field, value in (("predecessorReverse", word(7)),
                ("successorReverse", word(8)), ("successor", word(2)),
                ("active", word(0)), ("active", word(2)),
                ("declaration", b""), ("predecessor", b"")):
            self.change = lambda row, field=field, value=value: dict(row, **{field: value})
            self.assertEqual(self.request("GET", "/remint-history")[0], 503)

    def test_post_refuses_without_reading_or_dispatching_and_original_routes_remain(self):
        status, headers, _ = self.request("POST", "/remint-history", "action=remint")
        self.assertEqual(status, 405)
        self.assertEqual(headers["Allow"], "GET")
        self.assertEqual(self.calls, [])
        self.assertEqual(self.request("GET", "/gas")[0], 200)
        self.assertEqual(self.request("GET", "/remint-review")[0], 503)
        self.assertEqual(self.wallet_calls, [])

    def test_missing_reader_and_private_failures_are_localized_and_do_not_hide_gas(self):
        def failure(row):
            raise RuntimeError("PRIVATE_HISTORY_SENTINEL")
        self.change = failure
        status, _, body = self.request("GET", "/remint-history?lang=ja")
        self.assertEqual(status, 503)
        self.assertIn(WORDS["ja"][6], body)
        self.assertNotIn("PRIVATE_HISTORY_SENTINEL", body)
        self.server.remint_history = None
        self.assertEqual(self.request("GET", "/remint-history")[0], 503)
        self.assertEqual(self.request("GET", "/gas")[0], 200)

    def test_observation_is_detached_and_binding_is_not_a_remint_execution_gate(self):
        result = self.history.read("2")
        result["observedBlock"]["number"] = 0
        self.assertEqual(self.history.read("2")["observedBlock"]["number"], 900)
        self.assertEqual(self.wallet_calls, [])
        with self.assertRaises(ValueError):
            RemintChainHistoryBinding("receipt-1", CONTRACT, BILL, "0", original)
        self.change = lambda row: dict(row, successorReverse=word(9))
        with self.assertRaises(RemintHistoryUnavailable):
            self.history.read("2")
