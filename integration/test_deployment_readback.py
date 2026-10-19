"""Synthetic definitions for approved remote execution; no live origin assumed."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import unittest

from exchange.deployment_readback import ASSETS, Observation, ReadbackRefused, verify


ORIGIN = "https://synthetic.invalid:8443"
SOURCE = {"commit": "a" * 40, "tree": "b" * 40}


def fixture():
    health = {"schema": "8415ex-http-health-observation/1", "httpProcess": "serving",
              "declaredSource": dict(SOURCE), "sourceIdentity": "DECLARED_ONLY",
              "operationsREADY": "NOT_VERIFIED", "providerExecution": "NOT_EVALUATED",
              "chainAcceptance": "NOT_EVALUATED", "persistentRecovery": "NOT_EVALUATED",
              "configuredComponents": {name: False for name in
                  ("commandGateway", "referenceFeed", "gasPage", "registrationSources")}}
    bodies = {"/assets/" + name: ("synthetic-bytes-" + name).encode() for name in ASSETS}
    manifest = [{"path": path, "bytes": len(body),
                 "sha256": hashlib.sha256(body).hexdigest()}
                for path, body in bodies.items()]
    raw = json.dumps(health).encode()
    observations = {"/healthz": observation("/healthz", raw, "application/json")}
    observations.update({path: observation(path, body, ASSETS[path.rsplit("/", 1)[1]])
                         for path, body in bodies.items()})
    return health, manifest, observations


def observation(path, body, content_type):
    return Observation(200, {"Content-Type": content_type,
                       "Content-Length": str(len(body)), "Cache-Control": "no-store"},
                       body, ORIGIN + path)


class ServedResourceReadback(unittest.TestCase):
    def run_readback(self, manifest, observations, source=None):
        calls = []
        def read(path, limit):
            calls.append((path, limit))
            return observations[path]
        result = verify(ORIGIN, SOURCE if source is None else source, manifest, read=read)
        return result, calls

    def test_complete_exact_readback_still_does_not_attest_installed_source_or_business(self):
        _, manifest, observations = fixture()
        result, calls = self.run_readback(manifest, observations)
        self.assertTrue(result["httpReadbackPassed"])
        self.assertEqual(len(calls), 8)
        self.assertEqual({p for p, _ in calls}, {"/healthz"} | {x["path"] for x in manifest})
        self.assertEqual(result["assetCount"], 7)
        self.assertEqual(result["installedSourceIdentity"], "NOT_VERIFIED")
        self.assertEqual(result["operationsREADY"], "NOT_VERIFIED")
        self.assertEqual(result["providerExecution"], "NOT_EVALUATED")
        self.assertEqual(result["uiJourneyAcceptance"], "NOT_EVALUATED")
        self.assertEqual(result["completeProductAcceptance"], "OPEN")

    def test_declared_source_mismatch_stops_before_asset_requests(self):
        _, manifest, observations = fixture()
        calls = []
        def read(path, limit):
            calls.append(path)
            return observations[path]
        with self.assertRaisesRegex(ReadbackRefused, "DECLARED_SOURCE_MISMATCH"):
            verify(ORIGIN, dict(SOURCE, tree="c" * 40), manifest, read=read)
        self.assertEqual(calls, ["/healthz"])

    def test_modified_asset_bytes_and_short_reads_are_refused(self):
        _, manifest, observations = fixture()
        path = sorted(p for p in observations if p.startswith("/assets/"))[0]
        original = observations[path]
        for body in (b"x" * len(original.body), original.body[:-1], original.body + b"x"):
            with self.subTest(size=len(body)):
                changed = dict(observations)
                changed[path] = replace(original, body=body)
                with self.assertRaises(ReadbackRefused):
                    self.run_readback(manifest, changed)

    def test_redirect_status_auth_challenge_and_different_final_path_are_refused(self):
        _, manifest, observations = fixture()
        for change in ({"status": 302}, {"status": 401},
                       {"final_url": "https://elsewhere.invalid/healthz"},
                       {"final_url": ORIGIN + "/healthz?other=1"}):
            with self.subTest(change=change):
                changed = dict(observations)
                changed["/healthz"] = replace(changed["/healthz"], **change)
                with self.assertRaises(ReadbackRefused):
                    self.run_readback(manifest, changed)

    def test_incomplete_duplicate_or_nonapproved_asset_manifest_never_reads(self):
        _, manifest, _ = fixture()
        variants = [manifest[:-1], manifest[:-1] + [manifest[0]],
                    [dict(manifest[0], path="/assets/../private")] + manifest[1:],
                    [dict(manifest[0], bytes=True)] + manifest[1:]]
        for variant in variants:
            with self.subTest(variant=variant):
                with self.assertRaises(ReadbackRefused):
                    verify(ORIGIN, SOURCE, variant,
                           read=lambda *args: self.fail("invalid manifest reached transport"))

    def test_readiness_promotion_and_nonboolean_component_flags_are_refused(self):
        health, manifest, observations = fixture()
        variants = [dict(health, operationsREADY="READY"),
                    dict(health, providerExecution="VERIFIED"),
                    dict(health, configuredComponents=dict(health["configuredComponents"],
                                                           commandGateway="true"))]
        for changed_health in variants:
            with self.subTest(health=changed_health):
                changed = dict(observations)
                changed["/healthz"] = observation("/healthz", json.dumps(changed_health).encode(),
                                                   "application/json")
                with self.assertRaises(ReadbackRefused):
                    self.run_readback(manifest, changed)

    def test_mime_encoding_cache_length_and_header_ambiguity_are_refused(self):
        _, manifest, observations = fixture()
        original = observations["/healthz"]
        for changes in ({"Content-Type": "text/html"}, {"Content-Encoding": "gzip"},
                        {"Transfer-Encoding": "chunked"},
                        {"Cache-Control": "public"}, {"Content-Length": "0"},
                        {"content-length": str(len(original.body))}):
            with self.subTest(changes=changes):
                headers = dict(original.headers, **changes)
                changed = dict(observations)
                changed["/healthz"] = replace(original, headers=headers)
                with self.assertRaises(ReadbackRefused):
                    self.run_readback(manifest, changed)

    def test_duplicate_json_and_untrusted_private_response_are_not_echoed(self):
        _, manifest, observations = fixture()
        private = "private-untrusted-response-value"
        for body in (b'{"schema":1,"schema":2}', private.encode()):
            changed = dict(observations)
            changed["/healthz"] = observation("/healthz", body, "application/json")
            with self.assertRaises(ReadbackRefused) as error:
                self.run_readback(manifest, changed)
            self.assertNotIn(private, str(error.exception))

    def test_result_identity_and_asset_rows_do_not_alias_caller_expectations(self):
        _, manifest, observations = fixture()
        source = deepcopy(SOURCE)
        result, _ = self.run_readback(manifest, observations, source)
        source["commit"] = "c" * 40
        manifest[0]["sha256"] = "d" * 64
        self.assertEqual(result["declaredSource"], SOURCE)
        self.assertNotEqual(result["assets"][0]["sha256"], "d" * 64)


if __name__ == "__main__":
    unittest.main()
