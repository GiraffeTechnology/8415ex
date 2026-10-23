"""Synthetic balance and NFT0 denomination cases; not live wallet evidence."""
from dataclasses import replace
import unittest
from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.price_balance import NFT0PriceBalanceGate


class NFT0PriceAdmission(unittest.TestCase):
    def setUp(self):
        self.ex, self.clock = F.funded_exchange()
        self.match, _ = F.funded_hop(self.ex, F.A, F.B, 1, "transfer-price",
                                    "session-a", "session-b", lock=False)
        self.available = self.match.price
        self.frozen = 0
        self.currency = F.QUOTE_ASSET

    def gate(self, verify=True):
        def read(request, now):
            return {"request": request, "currency": self.currency, "unit": "base-units",
                    "availableBaseUnits": self.available, "boundFrozenBaseUnits": self.frozen,
                    "blockNumber": 1, "blockHash": "0x" + "11" * 32, "observedAt": now,
                    "sourceReference": "fixture-only"}
        return NFT0PriceBalanceGate(read, lambda request, row: verify)

    def test_nft0_currency_is_immutable_mint_metadata_not_exchange_default(self):
        receipt = self.ex.receipt("rcpt-8415-0001")
        self.assertEqual(receipt.price_currency, F.QUOTE_ASSET)
        view = self.ex.receipt_view(receipt.receipt_id)
        self.assertEqual(view["priceCurrency"], F.QUOTE_ASSET)
        self.assertFalse(view["conversionAvailable"])
        self.assertEqual(view["mintDeclaration"]["receipt"]["price_currency"], F.QUOTE_ASSET)

    def test_other_price_currency_is_not_converted_even_with_large_balance(self):
        self.available = 10 ** 30
        changed = replace(self.match, quote_asset="another-currency")
        result = self.gate().admit(changed, F.QUOTE_ASSET, None, self.clock())
        self.assertEqual(result["code"], "EX_NFT0_CURRENCY_MISMATCH")
        self.assertFalse(result["allowed"])

    def test_insufficient_price_blocks_before_escrow_even_with_eth(self):
        self.available -= 1
        self.ex._price_balance_gate = self.gate()
        with self.assertRaises(DomainError) as caught:
            self.ex.lock_escrow(self.match, "escrow-price")
        self.assertEqual(caught.exception.code, "EX_PRICE_BALANCE_INSUFFICIENT")
        self.assertEqual(self.ex.recorded_legs("rcpt-8415-0001"), 0)
        self.assertNotIn("escrow-price", self.ex._escrows)

    def test_exact_balance_and_original_frozen_units_are_separate_coverage(self):
        self.assertTrue(self.gate().admit(self.match, F.QUOTE_ASSET, None, self.clock())["allowed"])
        self.available = 0
        self.frozen = self.match.price
        self.assertTrue(self.gate().admit(self.match, F.QUOTE_ASSET, "escrow-price", self.clock())["allowed"])
        self.assertFalse(self.gate().admit(self.match, F.QUOTE_ASSET, None, self.clock())["allowed"])

    def test_unknown_or_other_currency_balance_is_refused_not_filled(self):
        self.assertFalse(self.gate(False).admit(self.match, F.QUOTE_ASSET, None, self.clock())["allowed"])
        self.currency = "ETH"
        self.assertFalse(self.gate().admit(self.match, F.QUOTE_ASSET, None, self.clock())["allowed"])

    def test_price_balance_is_rechecked_before_leg_execution(self):
        self.ex._price_balance_gate = self.gate()
        escrow = self.ex.lock_escrow(self.match, "escrow-price")
        self.available = 0
        with self.assertRaises(DomainError) as caught:
            self.ex.execute_transfer(self.match, "transfer-price", escrow.escrow_id)
        self.assertEqual(caught.exception.code, "EX_PRICE_BALANCE_INSUFFICIENT")
        self.assertEqual(self.ex.owner_of("rcpt-8415-0001"), F.A)
        self.assertEqual(self.ex.recorded_legs("rcpt-8415-0001"), 0)
