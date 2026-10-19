"""Approved Linux HTTP definitions; health does not perform business work."""
import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from exchange.health_observation import health_observation
from exchange.workbench import RuntimeBinding, WorkbenchServer


COMMIT = "a" * 40
TREE = "b" * 40
PRIVATE = "private-wallet-session-provider-value"


class NativeHealthReadbackTests(unittest.TestCase):
    def project(self, source, **flags):
        values = dict(gateway_configured=False, reference_feed_configured=False,
                      gas_page_configured=False, registration_sources_configured=False)
        values.update(flags)
        return health_observation(source, **values)

    def start(self, server):
        worker = threading.Thread(target=server.serve_forever,
                                  kwargs={"poll_interval": 0.02}, daemon=True)
        worker.start()
        def close():
            server.shutdown()
            worker.join(timeout=3)
            server.server_close()
        self.addCleanup(close)

    def get(self, server, path="/healthz", headers=None):
        with urlopen(Request(server.origin + path, headers=headers or {}), timeout=3) as response:
            return response.status, dict(response.headers), json.load(response)

    def test_projection_exposes_only_declared_source_and_component_presence(self):
        value = self.project({"commit": COMMIT, "tree": TREE, "token": PRIVATE,
                              "meaning": PRIVATE}, gateway_configured=True)
        self.assertEqual(value["declaredSource"], {"commit": COMMIT, "tree": TREE})
        self.assertEqual(value["sourceIdentity"], "DECLARED_ONLY")
        self.assertTrue(value["configuredComponents"]["commandGateway"])
        for key in ("operationsREADY", "providerExecution", "chainAcceptance", "persistentRecovery"):
            self.assertIn(value[key], ("NOT_VERIFIED", "NOT_EVALUATED"))
        self.assertNotIn(PRIVATE, json.dumps(value))
        self.assertNotIn("receiptId", value)

    def test_invalid_or_missing_source_is_unverified_and_flags_are_not_truthiness(self):
        for value in ({}, {"commit": PRIVATE, "tree": TREE},
                      {"commit": COMMIT, "tree": "B" * 40}):
            with self.subTest(value=value):
                self.assertEqual(self.project(value)["sourceIdentity"], "UNVERIFIED")
        with self.assertRaises(ValueError):
            self.project({"commit": COMMIT, "tree": TREE}, gateway_configured="true")

    def test_mounted_health_does_not_read_domain_or_dispatch_gateway(self):
        class Unreadable:
            def __getattr__(self, name):
                raise AssertionError("health must not read or dispatch " + name)
        server = WorkbenchServer(RuntimeBinding(Unreadable(), PRIVATE,
            gateway=Unreadable()), commit=COMMIT, tree=TREE)
        self.start(server)
        status, headers, value = self.get(server)
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["Content-Type"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(value["httpProcess"], "serving")
        self.assertTrue(value["configuredComponents"]["commandGateway"])
        self.assertFalse(value["configuredComponents"]["gasPage"])
        self.assertNotIn(PRIVATE, json.dumps(value))

    def test_health_rejects_parameters_and_foreign_host(self):
        server = WorkbenchServer(RuntimeBinding(object(), PRIVATE), commit=COMMIT, tree=TREE)
        self.start(server)
        for path in ("/healthz?receipt=" + PRIVATE, "/healthz?lang=en"):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                self.get(server, path)
            self.assertEqual(error.exception.code, 400)
            self.assertNotIn(PRIVATE, error.exception.read().decode())
        with self.assertRaises(HTTPError) as error:
            self.get(server, headers={"Host": "foreign.invalid"})
        self.assertEqual(error.exception.code, 421)

    def test_integrated_handler_inherits_health_without_invoking_controllers(self):
        from integration.test_integrated_runtime_inputs import IntegratedRuntimeInputsTests
        fixture = IntegratedRuntimeInputsTests("runTest")
        self.addCleanup(fixture.doCleanups)
        server = fixture.server()
        self.start(server)
        status, _, value = self.get(server)
        self.assertEqual(status, 200)
        self.assertTrue(value["configuredComponents"]["gasPage"])
        self.assertTrue(value["configuredComponents"]["registrationSources"])
        self.assertEqual(fixture.wallet_calls, [])
