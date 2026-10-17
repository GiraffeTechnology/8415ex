"""Synthetic contract regressions; no wallet, provider or native store."""
import unittest
from copy import deepcopy
from dataclasses import replace

from exchange.errors import DomainError
from exchange.model import Asset
from exchange.settlement import EscrowPosition, ReleaseAuthority, segment_binding
from exchange.principal_journal_contract import PrincipalBinding, PrincipalJournalBridge

BUYER = "0x" + "1" * 40
SELLER = "0x" + "2" * 40
TOKEN = "0x" + "3" * 40
NFT = "0x" + "4" * 40


def binding(leg=3):
    return PrincipalBinding(
        EscrowPosition("escrow-3", "receipt-1", leg, BUYER, SELLER, TOKEN, 5000001),
        Asset(11155111, NFT, 19), "transfer-3", TOKEN, 6, "native-op-3", "journal-3")


def snapshot(b, state="frozen", revision=7):
    values = {"absent": (0, 0, 0), "frozen": (5000001, 0, 0),
              "released": (0, 5000001, 0), "refunded": (0, 0, 5000001),
              "unknown": (None, None, None)}[state]
    return dict(binding=b.terms, sourceReference="original-principal-source", revision=revision,
                state=state, freezeReference=None if state == "absent" else "original-freeze-3",
                lockedBaseUnits=values[0], releasedBaseUnits=values[1], refundedBaseUnits=values[2],
                pendingAction="release" if state == "unknown" else None)


def release(b):
    p = b.position
    return ReleaseAuthority("authority-3", "original-registry-source", p.receipt_id, p.leg_index,
        b.transfer_id, b.asset, b.journal_reference,
        segment_binding(b.asset, p.receipt_id, p.leg_index, b.transfer_id,
                        p.payer, p.payee, p.principal, p.quote_asset, b.journal_reference), 100)


def authority(b, action):
    return dict(authorityReference="native-authority-3", bindingDigest=b.binding_digest,
                action=action, journalReference=b.journal_reference)


class PrincipalJournalContractTests(unittest.TestCase):
    def setUp(self):
        self.b = binding()
        self.calls = []
        self.bridge = PrincipalJournalBridge(
            lambda b, s: True,
            lambda a, b, s, e: self.calls.append(a) is None)

    def test_local_escrow_is_not_native_freeze(self):
        with self.assertRaises(DomainError):
            self.bridge.observe(self.b, self.b.position)
        refused = PrincipalJournalBridge(lambda b, s: False, lambda *args: True)
        with self.assertRaises(DomainError):
            refused.observe(self.b, snapshot(self.b))
        self.assertEqual(self.calls, [])

    def test_freeze_uses_exact_token_units_and_separate_eth(self):
        s = snapshot(self.b, "absent")
        result = self.bridge.prepare("freeze", self.b, s, authority(self.b, "freeze"))
        r = result["request"]
        self.assertEqual(r["principalAsset"], TOKEN)
        self.assertEqual(r["principalBaseUnits"], "5000001")
        self.assertEqual(r["debitBuyerBaseUnits"], "5000001")
        self.assertEqual(r["gasAsset"], "ETH")
        self.assertFalse(r["restoreConsumedGas"])
        self.assertFalse(result["fundsDispatched"])

    def test_release_consumes_same_freeze_without_second_payment(self):
        result = self.bridge.prepare("release", self.b, snapshot(self.b), release(self.b))
        self.assertEqual(result["originalFreezeReference"], "original-freeze-3")
        self.assertEqual(result["request"]["debitBuyerBaseUnits"], "0")
        self.assertEqual(result["request"]["recipient"], SELLER)
        self.assertTrue(result["request"]["consumeOriginalFreeze"])
        self.assertEqual(result["authority"]["binding"], release(self.b).binding)

    def test_refund_returns_original_buyer_and_keeps_consumed_gas(self):
        result = self.bridge.prepare("refund", self.b, snapshot(self.b), authority(self.b, "refund"))
        self.assertEqual(result["request"]["recipient"], BUYER)
        self.assertEqual(result["request"]["debitBuyerBaseUnits"], "0")
        self.assertFalse(result["request"]["restoreConsumedGas"])

    def test_unknown_is_only_reconciliation_for_every_action(self):
        for action in ("freeze", "release", "refund"):
            result = self.bridge.prepare(action, self.b, snapshot(self.b, "unknown"))
            self.assertEqual(result["disposition"], "RECONCILE_ONLY")
            self.assertIsNone(result["request"])
        self.assertEqual(self.calls, [])
        self.assertTrue(self.bridge.observe(self.b, snapshot(self.b, "unknown"))["reconcileOnly"])

    def test_terminal_idempotence_and_exclusive_outcomes(self):
        for action, state in (("release", "released"), ("refund", "refunded"), ("freeze", "frozen")):
            r = self.bridge.prepare(action, self.b, snapshot(self.b, state))
            self.assertEqual(r["disposition"], "ALREADY_RECORDED")
            self.assertIsNone(r["request"])
        for action, state in (("release", "refunded"), ("refund", "released"), ("freeze", "released")):
            with self.assertRaises(DomainError):
                self.bridge.prepare(action, self.b, snapshot(self.b, state))
        self.assertEqual(self.calls, [])

    def test_exact_asset_leg_operation_binding(self):
        for field, changed in (("chainId", 560048), ("tokenId", "20"),
                               ("globalLegId", 4), ("nativeOperationId", "other-op"),
                               ("journalReference", "other-journal"), ("paymentToken", NFT)):
            s = snapshot(self.b)
            s["binding"][field] = changed
            with self.assertRaises(DomainError):
                self.bridge.observe(self.b, s)

    def test_false_native_values_and_extra_fields_refused(self):
        bad = []
        for field, value in (("revision", True), ("lockedBaseUnits", 5000001.0),
                             ("releasedBaseUnits", 1), ("pendingAction", "release")):
            s = snapshot(self.b); s[field] = value; bad.append(s)
        s = snapshot(self.b); s["extra"] = "not-a-native-proof"; bad.append(s)
        s = snapshot(self.b, "unknown"); s["lockedBaseUnits"] = 5000001; bad.append(s)
        b = binding(1); s = snapshot(b); s["binding"]["globalLegId"] = True
        with self.assertRaises(DomainError):
            self.bridge.observe(b, s)
        for s in bad:
            with self.assertRaises(DomainError):
                self.bridge.observe(self.b, s)

    def test_release_requires_matching_original_authority(self):
        original = release(self.b)
        for changed in (replace(original, transfer_id="other-transfer"),
                        replace(original, leg_index=4),
                        replace(original, journal_reference="other-journal"),
                        replace(original, asset=Asset(11155111, NFT, 20))):
            with self.assertRaises(DomainError):
                self.bridge.prepare("release", self.b, snapshot(self.b), changed)
        refused = PrincipalJournalBridge(lambda *args: True, lambda *args: False)
        with self.assertRaises(DomainError):
            refused.prepare("release", self.b, snapshot(self.b), original)

    def test_action_authority_must_bind_original_journal(self):
        a = authority(self.b, "refund"); a["journalReference"] = "other-journal"
        with self.assertRaises(DomainError):
            self.bridge.prepare("refund", self.b, snapshot(self.b), a)
        with self.assertRaises(DomainError):
            self.bridge.prepare("freeze", self.b, snapshot(self.b, "absent"), "VALID")

    def test_stable_key_detached_output_and_native_cas(self):
        s = snapshot(self.b)
        r = self.bridge.prepare("release", self.b, s, release(self.b))
        r2 = self.bridge.prepare("release", self.b, snapshot(self.b, revision=8), release(self.b))
        self.assertEqual(r["operationKey"], r2["operationKey"])
        self.assertNotEqual(r["expectedNativeRevision"], r2["expectedNativeRevision"])
        self.assertTrue(r["request"]["requiresNativeCASAndRecheck"])
        r["binding"]["buyer"] = SELLER
        self.assertEqual(self.b.terms["buyer"], BUYER)
        self.assertEqual(s["binding"]["buyer"], BUYER)

    def test_sepolia_token_config_and_exact_units_required(self):
        with self.assertRaises(DomainError):
            replace(self.b, asset=Asset(560048, NFT, 19))
        with self.assertRaises(DomainError):
            replace(self.b, payment_token=NFT)
        with self.assertRaises(DomainError):
            replace(self.b, token_decimals=True)
        s = snapshot(self.b, "frozen")
        r = self.bridge.observe(self.b, s)
        self.assertTrue(r["principalKnownFrozen"])
        self.assertFalse(r["gasAccounted"])
        self.assertEqual(r["tradeAdmission"], "NOT_PERFORMED")
