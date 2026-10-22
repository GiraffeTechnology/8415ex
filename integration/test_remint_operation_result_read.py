"""Synthetic exact-response read-port contracts; no live RPC or crypto proof."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from exchange.remint_operation_result_read import (
    RemintOperationResultReadPort, RemintOperationReadRefused, SIGNATURE,
)
from integration import test_remint_operation_result as original

CONTRACT = "0x" + "ab"*20
OPERATION = "0x" + "cd"*32
BLOCK = {"number":30, "hash":"0x"+"ef"*32, "timestamp":100}


class RemintOperationResultReadContracts(unittest.TestCase):
    def setUp(self):
        self.requests, self.evidence = [], []
        self.response_data = "0x" + original.result(token=9).hex()
        self.response_change = lambda response:response
        self.raw_change = lambda raw:raw
        self.authenticated = True
        self.binding = {"chainId":11155111, "contract":CONTRACT, "block":deepcopy(BLOCK),
                        "function":SIGNATURE, "arguments":[OPERATION]}
        def keccak(raw):
            self.assertEqual(raw, SIGNATURE.encode("ascii"))
            return bytes.fromhex("12345678") + bytes(28)
        def transport(request):
            self.requests.append(deepcopy(request))
            response = {"jsonrpc":"2.0", "id":request["id"], "result":self.response_data}
            return self.raw_change(json.dumps(self.response_change(response)).encode())
        def verify(evidence):
            self.evidence.append(deepcopy(evidence))
            return self.authenticated
        self.port = RemintOperationResultReadPort(CONTRACT, keccak, transport, verify,
                                                  require_canonical=True)

    def read(self, binding=None, digest=original.DIGEST):
        return self.port(self.binding if binding is None else binding, expected_digest=digest)

    def test_exact_original_operation_and_block_request_reaches_original_decoder(self):
        result = self.read()
        self.assertEqual(len(self.requests), 1)
        request = self.requests[0]
        self.assertEqual(set(request), {"jsonrpc","id","method","params"})
        self.assertEqual(request["method"], "eth_call")
        self.assertEqual(request["params"], [
            {"to":CONTRACT, "data":"0x12345678"+OPERATION[2:]},
            {"blockHash":BLOCK["hash"], "requireCanonical":True}])
        self.assertEqual(result["binding"], self.binding)
        self.assertEqual(result["observation"]["newTokenId"], "9")
        self.assertEqual(result["observation"]["status"], "RECORDED")
        self.assertFalse(result["observation"]["replayAllowed"])
        self.assertFalse(result["observation"]["releaseAllowed"])
        self.assertEqual(result["observation"]["receiptFinality"], "NOT_ESTABLISHED")

    def test_zero_tuple_is_not_pending_absence_or_permission_to_replay(self):
        self.response_data = "0x" + bytes(64).hex()
        result = self.read()["observation"]
        self.assertEqual(result["status"], "NOT_RECORDED_AT_READ")
        self.assertIsNone(result["newTokenId"])
        self.assertEqual(result["nativePendingAbsence"], "NOT_ESTABLISHED")
        self.assertFalse(result["replayAllowed"])
        self.assertFalse(result["releaseAllowed"])
        self.assertEqual(len(self.requests), 1)

    def test_scope_or_digest_errors_refuse_before_transport_and_verifier(self):
        for key, value in (("chainId",1), ("chainId",True),
                ("contract","0x"+"11"*20), ("function","remintNFT0()"),
                ("arguments",["native-string"]), ("arguments",["0x"+"0"*64]),
                ("block",dict(BLOCK, number=True)), ("block",dict(BLOCK, hash="latest"))):
            with self.subTest(key=key), self.assertRaises(RemintOperationReadRefused):
                self.read(dict(self.binding, **{key:value}))
        with self.assertRaises(RemintOperationReadRefused):
            self.read(digest="history-sha")
        self.assertEqual(self.requests, [])
        self.assertEqual(self.evidence, [])

    def test_authentication_sees_exact_raw_bytes_and_context_before_result_decoding(self):
        self.raw_change = lambda raw:b"PRIVATE-NON-JSON"
        self.authenticated = False
        with patch("exchange.remint_operation_result_read.decode_remint_operation_result") as decode:
            with self.assertRaises(RemintOperationReadRefused):
                self.read()
            decode.assert_not_called()
        self.assertEqual(self.evidence[0]["rawResponse"], b"PRIVATE-NON-JSON")
        self.assertEqual(self.evidence[0]["binding"], self.binding)
        self.assertEqual(self.evidence[0]["expectedContractDigest"], original.DIGEST)
        self.assertEqual(self.evidence[0]["request"], self.requests[0])

    def test_error_wrong_id_version_batch_null_and_duplicate_json_are_not_results(self):
        changes = (lambda r:dict(r,id="other"), lambda r:dict(r,jsonrpc="1.0"),
            lambda r:dict(r,result=None), lambda r:[r], lambda r:None,
            lambda r:dict(r,error={"code":-32000,"message":"PRIVATE"}),
            lambda r:{"jsonrpc":"2.0","id":r["id"],"error":{"code":-32000}})
        for change in changes:
            self.response_change = change
            with self.assertRaises(RemintOperationReadRefused):
                self.read()
        self.response_change = lambda r:r
        self.raw_change = lambda raw:raw.replace(b'"result":', b'"id":"duplicate","result":')
        with self.assertRaises(RemintOperationReadRefused):
            self.read()
        self.assertEqual(len(self.requests), len(changes)+1)

    def test_conflict_trailing_and_half_empty_results_never_retry(self):
        for value in ("0x"+original.result(original.OTHER).hex(), "0x",
                "0x"+bytes(65).hex(), "0x"+original.result(token=0).hex()):
            self.response_data = value
            before = len(self.requests)
            with self.assertRaises(RemintOperationReadRefused):
                self.read()
            self.assertEqual(len(self.requests), before+1)

    def test_transport_response_bounds_and_verifier_failure_keep_private_errors_private(self):
        for raw in (b"", b"x"*(self.port.MAX_RESPONSE_BYTES+1), "text"):
            self.raw_change = lambda response:raw
            with self.assertRaises(RemintOperationReadRefused) as raised:
                self.read()
            self.assertNotIn("PRIVATE", str(raised.exception))
        self.assertEqual(self.evidence, [])
        calls = []
        def unavailable(request):
            calls.append(request)
            raise RuntimeError("PRIVATE-ROUTE")
        self.port.original_transport = unavailable
        with self.assertRaises(RemintOperationReadRefused) as raised:
            self.read()
        self.assertEqual(len(calls), 1)
        self.assertNotIn("PRIVATE-ROUTE", str(raised.exception))

    def test_detached_bindings_and_rpc_ids_do_not_become_operation_or_transaction_ids(self):
        before = deepcopy(self.binding)
        first = self.read()
        second = self.read()
        self.assertNotEqual(self.requests[0]["id"], self.requests[1]["id"])
        first["binding"]["arguments"][0] = "other"
        self.evidence[0]["binding"]["block"]["number"] = 0
        self.assertEqual(self.binding, before)
        self.assertEqual(second["binding"], before)
        for request in self.requests:
            self.assertNotIn("nonce", request)
            self.assertNotIn("from", request["params"][0])
            self.assertNotIn("value", request["params"][0])
            self.assertNotIn("gas", request["params"][0])
