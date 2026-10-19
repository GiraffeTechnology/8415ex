"""Authored contracts for independent QA; no provider or deployment evidence."""
import unittest
from unittest.mock import patch
from exchange.runtime_metrics import MeasuredGateway, ObservedRuntimeBinding, ObservedWorkbenchHandler, RuntimeMetrics

class RuntimeMetricsContracts(unittest.TestCase):
    def test_original_arguments_and_unknown_result_are_preserved(self):
        result = {"status": "unknown", "operationId": "original-op"}
        context, payload = {"journalKey": "original-key"}, {"legIndex": 1}
        calls = []
        class Original:
            def enquire(self, key, supplied):
                calls.append((key, supplied))
                return result
            def dispatch(self, action, supplied_payload, supplied_context):
                calls.append((action, supplied_payload, supplied_context))
                return result
        metrics = RuntimeMetrics(clock=iter((0, 2000000, 2000000, 5000000)).__next__)
        gateway = MeasuredGateway(Original(), metrics)
        self.assertIs(gateway.enquire("original-key", context), result)
        self.assertIs(gateway.dispatch("resume-payment", payload, context), result)
        self.assertIs(calls[0][1], context)
        self.assertIs(calls[1][1], payload)
        self.assertIs(calls[1][2], context)
        self.assertEqual(len(calls), 2)
        report = metrics.snapshot()
        self.assertEqual(report["methods"]["enquire"]["latencyMs"]["max"], 2)
        self.assertEqual(report["methods"]["dispatch"]["latencyMs"]["max"], 3)
        self.assertEqual(report["methods"]["dispatch"]["returned"], 1)
        self.assertNotIn("businessSuccess", report)

    def test_exception_identity_is_preserved_without_error_text_or_retry(self):
        failure = TimeoutError("private provider detail must not be retained")
        calls = []
        def operation():
            calls.append(1)
            raise failure
        metrics = RuntimeMetrics()
        with self.assertRaises(TimeoutError) as caught:
            metrics.call("dispatch", operation)
        self.assertIs(caught.exception, failure)
        self.assertEqual(calls, [1])
        report = metrics.snapshot()
        self.assertEqual(report["activeCalls"], 0)
        self.assertEqual(report["methods"]["dispatch"]["raisedRatio"], 1)
        self.assertNotIn("private provider", str(report))

    def test_bounded_window_keeps_lifetime_totals(self):
        metrics = RuntimeMetrics(sample_limit=2, clock=iter((0, 1000000, 0, 2000000, 0, 3000000)).__next__)
        for _ in range(3):
            metrics.call("enquire", lambda: None)
        row = metrics.snapshot()["methods"]["enquire"]
        self.assertEqual(row["started"], 3)
        self.assertEqual(row["latencyWindowCount"], 2)
        self.assertEqual(row["latencyMs"], {"min": 2, "max": 3, "mean": 2.5, "p95NearestRank": 3})

    def test_clock_failure_does_not_prevent_the_original_operation(self):
        calls = []
        def broken_clock():
            raise OSError("unavailable")
        metrics = RuntimeMetrics(clock=broken_clock)
        self.assertEqual(metrics.call("dispatch", lambda: calls.append(1) or 17), 17)
        self.assertEqual(calls, [1])
        row = metrics.snapshot()["methods"]["dispatch"]
        self.assertEqual(row["untimed"], 1)
        self.assertIsNone(row["latencyMs"]["max"])

    def test_active_call_is_visible_without_triggering_another_operation(self):
        metrics = RuntimeMetrics()
        observed = metrics.call("enquire", metrics.snapshot)
        self.assertEqual(observed["activeCalls"], 1)
        self.assertEqual(observed["highWaterCalls"], 1)
        self.assertEqual(metrics.snapshot()["activeCalls"], 0)
        self.assertEqual(metrics.snapshot()["methods"]["dispatch"]["started"], 0)

    def test_observations_do_not_change_the_business_revision(self):
        base = {"source": {"commit": "1" * 40}, "revision": "2" * 64,
                "state": {"receipt": {"legs": [{"registrationStatus": "pending"},
                                               {"registrationStatus": "confirmed"}]},
                          "overdue": [{}]}}
        binding = ObservedRuntimeBinding(object(), "receipt")
        with patch("exchange.runtime_metrics.RuntimeBinding.snapshot", return_value=base):
            result = binding.snapshot()
        self.assertEqual(result["revision"], "2" * 64)
        self.assertEqual(result["performance"]["domainQueueObservation"]["pendingRegistrationLegs"], 1)
        self.assertEqual(result["performance"]["domainQueueObservation"]["overdueRegistrationRequests"], 1)
        self.assertEqual(result["performance"]["methods"]["dispatch"]["started"], 0)
        self.assertIsNone(binding.gateway)

    def test_page_panel_escapes_values_and_preserves_original_content(self):
        class Binding:
            def snapshot(self):
                return {"performance": {"source": {"commit": "<unsafe>"}}}
        class Server:
            binding = Binding()
        handler = object.__new__(ObservedWorkbenchHandler)
        handler.server = Server()
        with patch("exchange.runtime_metrics.WorkbenchHandler.native_page", return_value="<main>original</main>"):
            page = handler.native_page("evidence")
            other = handler.native_page("receipt")
        self.assertIn("original", page)
        self.assertIn("&lt;unsafe&gt;", page)
        self.assertNotIn("<unsafe>", page)
        self.assertEqual(other, "<main>original</main>")

    def test_sample_limit_is_explicit_and_bounded(self):
        for value in (True, 0, 513, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                RuntimeMetrics(sample_limit=value)
