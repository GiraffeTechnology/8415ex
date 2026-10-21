"""Public scalar remint draft UI definitions; author execution NOT_RUN."""
import copy
import unittest
from urllib.parse import urlencode

from exchange.remint_draft_workbench import BUSINESS_FIELDS, BUSINESS_LABELS, WORDS
from integration import test_remint_draft_workbench as original_ui


class RemintBusinessDraft(unittest.TestCase):
    def setUp(self):
        self.original = original_ui.RemintDraftWorkbenchTests()
        self.original.setUp()
        self.addCleanup(self.original.doCleanups)
        self.editor = self.original.server.draft_editor
        self.editor.read_currency_choices = lambda receipt_id: ("quote-a", "quote-b", "quote-c")
        _, baseline = self.editor.draft()
        self.baseline = baseline["proposedBusinessFields"]

    def fields(self, **changes):
        result = copy.deepcopy(self.baseline)
        result.update(changes)
        return result

    def form(self, values=None, **extra):
        fields = {"csrf": self.original.server.csrf, "lang": "en",
                  "billTerms": "Changed unsigned bill terms", "priceCurrency": ["quote-c"]}
        fields.update(self.fields() if values is None else values)
        fields.update(extra)
        return urlencode(fields, doseq=True)

    def test_six_locale_labels_original_values_and_no_private_identity(self):
        for locale in WORDS:
            with self.subTest(locale=locale):
                status, _, body = self.original.request("GET", "/remint-draft?lang=" + locale)
                self.assertEqual(status, 200)
                for key, label in zip(BUSINESS_FIELDS, BUSINESS_LABELS[locale]):
                    self.assertIn('name="' + key + '"', body)
                    self.assertIn(label, body)
                self.assertIn(self.original.old.bill_of_lading_number, body)
                for value in (self.original.old.receipt.origin_account,
                              self.original.old.receipt.asset.contract,
                              self.original.old.original_document_mapping,
                              self.original.old.controlled_access_mapping):
                    self.assertNotIn(value, body)

    def test_changes_delegate_to_original_contract_without_mutating_old_seed_or_identity(self):
        values = self.fields(commodityName="New grain", commodityQuantity="123",
            commodityUnit="tonne", receiptNumber="new-receipt", billNumber="new-bill",
            issuer="new-issuer", registrar="new-registrar", storageLocation="new-storage",
            tradeStopAt="190", registrationDeadline="170", registrationComparison="LT")
        old, seed = self.original.old, self.original.seed
        _, result = self.editor.draft("New terms", ("quote-c",), values)
        proposed = result["specification"]
        self.assertEqual(result["proposedBusinessFields"], values)
        self.assertEqual(proposed.receipt.commodity_quantity, 123)
        self.assertEqual(proposed.receipt.asset, seed.receipt.asset)
        self.assertEqual(proposed.receipt.origin_account, seed.receipt.origin_account)
        self.assertEqual(proposed.controlled_access_mapping, seed.controlled_access_mapping)
        self.assertEqual(proposed.receipt.nft0_currency_reference, seed.receipt.nft0_currency_reference)
        self.assertEqual(proposed.receipt.allowed_price_currencies, ("quote-c",))
        self.assertEqual(old.receipt.commodity_quantity, 100)
        self.assertEqual(seed.receipt.commodity_quantity, 100)
        self.assertFalse(result["executionAuthorized"])
        self.assertEqual(result["signature"], "NOT_REQUESTED")
        self.assertEqual(result["execution"], "NOT_RUN")
        self.assertEqual(self.original.host.calls, [])

    def test_post_preview_and_get_reset_preserve_original_readers(self):
        status, _, body = self.original.request("POST", "/remint-draft",
            self.form(self.fields(commodityQuantity="123", issuer="Edited issuer")))
        self.assertEqual(status, 200)
        self.assertIn('name="commodityQuantity" value="123"', body)
        self.assertIn('name="issuer" value="Edited issuer"', body)
        self.assertIn('value="quote-c" checked', body)
        status, _, body = self.original.request("GET", "/remint-draft")
        self.assertEqual(status, 200)
        self.assertIn('name="commodityQuantity" value="100"', body)
        self.assertNotIn("Edited issuer", body)
        self.assertEqual(self.original.host.calls, [])

    def test_noncanonical_numbers_and_original_quantity_time_semantics_refuse(self):
        for changes in ({"commodityQuantity": "0"}, {"commodityQuantity": "1.5"},
                {"commodityQuantity": "01"}, {"commodityQuantity": "-1"},
                {"commodityQuantity": str(2 ** 256)}, {"tradeStopAt": "10"},
                {"registrationDeadline": "10"}, {"registrationComparison": "EQ"},
                {"receiptNumber": "not an identifier"}):
            with self.subTest(changes=changes):
                status, _, _ = self.original.request("POST", "/remint-draft",
                    self.form(self.fields(**changes)))
                self.assertEqual(status, 400)
        self.assertEqual(self.original.host.calls, [])

    def test_partial_duplicate_private_and_address_fields_refuse(self):
        partial = self.fields()
        partial.pop("issuer")
        bodies = [self.form(partial), self.form() + "&issuer=duplicate",
                  self.form(asset="other"), self.form(origin_account="other"),
                  self.form(self.fields(issuer="0x" + "a" * 40))]
        for body in bodies:
            self.assertEqual(self.original.request("POST", "/remint-draft", body)[0], 400)
        self.assertEqual(self.original.host.calls, [])

    def test_csrf_and_origin_still_refuse_before_original_source_read(self):
        before = len(self.original.read_calls)
        self.assertEqual(self.original.request("POST", "/remint-draft",
            self.form(csrf="invalid"))[0], 403)
        self.assertEqual(self.original.request("POST", "/remint-draft",
            self.form(), Origin="https://foreign.invalid")[0], 403)
        self.assertEqual(len(self.original.read_calls), before)

    def test_existing_currency_preview_without_new_business_fields_is_compatible(self):
        raw = urlencode({"csrf": self.original.server.csrf, "lang": "en",
            "billTerms": "Legacy text edit", "priceCurrency": ["quote-a"]}, doseq=True)
        status, _, body = self.original.request("POST", "/remint-draft", raw)
        self.assertEqual(status, 200)
        self.assertIn("Legacy text edit", body)
        self.assertIn('name="commodityQuantity" value="100"', body)
        self.assertEqual(self.original.host.calls, [])
