"""Original typed template/voucher choice definitions; author execution NOT_RUN."""
from dataclasses import replace
from html import escape
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from exchange.remint_draft_workbench import REPLACEMENT_WORDS, WORDS
from exchange import recovered_workbench_ui as recovered
from integration import test_remint_draft_workbench as original_ui


class RemintTemplateDraft(unittest.TestCase):
    def setUp(self):
        self.original = original_ui.RemintDraftWorkbenchTests()
        self.original.setUp()
        self.addCleanup(self.original.doCleanups)
        seed = self.original.seed
        template = replace(seed.template, template_id="alternate-template", version="2",
            applicable_fields=("moisture", "grade"), required_fields=("moisture",))
        voucher = replace(seed.voucher_format, format_id="alternate-voucher",
                          version="2", path="REG_ELECTRONIC")
        self.alternate = replace(seed, template=template, voucher_format=voucher,
            receipt=replace(seed.receipt, registration_path=voucher.path),
            public_attributes=(("moisture", "10 percent"),))
        self.editor = self.original.server.draft_editor
        self.choice_reads = []
        def choices(receipt_id):
            self.choice_reads.append(receipt_id)
            return (("Alternate template and electronic registration", self.alternate),)
        self.editor.read_replacement_choices = choices
        _, result = self.editor.draft()
        self.key = result["replacementChoices"][1][0]
        self.default_key = result["replacementChoices"][0][0]

    def choice_form(self, key=None, **extra):
        fields = {"csrf": self.original.server.csrf, "lang": "en",
                  "replacementChoice": self.key if key is None else key}
        fields.update(extra)
        return urlencode(fields)

    def test_six_locale_choice_form_and_private_mapping_exclusion(self):
        for locale in WORDS:
            with self.subTest(locale=locale):
                status, _, body = self.original.request("GET", "/remint-draft?lang=" + locale)
                self.assertEqual(status, 200)
                self.assertIn(escape(REPLACEMENT_WORDS[locale][0]), body)
                self.assertIn(escape(REPLACEMENT_WORDS[locale][2]), body)
                self.assertIn('action="/remint-draft-choice"', body)
                self.assertIn(self.key, body)
                for value in (self.original.seed.receipt.asset.contract,
                              self.original.seed.receipt.origin_account,
                              self.original.seed.controlled_access_mapping):
                    self.assertNotIn(value, body)

    def test_choice_reloads_original_typed_template_voucher_and_attribute_defaults(self):
        _, result = self.editor.draft(replacement_choice=self.key)
        proposed = result["specification"]
        self.assertEqual(proposed.template, self.alternate.template)
        self.assertEqual(proposed.voucher_format, self.alternate.voucher_format)
        self.assertEqual(proposed.receipt.registration_path, "REG_ELECTRONIC")
        self.assertEqual(proposed.public_attributes, (("moisture", "10 percent"),))
        self.assertEqual(proposed.receipt.asset, self.original.seed.receipt.asset)
        self.assertEqual(proposed.receipt.origin_account, self.original.seed.receipt.origin_account)
        self.assertEqual(proposed.controlled_access_mapping, self.original.seed.controlled_access_mapping)
        self.assertEqual(proposed.receipt.allowed_price_currencies,
                         self.original.seed.receipt.allowed_price_currencies)
        self.assertFalse(result["executionAuthorized"])
        self.assertEqual(result["execution"], "NOT_RUN")
        self.assertEqual(self.original.host.calls, [])

    def test_http_choice_then_preview_uses_selected_schema_without_saving(self):
        status, _, body = self.original.request("POST", "/remint-draft-choice", self.choice_form())
        self.assertEqual(status, 200)
        self.assertIn("moisture", body)
        self.assertIn('<textarea name="attribute.0" rows="4" maxlength="32768" data-max-codepoints="16384" required>\n10 percent</textarea>', body)
        self.assertIn('name="replacementChoice" value="' + self.key + '"', body)
        fields = {"csrf": self.original.server.csrf, "lang": "en", "billTerms": "New terms",
                  "replacementChoice": self.key, "attribute.0": "12 percent", "attribute.1": ""}
        status, _, body = self.original.request("POST", "/remint-draft", urlencode(fields))
        self.assertEqual(status, 200)
        self.assertIn('<textarea name="attribute.0" rows="4" maxlength="32768" data-max-codepoints="16384" required>\n12 percent</textarea>', body)
        status, _, body = self.original.request("GET", "/remint-draft")
        self.assertEqual(status, 200)
        self.assertIn('<textarea name="attribute.0" rows="4" maxlength="32768" data-max-codepoints="16384" required>\nfixture-grade</textarea>', body)
        self.assertNotIn("12 percent", body)
        self.assertEqual(self.original.seed.template.template_id, "fixture-template")
        self.assertEqual(self.original.host.calls, [])

    def test_unknown_changed_and_duplicate_choices_do_not_select_another_source(self):
        self.assertEqual(self.original.request("POST", "/remint-draft-choice",
            self.choice_form("0" * 64))[0], 400)
        self.assertEqual(self.original.request("POST", "/remint-draft-choice",
            self.choice_form() + "&replacementChoice=" + self.default_key)[0], 400)
        self.alternate = replace(self.alternate,
            template=replace(self.alternate.template, version="3"))
        self.assertEqual(self.original.request("POST", "/remint-draft-choice", self.choice_form())[0], 400)
        self.assertEqual(self.original.host.calls, [])

    def test_alternative_cannot_select_private_mapping_account_or_scalar_fields(self):
        baseline = self.alternate
        for candidate in (replace(baseline, controlled_access_mapping="foreign-map"),
                replace(baseline, issuer="foreign-issuer"),
                replace(baseline, receipt=replace(baseline.receipt, origin_account="0x" + "a" * 40))):
            with self.subTest(candidate=candidate):
                self.alternate = candidate
                status, _, body = self.original.request("GET", "/remint-draft")
                self.assertEqual(status, 503)
                self.assertNotIn("foreign-map", body)
                self.assertNotIn("0x" + "a" * 40, body)
        self.assertEqual(self.original.host.calls, [])

    def test_choice_origin_csrf_and_extra_fields_refuse_before_reader(self):
        before = len(self.choice_reads)
        self.assertEqual(self.original.request("POST", "/remint-draft-choice",
            self.choice_form(csrf="invalid"))[0], 403)
        self.assertEqual(self.original.request("POST", "/remint-draft-choice",
            self.choice_form(), Origin="https://foreign.invalid")[0], 403)
        self.assertEqual(self.original.request("POST", "/remint-draft-choice",
            self.choice_form(template="arbitrary"))[0], 400)
        self.assertEqual(len(self.choice_reads), before)

    def test_no_choice_reader_retains_original_form_and_refuses_choice_route(self):
        self.editor.read_replacement_choices = None
        status, _, body = self.original.request("GET", "/remint-draft")
        self.assertEqual(status, 200)
        self.assertNotIn('action="/remint-draft-choice"', body)
        self.assertEqual(self.original.request("POST", "/remint-draft", self.original.form())[0], 200)
        self.assertEqual(self.original.request("POST", "/remint-draft-choice", self.choice_form())[0], 400)
        self.assertEqual(self.original.host.calls, [])

    def test_recovered_composition_passes_reader_without_calling_it(self):
        callback = lambda receipt_id: self.fail("construction must not read template choices")
        reader = lambda receipt_id: self.fail("construction must not read declarations")
        server = SimpleNamespace(server_close=lambda: None)
        loaded = SimpleNamespace(server=server, checkpoint=SimpleNamespace(access=object()))
        with patch.object(recovered, "compose_checkpoint_workbench", return_value=loaded), \
             patch.object(recovered, "RemintDraftEditorBinding") as editor, \
             patch.object(recovered, "mount_remint_draft"):
            result = recovered.compose_recovered_workbench_ui(object(), "scope", object(), "receipt",
                read_draft_specifications=reader, read_draft_replacement_choices=callback)
        self.assertIs(result, loaded)
        editor.assert_called_once_with(loaded.checkpoint.access, "receipt", reader,
                                       read_replacement_choices=callback)
