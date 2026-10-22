"""Separate recorded trade execution definitions; author execution NOT_RUN."""
from copy import deepcopy
from html import escape
import unittest
from urllib.request import urlopen

from exchange.timeline_projection import timeline_projection
from exchange.timeline_page import EXECUTION_WORDS, WORDS, render_timeline
from integration.test_timeline_deadlines import domain
from integration import test_authorization_locale_transport as mounted


class TimelineExecutionObservationTests(unittest.TestCase):
    def test_only_original_executed_state_is_projected_as_recorded_trade(self):
        value = domain()
        value.entries[0]["executionStatus"] = "executed"
        value.entries[1]["executionStatus"] = "PRIVATE-NATIVE-SUCCESS"
        value.entries[2]["executionStatus"] = "confirmed"
        result = timeline_projection(value, "receipt-1")
        self.assertEqual([row["executionStatus"] for row in result["legs"]],
                         ["executed", "unknown", "unknown", "unknown"])
        self.assertNotIn("PRIVATE-NATIVE-SUCCESS", str(result))
        self.assertEqual(result["chainAcceptance"], "NOT_RUN")
        self.assertFalse(result["protocolFinalityEstablished"])

    def test_invalid_or_missing_time_stays_unknown_without_relabeling_it_as_block_time(self):
        value = domain()
        for entry, invalid in zip(value.entries, (None, True, -1, "101")):
            entry.update(executionStatus="executed", executedAt=invalid)
        result = timeline_projection(value, "receipt-1")
        self.assertTrue(all(row["executedAt"] is None for row in result["legs"]))
        for locale, words in WORDS.items():
            page = render_timeline(value, "receipt-1", locale=locale)
            self.assertIn(escape(words["unknown"]), page)
            self.assertIn(escape(EXECUTION_WORDS[locale][3]), page)

    def test_execution_registration_and_funding_never_collapse_into_one_success(self):
        value = domain()
        value.entries[0].update(executionStatus="executed", registrationStatus="pending", fundingStatus="locked")
        value.entries[1].update(executionStatus="executed", registrationStatus="rejected", fundingStatus="refunded")
        value.entries[2].update(registrationStatus="confirmed", fundingStatus="released")
        result = timeline_projection(value, "receipt-1")
        self.assertEqual([(row["executionStatus"], row["registrationStatus"], row["fundingStatus"])
                          for row in result["legs"][:3]], [
            ("executed", "pending", "locked"), ("executed", "rejected", "refunded"),
            ("unknown", "confirmed", "released")])
        self.assertNotIn("complete", result["legs"][0].values())

    def test_recorded_time_and_execution_fields_do_not_rewrite_original_history(self):
        value = domain()
        value.entries[0]["executionStatus"] = "executed"
        before = deepcopy(value.entries)
        result = timeline_projection(value, "receipt-1", now=125)
        self.assertEqual(value.entries, before)
        self.assertEqual(value.reads, [("receipt-1", 125)])
        self.assertEqual([row["executedAt"] for row in result["legs"]], [100, 101, 102, 103])
        self.assertEqual([row["fromPosition"] for row in result["legs"]], [0, 1, 0, 1])
        self.assertEqual([row["legIndex"] for row in result["legs"] if row["historicalWithdrawn"]], [1, 2])
        self.assertEqual(result["deadlines"]["registrationDeadline"], 250)

    def test_six_locales_display_recorded_execution_and_time_without_private_state_or_parties(self):
        value = domain()
        value.entries[0]["executionStatus"] = "executed"
        value.entries[1]["executionStatus"] = "PRIVATE-STATE"
        for locale, labels in EXECUTION_WORDS.items():
            with self.subTest(locale=locale):
                page = render_timeline(value, "receipt-1", locale=locale)
                for label in labels:
                    self.assertIn(escape(label), page)
                self.assertIn("<td>100</td>", page)
                self.assertIn('class="timeline-deadlines"', page)
                for private in ("PRIVATE-STATE", "PRIVATE-BUYER", "PRIVATE-SELLER", "private-0"):
                    self.assertNotIn(private, page)
                self.assertNotIn("<form", page)

    def test_future_or_ambiguous_execution_states_never_imply_recorded_execution(self):
        for invalid in ("submitted", "pending", "settled", "done", "0x" + "a" * 40, True, {}, []):
            value = domain()
            for entry in value.entries:
                entry["executionStatus"] = invalid
            result = timeline_projection(value, "receipt-1")
            self.assertTrue(all(row["executionStatus"] == "unknown" for row in result["legs"]))
            self.assertNotIn(EXECUTION_WORDS["en"][2], render_timeline(value, "receipt-1"))

    def test_empty_original_history_keeps_all_column_headers_and_explicit_empty_state(self):
        value = domain()
        value.originals = []
        value.entries = []
        original = value.receipt_view
        value.receipt_view = lambda *args: {**original(*args), "activeLegIndices": (),
                                          "historicalWithdrawnLegIndices": ()}
        for locale, words in WORDS.items():
            page = render_timeline(value, "receipt-1", locale=locale)
            self.assertIn('colspan="10"', page)
            self.assertIn(escape(words["empty"]), page)
            self.assertEqual(page.count('<th scope="col">'), 10)

    def test_existing_native_and_integrated_routes_keep_execution_and_cutoff_views_together(self):
        for integrated in (False, True):
            fixture = mounted.AuthorizationLocaleTransportTests("runTest")
            self.addCleanup(fixture.doCleanups)
            server = fixture.server(integrated)
            value = domain()
            value.entries[0]["executionStatus"] = "executed"
            server.binding.exchange = value
            server.binding.receipt_id = "receipt-1"
            for locale in EXECUTION_WORDS:
                with self.subTest(integrated=integrated, locale=locale):
                    with urlopen(server.origin + "/timeline?lang=" + locale, timeout=3) as response:
                        page = response.read().decode("utf-8")
                    self.assertIn(escape(EXECUTION_WORDS[locale][2]), page)
                    self.assertIn('class="timeline-deadlines"', page)
                    self.assertIn("<dd>250</dd>", page)
                    self.assertNotIn("PRIVATE-BUYER", page)
