"""Synthetic ETH admission regressions; no real wallet or chain execution."""
import copy
import unittest
from exchange import fixtures as F
from exchange.eth_trade_gas import ETHTradeGasGate
from exchange.errors import DomainError

R = "rcpt-8415-0001"


class ETHAdmission(unittest.TestCase):
    def setUp(self):
        self.exchange, self.clock = F.funded_exchange()
        self.match, _ = F.funded_hop(self.exchange, F.A, F.B, 1, "transfer-eth",
                                    "session-a", "session-b", lock=False)
        self.now = self.clock()
        self.row = {"asset": "ETH", "unit": "wei", "balanceWei": 100000,
                    "reservedWei": 10000, "requiredWei": 21000,
                    "blockNumber": 12, "blockHash": "0x" + "11" * 32,
                    "observedAt": self.now, "sourceReference": "fixture-only"}

    def gate(self, verify=True):
        def read(request, now):
            return dict(copy.deepcopy(self.row), request=request)
        return ETHTradeGasGate(read, lambda request, row: verify)

    def test_zero_eth_warns_and_refuses_even_with_token_principal(self):
        self.row["balanceWei"] = 0
        self.row["reservedWei"] = 0
        result = self.gate().admit(self.match, self.now)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["code"], "EX_ETH_GAS_EMPTY")
        self.assertIn("ETH", result["warning"])
        self.assertGreater(self.match.price, 0)

    def test_only_eth_wei_is_accepted(self):
        for field, value in (("asset", F.QUOTE_ASSET), ("unit", "gwei")):
            with self.subTest(field=field):
                old = self.row[field]
                self.row[field] = value
                self.assertEqual(self.gate().admit(self.match, self.now)["code"],
                                 "EX_ETH_GAS_UNVERIFIED")
                self.row[field] = old

    def test_reservations_and_current_fee_requirement_are_deducted(self):
        self.row.update(balanceWei=30000, reservedWei=10000)
        self.assertEqual(self.gate().admit(self.match, self.now)["code"],
                         "EX_ETH_GAS_INSUFFICIENT")
        self.row["balanceWei"] = 31000
        self.assertTrue(self.gate().admit(self.match, self.now)["allowed"])

    def test_unknown_stale_or_unverified_balance_never_allows_trade(self):
        self.assertFalse(self.gate(False).admit(self.match, self.now)["allowed"])
        self.row["observedAt"] = self.now - 31
        self.assertFalse(self.gate().admit(self.match, self.now)["allowed"])
        unavailable = ETHTradeGasGate(lambda request, now: (_ for _ in ()).throw(TimeoutError()),
                                      lambda request, row: True)
        self.assertEqual(unavailable.admit(self.match, self.now)["code"],
                         "EX_ETH_GAS_UNVERIFIED")

    def test_malformed_fee_or_balance_is_not_a_positive_balance(self):
        for field, value in (("balanceWei", True), ("reservedWei", -1), ("requiredWei", 0)):
            with self.subTest(field=field):
                old = self.row[field]
                self.row[field] = value
                self.assertFalse(self.gate().admit(self.match, self.now)["allowed"])
                self.row[field] = old

    def test_no_eth_does_not_append_leg_move_owner_or_consume_nonces(self):
        escrow = self.exchange.lock_escrow(self.match, "escrow-eth")
        self.row.update(balanceWei=0, reservedWei=0)
        self.exchange._eth_gas_gate = self.gate()
        nonces = set(self.exchange._used_nonces)
        with self.assertRaises(DomainError) as caught:
            self.exchange.execute_transfer(self.match, "transfer-eth", escrow.escrow_id)
        self.assertEqual(caught.exception.code, "EX_ETH_GAS_EMPTY")
        self.assertEqual(self.exchange.owner_of(R), F.A)
        self.assertEqual(self.exchange.recorded_legs(R), 0)
        self.assertEqual(self.exchange._used_nonces, nonces)
        self.assertEqual(self.exchange.escrow(escrow.escrow_id).status, "locked")

    def test_missing_original_gas_reader_is_not_an_opt_out(self):
        self.exchange._eth_gas_gate = None
        with self.assertRaises(DomainError) as caught:
            self.exchange.execute_transfer(self.match, "transfer-eth")
        self.assertEqual(caught.exception.code, "EX_ETH_GAS_UNVERIFIED")

    def test_positive_verified_eth_remains_a_native_recheck_requirement(self):
        result = self.gate().admit(self.match, self.now)
        self.assertTrue(result["allowed"])
        self.assertTrue(result["nativeAtomicRecheckRequired"])
        self.assertEqual((result["asset"], result["unit"]), ("ETH", "wei"))
