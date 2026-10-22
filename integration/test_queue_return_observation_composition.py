"""Synthetic joined queue display and original reserved-return result contracts."""
from copy import deepcopy
from html import escape
import unittest
from urllib.request import urlopen

from exchange.command_observation_page import (
    WORDS as COMMAND_WORDS, STATUSES, render_command_observations,
)
from exchange.funds_page import WORDS as FUND_WORDS
from exchange.queue_status_page import render_queue_status
from integration import test_authorization_locale_transport as mounted
from integration import test_queue_segment_funds as funds_fixture
from integration import test_wallet_direct_return_task as return_fixture


class QueueReturnObservationCompositionContracts(unittest.TestCase):
    def server(self, integrated=True):
        fixture = mounted.AuthorizationLocaleTransportTests("runTest")
        self.addCleanup(fixture.doCleanups)
        server = fixture.server(integrated)
        class NoGatewayCalls:
            def enquire(self, *args):
                raise AssertionError("Queue display must not query native operations")
            def dispatch(self, *args):
                raise AssertionError("Queue display must not dispatch native operations")
        server.binding.gateway = NoGatewayCalls()
        return server

    def page(self, server, locale):
        with urlopen(server.origin + "/queue?lang=" + locale, timeout=3) as response:
            self.assertEqual(response.headers["Cache-Control"], "no-store")
            return response.read().decode()

    def test_standalone_and_integrated_queue_keep_both_components_in_six_locales(self):
        for integrated in (False, True):
            server = self.server(integrated)
            server.command_observations["PRIVATE-CACHE"] = {
                "action":"advance-rollback", "enquired":True,
                "result":{"status":"unknown", "actor":"0x" + "a"*40}}
            for locale in COMMAND_WORDS:
                with self.subTest(integrated=integrated, locale=locale):
                    page = self.page(server, locale)
                    self.assertEqual(page.count('data-segment-funds="1"'), 1)
                    self.assertEqual(page.count('class="command-observations"'), 1)
                    self.assertIn(escape(FUND_WORDS[locale]["heading"]), page)
                    self.assertIn(escape(COMMAND_WORDS[locale]["heading"]), page)
                    self.assertIn(escape(STATUSES[locale]["unknown"]), page)
                    self.assertNotIn("PRIVATE-CACHE", page)
                    self.assertNotIn("0x" + "a"*40, page)

    def test_return_execute_result_stays_unknown_without_queue_triggered_wallet_calls(self):
        with return_fixture.direct_task() as (task, client, state, value, options):
            result = task.execute("4")
            before = deepcopy(state["calls"])
            server = self.server()
            server.command_observations["PRIVATE-ORIGINAL-OPERATION"] = {
                "action":"advance-rollback", "enquired":False, "result":result}
            for locale in COMMAND_WORDS:
                page = self.page(server, locale)
                self.assertIn(escape(STATUSES[locale]["unknown"]), page)
                self.assertIn(escape(COMMAND_WORDS[locale]["dispatched"]), page)
                for private in ("PRIVATE-ORIGINAL-OPERATION", result["taskDigest"],
                        result["childDigest"], result["walletOperationId"],
                        result["scope"]["nativeOperationId"]):
                    self.assertNotIn(private, page)
            self.assertEqual(state["calls"], before)
            self.assertEqual(len(return_fixture.executes(state)), 1)
            self.assertFalse(result["nativeOutcomeVerified"])
            self.assertFalse(result["replayAllowed"])

    def test_empty_cache_does_not_infer_original_operation_or_native_funds_absence(self):
        server = self.server()
        self.assertEqual(server.command_observations, {})
        for locale, words in COMMAND_WORDS.items():
            page = self.page(server, locale)
            self.assertIn(escape(words["empty"]), page)
            self.assertIn(escape(words["boundary"]), page)
            self.assertIn(escape(FUND_WORDS[locale]["boundary"]), page)
            self.assertNotIn("No original operations exist", page)

    def test_original_segment_units_and_unknown_command_remain_independent(self):
        source = funds_fixture.OriginalReader()
        before = deepcopy(source.report)
        observations = [{"action":"reconcile-payment", "enquired":True,
                         "result":{"status":"unknown"}}]
        for locale in COMMAND_WORDS:
            page = (render_queue_status(source, "receipt-fixture", locale=locale)
                + render_command_observations(observations, locale=locale))
            self.assertIn("700 PYUSD", page)
            self.assertIn("900 ETH", page)
            self.assertIn("11 ETH wei", page)
            self.assertIn("13 ETH wei", page)
            self.assertIn(escape(FUND_WORDS[locale]["releaseUnknown"]), page)
            self.assertIn(escape(STATUSES[locale]["unknown"]), page)
            self.assertNotIn("fixture-private-journal", page)
            self.assertNotIn("fixture-private-seller", page)
        self.assertEqual(source.report, before)
        self.assertEqual(source.calls, [("receipt-fixture", 100)]*len(COMMAND_WORDS))
