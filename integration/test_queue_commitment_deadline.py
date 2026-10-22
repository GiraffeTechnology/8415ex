"""Original per-leg commitment cutoff display definitions; author execution NOT_RUN."""
from html import escape
import unittest
from urllib.request import urlopen

from exchange.queue_status_page import WINDOW_TEXT, WORDS, render_queue_status
from integration.test_queue_status_locales import QueueDomain
from integration import test_authorization_locale_transport as mounted


class QueueCommitmentDeadlineTests(unittest.TestCase):
    def original(self, deadline=9):
        value = QueueDomain()
        value.overdue_times = []
        def overdue(receipt_id, now):
            value.overdue_times.append(now)
            return [{"legIndex": 2, "observedAt": now, "commitmentDeadlineAt": deadline,
                     "requestId": "PRIVATE-REQUEST", "transferId": "PRIVATE-TRANSFER"}]
        value.overdue_requests = overdue
        return value

    def test_original_reported_cutoff_uses_same_observation_and_keeps_pending_outcome(self):
        value = self.original(9)
        page = render_queue_status(value, "receipt-1", now=10)
        self.assertEqual(value.overdue_times, [10])
        self.assertEqual(value.reads, 1)
        self.assertIn("<td>9</td>", page)
        self.assertIn(WORDS["en"]["overdueDetail"], page)
        self.assertNotIn("registration failed", page)
        self.assertNotIn("<form", page)

    def test_six_locales_have_fixed_deadline_column_and_boundary(self):
        self.assertEqual(set(WINDOW_TEXT), set(WORDS))
        for locale, labels in WINDOW_TEXT.items():
            page = render_queue_status(self.original(), "receipt-1", locale=locale)
            self.assertIn(escape(labels[0]), page)
            self.assertIn(escape(labels[1]), page)
            self.assertIn(escape(labels[2]), page)
            self.assertIn("<td>9</td>", page)

    def test_missing_deadline_is_not_zero_observed_time_or_mint_registration_cutoff(self):
        value = QueueDomain()
        original = value.receipt_view
        value.receipt_view = lambda *args: {**original(*args), "registrationDeadline": 500,
            "mintDeclaration": {"canonicalDeclaration": {"time": {"registrationDeadline": 500}}}}
        page = render_queue_status(value, "receipt-1")
        self.assertIn(WINDOW_TEXT["en"][1], page)
        self.assertNotIn("<td>0</td></tr>", page)
        self.assertNotIn("<td>10</td>", page)
        self.assertNotIn("500", page)
        self.assertIn(WORDS["en"]["overdue"], page)

    def test_invalid_or_future_cutoff_is_unreported_without_changing_original_state(self):
        for invalid in (None, True, -1, "9", 9.5, 11, {"private": "PRIVATE-DEADLINE"}, []):
            value = self.original(invalid)
            with self.subTest(deadline=invalid):
                page = render_queue_status(value, "receipt-1")
                self.assertIn(WORDS["en"]["overdue"], page)
                self.assertIn(WINDOW_TEXT["en"][1], page)
                self.assertNotIn("PRIVATE-DEADLINE", page)
                self.assertNotIn("<td>11</td>", page)

    def test_conflicting_reports_do_not_pick_one_arbitrary_deadline(self):
        value = QueueDomain()
        value.overdue_requests = lambda rid, now: [
            {"legIndex": 2, "observedAt": now, "commitmentDeadlineAt": 8},
            {"legIndex": 2, "observedAt": now, "commitmentDeadlineAt": 9}]
        page = render_queue_status(value, "receipt-1")
        self.assertNotIn("<td>8</td>", page)
        self.assertNotIn("<td>9</td>", page)
        self.assertIn(WINDOW_TEXT["en"][1], page)
        value.overdue_requests = lambda rid, now: [
            {"legIndex": 2, "observedAt": now, "commitmentDeadlineAt": 9},
            {"legIndex": 2, "observedAt": now, "commitmentDeadlineAt": 9}]
        self.assertIn("<td>9</td>", render_queue_status(value, "receipt-1"))

    def test_explicit_zero_cutoff_and_equality_are_preserved_only_when_actually_reported(self):
        self.assertIn("<td>0</td></tr>", render_queue_status(self.original(0), "receipt-1"))
        self.assertIn("<td>10</td></tr>", render_queue_status(self.original(10), "receipt-1"))
        value = self.original()
        value.legs = []
        page = render_queue_status(value, "receipt-1")
        self.assertIn('colspan="4"', page)
        self.assertIn(WORDS["en"]["none"], page)

    def test_private_original_request_fields_never_enter_text_titles_or_attributes(self):
        for locale in WORDS:
            page = render_queue_status(self.original(), "receipt-1", locale=locale)
            for private in ("PRIVATE-REQUEST", "PRIVATE-TRANSFER", "PRIVATE-BUYER",
                            "PRIVATE-SELLER", "PRIVATE-PROOF"):
                self.assertNotIn(private, page)
            self.assertNotIn("title=", page)

    def test_existing_native_and_integrated_queue_routes_mount_the_deadline_column(self):
        for integrated in (False, True):
            fixture = mounted.AuthorizationLocaleTransportTests("runTest")
            self.addCleanup(fixture.doCleanups)
            server = fixture.server(integrated)
            for locale, labels in WINDOW_TEXT.items():
                with self.subTest(integrated=integrated, locale=locale):
                    with urlopen(server.origin + "/queue?lang=" + locale, timeout=3) as response:
                        page = response.read().decode("utf-8")
                    self.assertIn(escape(labels[0]), page)
                    self.assertIn(escape(labels[2]), page)
