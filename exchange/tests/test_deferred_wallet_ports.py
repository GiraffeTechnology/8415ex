"""Synthetic protocol bindings; no external HTTP, signatures or transactions."""
from dataclasses import asdict, replace
from pathlib import Path
import tempfile
import unittest

from exchange.deferred_settlement import DeferredRefused, Fact, Operation, Profile
from exchange.ids import digest
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
        self.profile = Profile(11155111, "PYUSD", 560048, "ETH", "vault", "escrow", "policy", 5000, 100, "case", "fee-receiver")
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
        chain = 560048 if op.kind in ("debt-liquidation", "collateral-unlock") else 11155111
        funding = {}
        if op.kind == "debt-liquidation":
            terms = op.liquidation_terms
            funding = dict(funding_payer=terms["gasPayer"], funding_budget=terms["gasBudget"],
                           funding_asset=terms["gasAsset"], funding_cap_units=terms["gasCapUnits"])
        elif op.normal_funding is not None:
            terms = op.normal_funding["terms"]
            funding = dict(funding_payer=terms["payer"], funding_budget=terms["budget"],
                           funding_asset="ETH", funding_cap_units=terms["capWei"])
        return NativeTaskBinding(op.commitment, chain, "0x" + "a" * 64,
                                 "logical-operation-1", "0x" + "c" * 64, "0", **funding)

    def operation(self, kind):
        from exchange.tests.test_deferred_settlement import DeferredTests
        policy = DeferredTests()
        terms = policy.liquidation_terms() if kind == "debt-liquidation" else None
        source = kind == "collateral-unlock"
        normal_funding = None if kind == "debt-liquidation" else {
            "chain": 560048 if source else 11155111, "asset": "ETH",
            "allocation": "synthetic-source-allocation" if source else "synthetic-normal-allocation",
            "terms": policy.source_normal_gas() if source else policy.normal_gas()}
        # Port tests do not authenticate these fields. Domain verifier tests do.
        funding = None if terms is None else asdict(Fact(
            "synthetic-ex-funding", "liquidation-ex-funding", 560048, terms["gasAsset"],
            terms["gasPayer"], terms["gasBudget"], "0x" + "d" * 64,
            terms["gasCapUnits"], 200, profile_commitment=digest(asdict(self.profile))))
        return Operation("operation", "obligation", kind, 100, "ETH" if source else "PYUSD",
                         560048 if source else 11155111,
                         "recipient", "0x" + "d" * 64, status="UNKNOWN",
                         liquidation_terms=terms, funding_record=funding, normal_funding=normal_funding)

    def test_ordinary_client_stays_sepolia_only(self):
        with self.assertRaises(WalletAPIRefused):
            WalletAPIClient("https://wallet.example.invalid", "synthetic", "0x" + "1" * 40, 560048)
        with self.assertRaises(WalletAPIRefused):
            HoodiCollateralWalletClient("https://wallet.example.invalid", "synthetic", "0x" + "1" * 40, 11155111)
        self.assertIsNot(self.sepolia._jar, self.hoodi._jar)
        self.assertEqual((self.sepolia._chain, self.hoodi._chain), ("11155111", "560048"))

    def test_liquidation_executes_source_chain_not_destination_chain(self):
        result = self.ports.execute_original(self.operation("debt-liquidation"))
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

    def test_preflight_resolves_without_dispatch_and_binds_claim(self):
        prepared = replace(self.operation("seller-payment"), status="PREPARED")
        execute = self.ports.prepare_original(prepared)
        self.assertEqual(self.sepolia.calls + self.hoodi.calls, [])
        with self.assertRaises(DeferredRefused):
            execute(replace(prepared, status="UNKNOWN", commitment="0x" + "e" * 64))
        self.assertEqual(self.sepolia.calls + self.hoodi.calls, [])
        execute(replace(prepared, status="UNKNOWN"))
        self.assertEqual(len(self.sepolia.calls), 1)

    def test_missing_binding_is_detected_by_read_only_preflight(self):
        ports = DeferredWalletPorts(self.profile, self.sepolia, self.hoodi, lambda op: None)
        with self.assertRaises(DeferredRefused):
            ports.prepare_original(replace(self.operation("debt-liquidation"), status="PREPARED"))
        self.assertEqual(self.sepolia.calls + self.hoodi.calls, [])

    def test_deprecated_gas_liquidation_route_is_not_available(self):
        operation = self.operation("gas-liquidation")
        with self.assertRaises(DeferredRefused):
            self.ports.execute_original(operation)
        with self.assertRaises(DeferredRefused):
            self.ports.prepare_original(replace(operation, status="PREPARED"))
        self.assertEqual(self.sepolia.calls + self.hoodi.calls, [])

    def test_liquidation_funding_binding_requires_all_four_original_fields(self):
        operation = self.operation("debt-liquidation")
        valid = self.binding(operation)
        for changes in ({"funding_payer": "B"}, {"funding_budget": "other-budget"},
                        {"funding_asset": "PYUSD"}, {"funding_cap_units": 6},
                        {"funding_payer": None, "funding_budget": None,
                         "funding_asset": None, "funding_cap_units": None}):
            binding = replace(valid, **changes)
            ports = DeferredWalletPorts(self.profile, self.sepolia, self.hoodi, lambda op: binding)
            with self.subTest(changes=changes), self.assertRaises(DeferredRefused):
                ports.prepare_original(replace(operation, status="PREPARED"))
        self.assertEqual(self.sepolia.calls + self.hoodi.calls, [])

    def test_funding_binding_rejects_missing_partial_and_boolean_amounts(self):
        binding = self.binding(self.operation("debt-liquidation"))
        for changes in ({"funding_payer": None}, {"funding_budget": None},
                        {"funding_asset": None}, {"funding_cap_units": None},
                        {"funding_cap_units": True}, {"funding_cap_units": 0},
                        {"funding_cap_units": 2 ** 256}):
            with self.subTest(changes=changes), self.assertRaises(DeferredRefused):
                replace(binding, **changes)

    def test_no_funding_record_blocks_liquidation_before_wallet_call(self):
        operation = replace(self.operation("debt-liquidation"), funding_record=None)
        with self.assertRaises(DeferredRefused):
            self.ports.prepare_original(replace(operation, status="PREPARED"))
        with self.assertRaises(DeferredRefused):
            self.ports.execute_original(operation)
        self.assertEqual(self.sepolia.calls + self.hoodi.calls, [])

    def test_original_funding_is_reread_between_preflight_and_execute(self):
        operation = self.operation("debt-liquidation")
        original = self.binding(operation)
        for changes in ({"funding_payer": "different-EX"},
                        {"funding_budget": "different-EX-budget"},
                        {"funding_asset": "PYUSD"}, {"funding_cap_units": 8},
                        {"expected_budget_revision": "1"},
                        {"task_digest": "0x" + "f" * 64},
                        {"child_digest": "0x" + "f" * 64}):
            current = [original]
            reads = []
            def resolve(op):
                reads.append(op.status)
                return current[0]
            ports = DeferredWalletPorts(self.profile, self.sepolia, self.hoodi, resolve)
            execute = ports.prepare_original(replace(operation, status="PREPARED"))
            current[0] = replace(original, **changes)
            with self.subTest(changes=changes), self.assertRaises(DeferredRefused):
                execute(operation)
            self.assertEqual(reads, ["PREPARED", "UNKNOWN"])
            self.assertEqual(self.sepolia.calls + self.hoodi.calls, [])

    def test_unchanged_original_ex_funding_reread_precedes_hoodi_call(self):
        operation = self.operation("debt-liquidation")
        reads = []
        def resolve(op):
            reads.append(op.status)
            return self.binding(op)
        ports = DeferredWalletPorts(self.profile, self.sepolia, self.hoodi, resolve)
        execute = ports.prepare_original(replace(operation, status="PREPARED"))
        result = execute(operation)
        self.assertEqual(reads, ["PREPARED", "UNKNOWN"])
        self.assertEqual(self.sepolia.calls, [])
        self.assertEqual(self.hoodi.calls, [("execute", self.binding(operation).payload())])
        self.assertEqual(result, {"observedOnly": True})
        # This recording port asserts one invocation, not native exactly-once
        # execution. Durable UNKNOWN/CAS guarantees are in checkpoint fixtures.

    def test_unlock_executes_hoodi_with_original_source_normal_budget(self):
        operation = self.operation("collateral-unlock")
        binding = self.binding(operation)
        self.assertEqual(binding.funding_payer, "synthetic-source-treasury")
        self.assertEqual(operation.normal_funding["chain"], 560048)
        self.assertIsNone(operation.liquidation_terms)
        execute = self.ports.prepare_original(replace(operation, status="PREPARED"))
        self.assertEqual(self.hoodi.calls + self.sepolia.calls, [])
        execute(operation)
        self.assertEqual(self.sepolia.calls, [])
        self.assertEqual(self.hoodi.calls, [("execute", binding.payload())])

    def test_normal_funding_requires_all_four_exact_original_binding_fields(self):
        for kind in ("seller-payment", "rollback", "excess-refund", "collateral-unlock"):
            operation = self.operation(kind)
            original = self.binding(operation)
            for changes in ({"funding_payer": "other-payer"}, {"funding_budget": "other-budget"},
                            {"funding_asset": "PYUSD"}, {"funding_cap_units": 1},
                            {"funding_payer": None, "funding_budget": None,
                             "funding_asset": None, "funding_cap_units": None}):
                binding = replace(original, **changes)
                ports = DeferredWalletPorts(self.profile, self.sepolia, self.hoodi, lambda op: binding)
                with self.subTest(kind=kind, changes=changes), self.assertRaises(DeferredRefused):
                    ports.prepare_original(replace(operation, status="PREPARED"))
                with self.assertRaises(DeferredRefused):
                    ports.execute_original(operation)
        self.assertEqual(self.sepolia.calls + self.hoodi.calls, [])

    def test_unlock_without_source_normal_budget_cannot_use_settlement_budget(self):
        operation = self.operation("collateral-unlock")
        original = self.binding(operation)
        ports = DeferredWalletPorts(self.profile, self.sepolia, self.hoodi, lambda op: original)
        invalid = (None, self.operation("seller-payment").normal_funding,
                   dict(operation.normal_funding, asset="PYUSD"),
                   dict(operation.normal_funding, terms=None),
                   dict(operation.normal_funding, allocation=None),
                   dict(operation.normal_funding, allocation="invalid allocation"),
                   {key: value for key, value in operation.normal_funding.items() if key != "allocation"})
        for funding in invalid:
            changed = replace(operation, normal_funding=funding)
            with self.subTest(funding=funding), self.assertRaises(DeferredRefused):
                ports.prepare_original(replace(changed, status="PREPARED"))
            with self.assertRaises(DeferredRefused):
                ports.execute_original(changed)
        self.assertEqual(self.sepolia.calls + self.hoodi.calls, [])

    def test_source_normal_funding_reread_blocks_changed_budget_or_authority(self):
        operation = self.operation("collateral-unlock")
        original = self.binding(operation)
        for changes in ({"funding_payer": "other-source-payer"}, {"funding_budget": "other-source-budget"},
                        {"funding_asset": "PYUSD"}, {"funding_cap_units": 8},
                        {"expected_budget_revision": "1"}, {"child_digest": "0x" + "f" * 64}):
            current = [original]
            reads = []
            def resolve(op):
                reads.append(op.status)
                return current[0]
            ports = DeferredWalletPorts(self.profile, self.sepolia, self.hoodi, resolve)
            execute = ports.prepare_original(replace(operation, status="PREPARED"))
            current[0] = replace(original, **changes)
            with self.subTest(changes=changes), self.assertRaises(DeferredRefused):
                execute(operation)
            self.assertEqual(reads, ["PREPARED", "UNKNOWN"])
        self.assertEqual(self.sepolia.calls + self.hoodi.calls, [])
