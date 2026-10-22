"""Unsigned original currency-choice UI definitions; author NOT_RUN."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from exchange.remint_draft_workbench import CURRENCY_WORDS, WORDS, RemintDraftEditorBinding
from exchange import recovered_workbench_ui as recovered
from integration import test_remint_draft_workbench as original_ui


class RemintCurrencyDraft(unittest.TestCase):
    def setUp(self):
        self.original = original_ui.RemintDraftWorkbenchTests()
        self.original.setUp()
        self.addCleanup(self.original.doCleanups)
        self.original.server.draft_editor.read_currency_choices = lambda receipt_id: (
            "quote-a", "quote-b", "quote-c")

    def form(self, selected=("quote-a", "quote-c"), locale="en", **extra):
        fields = {"csrf": self.original.server.csrf, "lang": locale,
                  "billTerms": "New unsigned terms", "priceCurrency": selected}
        fields.update(extra)
        return urlencode(fields, doseq=True)

    def test_all_locales_render_original_and_new_currency_choices(self):
        for locale in WORDS:
            with self.subTest(locale=locale):
                status, _, body = self.original.request("GET", "/remint-draft?lang=" + locale)
                self.assertEqual(status, 200)
                self.assertIn(CURRENCY_WORDS[locale][0], body)
                self.assertIn(CURRENCY_WORDS[locale][1], body)
                self.assertIn('value="quote-a" checked', body)
                self.assertIn('value="quote-c">', body)
                for private in (self.original.old.receipt.asset.contract,
                                self.original.old.controlled_access_mapping):
                    self.assertNotIn(private, body)

    def test_add_remove_currency_only_changes_unsigned_replacement(self):
        editor = self.original.server.draft_editor
        _, result = editor.draft("Changed", ("quote-c",))
        self.assertEqual(result["specification"].receipt.allowed_price_currencies, ("quote-c",))
        self.assertEqual(self.original.old.receipt.allowed_price_currencies, ("quote-a", "quote-b"))
        self.assertEqual(self.original.seed.receipt.allowed_price_currencies, ("quote-a", "quote-b"))
        self.assertEqual(result["signature"], "NOT_REQUESTED")
        self.assertEqual(result["metadataVerification"], "NOT_PERFORMED")
        self.assertEqual(result["execution"], "NOT_RUN")
        self.assertFalse(result["executionAuthorized"])
        self.assertEqual(self.original.host.calls, [])

    def test_post_preserves_selected_currency_and_get_restores_seed(self):
        status, _, body = self.original.request("POST", "/remint-draft", self.form())
        self.assertEqual(status, 200)
        self.assertIn('value="quote-c" checked', body)
        self.assertIn('value="quote-b">', body)
        status, _, body = self.original.request("GET", "/remint-draft")
        self.assertEqual(status, 200)
        self.assertIn('value="quote-b" checked', body)
        self.assertIn('value="quote-c">', body)
        self.assertEqual(self.original.host.calls, [])

    def test_empty_duplicate_unoffered_and_identity_fields_refused(self):
        for raw in (self.form(selected=()), self.form(selected=("quote-a", "quote-a")),
                    self.form(selected=("unknown-code",)), self.form(receiptId="other"),
                    self.form(currencySetReference="replacement")):
            with self.subTest(raw=raw):
                self.assertEqual(self.original.request("POST", "/remint-draft", raw)[0], 400)
        self.assertEqual(self.original.host.calls, [])

    def test_unavailable_private_or_stale_choice_source_is_not_rendered(self):
        editor = self.original.server.draft_editor
        for choices in (("quote-a", "0x" + "a" * 40), ("quote-a", "quote-a"), ("quote-c",)):
            editor.read_currency_choices = lambda receipt_id, value=choices: value
            status, _, body = self.original.request("GET", "/remint-draft?lang=ja")
            self.assertEqual(status, 503)
            self.assertIn(WORDS["ja"][6], body)
            self.assertNotIn("0x" + "a" * 40, body)
        self.assertEqual(self.original.host.calls, [])

    def test_original_form_without_choice_reader_stays_compatible(self):
        self.original.server.draft_editor.read_currency_choices = None
        status, _, body = self.original.request("POST", "/remint-draft", self.original.form())
        self.assertEqual(status, 200)
        self.assertNotIn('name="priceCurrency"', body)
        self.assertEqual(self.original.host.calls, [])

    def test_recovered_composition_passes_same_original_reader_without_invocation(self):
        callback = lambda receipt_id: self.fail("composition must not read currencies")
        server = SimpleNamespace(binding=object(), server_close=lambda: None)
        loaded = SimpleNamespace(server=server, checkpoint=SimpleNamespace(access=object()))
        reader = lambda receipt_id: self.fail("composition must not read declarations")
        with patch.object(recovered, "compose_checkpoint_workbench", return_value=loaded), \
             patch.object(recovered, "RemintDraftEditorBinding") as editor, \
             patch.object(recovered, "mount_remint_draft"):
            result = recovered.compose_recovered_workbench_ui(object(), "scope", object(), "receipt",
                read_draft_specifications=reader, read_draft_currency_choices=callback)
        self.assertIs(result, loaded)
        editor.assert_called_once_with(loaded.checkpoint.access, "receipt", reader,
                                       read_currency_choices=callback)
