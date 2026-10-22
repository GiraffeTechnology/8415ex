"""Synthetic ABI/receipt-port definitions; no RPC, real Keccak or chain effect."""
from copy import deepcopy
import hashlib
import json
import unittest
from exchange.remint_event_logs import (
    RemintEventLogDecoder, RemintLogRefused, SIGNATURES, TRANSFER_TOPIC,
)
from exchange.receipt_gas_observer import ReceiptGasObserver
from exchange.remint_receipt_observation import RemintReceiptObserver
from integration import test_remint_receipt_observation as original

TOPICS = {"Transfer":TRANSFER_TOPIC, "NFT0Declared":bytes.fromhex("5"*64),
          "NFT0Reminted":bytes.fromhex("6"*64)}


def word(value):
    return value.to_bytes(32, "big")


def topic(value):
    return "0x"+value.hex()


def address(value):
    return bytes(12)+bytes.fromhex(value[2:])


class RemintEventLogContracts(unittest.TestCase):
    def setUp(self):
        self.hash_calls = []
        def synthetic_keccak(raw):
            self.hash_calls.append(raw)
            return TOPICS[next(name for name, signature in SIGNATURES.items() if signature == raw)]
        self.decoder = RemintEventLogDecoder(original.CONTRACT, synthetic_keccak)
        self.context = dict(chainId=11155111, contract=original.CONTRACT,
            transactionHash=original.TX, blockHash=original.BLOCK, blockNumber=32, logIndex=0)

    def log(self, name, indexed, data=b"", index=0):
        return dict(address=original.CONTRACT, transactionHash=original.TX,
            blockHash=original.BLOCK, blockNumber="0x20", logIndex=hex(index), removed=False,
            topics=[topic(TOPICS[name])]+[topic(value) for value in indexed], data=topic(data))

    def declared(self, currencies=None):
        chosen = currencies if currencies is not None else original.REPLACEMENT["allowedCurrencies"]
        return self.log("NFT0Declared", [word(9), bytes.fromhex(original.REPLACEMENT["billKey"][2:])],
            bytes.fromhex(original.REPLACEMENT["termsHash"][2:])
            + bytes.fromhex(original.REPLACEMENT["currencyDeclarationHash"][2:])
            + word(96)+word(len(chosen))+b"".join(bytes.fromhex(c[2:]) for c in chosen))

    def test_fixed_signature_topics_use_original_keccak_and_refuse_sha3_or_aliases(self):
        self.assertEqual(self.hash_calls, list(SIGNATURES.values()))
        for invalid in (lambda raw:hashlib.sha3_256(raw).digest(),
                        lambda raw:bytes(32), lambda raw:"0x"+"1"*64,
                        lambda raw:TRANSFER_TOPIC):
            with self.assertRaises(RemintLogRefused):
                RemintEventLogDecoder(original.CONTRACT, invalid)

    def test_transfer_topics_decode_burn_and_mint_without_address_truncation(self):
        zero = "0x"+"0"*40
        for sender, recipient, token_id in ((original.ACTOR,zero,2), (zero,original.ACTOR,9)):
            log = self.log("Transfer", [address(sender), address(recipient), word(token_id)])
            self.assertEqual(self.decoder(log,self.context),
                dict(event="Transfer", **{"from":sender, "to":recipient, "tokenId":str(token_id)}))

    def test_declared_event_decodes_exact_indexed_bill_and_ordered_currency_tail(self):
        currencies = ["0x"+"4"*64, "0x"+"3"*64]
        result = self.decoder(self.declared(currencies), self.context)
        self.assertEqual(result, dict(event="NFT0Declared", tokenId="9",
            **dict(original.REPLACEMENT, allowedCurrencies=currencies)))

    def test_dynamic_offset_count_truncation_padding_and_duplicate_currency_refuse(self):
        good = self.declared()
        raw = bytes.fromhex(good["data"][2:])
        bad_data = (raw[:64]+word(128)+raw[96:], raw[:96]+word(2)+raw[128:],
                    raw[:-1], raw+word(0), raw[:96]+word(0))
        for data in bad_data:
            with self.assertRaises(RemintLogRefused):
                self.decoder(dict(good,data=topic(data)),self.context)
        repeated = [original.REPLACEMENT["allowedCurrencies"][0]]*2
        with self.assertRaises(RemintLogRefused):
            self.decoder(self.declared(repeated), self.context)

    def test_reminted_event_decodes_actual_new_id_and_rejects_address_padding(self):
        log = self.log("NFT0Reminted", [bytes.fromhex(original.OP[2:]),word(2),word(9)],
            address(original.ACTOR)+bytes.fromhex(original.REPLACEMENT["billKey"][2:]))
        result = self.decoder(log,self.context)
        self.assertEqual(result, dict(event="NFT0Reminted",operationId=original.OP,
            oldTokenId="2",newTokenId="9",holder=original.ACTOR,billKey=original.REPLACEMENT["billKey"]))
        raw = bytes.fromhex(log["data"][2:])
        with self.assertRaises(RemintLogRefused):
            self.decoder(dict(log,data=topic(b"\x01"+raw[1:])), self.context)

    def test_original_context_scope_removal_and_quantity_mismatches_refuse(self):
        log = self.declared()
        for key, value in (("chainId",1), ("contract","0x"+"7"*40),
                           ("blockNumber",True), ("logIndex",1), ("transactionHash","0x"+"7"*64)):
            with self.assertRaises(RemintLogRefused):
                self.decoder(log,dict(self.context, **{key:value}))
        for key,value in (("removed",True), ("blockNumber","0x020"), ("address","0x"+"7"*40)):
            with self.assertRaises(RemintLogRefused):
                self.decoder(dict(log, **{key:value}), self.context)

    def test_unknown_event_is_none_but_known_topic_shape_or_zero_token_refuse(self):
        log = self.declared()
        self.assertIsNone(self.decoder(dict(log,topics=["0x"+"8"*64]),self.context))
        for topics in (log["topics"][:-1], log["topics"]+[topic(word(1))],
                       [log["topics"][0],topic(word(0)),log["topics"][2]]):
            with self.assertRaises(RemintLogRefused):
                self.decoder(dict(log,topics=topics),self.context)

    def test_real_abi_shaped_logs_join_original_receipt_observer_without_mutating_inputs(self):
        fixture = original.RemintReceiptObservationContracts("runTest")
        fixture.setUp()
        zero = "0x"+"0"*40
        logs = [
            self.log("Transfer",[address(original.ACTOR),address(zero),word(2)],index=0),
            self.log("Transfer",[address(zero),address(original.ACTOR),word(9)],index=1),
            dict(self.declared(),logIndex="0x2"),
            self.log("NFT0Reminted",[bytes.fromhex(original.OP[2:]),word(2),word(9)],
                address(original.ACTOR)+bytes.fromhex(original.REPLACEMENT["billKey"][2:]),index=3),
        ]
        receipt = dict(fixture.receipt,logs=logs)
        before = deepcopy(receipt)
        verified = []
        observer = RemintReceiptObserver(ReceiptGasObserver(
            lambda evidence: verified.append(evidence) is None), self.decoder)
        result = observer.observe(json.dumps(receipt).encode(), attempt_id="fixture-attempt",
            transaction_hash=original.TX, proof_reference="fixture-proof",
            contract=original.CONTRACT, operation_id=original.OP,old_token_id="2",
            actor=original.ACTOR,replacement=original.REPLACEMENT)
        self.assertEqual(result["status"],"CORRELATED_ORIGINAL_RECEIPT")
        self.assertEqual(result["newTokenId"],"9")
        self.assertEqual(result["actualGasWei"],"42000")
        self.assertFalse(result["financialMutation"])
        self.assertEqual(len(verified),1)
        self.assertEqual(receipt,before)
        self.assertNotIn(original.ACTOR,json.dumps(result))
