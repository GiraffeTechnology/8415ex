"""Original gas prepayment recovery definitions, AUTHORED_NOT_RUN."""
from types import SimpleNamespace
import unittest
from exchange import fixtures as F
from exchange.eth_trade_gas import ETHTradeGasGate
from exchange.price_balance import NFT0PriceBalanceGate


class OriginalGasPrepayment(unittest.TestCase):
    def match(self):
        return SimpleNamespace(asset=F.asset(), buyer=F.B, sell_intent_digest="synthetic-sell",
            buy_intent_digest="synthetic-buy", price=100, quote_asset="ETH")

    def gate(self, bound=10, balance=0, required=10, verify=True):
        def read(request, now):
            return {"request": request, "asset": "ETH", "unit": "wei", "balanceWei": balance,
                "reservedWei": 0, "requiredWei": required, "boundGasWei": bound,
                "blockNumber": 10, "blockHash": "0x" + "1" * 64,
                "observedAt": now, "sourceReference": "synthetic-original-gas-journal"}
        return ETHTradeGasGate(read, lambda request, row: verify)

    def price(self, available, frozen):
        def read(request, now):
            return {"request": request, "currency": "ETH", "unit": "base-units",
                "availableBaseUnits": available, "boundFrozenBaseUnits": frozen,
                "blockNumber": 10, "blockHash": "0x" + "1" * 64, "observedAt": now,
                "sourceReference": "synthetic-original-principal-journal"}
        return NFT0PriceBalanceGate(read, lambda request, row: True)

    def test_exact_original_gas_freeze_avoids_second_prepayment(self):
        report = self.gate().admit(self.match(), 1000, "synthetic-original-escrow")
        self.assertTrue(report["allowed"])
        self.assertEqual((report["balanceWei"], report["boundGasWei"]), ("0", "10"))
        self.assertTrue(report["nativeAtomicRecheckRequired"])

    def test_fresh_operation_cannot_claim_an_original_gas_freeze(self):
        report = self.gate().admit(self.match(), 1000)
        self.assertFalse(report["allowed"])
        self.assertEqual(report["code"], "EX_ETH_GAS_UNVERIFIED")

    def test_consumed_prepayment_shortage_still_refuses(self):
        report = self.gate(bound=9).admit(self.match(), 1000, "synthetic-original-escrow")
        self.assertFalse(report["allowed"])
        self.assertEqual(report["code"], "EX_ETH_GAS_INSUFFICIENT")

    def test_zero_cash_and_zero_bound_eth_warns_and_refuses(self):
        report = self.gate(bound=0).admit(self.match(), 1000)
        self.assertFalse(report["allowed"])
        self.assertEqual(report["code"], "EX_ETH_GAS_EMPTY")

    def test_unverified_or_invalid_original_freeze_never_counts(self):
        for bound, verified in ((True, True), (-1, True), (2 ** 256, True), (10, False)):
            with self.subTest(bound=bound, verified=verified):
                report = self.gate(bound=bound, verify=verified).admit(
                    self.match(), 1000, "synthetic-original-escrow")
                self.assertFalse(report["allowed"])
                self.assertEqual(report["code"], "EX_ETH_GAS_UNVERIFIED")

    def test_original_operation_identity_reaches_authentication_verifier(self):
        observed = []
        gate = self.gate()
        gate.verify_native = lambda request, row: observed.append(request) or True
        self.assertTrue(gate.admit(self.match(), 1000, "synthetic-original-escrow")["allowed"])
        self.assertEqual(observed[0]["originalEscrowId"], "synthetic-original-escrow")
        self.assertEqual(observed[0]["buyIntentDigest"], "synthetic-buy")

    def test_original_principal_and_gas_freezes_are_disjoint(self):
        match = self.match()
        gas = self.gate().admit(match, 1000, "synthetic-original-escrow")
        self.assertTrue(self.price(0, 100).admit(match, "ETH", "synthetic-original-escrow",
                                                1000, gas)["allowed"])

    def test_excess_gas_freeze_cannot_pay_missing_principal(self):
        match = self.match()
        gas = self.gate(bound=110).admit(match, 1000, "synthetic-original-escrow")
        report = self.price(99, 0).admit(match, "ETH", "synthetic-original-escrow", 1000, gas)
        self.assertFalse(report["allowed"])
