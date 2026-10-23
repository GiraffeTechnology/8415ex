"""ETH principal bridge definitions; synthetic, no native execution acceptance."""
from dataclasses import replace
import unittest

from exchange.errors import DomainError
from exchange.model import Asset
from exchange.settlement import EscrowPosition
from exchange.principal_journal_contract import PrincipalBinding, PrincipalJournalBridge
from integration.test_principal_journal_contract import authority, release, snapshot

BUYER = "0x" + "1" * 40
SELLER = "0x" + "2" * 40
NFT = "0x" + "4" * 40
TOKEN = "0x" + "3" * 40


class NativeETHPrincipalContracts(unittest.TestCase):
    def setUp(self):
        self.binding = PrincipalBinding(
            EscrowPosition("escrow-3", "receipt-1", 3, BUYER, SELLER, "ETH", 5000001),
            Asset(11155111, NFT, 19), "transfer-3", "ETH", 18,
            "native-op-3", "journal-3")
        self.bridge = PrincipalJournalBridge(lambda *args: True, lambda *args: True)

    def test_eth_freeze_uses_exact_wei_separate_from_gas(self):
        b = self.binding
        prepared = self.bridge.prepare("freeze", b, snapshot(b, "absent"), authority(b, "freeze"))
        request = prepared["request"]
        self.assertEqual(request["principalAsset"], "ETH")
        self.assertEqual(request["principalBaseUnits"], "5000001")
        self.assertEqual(request["debitBuyerBaseUnits"], "5000001")
        self.assertEqual(request["principalUnit"], "wei")
        self.assertEqual(request["gasAsset"], "ETH")
        self.assertFalse(request["combinePrincipalWithGas"])
        self.assertTrue(request["requiresNativeCASAndRecheck"])
        self.assertFalse(prepared["fundsDispatched"])

    def test_eth_release_and_refund_consume_original_principal_only(self):
        b = self.binding
        for action, proof, recipient in (("release", release(b), SELLER),
                                        ("refund", authority(b, "refund"), BUYER)):
            with self.subTest(action=action):
                prepared = self.bridge.prepare(action, b, snapshot(b), proof)
                self.assertEqual(prepared["originalFreezeReference"], "original-freeze-3")
                self.assertEqual(prepared["request"]["recipient"], recipient)
                self.assertEqual(prepared["request"]["debitBuyerBaseUnits"], "0")
                self.assertTrue(prepared["request"]["consumeOriginalFreeze"])
                self.assertFalse(prepared["request"]["restoreConsumedGas"])

    def test_eth_unknown_cannot_prepare_another_effect(self):
        b = self.binding
        for action in ("freeze", "release", "refund"):
            result = self.bridge.prepare(action, b, snapshot(b, "unknown"))
            self.assertEqual(result["disposition"], "RECONCILE_ONLY")
            self.assertIsNone(result["request"])

    def test_native_units_alias_and_currency_substitution_refused(self):
        b = self.binding
        for changed in (dict(token_decimals=6), dict(token_decimals=True),
                        dict(payment_token="eth"), dict(payment_token="WETH"),
                        dict(payment_token="0x" + "0" * 40), dict(payment_token=TOKEN)):
            with self.subTest(changed=changed), self.assertRaises(DomainError):
                replace(b, **changed)

    def test_eth_native_snapshot_must_bind_asset_kind_and_unit(self):
        b = self.binding
        for field, value in (("principalAssetKind", "ERC20"), ("principalUnit", "ETH")):
            raw = snapshot(b)
            raw["binding"][field] = value
            with self.subTest(field=field), self.assertRaises(DomainError):
                self.bridge.observe(b, raw)
        self.assertFalse(self.bridge.observe(b, snapshot(b))["gasAccounted"])

    def test_erc20_terms_keep_exact_existing_identity(self):
        b = replace(self.binding,
            position=replace(self.binding.position, quote_asset=TOKEN),
            payment_token=TOKEN, token_decimals=6)
        self.assertNotIn("principalAssetKind", b.terms)
        self.assertNotIn("principalUnit", b.terms)
        self.assertEqual(b.terms["paymentToken"], TOKEN)
        self.assertNotEqual(b.binding_digest, self.binding.binding_digest)
