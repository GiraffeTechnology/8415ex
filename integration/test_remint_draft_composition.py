"""Synthetic contracts for unsigned editing alongside original read views."""
from dataclasses import replace
import unittest
from urllib.parse import urlencode

from exchange.remint_draft_composition import mount_remint_draft
from exchange.remint_draft_workbench import RemintDraftEditorBinding, WORDS
from integration import test_recovered_workbench_ui as recovered_fixture
from integration import test_remint_factory_wiring as remint_fixture


class RemintDraftCompositionContracts(unittest.TestCase):
    def setUp(self):
        self.ui = recovered_fixture.RecoveredWorkbenchUITests("runTest")
        self.ui.setUp()
        self.addCleanup(self.ui.doCleanups)
        self.views = remint_fixture.OriginalRemintFactoryContracts("runTest")
        self.views.setUp()
        self.addCleanup(self.views.doCleanups)

    def compose(self, **options):
        return self.ui.compose(remint_history=self.views.history,
            remint_receipt=self.views.receipt, **options)

    def test_construction_keeps_one_restored_access_and_lazy_optional_readers(self):
        changes = self.ui.db.total_changes
        result = self.compose(read_draft_specifications=self.ui.read_specs,
            collateral_selection=True, scenario_selection=True)
        server = result.server
        self.assertIs(server.binding.exchange, result.checkpoint.access)
        self.assertIs(server.draft_editor.access, result.checkpoint.access)
        self.assertIs(server.remint_history, self.views.history)
        self.assertIs(server.remint_receipt, self.views.receipt)
        self.assertEqual(self.ui.reads, [])
        self.assertEqual(self.views.history_calls, [])
        self.assertEqual(self.views.receipt_calls, [])
        self.assertEqual(self.ui.host.calls, [])
        self.assertEqual(self.ui.db.total_changes, changes)

    def test_six_locale_navigation_and_actual_read_routes_survive_together(self):
        server = self.ui.start(self.compose(read_draft_specifications=self.ui.read_specs,
            collateral_selection=True, scenario_selection=True))
        routes = {"/remint-draft":200, "/remint-history":503, "/remint-result":200,
            "/remint-review":200, "/gas":200, "/registration-source":200,
            "/market":200, "/collateral":200, "/scenarios":200}
        for locale in WORDS:
            for path, expected in routes.items():
                with self.subTest(locale=locale, path=path):
                    status, body = self.ui.request(server, path + "?lang=" + locale)
                    self.assertEqual(status, expected)
                    self.assertNotIn("PRIVATE_READER_ERROR", body)
            _, body = self.ui.request(server, "/market?lang=" + locale)
            for path in ("/remint-draft", "/remint-history", "/remint-result",
                         "/remint-review", "/collateral", "/scenarios"):
                self.assertEqual(body.count('href="' + path + '?lang=' + locale + '"'), 1)
        self.assertEqual(len(self.views.receipt_calls), 6)
        self.assertEqual(len(self.views.history_calls), 6)
        self.assertEqual(self.ui.host.calls, [])

    def test_unsigned_preview_does_not_read_chain_views_write_store_or_dispatch(self):
        result = self.compose(read_draft_specifications=self.ui.read_specs)
        server = self.ui.start(result)
        changes = self.ui.db.total_changes
        status, body = self.ui.request(server, "/remint-draft", "POST", urlencode({
            "csrf":server.csrf, "lang":"en", "billTerms":"Complete proposed unsigned terms"}))
        self.assertEqual(status, 200)
        self.assertIn("Complete proposed unsigned terms", body)
        self.assertEqual(self.ui.old.bill_terms, self.ui.seed.bill_terms)
        self.assertEqual(self.ui.db.total_changes, changes)
        self.assertEqual(self.views.history_calls, [])
        self.assertEqual(self.views.receipt_calls, [])
        self.assertEqual(self.ui.host.calls, [])

    def test_original_currency_and_template_callbacks_are_forwarded_lazily(self):
        calls = []
        def currencies(receipt_id):
            calls.append(("currency", receipt_id))
            return self.ui.seed.receipt.allowed_price_currencies
        original_version = self.ui.seed.template.version
        alternate = replace(self.ui.seed,
            template=replace(self.ui.seed.template, version="2"))
        def replacements(receipt_id):
            calls.append(("replacement", receipt_id))
            return (("Original alternate template", alternate),)
        result = self.compose(read_draft_specifications=self.ui.read_specs,
            read_draft_currency_choices=currencies,
            read_draft_replacement_choices=replacements)
        self.assertEqual(calls, [])
        self.assertIs(result.server.draft_editor.read_currency_choices, currencies)
        self.assertIs(result.server.draft_editor.read_replacement_choices, replacements)
        server = self.ui.start(result)
        _, draft = server.draft_editor.draft()
        key = draft["replacementChoices"][1][0]
        status, body = self.ui.request(server, "/remint-draft-choice", "POST",
            urlencode({"csrf":server.csrf, "lang":"en", "replacementChoice":key}))
        self.assertEqual(status, 200)
        self.assertIn('name="replacementChoice" value="' + key + '"', body)
        self.assertEqual(self.ui.seed.template.version, original_version)
        self.assertEqual(self.ui.host.calls, [])

    def test_missing_draft_reader_does_not_disable_original_read_views(self):
        server = self.ui.start(self.compose(collateral_selection=True))
        self.assertFalse(hasattr(server, "draft_editor"))
        self.assertEqual(self.ui.request(server, "/remint-draft")[0], 404)
        self.assertEqual(self.ui.request(server, "/remint-result")[0], 200)
        self.assertEqual(self.ui.request(server, "/remint-review")[0], 200)
        self.assertEqual(self.ui.request(server, "/collateral")[0], 200)
        self.assertEqual(self.ui.reads, [])
        self.assertEqual(self.ui.host.calls, [])

    def test_unavailable_draft_is_local_while_history_and_result_remain_independent(self):
        self.ui.unavailable = True
        server = self.ui.start(self.compose(read_draft_specifications=self.ui.read_specs))
        status, body = self.ui.request(server, "/remint-draft")
        self.assertEqual(status, 503)
        self.assertNotIn("private declaration diagnostic", body)
        self.assertEqual(self.views.history_calls, [])
        self.assertEqual(self.views.receipt_calls, [])
        self.assertEqual(self.ui.request(server, "/remint-result")[0], 200)
        self.assertEqual(self.ui.request(server, "/gas")[0], 200)
        for path in ("/remint-history", "/remint-result"):
            self.assertEqual(self.ui.request(server, path, "POST", "retry=true")[0], 405)
        self.assertEqual(self.views.history_calls, [])
        self.assertEqual(self.views.receipt_calls, ["read"])
        self.assertEqual(self.ui.host.calls, [])

    def test_csrf_refusal_precedes_draft_reads_and_keeps_other_routes(self):
        server = self.ui.start(self.compose(read_draft_specifications=self.ui.read_specs))
        status, _ = self.ui.request(server, "/remint-draft", "POST", urlencode({
            "csrf":"invalid", "lang":"en", "billTerms":"Proposed terms"}))
        self.assertEqual(status, 403)
        self.assertEqual(self.ui.reads, [])
        self.assertEqual(self.ui.request(server, "/remint-result")[0], 200)
        self.assertEqual(self.ui.host.calls, [])

    def test_mount_rejects_foreign_access_and_duplicate_rebinding_without_replacing_handler(self):
        result = self.compose(read_draft_specifications=self.ui.read_specs)
        server = result.server
        handler = server.RequestHandlerClass
        self.assertIs(mount_remint_draft(server, server.draft_editor), server)
        self.assertIs(server.RequestHandlerClass, handler)
        foreign = RemintDraftEditorBinding(self.ui.host.access, "receipt-1", self.ui.read_specs)
        with self.assertRaises(ValueError):
            mount_remint_draft(server, foreign)
        another = RemintDraftEditorBinding(result.checkpoint.access, "receipt-1", self.ui.read_specs)
        with self.assertRaises(ValueError):
            mount_remint_draft(server, another)
        self.assertIs(server.RequestHandlerClass, handler)
        self.assertEqual(self.ui.reads, [])
