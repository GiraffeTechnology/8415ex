"""Exact refusal diagnostics from synthetic verified rows, never live funds proof."""
from dataclasses import replace
import unittest

from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.eth_trade_gas import ETHTradeGasGate
from exchange.price_balance import NFT0PriceBalanceGate
from exchange.ledger import MatchResult


class BalanceRefusalAmounts(unittest.TestCase):
    def setUp(self):
        self.now = F.ManualClock().now
        self.match = MatchResult(sell_intent_digest="0x" + "a" * 64,
            buy_intent_digest="0x" + "b" * 64, seller=F.A, buyer=F.B,
            asset=F.asset(), price=100, quote_asset="ETH", units=1,
            basis={"scope": "synthetic-only"}, matched_at=self.now)

    def gas(self, balance, reserved, required, bound=0, verified=True):
        def read(request, now):
            return {"request": request, "asset": "ETH", "unit": "wei", "balanceWei": balance,
                "reservedWei": reserved, "requiredWei": required, "boundGasWei": bound,
                "blockNumber": 9, "blockHash": "0x" + "1" * 64, "observedAt": now,
                "sourceReference": "synthetic-row-only"}
        return ETHTradeGasGate(read, lambda *args: verified)

    def price(self, available, bound=0, verified=True):
        def read(request, now):
            return {"request": request, "currency": request["currency"], "unit": "base-units",
                "availableBaseUnits": available, "boundFrozenBaseUnits": bound,
                "blockNumber": 9, "blockHash": "0x" + "1" * 64, "observedAt": now,
                "sourceReference": "synthetic-row-only"}
        return NFT0PriceBalanceGate(read, lambda *args: verified)

    def test_zero_eth_refusal_exposes_required_and_shortfall_in_wei(self):
        report = self.gas(0, 0, 7).admit(self.match, self.now)
        self.assertFalse(report["allowed"])
        self.assertEqual(report["code"], "EX_ETH_GAS_EMPTY")
        self.assertEqual((report["availableWei"], report["requiredWei"], report["shortfallWei"]), ("0", "7", "7"))
        self.assertIn("No ETH", report["warning"])
        self.assertIn("shortfall 7 wei", report["warning"])

    def test_other_reservations_are_excluded_from_available_eth(self):
        report = self.gas(10, 9, 4).admit(self.match, self.now)
        self.assertEqual(report["code"], "EX_ETH_GAS_INSUFFICIENT")
        self.assertEqual((report["balanceWei"], report["reservedWei"], report["availableWei"]), ("10", "9", "1"))
        self.assertEqual(report["shortfallWei"], "3")

    def test_original_bound_gas_reduces_only_the_same_obligations_shortfall(self):
        insufficient = self.gas(0, 0, 4, bound=3).admit(self.match, self.now, "original-escrow")
        self.assertEqual(insufficient["shortfallWei"], "1")
        self.assertEqual(insufficient["boundGasWei"], "3")
        covered = self.gas(0, 0, 4, bound=4).admit(self.match, self.now, "original-escrow")
        self.assertTrue(covered["allowed"])
        new_trade = self.gas(0, 0, 4, bound=4).admit(self.match, self.now)
        self.assertEqual(new_trade["code"], "EX_ETH_GAS_UNVERIFIED")

    def test_selected_currency_principal_refusal_keeps_separate_base_units(self):
        match = replace(self.match, quote_asset="TOKEN_A")
        report = self.price(4, bound=3).admit(match, "TOKEN_A", "original-escrow", self.now)
        self.assertEqual(report["code"], "EX_PRICE_BALANCE_INSUFFICIENT")
        self.assertEqual(report["currency"], "TOKEN_A")
        self.assertEqual((report["availableBaseUnits"], report["boundFrozenBaseUnits"],
                          report["requiredPrincipalBaseUnits"], report["shortfallBaseUnits"]), ("4", "3", "100", "93"))
        self.assertFalse(report["conversionPerformed"])
        self.assertNotIn("availableWei", report)

    def test_combined_eth_failure_explains_disjoint_principal_and_gas_liabilities(self):
        gas = self.gas(100, 0, 7).admit(self.match, self.now)
        report = self.price(100).admit(self.match, "ETH", None, self.now, gas)
        self.assertEqual(report["code"], "EX_ETH_COMBINED_BALANCE_INSUFFICIENT")
        self.assertEqual((report["remainingPrincipalWei"], report["unfundedGasWei"],
                          report["requiredUnfrozenWei"], report["shortfallWei"]), ("100", "7", "107", "7"))
        self.assertFalse(report["conversionPerformed"])

    def test_unverified_rows_do_not_publish_invented_or_untrusted_amounts(self):
        gas = self.gas(123, 0, 999, verified=False).admit(self.match, self.now)
        self.assertEqual(gas["code"], "EX_ETH_GAS_UNVERIFIED")
        self.assertNotIn("availableWei", gas)
        self.assertNotIn("shortfallWei", gas)
        price = self.price(123, verified=False).admit(self.match, "ETH", None, self.now)
        self.assertEqual(price["code"], "EX_PRICE_BALANCE_UNVERIFIED")
        self.assertNotIn("availableBaseUnits", price)

    def test_actual_transfer_refusal_surfaces_amount_warning_before_forming_a_leg(self):
        exchange, clock = F.minted()
        for account, label, side, nonce in ((F.A, "a", "sell", 1), (F.B, "b", "buy", 2)):
            exchange.connect_wallet(account, "session-" + label)
            exchange.register_authorization(F.authorization(account, "grant-" + label, "session-" + label))
            exchange.submit_intent(F.intent("intent-" + label, side, account, "grant-" + label, None, nonce))
        match = exchange.match_intents("intent-a", "intent-b")
        exchange._eth_gas_gate = self.gas(0, 0, 7)
        with self.assertRaises(DomainError) as caught:
            exchange.execute_transfer(match, "refused-transfer")
        self.assertEqual(caught.exception.code, "EX_ETH_GAS_EMPTY")
        self.assertIn("shortfall 7 wei", caught.exception.detail)
        self.assertEqual(exchange.recorded_legs(F.receipt().receipt_id), 0)
        self.assertFalse(exchange._escrows)
