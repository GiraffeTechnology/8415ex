"""Synthetic protocol bindings; no external HTTP, signatures or transactions."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from exchange.deferred_settlement import DeferredRefused, Operation, Profile
from exchange.deferred_wallet_ports import DeferredWalletPorts, HoodiCollateralWalletClient, NativeTaskBinding
from exchange.wallet_api_client import WalletAPIClient, WalletAPIRefused
from exchange.wallet_execution_attempts import WalletExecutionAttempts


class RecordingSepolia(WalletAPIClient):
    def task(self, action, payload):
        self.calls.append((action, payload))
        return {"observedOnly": True}


class RecordingHoodi(HoodiCollateralWalletClient):
    def task(self, action, payload):
        self.calls.append((action, payload))
        return {"observedOnly": True}


class DeferredWalletPortTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.profile = Profile(11155111, "PYUSD", 560048, "ETH", "vault", "escrow", "policy", 5000, 100, "case")
        actor = "0x" + "1" * 40
        def client(cls, chain, name):
            c = cls("https://wallet.example.invalid", "synthetic", actor, chain,
                    execution_attempts=WalletExecutionAttempts(str(Path(self.directory.name) / name)))
            c.calls = []
            return c
        self.sepolia = client(RecordingSepolia, 11155111, "sepolia.db")
        self.hoodi = client(RecordingHoodi, 560048, "hoodi.db")
        self.ports = DeferredWalletPorts(self.profile, self.sepolia, self.hoodi, self.binding)

    def binding(self, op):
        chain = 560048 if op.kind in ("debt-liquidation", "gas-liquidation", "collateral-unlock") else 11155111
        return NativeTaskBinding(op.commitment, chain, "0x" + "a" * 64,
                                 "logical-operation-1", "0x" + "c" * 64, "0")

    def operation(self, kind):
        return Operation("operation", "obligation", kind, 100, "PYUSD", 11155111,
                         "recipient", "0x" + "d" * 64, status="UNKNOWN")

    def test_ordinary_client_stays_sepolia_only(self):
        with self.assertRaises(WalletAPIRefused):
            WalletAPIClient("https://wallet.example.invalid", "synthetic", "0x" + "1" * 40, 560048)
        with self.assertRaises(WalletAPIRefused):
            HoodiCollateralWalletClient("https://wallet.example.invalid", "synthetic", "0x" + "1" * 40, 11155111)
        self.assertIsNot(self.sepolia._jar, self.hoodi._jar)
        self.assertEqual((self.sepolia._chain, self.hoodi._chain), ("11155111", "560048"))

    def test_liquidation_executes_source_chain_not_destination_chain(self):
        result = self.ports.execute_original(self.operation("gas-liquidation"))
        self.assertEqual(self.sepolia.calls, [])
        self.assertEqual(len(self.hoodi.calls), 1)
        self.assertEqual(self.hoodi.calls[0][0], "execute")
        self.assertEqual(result, {"observedOnly": True})

    def test_payment_uses_original_settlement_client(self):
        self.ports.execute_original(self.operation("seller-payment"))
        self.assertEqual(len(self.sepolia.calls), 1)
        self.assertEqual(self.hoodi.calls, [])
        self.assertEqual(self.sepolia.calls[0][1]["operationId"], "logical-operation-1")

    def test_operation_identifier_preserves_original_protocol(self):
        binding = self.binding(self.operation("seller-payment"))
        for identifier in ("synthetic-operation", "logical:operation_1.2", "a" * 128):
            self.assertEqual(replace(binding, operation_id=identifier).payload()["operationId"], identifier)
        for identifier in ("", "a" * 129, "../operation", "operation with spaces", 1):
            with self.assertRaises(DeferredRefused):
                replace(binding, operation_id=identifier)

    def test_observation_never_dispatches_execution(self):
        self.ports.observe_original(self.operation("debt-liquidation"))
        self.assertEqual([kind for kind, _ in self.hoodi.calls], ["observe"])

    def test_wrong_chain_or_commitment_is_refused_before_any_call(self):
        operation = self.operation("debt-liquidation")
        for binding in (replace(self.binding(operation), source_chain=11155111),
                        replace(self.binding(operation), commitment="0x" + "e" * 64)):
            ports = DeferredWalletPorts(self.profile, self.sepolia, self.hoodi, lambda op: binding)
            with self.assertRaises(DeferredRefused):
                ports.execute_original(operation)
        self.assertEqual(self.sepolia.calls + self.hoodi.calls, [])

    def test_prepared_operation_cannot_bypass_durable_claim(self):
        with self.assertRaises(DeferredRefused):
            self.ports.execute_original(replace(self.operation("seller-payment"), status="PREPARED"))
        self.assertEqual(self.sepolia.calls + self.hoodi.calls, [])

    def test_missing_durable_attempt_store_is_not_a_fallback(self):
        self.hoodi._execution_attempts = None
        with self.assertRaises(DeferredRefused):
            DeferredWalletPorts(self.profile, self.sepolia, self.hoodi, self.binding)
