"""Source-only workbench contracts for independent Linux QA execution."""
import unittest
from exchange.cli import scenario
from exchange.workbench import RuntimeBinding, stable_revision, public_result

class Gateway:
    def __init__(self, previous=None):
        self.previous = previous
        self.dispatched = []
        self.enquired = []
    def enquire(self, key, context):
        self.enquired.append((key, context))
        return self.previous
    def dispatch(self, action, payload, context):
        self.dispatched.append((action,payload,context))
        return {"status":"pending", "operationId":"fixture-reference"}

class WorkbenchContracts(unittest.TestCase):
    def binding(self, gateway=None):
        ex, _, _, _ = scenario()
        return RuntimeBinding(ex,"rcpt-8415-0001",gateway=gateway)

    def test_unconfigured_gateway_never_dispatches(self):
        binding = self.binding()
        self.assertEqual(binding.snapshot()["commandGateway"],"NOT_CONFIGURED")
        with self.assertRaises(PermissionError):
            binding.command("advance-exit","fixture-key",binding.snapshot()["revision"],{})

    def test_unknown_previous_operation_is_enquired_without_resend(self):
        gateway=Gateway({"status":"unknown"}); binding=self.binding(gateway)
        result=binding.command("resume-payment","same-key",binding.snapshot()["revision"],{"legIndex":0})
        self.assertTrue(result["enquired"])
        self.assertEqual(result["result"]["status"],"unknown")
        self.assertEqual(gateway.dispatched,[])

    def test_checked_gateway_gets_action_payload_and_revision_binding(self):
        gateway=Gateway(); binding=self.binding(gateway)
        revision=binding.snapshot()["revision"]
        result=binding.command("submit-registration","new-key",revision,{"legIndex":1})
        self.assertFalse(result["enquired"])
        action,payload,context=gateway.dispatched[0]
        self.assertEqual(action,"submit-registration")
        self.assertEqual(payload,{"legIndex":1})
        self.assertEqual(context["action"],action)
        self.assertEqual(context["journalKey"],"new-key")
        self.assertEqual(context["observedRevision"],revision)
        self.assertEqual(len(context["payloadDigest"]),64)

    def test_invalid_or_stale_requests_do_not_reach_gateway(self):
        gateway=Gateway(); binding=self.binding(gateway)
        with self.assertRaises(ValueError):
            binding.command("manual-success","fixture-key",binding.snapshot()["revision"],{})
        with self.assertRaises(ValueError):
            binding.command("advance-exit","fixture-key","0"*64,{})
        self.assertEqual(gateway.enquired,[])
        self.assertEqual(gateway.dispatched,[])

    def test_revision_ignores_observation_clock_but_keeps_business_times(self):
        a={"observedAt":1,"nested":{"observedAt":2,"expiresAt":3}}
        b={"observedAt":9,"nested":{"observedAt":8,"expiresAt":3}}
        self.assertEqual(stable_revision(a),stable_revision(b))
        b["nested"]["expiresAt"]=4
        self.assertNotEqual(stable_revision(a),stable_revision(b))

    def test_gateway_payload_is_not_echoed_as_public_evidence(self):
        value=public_result({"status":"pending","secret":"never emit", "rawSignature":"never emit"})
        self.assertEqual(value,{"status":"pending"})
