"""Definitions for approved remote Linux QA; no live financial acceptance."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from exchange.public_workbench import snapshot, command_result
from exchange.workbench import WorkbenchHandler


SECRET = "wallet-private-identity"


def original():
    segment = {"legIndex": 3, "seller": SECRET, "buyer": SECRET,
               "principal": "123456789012345678901", "principalAsset": "USDC", "principalUnit": "base-units",
               "escrowStatus": "locked", "paymentStatus": "unknown", "registrationStatus": "pending",
               "fundingStatus": "release-outcome-unknown", "rollbackStatus": "available",
               "released": False, "refunded": False, "netToPayee": "0", "netToPayer": "0",
               "gasBorneBy": SECRET, "gasAsset": "ETH", "gasUnit": "wei", "gasTotal": "7001",
               "gasEntries": [{"bearer": SECRET, "note": SECRET, "amount": 7001, "asset": "ETH", "unit": "wei",
                               "sharedWith": (3, 4), "sharedOperation": True, "apportionment": "undecided"}]}
    return {"revision": "a" * 64, "commandGateway": "configured", "source": {"commit": "b" * 40, "tree": "c" * 40, "account": SECRET},
            "state": {"receipt": {"receiptId": SECRET, "owner": {"account": SECRET, "position": 4},
                                  "holder": {"account": SECRET, "position": 1}, "mintDeclaration": {"raw": SECRET}},
                      "funds": {"segments": [segment], "futurePrivateField": SECRET},
                      "rollback": {"open": True, "state": "blocked", "complete": False, "returnBoundaryAccount": SECRET,
                                   "lastFinalizedPosition": 1, "affectedLegs": (2, 3),
                                   "outstandingSteps": [{"stepId": SECRET, "legIndex": 3, "status": "blocked", "detail": {"account": SECRET}}]},
                      "overdue": [{"legIndex": 3, "commitmentDeadlineAt": 1700, "account": SECRET}],
                      "exit": {"requester": SECRET}, "timeline": [{"account": SECRET}], "authorizations": [{"session": SECRET}]}}


class PublicWorkbenchProjection(unittest.TestCase):
    def test_unknown_and_nested_private_fields_are_not_http_output(self):
        public = snapshot(original())
        encoded = json.dumps(public)
        self.assertNotIn(SECRET, encoded)
        for field in ("mintDeclaration", "returnBoundaryAccount", "authorizations", "session", "futurePrivateField"):
            self.assertNotIn(field, encoded)

    def test_principal_and_eth_gas_remain_exact_separate_assets_units_and_positions(self):
        row = snapshot(original())["state"]["funds"]["segments"][0]
        self.assertEqual((row["principal"], row["principalAsset"], row["principalUnit"]), ("123456789012345678901", "USDC", "base-units"))
        self.assertEqual((row["gasTotal"], row["gasAsset"], row["gasUnit"]), ("7001", "ETH", "wei"))
        self.assertEqual((row["sellerPosition"], row["buyerPosition"], row["gasBearerPosition"]), (3, 4, 4))
        self.assertEqual(row["gasBearerRole"], "this-leg-buyer")
        self.assertEqual(row["paymentStatus"], "unknown")
        self.assertFalse(row["released"])
        self.assertFalse(row["refunded"])

    def test_shared_gas_is_preserved_once_without_inventing_allocation(self):
        rows = snapshot(original())["state"]["funds"]["segments"]
        self.assertEqual(len(rows[0]["gasEntries"]), 1)
        self.assertEqual(rows[0]["gasEntries"][0], {"amount": "7001", "asset": "ETH", "unit": "wei",
                          "sharedWith": [3, 4], "sharedOperation": True, "apportionment": "undecided"})
        raw = original()
        raw["state"]["funds"]["segments"][0]["gasBorneBy"] = "different-private-party"
        row = snapshot(raw)["state"]["funds"]["segments"][0]
        self.assertEqual(row["gasBearerRole"], "unknown")
        self.assertIsNone(row["gasBearerPosition"])

    def test_invalid_amount_and_state_are_unknown_instead_of_zero_or_echoed_text(self):
        raw = original()
        row = raw["state"]["funds"]["segments"][0]
        row.update(principal=SECRET, principalAsset=SECRET, paymentStatus=SECRET, gasTotal="1.5")
        public = snapshot(raw)["state"]["funds"]["segments"][0]
        self.assertIsNone(public["principal"])
        self.assertIsNone(public["principalAsset"])
        self.assertIsNone(public["gasTotal"])
        self.assertEqual(public["paymentStatus"], "unknown")

    def test_private_state_revision_and_original_backend_records_are_unchanged(self):
        raw = original()
        before = deepcopy(raw)
        result = snapshot(raw)
        self.assertEqual(raw, before)
        self.assertEqual(result["revision"], raw["revision"])
        self.assertEqual(result["state"]["positions"], {"owner": 4, "holder": 1})
        self.assertEqual(result["state"]["rollback"]["lastFinalizedPosition"], 1)

    def test_gateway_arbitrary_text_and_party_bearing_reference_are_not_echoed(self):
        self.assertEqual(command_result({"status": SECRET, "code": SECRET, "state": SECRET, "operationId": SECRET,
                                         "transactionHash": SECRET}), {"status": "unknown"})
        tx = "0x" + "d" * 64
        self.assertEqual(command_result({"status": "pending", "transactionHash": tx}), {"status": "pending", "transactionHash": tx})

    def test_actual_http_snapshot_dispatch_uses_public_projection(self):
        bodies = []
        handler = SimpleNamespace(path="/api/snapshot", host_ok=lambda: True,
            server=SimpleNamespace(binding=SimpleNamespace(snapshot=original)),
            send_body=lambda *args, **kwargs: bodies.append(args))
        WorkbenchHandler.do_GET(handler)
        self.assertEqual(bodies[0][0], 200)
        self.assertNotIn(SECRET, bodies[0][1])
        self.assertEqual(json.loads(bodies[0][1])["schema"], "8415ex-public-workbench/2")

    def test_actual_http_refusal_does_not_echo_original_exception_text(self):
        bodies = []
        def refused():
            raise ValueError(SECRET)
        handler = SimpleNamespace(path="/api/snapshot", host_ok=lambda: True,
            server=SimpleNamespace(binding=SimpleNamespace(snapshot=refused)),
            send_body=lambda *args, **kwargs: bodies.append(args))
        WorkbenchHandler.do_GET(handler)
        self.assertEqual(bodies[0][0], 400)
        self.assertNotIn(SECRET, bodies[0][1])
