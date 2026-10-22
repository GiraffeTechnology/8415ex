"""Synthetic existing-operation correlations, no Wallet/provider execution."""
from copy import deepcopy
from dataclasses import replace
import unittest

from exchange.model import Asset
from exchange.rollback import RollbackAuthority, rollback_binding
from exchange.wallet_direct_return_operation import (
    bind_wallet_direct_return, DirectReturnOperationRefused)

OWNER = "0x" + "a" * 40
HOLDER = "0x" + "b" * 40
CONTRACT = "0x" + "c" * 40


def fixture():
    asset = Asset(11155111, CONTRACT, 7)
    legs = ["leg-b-c", "leg-c-d"]
    authority = RollbackAuthority("authority-1", "original-control", "receipt-1",
        3, asset, HOLDER, rollback_binding(asset, "receipt-1", 3, HOLDER, legs), 100)
    scope = {"receiptId": "receipt-1", "chainId": 11155111, "contract": CONTRACT,
             "tokenId": "7", "globalLegId": 3, "action": "rollback",
             "nativeOperationId": "native-return-1", "intentDigest": "d" * 64,
             "journalReference": "original-journal-1"}
    operation = {"kind": "erc721-transfer", "chainId": "11155111", "actor": OWNER,
                 "contract": CONTRACT, "recipient": HOLDER, "tokenId": "7"}
    return scope, authority, legs, operation


class OriginalWalletDirectReturnContracts(unittest.TestCase):
    def test_one_existing_direct_transfer_keeps_original_native_scope(self):
        scope, authority, legs, operation = fixture()
        result = bind_wallet_direct_return(scope, authority, OWNER, legs, operation)
        self.assertEqual(result["scope"], scope)
        self.assertEqual(result["operation"], operation)
        self.assertEqual(result["assetControlOperations"], 1)
        self.assertFalse(result["walkedIntermediateWallets"])
        self.assertFalse(result["dispatchAuthorized"])
        self.assertFalse(result["nativeOutcomeVerified"])

    def test_intermediate_or_different_recipient_cannot_replace_boundary(self):
        scope, authority, legs, operation = fixture()
        for recipient in (OWNER, "0x" + "e" * 40):
            with self.subTest(recipient=recipient), self.assertRaises(
                    DirectReturnOperationRefused):
                bind_wallet_direct_return(scope, authority, OWNER, legs,
                                           dict(operation, recipient=recipient))

    def test_return_hop_arbitrary_call_or_extra_fields_are_not_direct_transfer(self):
        scope, authority, legs, operation = fixture()
        for changed in (dict(operation, kind="return-hop"),
                        dict(operation, kind="arbitrary-call"),
                        dict(operation, data="0x"),
                        dict(operation, chainId=11155111),
                        dict(operation, tokenId="07")):
            with self.subTest(changed=changed), self.assertRaises(
                    DirectReturnOperationRefused):
                bind_wallet_direct_return(scope, authority, OWNER, legs, changed)

    def test_receipt_asset_leg_or_action_drift_refuses_original_scope(self):
        scope, authority, legs, operation = fixture()
        for changes in ({"receiptId": "other"}, {"tokenId": "8"},
                        {"contract": "0x" + "e" * 40}, {"globalLegId": 4},
                        {"action": "refund"}):
            with self.subTest(changes=changes), self.assertRaises(
                    DirectReturnOperationRefused):
                bind_wallet_direct_return(dict(scope, **changes), authority,
                                           OWNER, legs, operation)

    def test_original_interval_cannot_be_reordered_dropped_or_rebound(self):
        scope, authority, legs, operation = fixture()
        for changed in (legs[::-1], legs[:1], []):
            with self.subTest(changed=changed), self.assertRaises(
                    DirectReturnOperationRefused):
                bind_wallet_direct_return(scope, authority, OWNER, changed, operation)
        with self.assertRaises(DirectReturnOperationRefused):
            bind_wallet_direct_return(scope, replace(authority, boundary_account=OWNER),
                                       OWNER, legs, operation)

    def test_results_are_detached_and_do_not_mutate_originals(self):
        scope, authority, legs, operation = fixture()
        original = deepcopy((scope, legs, operation))
        result = bind_wallet_direct_return(scope, authority, OWNER, legs, operation)
        result["scope"]["nativeOperationId"] = "other"
        result["operation"]["recipient"] = OWNER
        result["affectedLegs"].clear()
        self.assertEqual((scope, legs, operation), original)
        result = bind_wallet_direct_return(scope, authority, OWNER, legs, operation)
        self.assertEqual(result["operation"]["recipient"], HOLDER)
