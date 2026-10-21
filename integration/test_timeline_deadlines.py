"""Timeline cutoff display definitions; author execution NOT_RUN."""
from copy import deepcopy
from html import escape
import unittest
from urllib.request import urlopen

from exchange.timeline_projection import timeline_projection
from exchange.timeline_page import DEADLINE_WORDS, DEADLINE_RULES, render_timeline
from integration.test_timeline_predecessor import TimelineDomain
from integration import test_authorization_locale_transport as mounted


def domain(comparison="LTE"):
    value = TimelineDomain()
    original = value.receipt_view
    declaration = {"receiptId": "receipt-1", "canonicalDeclaration": {
        "schema": "8415ex-mint-declaration/1",
        "receipt": {"receipt_id": "receipt-1", "minted_at": 50, "trade_stop_at": 200,
                    "origin_account": "PRIVATE-ORIGIN"},
        "time": {"unit": "unix-second", "timezone": "UTC", "precision": "integer",
                 "tradeStopAt": 200, "tradeComparison": "LT",
                 "registrationDeadline": 250, "registrationComparison": comparison,
                 "registrationAlsoMustNotExceedTradeStop": True},
        "controlledAccessMapping": "PRIVATE-CONTROLLED-MAPPING"}}
    value.declaration = declaration
    value.reads = []
    def read(receipt_id, now):
        value.reads.append((receipt_id, now))
        return {**original(receipt_id, now), "tradeStopAt": 200, "simulatedRegistration": True,
                "mintDeclaration": deepcopy(value.declaration)}
    value.receipt_view = read
    return value


class TimelineDeadlineTests(unittest.TestCase):
    def test_original_mint_time_semantics_are_distinct_from_observation_and_request_windows(self):
        result = timeline_projection(domain(), "receipt-1", now=110)
        times = result["deadlines"]
        self.assertEqual(times["tradeStopAt"], 200)
        self.assertEqual(times["registrationDeadline"], 250)
        self.assertEqual(times["tradeComparison"], "LT")
        self.assertEqual(times["registrationComparison"], "LTE")
        self.assertEqual((times["unit"], times["timezone"], times["precision"]),
                         ("unix-second", "UTC", "integer"))
        self.assertTrue(times["registrationAlsoMustNotExceedTradeStop"])
        self.assertEqual(result["observedAt"], 110)
        self.assertNotIn("commitmentDeadlineAt", times)

    def test_legacy_missing_declaration_stays_unknown_without_fabricated_utc_or_registration_time(self):
        result = timeline_projection(TimelineDomain(), "receipt-1")
        times = result["deadlines"]
        self.assertEqual(times["declarationStatus"], "not-provided")
        for field in ("tradeStopAt", "registrationDeadline", "unit", "timezone", "precision",
                      "tradeComparison", "registrationComparison"):
            self.assertIsNone(times[field])
        value = domain()
        value.declaration = None
        times = timeline_projection(value, "receipt-1")["deadlines"]
        self.assertEqual(times["tradeStopAt"], 200)
        self.assertIsNone(times["unit"])
        self.assertIsNone(times["registrationDeadline"])

    def test_foreign_or_conflicting_declaration_only_makes_cutoff_semantics_unavailable(self):
        changes = [
            lambda d: d.update(receiptId="other"),
            lambda d: d["canonicalDeclaration"]["receipt"].update(receipt_id="other"),
            lambda d: d["canonicalDeclaration"]["receipt"].update(trade_stop_at=True),
            lambda d: d["canonicalDeclaration"]["time"].update(tradeStopAt=201),
            lambda d: d["canonicalDeclaration"]["time"].update(unit="millisecond"),
            lambda d: d["canonicalDeclaration"]["time"].update(timezone="PRIVATE-ZONE"),
            lambda d: d["canonicalDeclaration"]["time"].update(registrationDeadline=True),
            lambda d: d["canonicalDeclaration"]["time"].update(registrationComparison="PRIVATE-RULE"),
            lambda d: d["canonicalDeclaration"]["time"].update(registrationAlsoMustNotExceedTradeStop=False)]
        for change in changes:
            value = domain()
            change(value.declaration)
            with self.subTest(change=change):
                result = timeline_projection(value, "receipt-1")
                self.assertEqual(result["deadlines"]["declarationStatus"], "unavailable")
                self.assertIsNone(result["deadlines"]["registrationDeadline"])
                self.assertEqual(len(result["legs"]), 4)
                self.assertEqual(result["holderPosition"], 1)
                self.assertNotIn("PRIVATE-RULE", str(result))

    def test_lt_and_lte_keep_original_equality_semantics_without_admission_or_effective_result(self):
        for comparison in ("LT", "LTE"):
            value = domain(comparison)
            value.evaluate_deadline = lambda *args: self.fail("display must not evaluate or execute recovery")
            result = timeline_projection(value, "receipt-1", now=200)
            self.assertEqual(result["deadlines"]["registrationComparison"], comparison)
            self.assertNotIn("newTradesAccepted", result)
            self.assertNotIn("registrationEffective", result)
            self.assertFalse(result["protocolFinalityEstablished"])
            self.assertEqual(result["chainAcceptance"], "NOT_RUN")

    def test_single_original_observation_clock_and_withdrawn_branch_history_are_preserved(self):
        value = domain()
        result = timeline_projection(value, "receipt-1", now=119)
        self.assertEqual(value.reads, [("receipt-1", 119)])
        self.assertEqual([row["fromPosition"] for row in result["legs"]], [0, 1, 0, 1])
        self.assertEqual([row["legIndex"] for row in result["legs"] if row["historicalWithdrawn"]], [1, 2])
        self.assertEqual(result["ownerPosition"], 4)

    def test_six_languages_render_original_numbers_and_exact_comparison_without_private_fields(self):
        for comparison in ("LT", "LTE"):
            for locale, words in DEADLINE_WORDS.items():
                with self.subTest(comparison=comparison, locale=locale):
                    page = render_timeline(domain(comparison), "receipt-1", locale=locale, now=110)
                    for key in ("heading", "trade", "registration", "unit", "boundary"):
                        self.assertIn(escape(words[key]), page)
                    rules = DEADLINE_RULES[locale]
                    self.assertIn(escape(rules[0]), page)
                    self.assertIn(escape(rules[1] if comparison == "LT" else rules[2]), page)
                    self.assertIn("<dd>200</dd>", page)
                    self.assertIn("<dd>250</dd>", page)
                    self.assertIn("<dd>UTC</dd>", page)
                    for private in ("PRIVATE-ORIGIN", "PRIVATE-CONTROLLED-MAPPING", "private-0"):
                        self.assertNotIn(private, page)
                    self.assertNotIn("<form", page)

    def test_unavailable_semantics_are_localized_without_upper_bound_success_statement(self):
        value = domain()
        value.declaration["canonicalDeclaration"]["time"]["precision"] = "PRIVATE-PRECISION"
        for locale, words in DEADLINE_WORDS.items():
            page = render_timeline(value, "receipt-1", locale=locale)
            self.assertIn(escape(words["unknown"]), page)
            self.assertNotIn(escape(words["upperBound"]), page)
            self.assertNotIn("PRIVATE-PRECISION", page)

    def test_existing_native_and_integrated_timeline_routes_mount_the_same_deadline_panel(self):
        for integrated in (False, True):
            fixture = mounted.AuthorizationLocaleTransportTests("runTest")
            self.addCleanup(fixture.doCleanups)
            server = fixture.server(integrated)
            server.binding.exchange = domain()
            server.binding.receipt_id = "receipt-1"
            for locale in DEADLINE_WORDS:
                with self.subTest(integrated=integrated, locale=locale):
                    with urlopen(server.origin + "/timeline?lang=" + locale, timeout=3) as response:
                        page = response.read().decode("utf-8")
                    self.assertIn('class="timeline-deadlines"', page)
                    self.assertIn(escape(DEADLINE_WORDS[locale]["heading"]), page)
                    self.assertIn("<dd>200</dd>", page)
                    self.assertIn("<dd>250</dd>", page)
                    self.assertNotIn("PRIVATE-CONTROLLED-MAPPING", page)
