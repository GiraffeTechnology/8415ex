"""Synthetic original-port contracts; not live provider or crypto acceptance."""
from copy import deepcopy
import json
import unittest
from exchange.remint_pinned_call_port import RemintPinnedCallPort, RemintPinnedReadRefused
from exchange.remint_read_calls import RemintReadCallEncoder, SIGNATURES
from exchange.remint_history_snapshot import RemintHistorySnapshotReader
from exchange.remint_history_workbench import RemintChainHistoryBinding, RemintHistoryUnavailable
from integration import test_remint_history_snapshot as original

SELECTORS={signature:bytes([index+1])*4 for index,signature in enumerate(SIGNATURES)}


class RemintPinnedCallPortContracts(unittest.TestCase):
    def setUp(self):
        self.fixture=original.RemintHistorySnapshotContracts("runTest")
        self.fixture.setUp()
        self.requests,self.verified=[],[]
        self.response_change=lambda response:response
        self.raw_change=lambda raw:raw
        self.verify_result=True
        self.encoder=RemintReadCallEncoder(original.CONTRACT,
            lambda raw:SELECTORS[raw.decode()]+bytes(28),require_canonical=True)
        def transport(request):
            self.requests.append(deepcopy(request))
            raw=bytes.fromhex(request["params"][0]["data"][2:])
            signature=next(name for name,selector in SELECTORS.items() if selector==raw[:4])
            argument=("0x"+raw[4:].hex() if "bytes32" in signature
                      else str(int.from_bytes(raw[4:],"big")))
            data=self.fixture.results[(signature,argument)]
            response={"jsonrpc":"2.0","id":request["id"],"result":"0x"+data.hex()}
            return self.raw_change(json.dumps(self.response_change(response)).encode())
        self.transport=transport
        def verify(evidence):
            self.verified.append(deepcopy(evidence))
            return self.verify_result
        self.port=RemintPinnedCallPort(self.encoder,transport,verify)
        self.reader=RemintHistorySnapshotReader(original.CONTRACT,original.BILL,
            self.fixture.reader.read_original_block,self.port)
        self.binding={"chainId":11155111,"contract":original.CONTRACT,
            "block":deepcopy(self.fixture.block),"function":"predecessorOf(uint256)",
            "arguments":["2"]}

    def test_original_history_binding_joins_six_exact_block_calls_and_actual_raw_results(self):
        view=RemintChainHistoryBinding("receipt-1",original.CONTRACT,original.BILL,
                                      "2",self.reader).read("2")
        self.assertEqual((view["predecessor"],view["successor"],view["active"]),("1","3","3"))
        self.assertEqual(len(self.requests),6)
        self.assertEqual(len(self.verified),6)
        self.assertEqual(len(self.fixture.headers),1)
        for request,evidence in zip(self.requests,self.verified):
            self.assertEqual(request["method"],"eth_call")
            self.assertEqual(request["params"][1],
                {"blockHash":self.fixture.block["hash"],"requireCanonical":True})
            self.assertEqual(evidence["binding"]["block"],self.fixture.block)
            self.assertEqual(evidence["request"],request)
            self.assertEqual(json.loads(evidence["rawResponse"])["id"],request["id"])

    def test_exact_raw_response_and_private_binding_reach_verifier_before_abi_decoding(self):
        self.raw_change=lambda raw:b"not-json-private-marker"
        with self.assertRaises(RemintPinnedReadRefused) as raised:
            self.port(self.binding)
        self.assertEqual(len(self.requests),1)
        self.assertEqual(self.verified[0]["rawResponse"],b"not-json-private-marker")
        self.assertEqual(self.verified[0]["binding"],self.binding)
        self.assertNotIn("private-marker",str(raised.exception))

    def test_error_wrong_id_version_null_batch_and_duplicate_json_are_not_success(self):
        changes=(
            lambda r:dict(r,id="different"),
            lambda r:dict(r,jsonrpc="1.0"),
            lambda r:{"jsonrpc":"2.0","id":r["id"],"error":{"code":-32000,"message":"private"}},
            lambda r:dict(r,error={"code":-32000,"message":"private"}),
            lambda r:dict(r,result=None),lambda r:None,lambda r:[r])
        for change in changes:
            self.response_change=change
            with self.assertRaises(RemintPinnedReadRefused):
                self.port(self.binding)
        self.response_change=lambda r:r
        self.raw_change=lambda raw:raw.replace(b'"result":',b'"id":"duplicate","result":')
        with self.assertRaises(RemintPinnedReadRefused):
            self.port(self.binding)
        self.assertEqual(len(self.requests),len(changes)+1)

    def test_invalid_scope_is_refused_before_any_transport_or_authentication_call(self):
        for key,value in (("chainId",1),("contract","0x"+"7"*40),
                          ("function","remintNFT0()"),("arguments",[True])):
            with self.assertRaises(RemintPinnedReadRefused):
                self.port(dict(self.binding,**{key:value}))
        self.assertEqual(self.requests,[])
        self.assertEqual(self.verified,[])

    def test_abi_revert_empty_trailing_data_and_partial_snapshot_never_become_zero(self):
        for invalid in ("0x","0x"+"00"*64,"0x01"):
            self.response_change=lambda r:dict(r,result=invalid)
            with self.assertRaises(RemintPinnedReadRefused):
                self.port(self.binding)
        self.response_change=lambda r:r
        self.fixture.results[("predecessorOf(uint256)","2")]=original.word(0)
        self.assertEqual(self.port(self.binding)["data"],"0x"+original.word(0).hex())
        self.requests.clear()
        def fail_active(response):
            if self.requests[-1]["params"][0]["data"][2:10]==SELECTORS[SIGNATURES[3]].hex():
                return dict(response,result="0x")
            return response
        self.response_change=fail_active
        with self.assertRaises(RemintHistoryUnavailable):
            self.reader(self.fixture.scope)
        self.assertEqual(len(self.requests),4)

    def test_transport_or_authentication_failures_never_retry_or_echo_private_errors(self):
        calls=[]
        def fail(request):
            calls.append(request)
            raise RuntimeError("PRIVATE_ROUTE_ERROR")
        port=RemintPinnedCallPort(self.encoder,fail,lambda evidence:True)
        with self.assertRaises(RemintPinnedReadRefused) as raised:
            port(self.binding)
        self.assertEqual(len(calls),1)
        self.assertNotIn("PRIVATE_ROUTE_ERROR",str(raised.exception))
        for value in (False,None,1):
            self.verify_result=value
            with self.assertRaises(RemintPinnedReadRefused):
                self.port(self.binding)
        self.assertEqual(len(self.requests),3)

    def test_response_bounds_and_detachment_preserve_original_inputs(self):
        before=deepcopy(self.binding)
        for invalid in (b"",b"x"*(RemintPinnedCallPort.MAX_RESPONSE_BYTES+1),"text"):
            self.raw_change=lambda raw:invalid
            with self.assertRaises(RemintPinnedReadRefused):
                self.port(self.binding)
        self.assertEqual(self.verified,[])
        self.raw_change=lambda raw:raw
        result=self.port(self.binding)
        result["binding"]["arguments"][0]="9"
        self.verified[-1]["binding"]["block"]["number"]=0
        self.assertEqual(self.binding,before)

    def test_each_call_has_its_own_rpc_id_and_no_effect_or_wallet_fields(self):
        self.port(self.binding)
        self.port(self.binding)
        self.assertNotEqual(self.requests[0]["id"],self.requests[1]["id"])
        for request in self.requests:
            self.assertEqual(set(request),{"jsonrpc","id","method","params"})
            self.assertEqual(request["method"],"eth_call")
            self.assertEqual(set(request["params"][0]),{"to","data"})
            self.assertNotIn("nonce",request)
            self.assertNotIn("operationId",request)
