"""Synthetic saved-state UI wiring, preserving the original writer and routes."""
from dataclasses import replace
import http.client
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from urllib.parse import urlencode

from exchange.aggregate_checkpoint import AggregateCheckpointStore
from exchange.checkpoint_workbench_composition import CheckpointWorkbenchUnavailable
from exchange.exchange_fact_snapshot import encode_exchange_snapshot
from exchange.exchange_snapshot_checkpoint import ExchangeSnapshotCheckpoint
from exchange.recovered_workbench_ui import compose_recovered_workbench_ui
from exchange.remint_draft_workbench import WORDS as DRAFT_WORDS
from integration.test_exchange_fact_rehydration import current_runtime
from integration.test_mint_specification_codec import specification
from integration import test_serialized_workbench_composition as original_host


class RecoveredWorkbenchUITests(unittest.TestCase):
    def setUp(self):
        self.host = original_host.SerializedWorkbenchCompositionTests("runTest")
        self.host.setUp()
        self.addCleanup(self.host.doCleanups)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.db = sqlite3.connect(Path(directory.name) / "original-checkpoint.db")
        self.addCleanup(self.db.close)
        AggregateCheckpointStore.initialize(self.db)
        self.checkpoint = ExchangeSnapshotCheckpoint(AggregateCheckpointStore(self.db,
            components=("owned-facts",), source_commit="a" * 40, source_tree="b" * 40))
        self.checkpoint.save("original-scope", encode_exchange_snapshot(self.host.exchange), expected_generation=0)
        self.old = specification()
        self.seed = replace(self.old, receipt=replace(self.old.receipt,
            asset=replace(self.old.receipt.asset, token_id=9)))
        self.reads = []
        self.unavailable = False

    def read_specs(self, receipt_id):
        self.reads.append(receipt_id)
        if self.unavailable:
            raise RuntimeError("private declaration diagnostic")
        return self.old, self.seed

    def compose(self, **options):
        scope = options.pop("scope", "original-scope")
        result = compose_recovered_workbench_ui(self.checkpoint, scope,
            current_runtime(self.host.exchange), "receipt-1",
            gas_page=self.host.gas, registration_sources=self.host.server.registration_sources,
            current_time=lambda: 110, commit="c" * 40, tree="d" * 40,
            detail_receipts=(("receipt-2", {}),), remint_review=self.host.review,
            port=0, **options)
        self.addCleanup(result.server.server_close)
        return result

    def start(self, result):
        server = result.server
        worker = threading.Thread(target=server.serve_forever,
            kwargs={"poll_interval": 0.02}, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 3)
        self.addCleanup(server.shutdown)
        return server

    def request(self, server, path, method="GET", body=None):
        connection = http.client.HTTPConnection(*server.server_address, timeout=3)
        headers = {} if method == "GET" else {
            "Origin": server.origin, "Content-Type": "application/x-www-form-urlencoded"}
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            return response.status, response.read().decode()
        finally:
            connection.close()

    def test_constructing_all_pages_uses_one_restored_access_without_reads_effects_or_store_writes(self):
        changes = self.db.total_changes
        result = self.compose(read_draft_specifications=self.read_specs,
            collateral_selection=True, scenario_selection=True)
        server = result.server
        self.assertIs(server.binding.exchange, result.checkpoint.access)
        self.assertIs(server.draft_editor.access, result.checkpoint.access)
        self.assertIsNot(result.checkpoint.access, self.host.access)
        for binding in server.nft_directory._bindings.values():
            self.assertIs(binding.exchange, result.checkpoint.access)
        self.assertEqual(self.reads, [])
        self.assertEqual(self.host.calls, [])
        self.assertEqual(self.db.total_changes, changes)
        self.assertEqual(result.checkpoint.generation, 1)

    def test_all_six_language_routes_survive_editor_then_selector_composition(self):
        server = self.start(self.compose(read_draft_specifications=self.read_specs,
            collateral_selection=True, scenario_selection=True))
        for locale in DRAFT_WORDS:
            for path in ("/remint-draft", "/remint-review", "/collateral", "/scenarios", "/market"):
                with self.subTest(locale=locale, path=path):
                    status, body = self.request(server, path + "?lang=" + locale)
                    self.assertEqual(status, 200)
                    self.assertIn('lang="' + locale + '"', body)
            _, market = self.request(server, "/market?lang=" + locale)
            for path in ("/remint-draft", "/collateral", "/scenarios"):
                self.assertEqual(market.count('href="' + path + '?lang=' + locale + '"'), 1)
        self.assertEqual(self.host.calls, [])

    def test_unsigned_post_still_uses_original_editor_and_does_not_save_or_mutate_terms(self):
        result = self.compose(read_draft_specifications=self.read_specs,
            collateral_selection=True, scenario_selection=True)
        server = self.start(result)
        changes = self.db.total_changes
        text = "Updated complete unsigned business terms"
        status, body = self.request(server, "/remint-draft", "POST", urlencode(
            {"csrf": server.csrf, "lang": "en", "billTerms": text}))
        self.assertEqual(status, 200)
        self.assertIn(text, body)
        self.assertEqual(result.checkpoint.access.receipt("receipt-1").receipt_id, "receipt-1")
        self.assertEqual(self.old.bill_terms, self.seed.bill_terms)
        self.assertEqual(self.db.total_changes, changes)
        self.assertEqual(self.host.calls, [])

    def test_unavailable_draft_reader_is_local_to_editor_not_a_global_ui_gate(self):
        self.unavailable = True
        server = self.start(self.compose(read_draft_specifications=self.read_specs,
            collateral_selection=True, scenario_selection=True))
        status, body = self.request(server, "/remint-draft?lang=ja")
        self.assertEqual(status, 503)
        self.assertIn(DRAFT_WORDS["ja"][6], body)
        self.assertNotIn("private declaration diagnostic", body)
        for path in ("/market", "/gas", "/registration-source", "/remint-review", "/collateral", "/scenarios"):
            self.assertEqual(self.request(server, path)[0], 200)
        self.assertEqual(self.host.calls, [])

    def test_omitted_draft_reader_keeps_original_routes_without_synthetic_terms(self):
        server = self.start(self.compose(collateral_selection=True, scenario_selection=True))
        self.assertFalse(hasattr(server, "draft_editor"))
        self.assertEqual(self.request(server, "/remint-draft")[0], 404)
        self.assertEqual(self.request(server, "/remint-review")[0], 200)
        self.assertEqual(self.request(server, "/collateral")[0], 200)
        self.assertEqual(self.request(server, "/scenarios")[0], 200)
        self.assertEqual(self.reads, [])

    def test_original_gateway_is_not_queried_or_replaced_by_optional_mounts(self):
        class Gateway:
            def enquire(self, *args):
                raise AssertionError("UI mount queried native journal")
            def dispatch(self, *args):
                raise AssertionError("UI mount dispatched native effect")
        gateway = Gateway()
        result = self.compose(runtime_options={"gateway": gateway},
            read_draft_specifications=self.read_specs, collateral_selection=True, scenario_selection=True)
        self.assertIs(result.server.binding.gateway, gateway)
        self.assertEqual(self.reads, [])
        self.assertEqual(self.host.calls, [])

    def test_bad_options_fail_before_loading_and_absent_checkpoint_is_not_empty_success(self):
        for options in ({"collateral_selection": "yes"}, {"scenario_selection": 1},
                        {"read_draft_specifications": "not-callable"}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                compose_recovered_workbench_ui(None, None, None, None, **options)
        with self.assertRaises(CheckpointWorkbenchUnavailable):
            self.compose(scope="missing-original-scope", collateral_selection=True, scenario_selection=True)
