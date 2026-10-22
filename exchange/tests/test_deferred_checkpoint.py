"""File-backed synthetic recovery source for authorized CI; not run locally."""
from dataclasses import asdict
from pathlib import Path
import sqlite3
import tempfile
import unittest

from exchange.aggregate_checkpoint import AggregateCheckpointStore, CheckpointRefused
from exchange.deferred_checkpoint import DeferredCheckpoint
from exchange.deferred_settlement import DeferredRefused
from exchange.ids import canonical_json, digest
from exchange.tests import test_deferred_settlement as fixture_module


class SyntheticPort:
    """Test-only preflight; no real route or financial execution."""
    def __init__(self, execute):
        self.execute = execute

    def prepare_original(self, operation):
        return self.execute


class DeferredCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.DeferredTests()
        self.fixture.setUp()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.connection = sqlite3.connect(Path(self.directory.name) / "checkpoint.db")
        self.addCleanup(self.connection.close)
        self.connection.execute("PRAGMA synchronous=FULL")
        AggregateCheckpointStore.initialize(self.connection)
        self.store = AggregateCheckpointStore(self.connection,
            components=("deferred-settlement", "original"), source_commit="a" * 40, source_tree="b" * 40)
        self.store.save("case", {"original": b"original immutable component",
            "deferred-settlement": canonical_json(self.fixture.engine.snapshot()).encode()}, expected_generation=0)
        self.service = DeferredCheckpoint(self.store, "case", self.fixture.profile, self.fixture.verifier)

    def apply(self, command, *args, **kwargs):
        return self.service.apply(command, *args, expected_generation=self.service.read()[0]["generation"], **kwargs)

    def reserve(self):
        return self.apply("reserve", "ab", "lock-1", **self.fixture.reserve_arguments())

    def payment(self):
        self.reserve()
        self.apply("observe_registration", "ab", self.fixture.fact("registration-cut", at=150), now=150)
        self.apply("credit_escrow", "ab", self.fixture.fact("principal-allocation", units=800), now=150)
        return self.apply("prepare", "pay", "ab", kind="seller-payment", now=150)

    def test_complete_snapshot_retains_original_component_and_reservation(self):
        self.reserve()
        row, model = self.service.read()
        self.assertEqual(row["components"]["original"], b"original immutable component")
        self.assertEqual(model.locks["lock-1"].reserved, 800)
        self.assertEqual(model.obligations["ab"].paid, 0)

    def test_stale_generation_does_not_mutate_or_dispatch(self):
        self.payment()
        calls = []
        with self.assertRaises(DeferredRefused):
            self.service.dispatch_once("pay", SyntheticPort(calls.append), expected_generation=1, now=200)
        self.assertEqual(calls, [])
        self.assertEqual(self.service.read()[1].operations["pay"].status, "PREPARED")

    def test_unknown_is_durable_before_callback_and_restart_cannot_replay(self):
        prepared = self.payment()
        calls = []
        def uncertain(op):
            self.assertEqual(self.service.read()[1].operations["pay"].status, "UNKNOWN")
            calls.append(op.identity)
            raise TimeoutError("synthetic transport failure")
        result = self.service.dispatch_once("pay", SyntheticPort(uncertain), expected_generation=prepared["generation"], now=200)
        self.assertEqual(result["status"], "UNKNOWN")
        restarted = DeferredCheckpoint(self.store, "case", self.fixture.profile, self.fixture.verifier)
        with self.assertRaises(DeferredRefused):
            restarted.dispatch_once("pay", SyntheticPort(calls.append), expected_generation=result["generation"], now=200)
        self.assertEqual(calls, ["pay"])
        self.assertEqual(restarted.read()[1].obligations["ab"].paid, 0)

    def test_untrusted_executor_response_is_not_payment_confirmation(self):
        prepared = self.payment()
        self.service.dispatch_once("pay", SyntheticPort(lambda op: {"success": True}), expected_generation=prepared["generation"], now=200)
        model = self.service.read()[1]
        self.assertEqual(model.operations["pay"].status, "UNKNOWN")
        self.assertEqual(model.obligations["ab"].paid, 0)

    def test_malformed_state_is_refused_without_overwriting_history(self):
        row = self.store.read("case")
        components = dict(row["components"])
        components["deferred-settlement"] = b'{"schema":"forged"}'
        self.store.save("case", components, expected_generation=row["generation"])
        with self.assertRaises(DeferredRefused):
            self.service.read()

    def test_true_reopen_and_independent_connection_reject_stale_writer(self):
        self.reserve()
        second_connection = sqlite3.connect(Path(self.directory.name) / "checkpoint.db")
        self.addCleanup(second_connection.close)
        second_connection.execute("PRAGMA synchronous=FULL")
        second_store = AggregateCheckpointStore(second_connection,
            components=("deferred-settlement", "original"), source_commit="a" * 40, source_tree="b" * 40)
        second = DeferredCheckpoint(second_store, "case", self.fixture.profile, self.fixture.verifier)
        stale = second.read()[0]["generation"]
        self.apply("observe_registration", "ab", self.fixture.fact("registration-cut", at=150), now=150)
        with self.assertRaises(DeferredRefused):
            second.apply("credit_escrow", "ab", self.fixture.fact("principal-allocation", units=800),
                         now=150, expected_generation=stale)
        self.connection.close()
        self.assertTrue(second.read()[1].obligations["ab"].registered)
        self.assertEqual(second.read()[1].obligations["ab"].escrow, 0)

    def test_commit_acknowledgement_failure_never_calls_executor(self):
        from unittest.mock import patch
        from exchange.aggregate_checkpoint import CheckpointCommitUnknown
        prepared = self.payment()
        original_save = self.store.save
        def uncertain(*args, **kwargs):
            original_save(*args, **kwargs)
            raise CheckpointCommitUnknown("synthetic lost acknowledgement")
        calls = []
        with patch.object(self.store, "save", side_effect=uncertain):
            with self.assertRaises(CheckpointCommitUnknown):
                self.service.dispatch_once("pay", SyntheticPort(calls.append), expected_generation=prepared["generation"], now=200)
        self.assertEqual(calls, [])
        row, model = self.service.read()
        self.assertEqual(model.operations["pay"].status, "UNKNOWN")
        with self.assertRaises(DeferredRefused):
            self.service.dispatch_once("pay", SyntheticPort(calls.append), expected_generation=row["generation"], now=200)
        self.assertEqual(calls, [])

    def test_failure_before_save_does_not_dispatch_or_change_prepared_state(self):
        from unittest.mock import patch
        prepared = self.payment()
        calls = []
        with patch.object(self.store, "save", side_effect=CheckpointRefused("synthetic refusal")):
            with self.assertRaises(CheckpointRefused):
                self.service.dispatch_once("pay", SyntheticPort(calls.append), expected_generation=prepared["generation"], now=200)
        self.assertEqual(calls, [])
        self.assertEqual(self.service.read()[1].operations["pay"].status, "PREPARED")

    def test_same_profile_cannot_use_another_ledger_scope_to_replay_capacity(self):
        with self.assertRaises(DeferredRefused):
            DeferredCheckpoint(self.store, "another-case", self.fixture.profile, self.fixture.verifier)

    def test_missing_route_stays_prepared_without_claim_or_dispatch(self):
        prepared = self.payment()
        before = self.service.read()[0]
        class MissingRoute:
            def prepare_original(self, operation):
                raise DeferredRefused("synthetic missing route")
        result = self.service.dispatch_once("pay", MissingRoute(), expected_generation=prepared["generation"], now=200)
        self.assertEqual(result, {"generation": prepared["generation"], "status": "BLOCKED_NOT_DISPATCHED", "dispatched": False})
        after, model = self.service.read()
        self.assertEqual(after, before)
        self.assertEqual(model.operations["pay"].status, "PREPARED")
        calls = []
        self.service.dispatch_once("pay", SyntheticPort(calls.append), expected_generation=prepared["generation"], now=200)
        self.assertEqual(len(calls), 1)

    def test_legacy_callback_cannot_accidentally_execute_during_preflight(self):
        prepared = self.payment()
        calls = []
        with self.assertRaises(DeferredRefused):
            self.service.dispatch_once("pay", calls.append, expected_generation=prepared["generation"], now=200)
        self.assertEqual(calls, [])
        self.assertEqual(self.service.read()[1].operations["pay"].status, "PREPARED")

    def test_competing_change_during_read_only_preflight_blocks_execution(self):
        prepared = self.payment()
        calls = []
        service = self.service
        class ChangedRoute:
            def prepare_original(inner, operation):
                row = service.read()[0]
                service.store.save("case", row["components"], expected_generation=row["generation"])
                return calls.append
        with self.assertRaises(DeferredRefused):
            self.service.dispatch_once("pay", ChangedRoute(), expected_generation=prepared["generation"], now=200)
        self.assertEqual(calls, [])

    def liquidation(self):
        self.reserve()
        self.apply("observe_registration", "ab", self.fixture.fact("registration-cut", at=150), now=150)
        # Separate synthetic fixture builds exact bound evidence, never executes.
        self.fixture.reserve(); self.fixture.register()
        quote = self.fixture.quote("debt-liquidation", 800)
        original = self.fixture.prepare("sale", "ab", kind="debt-liquidation", now=200,
                                        liquidation_quote=quote)
        authority = ("synthetic:" + original.authority_record["identity"]).encode()
        return self.apply("prepare", "sale", "ab", kind="debt-liquidation", now=200,
                          liquidation_quote=quote, liquidation_terms=original.liquidation_terms,
                          liquidation_authority=authority)

    def fund_liquidation(self, prepared):
        operation = prepared["result"]
        terms = operation.liquidation_terms
        raw = self.fixture.fact("liquidation-ex-funding", chain=560048, asset=terms["gasAsset"],
            account=terms["gasPayer"], location=terms["gasBudget"], reference=operation.commitment,
            units=terms["gasCapUnits"], at=200)
        return self.apply("observe_liquidation_funding", "sale", raw, now=200)

    def test_fee_admission_failure_never_saves_partial_reservation(self):
        arguments = self.fixture.reserve_arguments()
        arguments["fee_receipt"] = b"unverified-fee"
        before = self.store.read("case")
        with self.assertRaises(DeferredRefused):
            self.apply("reserve", "ab", "lock-1", **arguments)
        self.assertEqual(self.store.read("case"), before)
        self.assertEqual(self.service.read()[1].obligations, {})

    def test_schema_one_checkpoint_is_read_only_held_without_migration_or_dispatch(self):
        import json
        self.reserve()
        row = self.store.read("case")
        components = dict(row["components"])
        state = json.loads(components["deferred-settlement"].decode())
        state["schema"] = "8415ex-deferred/1"
        components["deferred-settlement"] = canonical_json(state).encode()
        self.store.save("case", components, expected_generation=row["generation"])
        before = self.store.read("case")
        calls = []
        with self.assertRaisesRegex(DeferredRefused, "LEGACY_FEE_ACCOUNTING_RECONCILIATION_REQUIRED"):
            self.service.read()
        with self.assertRaises(DeferredRefused):
            self.service.dispatch_once("sale", SyntheticPort(calls.append),
                expected_generation=before["generation"], now=200)
        with self.assertRaises(DeferredRefused):
            self.service.apply("reserve", "other", "lock-1", expected_generation=before["generation"],
                               **self.fixture.reserve_arguments(identity="other", principal=100))
        self.assertEqual(self.store.read("case"), before)
        self.assertEqual(calls, [])

    def test_concurrent_same_aggregate_cannot_double_allocate_original_normal_budget(self):
        generation = self.service.read()[0]["generation"]
        first = self.fixture.reserve_arguments(principal=400)
        normal = self.fixture.normal_gas("other")
        normal["budget"] = first["normal_gas"]["budget"]
        second = self.fixture.reserve_arguments(identity="other", principal=400, normal_gas=normal)
        self.service.apply("reserve", "ab", "lock-1", expected_generation=generation, **first)
        with self.assertRaises(DeferredRefused):
            self.service.apply("reserve", "other", "lock-1", expected_generation=generation, **second)
        current = self.service.read()[0]["generation"]
        with self.assertRaises(DeferredRefused):
            self.service.apply("reserve", "other", "lock-1", expected_generation=current, **second)
        row, model = self.service.read()
        self.assertEqual(row["generation"], current)
        self.assertEqual(set(model.obligations), {"ab"})
        self.assertEqual(model.locks["lock-1"].reserved, 400)
        self.assertEqual(row["components"]["original"], b"original immutable component")

    def test_liquidation_without_ex_funding_cannot_claim_unknown_or_execute(self):
        prepared = self.liquidation()
        calls = []
        before = self.store.read("case")
        with self.assertRaises(DeferredRefused):
            self.service.dispatch_once("sale", SyntheticPort(calls.append),
                expected_generation=prepared["generation"], now=200)
        self.assertEqual(calls, [])
        self.assertEqual(self.store.read("case"), before)
        self.assertEqual(self.service.read()[1].operations["sale"].status, "PREPARED")

    def test_funded_liquidation_claim_persists_before_execute_without_new_b_eth(self):
        funded = self.fund_liquidation(self.liquidation())
        calls = []
        def execute(operation):
            row, model = self.service.read()
            self.assertEqual(model.operations["sale"].status, "UNKNOWN")
            self.assertEqual(model.operations["sale"].funding_record, operation.funding_record)
            self.assertEqual(model.obligations["ab"].escrow, 0)
            self.assertEqual(model.obligations["ab"].settlement_fee_wei, 20)
            self.assertEqual(row["components"]["original"], b"original immutable component")
            calls.append(operation.identity)
            return {"syntheticOnly": True}
        outcome = self.service.dispatch_once("sale", SyntheticPort(execute),
            expected_generation=funded["generation"], now=200)
        self.assertEqual(outcome["status"], "UNKNOWN")
        self.assertEqual(calls, ["sale"])
        self.assertEqual(self.service.read()[1].obligations["ab"].paid, 0)

    def test_uncertain_funded_liquidation_save_never_calls_executor(self):
        from unittest.mock import patch
        from exchange.aggregate_checkpoint import CheckpointCommitUnknown
        funded = self.fund_liquidation(self.liquidation())
        original_save = self.store.save
        def uncertain(*args, **kwargs):
            original_save(*args, **kwargs)
            raise CheckpointCommitUnknown("synthetic committed but acknowledgement lost")
        calls = []
        with patch.object(self.store, "save", side_effect=uncertain):
            with self.assertRaises(CheckpointCommitUnknown):
                self.service.dispatch_once("sale", SyntheticPort(calls.append),
                    expected_generation=funded["generation"], now=200)
        self.assertEqual(calls, [])
        row, model = self.service.read()
        self.assertEqual(model.operations["sale"].status, "UNKNOWN")
        self.assertIsNotNone(model.operations["sale"].funding_record)
        with self.assertRaises(DeferredRefused):
            self.service.dispatch_once("sale", SyntheticPort(calls.append),
                expected_generation=row["generation"], now=200)
        self.assertEqual(calls, [])

    def test_funding_change_during_preflight_cannot_execute_stale_aggregate(self):
        funded = self.fund_liquidation(self.liquidation())
        calls = []
        service = self.service
        class ConcurrentFundingRead:
            def prepare_original(inner, operation):
                row = service.read()[0]
                service.store.save("case", row["components"], expected_generation=row["generation"])
                return calls.append
        with self.assertRaises(DeferredRefused):
            self.service.dispatch_once("sale", ConcurrentFundingRead(),
                expected_generation=funded["generation"], now=200)
        self.assertEqual(calls, [])
        self.assertEqual(self.service.read()[1].operations["sale"].status, "PREPARED")

    def normal_availability(self, *, at=200, units=10, required=10, now=None):
        item = self.service.read()[1].obligations["ab"]
        reference = digest({"obligation": "ab", "terms": item.consent,
                            "allocation": item.gas_allocation, "normalGas": item.normal_gas})
        raw = self.fixture.fact("normal-gas-availability", asset="ETH",
            location=item.normal_gas["location"], reference=reference,
            units=units, destination_units=required, at=at)
        return self.apply("observe_gas_requirement", "ab", raw, now=at if now is None else now)

    def rollback(self):
        self.reserve()
        evidence = self.fixture.fact("deadline-registration", units=0, at=200)
        self.apply("deadline", "ab", now=200, registration_evidence=evidence)
        self.normal_availability()
        return self.apply("prepare", "return", "ab", kind="rollback", now=200)

    def test_exact_reserve_retry_does_not_duplicate_checkpoint_fee_or_capacity(self):
        arguments = self.fixture.reserve_arguments()
        self.apply("reserve", "ab", "lock-1", **arguments)
        before = self.service.read()[1].snapshot()
        self.apply("reserve", "ab", "lock-1", **dict(arguments, now=300))
        row, model = self.service.read()
        self.assertEqual(model.snapshot(), before)
        self.assertEqual(model.locks["lock-1"].reserved, 800)
        self.assertEqual(len(model.obligations), 1)
        self.assertEqual(row["components"]["original"], b"original immutable component")

    def test_stale_original_normal_observation_blocks_checkpoint_dispatch(self):
        prepared = self.rollback()
        before = self.store.read("case")
        calls = []
        with self.assertRaises(DeferredRefused):
            self.service.dispatch_once("return", SyntheticPort(calls.append),
                expected_generation=prepared["generation"], now=301)
        self.assertEqual(calls, [])
        self.assertEqual(self.store.read("case"), before)
        restored = self.service.read()[1]
        self.assertEqual(restored.operations["return"].status, "PREPARED")
        self.assertEqual(restored.obligations["ab"].normal_gas_availability["observed_at"], 200)

    def test_fabricated_normal_gas_metrics_checkpoint_is_held_without_dispatch(self):
        import json
        self.reserve()
        evidence = self.fixture.fact("deadline-registration", units=0, at=200)
        self.apply("deadline", "ab", now=200, registration_evidence=evidence)
        row = self.store.read("case")
        components = dict(row["components"])
        state = json.loads(components["deferred-settlement"].decode())
        item = state["obligations"]["ab"]
        item.update(gas_assessed=True, gas_received=10, gas_required=10)
        components["deferred-settlement"] = canonical_json(state).encode()
        self.store.save("case", components, expected_generation=row["generation"])
        before = self.store.read("case")
        calls = []
        with self.assertRaises(DeferredRefused):
            self.service.read()
        with self.assertRaises(DeferredRefused):
            self.service.dispatch_once("return", SyntheticPort(calls.append),
                expected_generation=before["generation"], now=200)
        self.assertEqual(calls, [])
        self.assertEqual(self.store.read("case"), before)

    def test_same_binding_ex_funding_refresh_is_durable_before_dispatch(self):
        funded = self.fund_liquidation(self.liquidation())
        original = self.service.read()[1].operations["sale"].funding_record
        terms = self.service.read()[1].operations["sale"].liquidation_terms
        raw = self.fixture.fact("liquidation-ex-funding", chain=560048, asset=terms["gasAsset"],
            account=terms["gasPayer"], location=terms["gasBudget"],
            reference=self.service.read()[1].operations["sale"].commitment,
            units=terms["gasCapUnits"], at=201)
        self.apply("observe_liquidation_funding", "sale", raw, now=201)
        row, model = self.service.read()
        self.assertEqual(model.operations["sale"].funding_record["observed_at"], 201)
        self.assertIn(original["identity"], model.evidence)
        calls = []
        result = self.service.dispatch_once("sale", SyntheticPort(calls.append),
            expected_generation=row["generation"], now=231)
        self.assertTrue(result["dispatched"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].funding_record["observed_at"], 201)

    def test_prepared_rollback_refresh_retains_identity_and_saves_before_execute(self):
        prepared = self.rollback()
        commitment = prepared["result"].commitment
        calls = []
        with self.assertRaises(DeferredRefused):
            self.service.dispatch_once("return", SyntheticPort(calls.append),
                expected_generation=prepared["generation"], now=301)
        refreshed = self.normal_availability(at=301, units=8, required=7)
        def execute(operation):
            model = self.service.read()[1]
            self.assertEqual(model.operations["return"].status, "UNKNOWN")
            self.assertEqual(model.operations["return"].commitment, commitment)
            self.assertEqual(model.obligations["ab"].normal_gas_availability["observed_at"], 301)
            calls.append(operation.identity)
        outcome = self.service.dispatch_once("return", SyntheticPort(execute),
            expected_generation=refreshed["generation"], now=301)
        self.assertEqual(calls, ["return"])
        self.assertTrue(outcome["dispatched"])
        self.assertEqual(self.service.read()[1].obligations["ab"].settlement_fee_wei, 20)

    def test_nonterminal_receipt_cannot_finalize_checkpoint(self):
        prepared = self.payment()
        operation = prepared["result"]
        self.service.dispatch_once("pay", SyntheticPort(lambda op: None),
            expected_generation=prepared["generation"], now=200)
        fragment = self.fixture.fact("operation-receipt", account=operation.recipient,
                                     reference=operation.commitment, units=800, at=200)
        before = self.store.read("case")
        with self.assertRaises(DeferredRefused):
            self.apply("confirm", "pay", fragment, now=200)
        self.assertEqual(self.store.read("case"), before)
        self.assertEqual(self.service.read()[1].operations["pay"].status, "UNKNOWN")
        self.assertEqual(self.service.read()[1].obligations["ab"].paid, 0)
        terminal = self.fixture.fact("terminal-operation-receipt", account=operation.recipient,
                                     reference=operation.commitment, units=800, at=200)
        self.apply("confirm", "pay", terminal, now=200)
        self.assertEqual(self.service.read()[1].obligations["ab"].paid, 800)

    def unlock(self):
        prepared = self.payment()
        payment = prepared["result"]
        self.service.dispatch_once("pay", SyntheticPort(lambda operation: None),
            expected_generation=prepared["generation"], now=200)
        terminal = self.fixture.fact("terminal-operation-receipt", account=payment.recipient,
                                     reference=payment.commitment, units=payment.units, at=200)
        self.apply("confirm", "pay", terminal, now=200)
        return self.apply("prepare", "unlock", "ab", kind="collateral-unlock", now=200)

    def test_source_unlock_missing_original_allocation_holds_without_execute(self):
        self.unlock()
        row, model = self.service.read()
        snapshot = model.snapshot()
        source_identity = snapshot["obligations"]["ab"]["source_gas_allocation"]
        del snapshot["evidence"][source_identity]
        components = dict(row["components"])
        components["deferred-settlement"] = canonical_json(snapshot).encode()
        saved = self.store.save("case", components, expected_generation=row["generation"])
        before = self.store.read("case")
        calls = []
        with self.assertRaises(DeferredRefused):
            self.service.dispatch_once("unlock", SyntheticPort(calls.append),
                expected_generation=saved["generation"], now=200)
        self.assertEqual(calls, [])
        self.assertEqual(self.store.read("case"), before)

    def test_source_unlock_saves_separate_hoodi_normal_binding_before_callback(self):
        prepared = self.unlock()
        calls = []
        def execute(operation):
            row, model = self.service.read()
            item = model.obligations["ab"]
            self.assertEqual(model.operations["unlock"].status, "UNKNOWN")
            self.assertEqual(operation.normal_funding, {"chain": 560048, "asset": "ETH",
                "allocation": item.source_gas_allocation, "terms": item.source_normal_gas})
            self.assertNotEqual(item.source_gas_allocation, item.gas_allocation)
            self.assertEqual(row["components"]["original"], b"original immutable component")
            calls.append(operation.identity)
        result = self.service.dispatch_once("unlock", SyntheticPort(execute),
            expected_generation=prepared["generation"], now=200)
        self.assertEqual(calls, ["unlock"])
        self.assertTrue(result["dispatched"])

    def test_original_source_budget_cannot_be_reserved_twice_in_same_aggregate(self):
        first = self.fixture.reserve_arguments(principal=400)
        source = self.fixture.source_normal_gas("other")
        source["budget"] = first["source_normal_gas"]["budget"]
        second = self.fixture.reserve_arguments(identity="other", principal=400, source_normal_gas=source)
        generation = self.service.read()[0]["generation"]
        accepted = self.service.apply("reserve", "ab", "lock-1", expected_generation=generation, **first)
        with self.assertRaises(DeferredRefused):
            self.service.apply("reserve", "other", "lock-1", expected_generation=generation, **second)
        with self.assertRaises(DeferredRefused):
            self.service.apply("reserve", "other", "lock-1", expected_generation=accepted["generation"], **second)
        row, model = self.service.read()
        self.assertEqual(row["generation"], accepted["generation"])
        self.assertEqual(set(model.obligations), {"ab"})
        self.assertEqual(model.locks["lock-1"].reserved, 400)
