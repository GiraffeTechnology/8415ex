"""Original template public attribute draft definitions; author NOT_RUN."""
from dataclasses import replace
from html import escape
from html.parser import HTMLParser
import unittest
from urllib.parse import urlencode

from exchange.remint_draft_workbench import ATTRIBUTE_WORDS, WORDS
from integration import test_remint_draft_workbench as original_ui


class RemintAttributeDraft(unittest.TestCase):
    def setUp(self):
        self.original = original_ui.RemintDraftWorkbenchTests()
        self.original.setUp()
        self.addCleanup(self.original.doCleanups)
        self.original.seed = replace(self.original.seed,
            public_attributes=(("grade", "Seed grade"), ("packing", "Seed packing")))
        self.editor = self.original.server.draft_editor

    def form(self, grade="Proposed grade", packing="Proposed packing", **extra):
        fields = {"csrf": self.original.server.csrf, "lang": "en", "billTerms": "Unsigned terms",
                  "attribute.0": grade, "attribute.1": packing}
        fields.update(extra)
        return urlencode(fields)

    def test_six_locale_group_labels_original_attributes_and_template_fields(self):
        for locale in WORDS:
            with self.subTest(locale=locale):
                status, _, body = self.original.request("GET", "/remint-draft?lang=" + locale)
                self.assertEqual(status, 200)
                self.assertIn(ATTRIBUTE_WORDS[locale][0], body)
                self.assertIn(ATTRIBUTE_WORDS[locale][1], body)
                self.assertIn('<textarea name="attribute.0" rows="4" maxlength="32768" data-max-codepoints="16384" required>\nSeed grade</textarea>', body)
                self.assertIn('<textarea name="attribute.1" rows="4" maxlength="32768" data-max-codepoints="16384">\nSeed packing</textarea>', body)
                self.assertIn("fixture-grade", body)
                self.assertNotIn(self.original.old.controlled_access_mapping, body)

    def test_remove_optional_and_change_required_without_mutating_old_or_seed(self):
        _, result = self.editor.draft("Unsigned", attribute_fields={
            "attribute.0": "New grade", "attribute.1": ""})
        self.assertEqual(result["specification"].public_attributes, (("grade", "New grade"),))
        self.assertEqual(self.original.old.public_attributes, (("grade", "fixture-grade"),))
        self.assertEqual(self.original.seed.public_attributes,
                         (("grade", "Seed grade"), ("packing", "Seed packing")))
        self.assertFalse(result["executionAuthorized"])
        self.assertEqual(result["execution"], "NOT_RUN")
        self.assertEqual(self.original.host.calls, [])

    def test_add_original_optional_field_and_preserve_surviving_seed_order(self):
        self.original.seed = replace(self.original.seed, public_attributes=(("grade", "Seed grade"),))
        _, result = self.editor.draft(attribute_fields={
            "attribute.0": "Seed grade", "attribute.1": "New packing"})
        self.assertEqual(result["specification"].public_attributes,
                         (("grade", "Seed grade"), ("packing", "New packing")))
        self.original.seed = replace(self.original.seed,
            public_attributes=(("packing", "Seed packing"), ("grade", "Seed grade")))
        _, result = self.editor.draft(attribute_fields={
            "attribute.0": "Changed", "attribute.1": "Seed packing"})
        self.assertEqual(result["specification"].public_attributes,
                         (("packing", "Seed packing"), ("grade", "Changed")))

    def test_required_removal_partial_unknown_and_duplicate_fields_refuse(self):
        partial = urlencode({"csrf": self.original.server.csrf, "lang": "en",
                             "billTerms": "Unsigned", "attribute.0": "New"})
        for body in (self.form(grade=""), partial, self.form(**{"attribute.9": "Other"}),
                     self.form() + "&attribute.0=duplicate", self.form(template="foreign")):
            with self.subTest(body=body):
                self.assertEqual(self.original.request("POST", "/remint-draft", body)[0], 400)
        self.assertEqual(self.original.host.calls, [])

    def test_address_refusal_and_html_escaping(self):
        self.assertEqual(self.original.request("POST", "/remint-draft",
            self.form(packing="0x" + "a" * 40))[0], 400)
        text = '<script>alert("fixture")</script>'
        status, _, body = self.original.request("POST", "/remint-draft", self.form(packing=text))
        self.assertEqual(status, 200)
        self.assertIn(escape(text, quote=True), body)
        self.assertNotIn(text, body)
        self.assertEqual(self.original.host.calls, [])

    def test_preview_is_not_saved_and_legacy_posts_remain_compatible(self):
        status, _, body = self.original.request("POST", "/remint-draft", self.form(packing="Preview packing"))
        self.assertEqual(status, 200)
        self.assertIn('<textarea name="attribute.1" rows="4" maxlength="32768" data-max-codepoints="16384">\nPreview packing</textarea>', body)
        status, _, body = self.original.request("GET", "/remint-draft")
        self.assertEqual(status, 200)
        self.assertNotIn("Preview packing", body)
        self.assertIn("Seed packing", body)
        status, _, _ = self.original.request("POST", "/remint-draft", self.original.form())
        self.assertEqual(status, 200)
        self.assertEqual(self.original.host.calls, [])

    def test_original_csrf_and_source_unavailability_are_preserved(self):
        before = len(self.original.read_calls)
        self.assertEqual(self.original.request("POST", "/remint-draft",
            self.form(csrf="invalid"))[0], 403)
        self.assertEqual(self.original.request("POST", "/remint-draft",
            self.form(), Origin="https://foreign.invalid")[0], 403)
        self.assertEqual(len(self.original.read_calls), before)
        self.original.mode = "unavailable"
        status, _, body = self.original.request("GET", "/remint-draft?lang=fr")
        self.assertEqual(status, 503)
        self.assertIn(WORDS["fr"][6], body)
        self.assertNotIn("private source diagnostic", body)

    def test_multiline_textarea_form_round_trip_preserves_original_attribute(self):
        class Textareas(HTMLParser):
            def __init__(self):
                super().__init__(convert_charrefs=True)
                self.name = None
                self.values = {}

            def handle_starttag(self, tag, attrs):
                if tag == "textarea":
                    self.name = dict(attrs).get("name")
                    self.values[self.name] = ""

            def handle_data(self, data):
                if self.name is not None:
                    self.values[self.name] += data

            def handle_endtag(self, tag):
                if tag == "textarea":
                    self.name = None

        original = "\nFirst line\r\nSecond line\rThird line <keep> & preserve"
        self.original.seed = replace(self.original.seed,
            public_attributes=(("grade", original), ("packing", "Seed packing")))
        status, _, body = self.original.request("GET", "/remint-draft")
        self.assertEqual(status, 200)
        self.assertNotIn('<input name="attribute.', body)
        self.assertIn(escape(original), body)
        controls = Textareas()
        # Model the documented HTML newline and form-serialization rules.
        # This is a synthetic HTTP regression, not live browser acceptance.
        controls.feed(body.replace("\r\n", "\n").replace("\r", "\n"))
        value = controls.values["attribute.0"]
        self.assertTrue(value.startswith("\n"))
        submitted = value[1:].replace("\n", "\r\n")
        status, _, preview = self.original.request("POST", "/remint-draft",
            self.form(grade=submitted, packing="Changed packing"))
        self.assertEqual(status, 200)
        self.assertIn(escape(original), preview)
        self.assertEqual(self.original.seed.public_attributes[0], ("grade", original))
        _, result = self.editor.draft(attribute_fields={
            "attribute.0": submitted, "attribute.1": "Changed packing"})
        self.assertEqual(result["specification"].public_attributes[0], ("grade", original))
        self.assertEqual(self.original.host.calls, [])

    def test_unchanged_newline_expansion_is_restored_before_character_limit(self):
        original = "x" + "\n" * 16383
        self.original.seed = replace(self.original.seed,
            public_attributes=(("grade", original), ("packing", "Seed packing")))
        _, result = self.editor.draft(attribute_fields={
            "attribute.0": original.replace("\n", "\r\n"), "attribute.1": "Seed packing"})
        self.assertEqual(result["specification"].public_attributes[0], ("grade", original))
        self.assertEqual(self.original.host.calls, [])

    def test_changed_multiline_value_uses_logical_character_limit(self):
        changed = "y" + "\n" * 16383
        _, result = self.editor.draft(attribute_fields={
            "attribute.0": changed.replace("\n", "\r\n"), "attribute.1": "Seed packing"})
        self.assertEqual(result["specification"].public_attributes[0], ("grade", changed))
        with self.assertRaises(ValueError):
            self.editor.draft(attribute_fields={
                "attribute.0": changed + "z", "attribute.1": "Seed packing"})
        self.assertEqual(self.original.host.calls, [])
