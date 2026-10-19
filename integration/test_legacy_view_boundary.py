"""Remote-only legacy library/rendering privacy boundary definitions."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from exchange import views
from integration.test_nft_detail import OriginalReadOnlyDomain


class LegacyViewBoundary(unittest.TestCase):
    def test_direct_receipt_renderer_uses_privacy_detail_without_raw_bill_fallback(self):
        # This original read-only fixture intentionally provides no raw bill API.
        domain = OriginalReadOnlyDomain()
        html = views.receipt_page(domain, "one")
        self.assertNotIn("private-owner-name", html)
        self.assertNotIn("private-holder-name", html)
        self.assertIn("<!doctype html>", html)
        self.assertIn("Not provided", html)
        self.assertNotIn("canonicalDeclaration", html)

    def test_legacy_page_entry_returns_one_complete_safe_receipt_document(self):
        html = views.page(OriginalReadOnlyDomain(), "one", "receipt")
        self.assertEqual(html.count("<!doctype html>"), 1)
        self.assertEqual(html.count("<html"), 1)
        self.assertNotIn("private-owner-name", html)
        self.assertIn("NFT transfer details", html)

    def test_evidence_metadata_excludes_arbitrary_identity_text_but_keeps_valid_hashes(self):
        private = "private-wallet-and-session"
        source = {"scenario": private, "runId": private, "commit": "a" * 40, "tree": "b" * 40,
                  "transactionHashes": [private, "0x" + "c" * 64], "account": private}
        domain = SimpleNamespace(receipt_view=lambda *args: {"asset": {"chainId": 11155111},
            "owner": {"position": 4}, "holder": {"position": 1}, "registeredPrefixLegs": 1, "observedAt": 123})
        before = deepcopy(source)
        html = views.evidence_page(domain, "one", source)
        self.assertNotIn(private, html)
        self.assertIn("a" * 40, html)
        self.assertIn("b" * 40, html)
        self.assertIn("0x" + "c" * 64, html)
        self.assertIn("owner position 4", html)
        self.assertIn("holder position 1", html)
        self.assertEqual(source, before)
