"""Process-local queue observation display definitions; author execution NOT_RUN."""
from html import escape
import unittest
from urllib.request import urlopen

from exchange.command_observation_page import (
    WORDS, STATUSES, STATUS_KEYS, ACTIONS, render_command_observations,
)
from exchange.public_workbench import STATES
from integration import test_authorization_locale_transport as mounted


class CommandObservationPageTests(unittest.TestCase):
    def test_all_original_public_statuses_have_six_fixed_language_resources(self):
        self.assertEqual(set(STATUS_KEYS), set(STATES))
        self.assertEqual(set(WORDS), set(STATUSES))
        observations = [{"action": "reconcile-payment", "result": {"status": state},
                         "enquired": True} for state in STATUS_KEYS]
        for locale, statuses in STATUSES.items():
            page = render_command_observations(observations, locale=locale)
            self.assertEqual(set(statuses), set(STATES))
            for label in statuses.values():
                self.assertIn(escape(label), page)
            self.assertIn(escape(WORDS[locale]["boundary"]), page)

    def test_raw_keys_accounts_diagnostics_payloads_and_unknown_actions_never_enter_html(self):
        address = "0x" + "a" * 40
        observations = [{"action": address, "enquired": "PRIVATE-PATH",
                         "journalKey": "PRIVATE-JOURNAL", "payload": {"actor": address},
                         "meaning": "PRIVATE-DIAGNOSTIC",
                         "result": {"status": "PRIVATE-STATUS", "actor": address,
                                    "transactionHash": address, "error": "PRIVATE-ERROR"}}]
        for locale in WORDS:
            page = render_command_observations(observations, locale=locale)
            for raw in (address, "PRIVATE-PATH", "PRIVATE-JOURNAL", "PRIVATE-DIAGNOSTIC",
                        "PRIVATE-STATUS", "PRIVATE-ERROR"):
                self.assertNotIn(raw, page)
            self.assertIn(escape(WORDS[locale]["unknown"]), page)

    def test_enquiry_dispatch_and_unknown_paths_are_independent_of_reported_completion(self):
        observations = [
            {"action": "reconcile-payment", "enquired": True, "result": {"status": "unknown"}},
            {"action": "submit-registration", "enquired": False, "result": {"status": "pending"}},
            {"action": "advance-rollback", "enquired": "false", "result": {"status": "done"}}]
        page = render_command_observations(observations)
        self.assertIn(WORDS["en"]["enquired"], page)
        self.assertIn(WORDS["en"]["dispatched"], page)
        self.assertIn(STATUSES["en"]["unknown"], page)
        self.assertIn(STATUSES["en"]["pending"], page)
        self.assertIn(STATUSES["en"]["done"], page)
        self.assertNotIn("<form", page)

    def test_empty_or_restart_view_does_not_claim_original_journal_absence(self):
        for locale, words in WORDS.items():
            page = render_command_observations([], locale=locale)
            self.assertIn(escape(words["empty"]), page)
            self.assertIn(escape(words["boundary"]), page)
            self.assertIn('colspan="5"', page)
            self.assertNotIn("No original operations exist", page)

    def test_bounded_sixty_four_observations_are_all_retained_without_private_cache_keys(self):
        values = [{"action": "resume-payment", "enquired": True,
                   "result": {"status": "unknown"}} for _ in range(64)]
        page = render_command_observations(values)
        self.assertEqual(page.count("<tbody><tr>"), 1)
        self.assertEqual(page.count("<tr>"), 65)
        self.assertIn("<td>64</td>", page)
        with self.assertRaises(ValueError):
            render_command_observations(values + [values[0]])
        with self.assertRaises(ValueError):
            render_command_observations({"PRIVATE-KEY": values[0]})
        with self.assertRaises(ValueError):
            render_command_observations(object(), locale="de")

    def test_only_complete_original_transaction_hash_is_shown_without_new_explorer_route(self):
        transaction = "0x" + "b" * 64
        page = render_command_observations([{"action": "resume-payment",
            "result": {"status": "pending", "transactionHash": transaction}}])
        self.assertIn(transaction, page)
        self.assertNotIn('href=', page)
        self.assertNotIn("etherscan", page)
        for invalid in ("0x" + "c" * 40, "<script>private</script>", transaction + "0"):
            page = render_command_observations([{"result": {"status": "pending", "transactionHash": invalid}}])
            self.assertNotIn(invalid, page)

    def test_malformed_rows_and_unfamiliar_statuses_remain_visible_as_unknown(self):
        values = [None, "PRIVATE-ROW", {"result": {"status": "DONE"}},
                  {"result": {"status": True}}, {"result": None}]
        for locale in WORDS:
            page = render_command_observations(values, locale=locale)
            self.assertIn("<td>5</td>", page)
            self.assertIn(escape(WORDS[locale]["unknown"]), page)
            self.assertNotIn("PRIVATE-ROW", page)
            self.assertNotIn(">DONE<", page)

    def test_existing_native_and_integrated_queue_routes_use_ram_only_without_gateway_calls(self):
        class ForbiddenGateway:
            def enquire(self, *args):
                raise AssertionError("queue display must not enquire native operations")
            def dispatch(self, *args):
                raise AssertionError("queue display must not dispatch native operations")
        for integrated in (False, True):
            fixture = mounted.AuthorizationLocaleTransportTests("runTest")
            self.addCleanup(fixture.doCleanups)
            server = fixture.server(integrated)
            server.binding.gateway = ForbiddenGateway()
            server.command_observations["PRIVATE-KEY"] = {
                "action": "reconcile-payment", "enquired": True,
                "result": {"status": "unknown", "diagnostic": "PRIVATE-DIAGNOSTIC"}}
            for locale, words in WORDS.items():
                with self.subTest(integrated=integrated, locale=locale):
                    with urlopen(server.origin + "/queue?lang=" + locale, timeout=3) as response:
                        page = response.read().decode("utf-8")
                    self.assertIn('class="command-observations"', page)
                    self.assertIn(escape(words["heading"]), page)
                    self.assertIn(escape(words["enquired"]), page)
                    self.assertNotIn("PRIVATE-KEY", page)
                    self.assertNotIn("PRIVATE-DIAGNOSTIC", page)
