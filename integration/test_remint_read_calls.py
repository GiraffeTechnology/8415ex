"""Synthetic encoding-port definitions; no RPC, actual Keccak or contract call."""
from copy import deepcopy
import unittest
from exchange.remint_read_calls import RemintReadCallEncoder, RemintReadCallRefused, SIGNATURES

CONTRACT, BLOCK = "0x"+"1"*40, "0x"+"2"*64
SELECTORS = {signature:bytes([index+1])*4 for index, signature in enumerate(SIGNATURES)}


class RemintReadCallContracts(unittest.TestCase):
    def setUp(self):
        self.hash_calls = []
        def keccak(raw):
            self.hash_calls.append(raw)
            return SELECTORS[raw.decode("ascii")]+bytes(28)
        self.encoder = RemintReadCallEncoder(CONTRACT, keccak, require_canonical=True)
        self.binding = {"chainId":11155111, "contract":CONTRACT,
            "block":{"number":32,"hash":BLOCK,"timestamp":1800},
            "function":"declarationOf(uint256)", "arguments":["2"]}

    def test_only_four_fixed_getters_are_hashed_and_encoded_to_original_destination(self):
        self.assertEqual(self.hash_calls,[value.encode("ascii") for value in SIGNATURES])
        for signature in SIGNATURES:
            argument = "0x"+"3"*64 if "bytes32" in signature else "2"
            result = self.encoder(dict(self.binding,function=signature,arguments=[argument]))
            call, block = result["request"]["params"]
            raw = bytes.fromhex(call["data"][2:])
            self.assertEqual(raw[:4],SELECTORS[signature])
            self.assertEqual(len(raw),36)
            self.assertEqual(call["to"],CONTRACT)
            expected = bytes.fromhex(argument[2:]) if "bytes32" in signature else (2).to_bytes(32,"big")
            self.assertEqual(raw[4:],expected)
            self.assertEqual(block,dict(blockHash=BLOCK,requireCanonical=True))
            self.assertEqual(result["request"]["method"],"eth_call")

    def test_uint256_zero_and_maximum_are_preserved_without_json_precision_loss(self):
        for token in ("0",str(2**256-1)):
            result = self.encoder(dict(self.binding,arguments=[token]))
            raw = bytes.fromhex(result["request"]["params"][0]["data"][2:])
            self.assertEqual(int.from_bytes(raw[4:],"big"),int(token))
            self.assertEqual(result["binding"]["arguments"],[token])
        for invalid in (True,2,"02","-1",str(2**256),"2.0"):
            with self.assertRaises(RemintReadCallRefused):
                self.encoder(dict(self.binding,arguments=[invalid]))

    def test_bill_words_are_not_hashed_converted_sorted_or_treated_as_balances(self):
        for word in ("0x"+"0"*64,"0x"+"a"*64):
            result = self.encoder(dict(self.binding,function=SIGNATURES[3],arguments=[word]))
            self.assertTrue(result["request"]["params"][0]["data"].endswith(word[2:]))
        for invalid in ("bill-1","0x1234",1,{"billKey":"0x"+"a"*64}):
            with self.assertRaises(RemintReadCallRefused):
                self.encoder(dict(self.binding,function=SIGNATURES[3],arguments=[invalid]))
        self.assertEqual(len(self.hash_calls),4)

    def test_block_hash_is_used_without_latest_number_or_safe_finalized_substitution(self):
        before = deepcopy(self.binding)
        result = self.encoder(self.binding)
        self.assertEqual(self.binding,before)
        result["binding"]["block"]["hash"]="0x"+"f"*64
        result["request"]["params"][1]["blockHash"]="0x"+"e"*64
        self.assertEqual(self.binding,before)
        block_parameter = self.encoder(self.binding)["request"]["params"][1]
        self.assertNotIn("blockNumber",block_parameter)
        self.assertNotIn("latest",str(block_parameter))

    def test_original_canonical_policy_is_explicit_and_is_not_finality_evidence(self):
        other = RemintReadCallEncoder(CONTRACT,
            lambda raw:SELECTORS[raw.decode()]+bytes(28),require_canonical=False)
        result = other(self.binding)
        self.assertIs(result["request"]["params"][1]["requireCanonical"],False)
        self.assertNotIn("finality",result)
        for invalid in (1,"true",None):
            with self.assertRaises(RemintReadCallRefused):
                RemintReadCallEncoder(CONTRACT,lambda raw:bytes(32),require_canonical=invalid)

    def test_other_chain_contract_block_types_or_unexpected_request_fields_refuse(self):
        for key,value in (("chainId",True),("chainId",1),("contract","0x"+"4"*40),
                          ("arguments",("2",)),("arguments",["2","3"])):
            with self.assertRaises(RemintReadCallRefused):
                self.encoder(dict(self.binding,**{key:value}))
        for key,value in (("number",True),("timestamp",-1),("hash","latest")):
            block = dict(self.binding["block"],**{key:value})
            with self.assertRaises(RemintReadCallRefused):
                self.encoder(dict(self.binding,block=block))
        with self.assertRaises(RemintReadCallRefused):
            self.encoder(dict(self.binding,fromAddress="private-selection"))

    def test_effect_signatures_and_transport_or_signer_fields_are_never_generated(self):
        for signature in ("remintNFT0(bytes32,uint256,(bytes32,bytes32,bytes32,bytes32[]))",
                          "transferFrom(address,address,uint256)","operationResult(bytes32)"):
            with self.assertRaises(RemintReadCallRefused):
                self.encoder(dict(self.binding,function=signature))
        result = self.encoder(self.binding)
        self.assertEqual(set(result),{"binding","request"})
        self.assertEqual(set(result["request"]),{"method","params"})
        self.assertEqual(set(result["request"]["params"][0]),{"to","data"})
        for absent in ("from","value","gas","nonce","url","id","signature","send"):
            self.assertNotIn(absent,result["request"])

    def test_unavailable_wrong_type_or_colliding_crypto_results_fail_without_error_echo(self):
        def fail(raw):
            raise RuntimeError("PRIVATE_CRYPTO_ERROR")
        for callback in (fail,lambda raw:"0x"+"1"*64,lambda raw:bytes(31),
                         lambda raw:bytes(32)):
            with self.assertRaises(RemintReadCallRefused) as raised:
                RemintReadCallEncoder(CONTRACT,callback,require_canonical=True)
            self.assertNotIn("PRIVATE_CRYPTO_ERROR",str(raised.exception))
