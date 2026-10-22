"""Ordered public remint differences; no signing, storage or native execution."""
from copy import deepcopy
from html import escape
import unittest

from exchange.remint_review import RemintReviewBinding, RemintReviewUnavailable, WORDS


def detail(receipt, clauses):
    return {"schema": "8415ex-public-nft-detail/1", "receiptId": receipt,
            "sourceStatus": "verified-original-reader",
            "terms": {"status": "provided-verified-projection",
                      "clauses": [{"label": label, "text": text} for label, text in clauses]}}


class RemintClauseChangesContracts(unittest.TestCase):
    def render(self, before, after, locale="en"):
        self.pair = (detail("receipt-old", before), detail("receipt-new", after))
        self.calls = []
        def original_pair(old, new):
            self.calls.append((old, new))
            return self.pair
        self.binding = RemintReviewBinding("receipt-old", "receipt-new", original_pair)
        prior = deepcopy(self.pair)
        document = self.binding.render(locale)
        self.assertEqual(self.pair, prior)
        self.assertEqual(self.calls, [("receipt-old", "receipt-new")])
        return document

    def test_added_clause_preserves_full_before_after_and_exact_position(self):
        document = self.render([("Grade", "A")], [("Grade", "A"), ("Location", "Port")])
        self.assertIn('data-clause-change="insert"', document)
        self.assertIn('<ins><article data-clause-position="2">', document)
        self.assertNotIn('<del>', document)
        self.assertIn('data-remint-clause-changes="1"', document)
        self.assertEqual(document.count('<pre>A</pre>'), 2)
        self.assertEqual(document.count('<pre>Port</pre>'), 2)

    def test_removed_clause_is_explicit_without_rewriting_complete_terms(self):
        document = self.render([("Grade", "A"), ("Location", "Port")], [("Grade", "A")])
        self.assertIn('data-clause-change="delete"', document)
        self.assertIn('<del><article data-clause-position="2">', document)
        self.assertNotIn('<ins>', document)
        self.assertEqual(document.count('<pre>Port</pre>'), 2)

    def test_changed_text_preserves_both_exact_original_texts(self):
        document = self.render([("Quantity", "1 whole receipt")],
                               [("Quantity", "2 whole receipts")])
        self.assertIn('data-clause-change="replace"', document)
        self.assertIn('<del>', document)
        self.assertIn('<ins>', document)
        self.assertEqual(document.count('<pre>1 whole receipt</pre>'), 2)
        self.assertEqual(document.count('<pre>2 whole receipts</pre>'), 2)

    def test_identical_ordered_clauses_have_no_artificial_changes(self):
        clauses = [("Grade", "A"), ("Currency", "Original terms")]
        document = self.render(clauses, clauses)
        self.assertNotIn('data-remint-clause-changes', document)
        self.assertNotIn('<del>', document)
        self.assertNotIn('<ins>', document)
        self.assertIn(WORDS["en"][4], document)

    def test_duplicate_labels_and_reordering_use_exact_ordered_clauses(self):
        before = [("Condition", "First"), ("Condition", "Second"), ("Condition", "Third")]
        after = [("Condition", "Second"), ("Condition", "First"), ("Condition", "Third")]
        document = self.render(before, after)
        self.assertIn('data-clause-change="delete"', document)
        self.assertIn('data-clause-change="insert"', document)
        self.assertEqual(document.count('<pre>Third</pre>'), 2)
        counts = [document.count('<pre>First</pre>'), document.count('<pre>Second</pre>')]
        self.assertEqual(sorted(counts), [2, 4])

    def test_six_locales_use_existing_labels_and_escaped_original_text(self):
        before = [("<em>Clause</em>", "A <script>alert(1)</script>")]
        after = [("<em>Clause</em>", "B & C")]
        for locale, words in WORDS.items():
            document = self.render(before, after, locale)
            self.assertIn(escape(words[1]) + " 1–1", document)
            self.assertIn(escape(words[2]) + " 1–1", document)
            self.assertIn(escape(words[3]), document)
            self.assertNotIn('<script>', document)
            self.assertNotIn('<em>', document)
            self.assertIn('A &lt;script&gt;alert(1)&lt;/script&gt;', document)
            self.assertIn('B &amp; C', document)

    def test_unavailable_or_identity_bearing_projection_never_leaks_partial_diff(self):
        pair = (detail("receipt-old", [("Public", "Safe before")]),
                detail("receipt-new", [("Private", "0x" + "1" * 40)]))
        binding = RemintReviewBinding("receipt-old", "receipt-new", lambda *_: pair)
        with self.assertRaises(RemintReviewUnavailable):
            binding.render()
        pair[1]["terms"]["clauses"][0]["text"] = "Safe after"
        pair[1]["sourceStatus"] = "unverified"
        with self.assertRaises(RemintReviewUnavailable):
            binding.render()

    def test_diff_output_adds_no_form_execution_or_authority_controls(self):
        document = self.render([("Terms", "Old")], [("Terms", "New")])
        for marker in ('<form', '<input', '<button', 'onclick=', 'data-remint-execute'):
            self.assertNotIn(marker, document)
        self.assertIn(WORDS["en"][6], document)
        self.assertIn(WORDS["en"][7], document)


if __name__ == "__main__":
    unittest.main()
