"""Synthetic original-row composition sources; execution belongs to CI only."""
from dataclasses import replace
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from exchange.aggregate_checkpoint import (AggregateCheckpointStore, CheckpointRefused,
    CheckpointCommitUnknown)
from exchange.checkpoint_runtime_load import load_exchange_checkpoint
from exchange.checkpointed_command_workbench import compose_checkpointed_command_workbench
from exchange.checkpointed_operation import CheckpointedOperationBridge
from exchange.checkpointed_workbench_gateway import CheckpointedWorkbenchGateway
from exchange.composite_exchange_checkpoint import CompositeExchangeSnapshotCheckpoint
from exchange.deferred_checkpoint import DeferredCheckpoint
from exchange.deferred_settlement import DeferredRefused
from exchange.durable_operation import DurableEXOperationJournal
from exchange.exchange_fact_snapshot import encode_exchange_snapshot
from exchange.exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint, ExchangeCheckpointRefused
from exchange.fixtures import A
from exchange.ids import canonical_json
from exchange.ledger import Exchange
from exchange.tests import test_deferred_settlement as deferred_fixtures
from integration.test_exchange_fact_rehydration import current_runtime
from integration.test_mint_specification_codec import specification
from integration import test_serialized_workbench_composition as workbench_fixtures


COMPONENTS = ("owned-facts", "deferred-settlement", "original-opaque")
OPAQUE = b"\x00\xfforiginal bytes, not JSON\n"
SCOPE = "case"


class SyntheticPort:
    def __init__(self, execute):
        self.execute = execute

    def prepare_original(self, operation):
        return self.execute


class CompositeExchangeCheckpointTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "original.db"
        self.db = self.connect()
        AggregateCheckpointStore.initialize(self.db)
        self.store = self.make_store(self.db)
        self.exchange = Exchange(lambda: 20, mint_verifier=lambda kind, evidence: True)
        spec = specification()
        self.exchange.mint(spec.receipt, spec)
        self.exchange._used_nonces.add((A, 7))
        self.original = encode_exchange_snapshot(self.exchange)
        self.fixture = deferred_fixtures.DeferredTests("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        # Explicit synthetic setup, not adapter initialization or migration.
        self.store.save(SCOPE, {"owned-facts": self.original,
            "deferred-settlement": canonical_json(self.fixture.engine.snapshot()).encode(),
            "original-opaque": OPAQUE}, expected_generation=0)
        self.checkpoint = self.adapter(self.store)
        self.service = self.deferred(self.store)

    def connect(self):
        db = sqlite3.connect(self.path, check_same_thread=False)
        db.execute("PRAGMA synchronous=FULL")
        self.addCleanup(db.close)
        return db

    def make_store(self, db, *, cls=AggregateCheckpointStore, **overrides):
        options = dict(components=COMPONENTS, source_commit="a" * 40, source_tree="b" * 40)
        options.update(overrides)
        return cls(db, **options)

    def adapter(self, store, *, scope=SCOPE, components=COMPONENTS):
        return CompositeExchangeSnapshotCheckpoint(store, scope=scope, components=components)

    def deferred(self, store):
        return DeferredCheckpoint(store, SCOPE, self.fixture.profile, self.fixture.verifier)

    def candidate(self):
        self.exchange._events["receipt-1"].append({"synthetic": "retained event"})
        return encode_exchange_snapshot(self.exchange)

    def apply(self, command, *args, **kwargs):
        return self.service.apply(command, *args,
            expected_generation=self.store.read(SCOPE)["generation"], **kwargs)

    def payment(self):
        self.apply("reserve", "ab", "lock-1", **self.fixture.reserve_arguments())
        self.apply("observe_registration", "ab", self.fixture.fact("registration-cut", at=150), now=150)
        self.apply("credit_escrow", "ab", self.fixture.fact("principal-allocation", units=800), now=150)
        return self.apply("prepare", "pay", "ab", kind="seller-payment", now=150)

    def test_explicit_full_component_opt_in_keeps_strict_default_and_scope(self):
        with self.assertRaises(ExchangeCheckpointRefused):
            ExchangeSnapshotCheckpoint(self.store)
        invalid = (("owned-facts",), COMPONENTS + ("extra",), COMPONENTS + ("owned-facts",),
                   "owned-facts", ("owned-facts", []))
        for components in invalid:
            with self.subTest(components=components), self.assertRaises(ExchangeCheckpointRefused):
                self.adapter(self.store, components=components)
        for components in (("owned-facts",), ("deferred-settlement", "original-opaque")):
            with self.subTest(components=components), self.assertRaises(ExchangeCheckpointRefused):
                self.adapter(self.make_store(self.db, components=components), components=components)
        with self.assertRaises(ExchangeCheckpointRefused):
            self.checkpoint.read("another-original-scope")
        with self.assertRaises(DeferredRefused):
            DeferredCheckpoint(self.store, "another-original-scope", self.fixture.profile, self.fixture.verifier)

    def test_load_is_read_only_and_keeps_exact_original_generation_source_and_bytes(self):
        before = self.store.read(SCOPE)
        changes = self.db.total_changes
        with patch.object(self.fixture.verifier, "verify", side_effect=AssertionError("no proof lookup on snapshot load")):
            loaded = load_exchange_checkpoint(self.checkpoint, SCOPE, current_runtime(self.exchange))
        self.assertEqual((loaded.scope, loaded.generation, loaded.digest),
                         (SCOPE, before["generation"], before["digest"]))
        self.assertEqual((loaded.source_commit, loaded.source_tree), ("a" * 40, "b" * 40))
        self.assertEqual(loaded.access.receipt("receipt-1"), self.exchange.receipt("receipt-1"))
        self.assertEqual(self.db.total_changes, changes)
        self.assertEqual(self.store.read(SCOPE), before)

    def test_both_writers_share_generation_and_preserve_all_untouched_bytes(self):
        before = self.store.read(SCOPE)
        raw = self.candidate()
        with patch.object(self.store, "save", wraps=self.store.save) as save:
            result = self.checkpoint.save(SCOPE, raw, expected_generation=1)
        self.assertEqual(result["generation"], 2)
        self.assertFalse(result["completeRecovery"])
        self.assertEqual(set(save.call_args.kwargs["immutable_components"]),
                         {"deferred-settlement", "original-opaque"})
        row = self.store.read(SCOPE)
        self.assertEqual(row["components"]["deferred-settlement"], before["components"]["deferred-settlement"])
        self.assertEqual(row["components"]["original-opaque"], OPAQUE)
        self.apply("reserve", "ab", "lock-1", **self.fixture.reserve_arguments())
        row, model = self.service.read()
        self.assertEqual(row["generation"], 3)
        self.assertEqual(row["components"]["owned-facts"], raw)
        self.assertEqual(row["components"]["original-opaque"], OPAQUE)
        self.assertEqual(model.locks["lock-1"].reserved, 800)
        self.assertEqual(self.checkpoint.read(SCOPE)["generation"], 3)

    def test_missing_row_is_not_initialized_and_foreign_scope_cannot_get_companions(self):
        missing = self.adapter(self.store, scope="missing-original-scope")
        self.assertIsNone(load_exchange_checkpoint(missing, missing.scope, current_runtime(self.exchange)))
        with self.assertRaises(ExchangeCheckpointRefused):
            missing.save(missing.scope, self.original, expected_generation=0)
        with self.assertRaises(ExchangeCheckpointRefused):
            self.checkpoint.save("pre-effect:synthetic", self.original, expected_generation=0)
        self.assertIsNone(self.store.read(missing.scope))
        self.assertIsNone(self.store.read("pre-effect:synthetic"))
        self.assertEqual(self.store.read(SCOPE)["generation"], 1)

    def test_continuity_and_exact_input_guards_remain_at_correct_generation(self):
        before = self.store.read(SCOPE)
        self.exchange._used_nonces.clear()
        with self.assertRaises(ExchangeCheckpointRefused):
            self.checkpoint.save(SCOPE, encode_exchange_snapshot(self.exchange), expected_generation=1)
        self.exchange._used_nonces.add((A, 7))
        self.exchange._receipts["receipt-1"] = replace(self.exchange._receipts["receipt-1"], commodity_name="Changed")
        with self.assertRaises(ExchangeCheckpointRefused):
            self.checkpoint.save(SCOPE, encode_exchange_snapshot(self.exchange), expected_generation=1)
        for raw, generation in ((self.original, True), (self.original, 0), (bytearray(self.original), 1)):
            with self.subTest(generation=generation), self.assertRaises(ExchangeCheckpointRefused):
                self.checkpoint.save(SCOPE, raw, expected_generation=generation)
        self.assertEqual(self.store.read(SCOPE), before)

    def test_source_identity_mismatch_does_not_load_or_change_original_row(self):
        before = self.store.read(SCOPE)
        other = self.adapter(self.make_store(self.connect(), source_tree="c" * 40))
        with self.assertRaises(CheckpointRefused):
            load_exchange_checkpoint(other, SCOPE, current_runtime(self.exchange))
        self.assertEqual(self.store.read(SCOPE), before)

    def test_stale_generations_from_either_subsystem_refuse_without_merging(self):
        stale = self.checkpoint.read(SCOPE)["generation"]
        self.apply("reserve", "ab", "lock-1", **self.fixture.reserve_arguments())
        with self.assertRaises(ExchangeCheckpointRefused):
            self.checkpoint.save(SCOPE, self.candidate(), expected_generation=stale)
        stale = self.service.read()[0]["generation"]
        self.checkpoint.save(SCOPE, self.original, expected_generation=stale)
        before = self.store.read(SCOPE)
        with self.assertRaises(DeferredRefused):
            self.service.apply("observe_registration", "ab", self.fixture.fact("registration-cut", at=150),
                               now=150, expected_generation=stale)
        self.assertEqual(self.store.read(SCOPE), before)

    def test_deferred_write_between_snapshot_preflight_and_cas_is_retained(self):
        other = self.deferred(self.make_store(self.connect()))
        original_save = self.store.save
        arguments = self.fixture.reserve_arguments()
        def interposed(*args, **kwargs):
            other.apply("reserve", "ab", "lock-1", expected_generation=1, **arguments)
            return original_save(*args, **kwargs)
        with patch.object(self.store, "save", side_effect=interposed):
            with self.assertRaises(CheckpointRefused):
                self.checkpoint.save(SCOPE, self.candidate(), expected_generation=1)
        row, model = other.read()
        self.assertEqual(row["generation"], 2)
        self.assertEqual(row["components"]["owned-facts"], self.original)
        self.assertEqual(row["components"]["original-opaque"], OPAQUE)
        self.assertEqual(model.locks["lock-1"].reserved, 800)

    def test_snapshot_write_during_deferred_route_preflight_prevents_dispatch(self):
        prepared = self.payment()
        raw = self.candidate()
        calls = []
        checkpoint = self.adapter(self.make_store(self.connect()))
        class ChangedRoute:
            def prepare_original(inner, operation):
                checkpoint.save(SCOPE, raw, expected_generation=prepared["generation"])
                return calls.append
        with self.assertRaises(DeferredRefused):
            self.service.dispatch_once("pay", ChangedRoute(), expected_generation=prepared["generation"], now=200)
        row, model = self.service.read()
        self.assertEqual(calls, [])
        self.assertEqual(model.operations["pay"].status, "PREPARED")
        self.assertEqual(row["components"]["owned-facts"], raw)

    def test_concurrent_cross_component_writers_have_one_original_row_winner(self):
        barrier = threading.Barrier(2)
        outcomes = []
        raw = self.candidate()
        arguments = self.fixture.reserve_arguments()
        class RacingStore(AggregateCheckpointStore):
            def save(inner, *args, **kwargs):
                barrier.wait(timeout=5)
                return super().save(*args, **kwargs)
        def write(kind):
            db = sqlite3.connect(self.path)
            try:
                db.execute("PRAGMA synchronous=FULL")
                store = self.make_store(db, cls=RacingStore)
                if kind == "owned":
                    self.adapter(store).save(SCOPE, raw, expected_generation=1)
                else:
                    self.deferred(store).apply("reserve", "ab", "lock-1", expected_generation=1, **arguments)
                outcomes.append((kind, "saved"))
            except CheckpointRefused:
                outcomes.append((kind, "stale"))
            except Exception as error:
                outcomes.append((kind, type(error).__name__))
            finally:
                db.close()
        workers = [threading.Thread(target=write, args=(kind,)) for kind in ("owned", "deferred")]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(10)
            self.assertFalse(worker.is_alive())
        self.assertEqual(sorted(outcome for _, outcome in outcomes), ["saved", "stale"])
        row, model = self.service.read()
        self.assertEqual(row["generation"], 2)
        self.assertEqual(row["components"]["original-opaque"], OPAQUE)
        won = dict(outcomes)["owned"] == "saved"
        self.assertEqual(row["components"]["owned-facts"], raw if won else self.original)
        self.assertEqual(model.locks["lock-1"].reserved, 0 if won else 800)

    def test_unknown_before_execute_survives_owned_save_and_true_connection_restart(self):
        prepared = self.payment()
        calls = []
        def uncertain(operation):
            row, model = self.service.read()
            self.assertEqual(model.operations["pay"].status, "UNKNOWN")
            self.assertEqual(self.checkpoint.read(SCOPE)["generation"], row["generation"])
            self.assertEqual(row["components"]["owned-facts"], self.original)
            calls.append(operation.identity)
            raise TimeoutError("synthetic uncertain response")
        result = self.service.dispatch_once("pay", SyntheticPort(uncertain),
            expected_generation=prepared["generation"], now=200)
        deferred_bytes = self.store.read(SCOPE)["components"]["deferred-settlement"]
        raw = self.candidate()
        self.checkpoint.save(SCOPE, raw, expected_generation=result["generation"])
        self.db.close()
        store = self.make_store(self.connect())
        restarted = self.deferred(store)
        row, model = restarted.read()
        loaded = load_exchange_checkpoint(self.adapter(store), SCOPE, current_runtime(self.exchange))
        self.assertEqual(loaded.generation, row["generation"])
        self.assertEqual(row["components"]["deferred-settlement"], deferred_bytes)
        self.assertEqual(row["components"]["owned-facts"], raw)
        self.assertEqual(row["components"]["original-opaque"], OPAQUE)
        self.assertEqual(model.operations["pay"].status, "UNKNOWN")
        self.assertEqual(model.obligations["ab"].paid, 0)
        with self.assertRaises(DeferredRefused):
            restarted.dispatch_once("pay", SyntheticPort(calls.append), expected_generation=row["generation"], now=200)
        self.assertEqual(calls, ["pay"])

    def test_lost_snapshot_commit_ack_is_not_retried_or_allowed_to_erase_companions(self):
        before = self.store.read(SCOPE)
        original_save = self.store.save
        raw = self.candidate()
        def uncertain(*args, **kwargs):
            original_save(*args, **kwargs)
            raise CheckpointCommitUnknown("synthetic lost acknowledgement")
        with patch.object(self.store, "save", side_effect=uncertain) as save:
            with self.assertRaises(CheckpointCommitUnknown):
                self.checkpoint.save(SCOPE, raw, expected_generation=1)
        self.assertEqual(save.call_count, 1)
        row = self.adapter(self.make_store(self.connect())).read(SCOPE)
        self.assertEqual(row["generation"], 2)
        self.assertEqual(row["components"], dict(before["components"], **{"owned-facts": raw}))

    def test_workbench_loads_same_row_but_pre_effect_refusal_keeps_original_unknown(self):
        host = workbench_fixtures.SerializedWorkbenchCompositionTests("runTest")
        host.setUp()
        self.addCleanup(host.doCleanups)
        DurableEXOperationJournal.initialize(self.db)
        journal = DurableEXOperationJournal(self.db)
        CheckpointedWorkbenchGateway.initialize(journal)
        calls, builders = [], []
        asset = self.exchange.receipt("receipt-1").asset
        binding = {"receiptId": "receipt-1", "chainId": asset.chain_id,
            "contract": asset.contract, "tokenId": str(asset.token_id), "globalLegId": 0,
            "action": "rollback", "nativeOperationId": "original-composite-command",
            "intentDigest": "c" * 64, "journalReference": "original-journal"}
        def ports(access, gateway):
            builders.append(access)
            return {"resolve_command": lambda *args: binding,
                "enquire_original": lambda scope: None, "execute_original": calls.append}
        before = self.store.read(SCOPE)
        changes = self.db.total_changes
        loaded = compose_checkpointed_command_workbench(self.checkpoint, SCOPE,
            current_runtime(self.exchange), "receipt-1", operation_journal=journal,
            make_original_ports=ports, gas_page=host.gas,
            registration_sources=host.server.registration_sources, current_time=lambda: 110,
            commit="a" * 40, tree="b" * 40, port=0)
        self.addCleanup(loaded.server.server_close)
        self.assertEqual(self.db.total_changes, changes)
        self.assertEqual(builders, [loaded.checkpoint.access])
        bridge = loaded.server.binding.gateway.bridge
        self.assertIs(bridge.access, loaded.checkpoint.access)
        self.assertIs(bridge.checkpoint, self.checkpoint)
        self.assertIsInstance(bridge, CheckpointedOperationBridge)
        with self.assertRaises(ExchangeCheckpointRefused):
            bridge.invoke(binding, expected_operation_revision=0,
                enquire_original=lambda scope: None, execute_original=calls.append)
        self.assertEqual(calls, [])
        self.assertEqual(journal.lookup(binding["nativeOperationId"])["status"], "UNKNOWN")
        self.assertIsNone(self.store.read(bridge.pre_effect_scope(binding)))
        self.assertEqual(self.store.read(SCOPE), before)
        result = bridge.invoke(binding, expected_operation_revision=1,
            enquire_original=lambda scope: {"status": "unknown"}, execute_original=calls.append)
        self.assertFalse(result["operation"]["nativeGateInvoked"])
        self.assertEqual(calls, [])
        self.assertEqual(journal.lookup(binding["nativeOperationId"])["status"], "UNKNOWN")
