"""Archive integrity and evidence-boundary regression checks."""
import copy
import io
import json
import unittest
import zipfile
from exchange.delivery import build_bundle, verify_bundle, git_tree, sha256, validate_evidence

class DeliveryIntegrity(unittest.TestCase):
    def setUp(self):
        self.files = {"example.py": b"print('synthetic integrity fixture')\n"}
        self.logs = {"test.log": b"synthetic verification fixture; not a product test result\n"}
        self.evidence = {
            "kind": "LOCAL_SIMULATION", "commit": "ab" * 20, "tree": git_tree(self.files),
            "runs": [{"testedTree": git_tree(self.files), "command": "synthetic fixture",
                      "exitCode": 0, "status": "passed", "log": "test.log",
                      "logSHA256": sha256(self.logs["test.log"]),
                      "startUTC": "2026-01-01T00:00:00Z", "endUTC": "2026-01-01T00:00:01Z"}],
            "notRun": [{"status": "NOT_RUN", "obligation": "real deployment"}]}
    def test_repeatable_archive_and_complete_tree_binding(self):
        first = build_bundle(self.files, self.evidence, self.logs)
        self.assertEqual(first, build_bundle(self.files, self.evidence, self.logs))
        result = verify_bundle(first)
        self.assertTrue(result["verified"])
        self.assertEqual(result["tree"], self.evidence["tree"])
        self.assertEqual(result["sha256"], sha256(first))

    def test_non_string_and_short_source_identity_refused(self):
        for field in ("commit", "tree"):
            for bad in (None, 0, False, [], {}, "abc"):
                with self.subTest(field=field, value=bad):
                    evidence = copy.deepcopy(self.evidence)
                    evidence[field] = bad
                    with self.assertRaises(ValueError):
                        validate_evidence(evidence, self.logs)

    def test_missing_log_or_false_exit_claim_refused(self):
        for change in ({"log": "missing"}, {"logSHA256": "0" * 64},
                       {"exitCode": True}, {"exitCode": 1}, {"endUTC": "2025-01-01T00:00:00Z"}):
            with self.subTest(change=change):
                evidence = copy.deepcopy(self.evidence)
                evidence["runs"][0].update(change)
                with self.assertRaises(ValueError):
                    validate_evidence(evidence, self.logs)

    def test_changed_source_refused_even_when_member_hashes_are_current(self):
        with self.assertRaisesRegex(ValueError, "source tree"):
            build_bundle({"example.py": b"changed"}, self.evidence, self.logs)

    def rewrite(self, mutate):
        blob = build_bundle(self.files, self.evidence, self.logs)
        with zipfile.ZipFile(io.BytesIO(blob)) as source:
            members = {name: source.read(name) for name in source.namelist()}
        mutate(members)
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as target:
            for name, value in members.items():
                target.writestr(name, value)
        return out.getvalue()

    def test_modified_log_and_missing_inventory_member_refused(self):
        def change(members):
            members["logs/test.log"] = b"forged log"
        with self.assertRaises(ValueError):
            verify_bundle(self.rewrite(change))
        def omit(members):
            del members["source/example.py"]
        with self.assertRaisesRegex(ValueError, "inventory"):
            verify_bundle(self.rewrite(omit))

    def test_traversal_member_and_missing_not_run_boundary_refused(self):
        def traversal(members):
            members["../escape"] = b"no"
        with self.assertRaisesRegex(ValueError, "unsafe"):
            verify_bundle(self.rewrite(traversal))
        evidence = copy.deepcopy(self.evidence)
        evidence["notRun"] = []
        with self.assertRaises(ValueError):
            build_bundle(self.files, evidence, self.logs)
