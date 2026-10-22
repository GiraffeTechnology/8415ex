"""Synthetic authenticated-port definitions; no real transaction or RPC."""
from copy import deepcopy
import json
import unittest
from exchange.receipt_gas_observer import ReceiptGasObserver
from exchange.remint_receipt_observation import RemintReceiptObserver, RemintReceiptRefused, ZERO

CONTRACT, ACTOR = "0x"+"1"*40, "0x"+"2"*40
TX, BLOCK, OP = "0x"+"a"*64, "0x"+"b"*64, "0x"+"c"*64
REPLACEMENT = {"billKey":"0x"+"d"*64, "termsHash":"0x"+"e"*64,
               "currencyDeclarationHash":"0x"+"f"*64, "allowedCurrencies":["0x"+"3"*64]}


class RemintReceiptObservationContracts(unittest.TestCase):
    def setUp(self):
        self.verifications, self.decodes = [], []
        self.events = [
            {"event":"Transfer", "from":ACTOR, "to":ZERO, "tokenId":"2"},
            {"event":"Transfer", "from":ZERO, "to":ACTOR, "tokenId":"9"},
            {"event":"NFT0Declared", "tokenId":"9", **deepcopy(REPLACEMENT)},
            {"event":"NFT0Reminted", "operationId":OP, "oldTokenId":"2",
             "newTokenId":"9", "holder":ACTOR, "billKey":REPLACEMENT["billKey"]},
        ]
        self.receipt = {"transactionHash":TX, "blockHash":BLOCK, "blockNumber":"0x20",
            "gasUsed":"0x5208", "effectiveGasPrice":"0x2", "status":"0x1", "type":"0x2",
            "logs":[{"address":CONTRACT, "transactionHash":TX, "blockHash":BLOCK,
                     "blockNumber":"0x20", "logIndex":hex(i), "removed":False,
                     "topics":[], "data":"fixture-"+str(i)} for i in range(4)]}
        self.verified = True
        def verify(evidence):
            self.verifications.append(evidence)
            return self.verified
        def decode(log, context):
            self.decodes.append((deepcopy(log),deepcopy(context)))
            return deepcopy(self.events[int(log["data"].split("-")[1])])
        self.observer = RemintReceiptObserver(ReceiptGasObserver(verify), decode)

    def observe(self, value=None):
        raw = json.dumps(self.receipt if value is None else value).encode()
        return self.observer.observe(raw, attempt_id="fixture-attempt", transaction_hash=TX,
            proof_reference="private-original-proof", contract=CONTRACT, operation_id=OP,
            old_token_id="2", actor=ACTOR, replacement=REPLACEMENT)

    def test_original_success_correlates_all_events_and_derives_actual_new_id(self):
        result = self.observe()
        self.assertEqual(result["status"], "CORRELATED_ORIGINAL_RECEIPT")
        self.assertEqual(result["newTokenId"], "9")
        self.assertEqual(result["actualGasWei"], str(21000*2))
        self.assertEqual(result["declaration"], REPLACEMENT)
        self.assertEqual(result["logIndices"], {"oldBurn":0,"newMint":1,"declaration":2,"remint":3})
        public = json.dumps(result)
        for private in (ACTOR, CONTRACT, "private-original-proof", "fixture-"):
            self.assertNotIn(private, public)
        self.assertEqual(len(self.verifications), 1)
        self.assertEqual(len(self.decodes), 4)

    def test_not_mined_failed_and_no_event_are_distinct_and_never_allow_replay(self):
        raw = b"null"
        pending = self.observer.observe(raw, attempt_id="fixture-attempt", transaction_hash=TX,
            proof_reference="private-original-proof", contract=CONTRACT, operation_id=OP,
            old_token_id="2", actor=ACTOR, replacement=REPLACEMENT)
        self.assertEqual(pending["status"], "NOT_MINED_AT_READ")
        self.assertIsNone(pending["actualGasWei"])
        failed = self.observe(dict(self.receipt, status="0x0"))
        self.assertEqual(failed["status"], "FAILED_RECEIPT")
        self.assertEqual(failed["actualGasWei"], "42000")
        no_event = self.observe(dict(self.receipt, logs=[]))
        self.assertEqual(no_event["status"], "NO_MATCHING_EVENT_AT_READ")
        for value in (pending, failed, no_event):
            self.assertFalse(value["replayAllowed"])
            self.assertEqual(value["businessAcceptance"], "NOT_ESTABLISHED")
            self.assertFalse(value["financialMutation"])
        self.assertEqual(self.decodes, [])

    def test_wrong_operation_event_is_not_absence_but_wrong_bound_event_is_refused(self):
        self.events[3]["operationId"] = "0x"+"4"*64
        self.assertEqual(self.observe()["status"], "NO_MATCHING_EVENT_AT_READ")
        self.events[3]["operationId"] = OP
        for field, value in (("oldTokenId","4"), ("holder","0x"+"5"*40),
                             ("billKey","0x"+"6"*64), ("newTokenId","2")):
            before = deepcopy(self.events[3])
            self.events[3][field] = value
            with self.assertRaises(RemintReceiptRefused):
                self.observe()
            self.events[3] = before

    def test_log_block_transaction_removal_and_order_conflicts_refuse(self):
        for field, value in (("transactionHash","0x"+"7"*64), ("blockHash","0x"+"8"*64),
                             ("blockNumber","0x21"), ("removed",True), ("logIndex","0x0")):
            before = deepcopy(self.receipt)
            self.receipt["logs"][1][field] = value
            with self.assertRaises(RemintReceiptRefused):
                self.observe()
            self.receipt = before

    def test_missing_burn_mint_declaration_or_wrong_original_event_order_refuse(self):
        for index in (0,1,2):
            before = deepcopy(self.events)
            self.events[index]["event"] = "UnrelatedFixtureEvent"
            with self.assertRaises(RemintReceiptRefused):
                self.observe()
            self.events = before
        self.events[0], self.events[1] = self.events[1], self.events[0]
        with self.assertRaises(RemintReceiptRefused):
            self.observe()

    def test_replacement_terms_currency_changes_and_duplicate_events_are_refused(self):
        for key, value in (("termsHash","0x"+"7"*64),
                           ("allowedCurrencies",["0x"+"8"*64])):
            before = deepcopy(self.events[2])
            self.events[2][key] = value
            with self.assertRaises(RemintReceiptRefused):
                self.observe()
            self.events[2] = before
        self.receipt["logs"].append(dict(self.receipt["logs"][3], logIndex="0x4"))
        with self.assertRaises(RemintReceiptRefused):
            self.observe()

    def test_original_verification_precedes_abi_decode_and_errors_do_not_echo(self):
        self.verified = False
        with self.assertRaises(RemintReceiptRefused):
            self.observe()
        self.assertEqual(self.decodes, [])
        self.verified = True
        def fail(*args):
            raise RuntimeError("PRIVATE_DECODER_SENTINEL")
        self.observer.decode_original_log = fail
        with self.assertRaises(RemintReceiptRefused) as raised:
            self.observe()
        self.assertNotIn("PRIVATE_DECODER_SENTINEL", str(raised.exception))

    def test_observation_does_not_mutate_original_inputs_or_establish_settlement(self):
        before = deepcopy((self.receipt, self.events, REPLACEMENT))
        result = self.observe()
        result["declaration"]["allowedCurrencies"].clear()
        self.assertEqual((self.receipt,self.events,REPLACEMENT), before)
        self.assertEqual(result["businessAcceptance"], "NOT_ESTABLISHED")
        self.assertFalse(result["replayAllowed"])
        self.assertNotIn("owner", result)
        self.assertNotIn("holder", result)
