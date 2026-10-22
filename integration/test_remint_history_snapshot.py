"""Synthetic definitions for pinned original read ports; no live RPC."""
from copy import deepcopy
import unittest
from exchange.remint_history_snapshot import RemintHistorySnapshotReader
from exchange.remint_history_workbench import RemintChainHistoryBinding, RemintHistoryUnavailable
from integration.test_remint_history_workbench import CONTRACT, BILL, word


class RemintHistorySnapshotContracts(unittest.TestCase):
    def setUp(self):
        self.headers, self.calls = [], []
        self.header_change = lambda row: row
        self.response_change = lambda row: row
        self.block = {"number": 900, "hash": "0x"+"a"*64, "timestamp": 1800}
        self.results = {
            ("declarationOf(uint256)", "2"): b"".join(word(n) for n in (32,1,2,3,128,1,4)),
            ("predecessorOf(uint256)", "2"): word(1),
            ("successorOf(uint256)", "2"): word(3),
            ("activeTokenForBill(bytes32)", BILL): word(3),
            ("successorOf(uint256)", "1"): word(2),
            ("predecessorOf(uint256)", "3"): word(2),
        }
        def header(request):
            self.headers.append(deepcopy(request))
            return self.header_change({"binding": deepcopy(request), "block": deepcopy(self.block)})
        def call(request):
            self.calls.append(deepcopy(request))
            data = self.results[(request["function"], request["arguments"][0])]
            return self.response_change({"binding": deepcopy(request), "data": data})
        self.reader = RemintHistorySnapshotReader(CONTRACT, BILL, header, call)
        self.scope = {"chainId":11155111, "contract":CONTRACT, "billKey":BILL, "tokenId":"2"}

    def test_history_page_binding_consumes_all_original_getters_at_one_exact_block(self):
        bound = RemintChainHistoryBinding("receipt-1", CONTRACT, BILL, "2", self.reader)
        view = bound.read("2")
        self.assertEqual((view["predecessor"], view["successor"], view["active"]), ("1","3","3"))
        self.assertEqual(view["observedBlock"], self.block)
        self.assertEqual(len(self.headers), 1)
        self.assertEqual(len(self.calls), 6)
        for call in self.calls:
            self.assertEqual(call["chainId"], 11155111)
            self.assertEqual(call["contract"], CONTRACT)
            self.assertEqual(call["block"], self.block)
        self.assertEqual(self.calls[3]["arguments"], [BILL])

    def test_caller_cannot_change_fixed_chain_contract_bill_or_token_types(self):
        for key, value in (("chainId",1), ("chainId",11155111.0), ("contract","0x"+"2"*40),
                           ("billKey","0x"+"b"*64), ("tokenId",2), ("tokenId","0"),
                           ("tokenId","02"), ("tokenId",str(2**256))):
            with self.assertRaises(RemintHistoryUnavailable):
                self.reader(dict(self.scope, **{key:value}))
        self.assertEqual(self.headers, [])
        self.assertEqual(self.calls, [])

    def test_wrong_or_malformed_header_stops_before_any_contract_query(self):
        for change in (
                lambda row: dict(row, binding=dict(row["binding"], chainId=1)),
                lambda row: dict(row, block=dict(row["block"], number=True)),
                lambda row: dict(row, block=dict(row["block"], hash="0x"+"0"*64)),
                lambda row: dict(row, block={"number":900})):
            self.header_change = change
            with self.assertRaises(RemintHistoryUnavailable):
                self.reader(self.scope)
        self.assertEqual(self.calls, [])

    def test_every_response_requires_exact_block_function_and_argument_binding(self):
        changes = (
            lambda row: dict(row, binding=dict(row["binding"], block=dict(self.block, hash="0x"+"b"*64))),
            lambda row: dict(row, binding=dict(row["binding"], function="ownerOf(uint256)")),
            lambda row: dict(row, binding=dict(row["binding"], arguments=[2])),
            lambda row: dict(row, binding=dict(row["binding"], contract="0x"+"2"*40)),
        )
        for change in changes:
            self.calls.clear()
            self.response_change = change
            with self.assertRaises(RemintHistoryUnavailable):
                self.reader(self.scope)
            self.assertEqual(len(self.calls), 1)

    def test_invalid_declaration_discards_snapshot_before_link_queries(self):
        key = ("declarationOf(uint256)", "2")
        for data in (b"", word(0), b"".join(word(n) for n in (32,8,2,3,128,1,4))):
            self.calls.clear()
            self.results[key] = data
            with self.assertRaises(RemintHistoryUnavailable):
                self.reader(self.scope)
            self.assertEqual(len(self.calls), 1)

    def test_real_zero_links_are_preserved_without_token_zero_queries(self):
        self.results[("predecessorOf(uint256)", "2")] = word(0)
        self.results[("successorOf(uint256)", "2")] = word(0)
        self.results[("activeTokenForBill(bytes32)", BILL)] = word(2)
        result = self.reader(self.scope)
        self.assertIsNone(result["predecessorReverse"])
        self.assertIsNone(result["successorReverse"])
        self.assertEqual(len(self.calls), 4)
        self.assertFalse(any(call["arguments"] == ["0"] for call in self.calls))
        bound = RemintChainHistoryBinding("receipt-1", CONTRACT, BILL, "2", self.reader)
        self.assertEqual(bound.read("2")["active"], "2")

    def test_failure_has_no_partial_return_retry_or_latest_block_fallback(self):
        def fail(row):
            if row["binding"]["function"] == "activeTokenForBill(bytes32)":
                raise RuntimeError("PRIVATE_PROVIDER_SENTINEL")
            return row
        self.response_change = fail
        with self.assertRaises(RemintHistoryUnavailable) as raised:
            self.reader(self.scope)
        self.assertNotIn("PRIVATE_PROVIDER_SENTINEL", str(raised.exception))
        self.assertEqual(len(self.headers), 1)
        self.assertEqual(len(self.calls), 4)
        self.assertTrue(all(call["block"] == self.block for call in self.calls))

    def test_scope_block_and_returned_snapshots_are_detached_without_new_authority(self):
        before = deepcopy(self.scope)
        result = self.reader(self.scope)
        result["scope"]["tokenId"] = "9"
        result["observedBlock"]["number"] = 0
        self.assertEqual(self.scope, before)
        self.assertEqual(self.block["number"], 900)
        self.assertNotIn("replayAllowed", result)
        self.assertNotIn("transaction", result)
        self.assertNotIn("businessAcceptance", result)
