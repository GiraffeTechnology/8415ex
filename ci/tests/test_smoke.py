"""Filesystem tests require an explicit controller-approved test root."""

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from ci.evidence import EvidenceError, verify_sha256
from ci.smoke import PAYLOAD, main, run_smoke


def identity():
    return {
        "repository": "GiraffeTechnology/8415ex",
        "commit_sha": "a" * 40,
        "tree_sha": "b" * 40,
        "config_sha256": "c" * 64,
        "run_id": "synthetic-smoke-1",
    }


class SmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = os.environ.get("BOOTSTRAP_TEST_ROOT")
        if not raw:
            raise RuntimeError("Set BOOTSTRAP_TEST_ROOT to approved non-system-disk storage")
        root = Path(raw)
        if not root.is_absolute() or not root.is_dir() or root.resolve() != root:
            raise RuntimeError("BOOTSTRAP_TEST_ROOT must be an existing canonical absolute directory")
        cls.root = root

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="8415ex-smoke-test-", dir=self.root)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)

    def test_success_writes_artifact_and_identity_manifest(self):
        self.assertEqual(run_smoke(self.path, identity(), "success"), 0)
        self.assertEqual((self.path / "smoke.txt").read_bytes(), PAYLOAD)
        manifest = json.loads((self.path / "smoke-manifest.json").read_text())
        self.assertEqual(manifest["identity"], identity())
        self.assertEqual(manifest["outcome"], "success")
        artifact = manifest["artifacts"][0]
        self.assertEqual(artifact["path"], "smoke.txt")
        self.assertEqual(artifact["size_bytes"], len(PAYLOAD))
        verify_sha256((self.path / artifact["path"]).read_bytes(), artifact["sha256"])

    def test_deliberate_failure_returns_nonzero_and_no_success_artifact(self):
        self.assertEqual(run_smoke(self.path, identity(), "failure"), 1)
        manifest = json.loads((self.path / "smoke-manifest.json").read_text())
        self.assertEqual(manifest["outcome"], "failure")
        self.assertEqual(manifest["artifacts"], [])
        self.assertFalse((self.path / "smoke.txt").exists())

    def test_repeated_run_cannot_overwrite_prior_evidence(self):
        run_smoke(self.path, identity(), "success")
        before = (self.path / "smoke-manifest.json").read_bytes()
        with self.assertRaises(EvidenceError):
            run_smoke(self.path, identity(), "failure")
        self.assertEqual((self.path / "smoke-manifest.json").read_bytes(), before)

    def test_missing_directory_is_not_created(self):
        missing = self.path / "missing"
        with self.assertRaises(EvidenceError):
            run_smoke(missing, identity(), "success")
        self.assertFalse(missing.exists())

    def test_relative_directory_is_rejected(self):
        with self.assertRaises(EvidenceError):
            run_smoke("relative-output", identity(), "success")

    def test_symlink_directory_is_rejected(self):
        target = self.path / "target"
        target.mkdir()
        link = self.path / "link"
        link.symlink_to(target, target_is_directory=True)
        with self.assertRaises(EvidenceError):
            run_smoke(link, identity(), "success")

    def test_invalid_identity_writes_nothing(self):
        invalid = identity()
        invalid["commit_sha"] = "short"
        with self.assertRaises(EvidenceError):
            run_smoke(self.path, invalid, "success")
        self.assertEqual(list(self.path.iterdir()), [])

    def test_invalid_mode_writes_nothing(self):
        with self.assertRaises(EvidenceError):
            run_smoke(self.path, identity(), "unknown")
        self.assertEqual(list(self.path.iterdir()), [])

    def test_cli_requires_explicit_output_and_identity(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                main([])
        self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
