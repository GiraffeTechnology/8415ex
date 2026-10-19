"""Synthetic regression definitions; NOT_RUN, never native execution evidence."""
from types import SimpleNamespace
import unittest
from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.price_balance import NFT0PriceBalanceGate
from exchange.eth_trade_gas import ETHTradeGasGate


class ETHPriceGasSeparation(unittest.TestCase):
    def match(self, currency="ETH", price=100):
        return SimpleNamespace(asset=F.asset(), buyer=F.B,
            sell_intent_digest="synthetic-sell", buy_intent_digest="synthetic-buy",
            quote_asset=currency, price=price)

    def gate(self, available, frozen=0):
        def read(request, now):
            return {"request": request, "currency": request["currency"], "unit": "base-units",
                "availableBaseUnits": available, "boundFrozenBaseUnits": frozen,
                "blockNumber": 10, "blockHash": "0x" + "1" * 64,
                "observedAt": now, "sourceReference": "synthetic-price-source"}
        return NFT0PriceBalanceGate(read, lambda request, row: True)

    def gas(self, available=100, required=10):
        return {"allowed": True, "asset": "ETH", "unit": "wei",
                "balanceWei": str(available), "reservedWei": "0", "requiredWei": str(required),
                "blockNumber": 10, "blockHash": "0x" + "1" * 64, "observedAt": 1000}

    def test_separately_sufficient_same_eth_is_rejected_if_sum_is_insufficient(self):
        report = self.gate(100).admit(self.match(), "ETH", None, 1000, self.gas())
        self.assertFalse(report["allowed"])
        self.assertEqual(report["code"], "EX_ETH_COMBINED_BALANCE_INSUFFICIENT")

    def test_exact_combined_boundary_passes_only_without_double_count(self):
        report = self.gate(110).admit(self.match(), "ETH", None, 1000, self.gas(110))
        self.assertTrue(report["allowed"])
        self.assertTrue(report["nativeAtomicRecheckRequired"])

    def test_existing_original_principal_freeze_covers_only_principal(self):
        match = self.match()
        self.assertTrue(self.gate(10, 100).admit(match, "ETH", "synthetic-escrow", 1000,
                                               self.gas(10))["allowed"])
        self.assertFalse(self.gate(9, 100).admit(match, "ETH", "synthetic-escrow", 1000,
                                                self.gas(9))["allowed"])
        self.assertFalse(self.gate(10, 100).admit(match, "ETH", None, 1000,
                                                self.gas(10))["allowed"])

    def test_missing_or_different_block_gas_evidence_cannot_be_combined(self):
        for gas in (None, dict(self.gas(110), blockNumber=11),
                    dict(self.gas(110), blockHash="0x" + "2" * 64),
                    dict(self.gas(110), observedAt=999)):
            with self.subTest(gas=gas):
                self.assertFalse(self.gate(110).admit(self.match(), "ETH", None, 1000, gas)["allowed"])

    def test_non_eth_price_does_not_consume_eth_gas_units(self):
        report = self.gate(100).admit(self.match("synthetic-token"), "synthetic-token",
                                    None, 1000, self.gas(10))
        self.assertTrue(report["allowed"])
        self.assertEqual(report["currency"], "synthetic-token")

    def test_empty_eth_prevents_principal_lock_without_creating_escrow(self):
        ex, clock = F.funded_exchange()
        match, _ = F.funded_hop(ex, F.A, F.B, 1, "transfer-empty-eth",
                               "session-a", "session-b", lock=False)
        def read(request, now):
            return {"request": request, "asset": "ETH", "unit": "wei", "balanceWei": 0,
                "reservedWei": 0, "requiredWei": 10, "blockNumber": 10,
                "blockHash": "0x" + "1" * 64, "observedAt": now,
                "sourceReference": "synthetic-empty-gas-source"}
        ex._eth_gas_gate = ETHTradeGasGate(read, lambda request, row: True)
        before_legs, before_escrows = len(ex.legs("rcpt-8415-0001")), dict(ex._escrows)
        with self.assertRaises(DomainError) as caught:
            ex.lock_escrow(match, "synthetic-lock-refused")
        self.assertEqual(caught.exception.code, "EX_ETH_GAS_EMPTY")
        self.assertEqual(ex._escrows, before_escrows)
        self.assertEqual(len(ex.legs("rcpt-8415-0001")), before_legs)
