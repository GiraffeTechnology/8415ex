"""The manifest must bind a run to the exact source it came from."""
import hashlib
import unittest
from pathlib import Path

from scenarios import manifest

ROOT = str(Path(__file__).resolve().parents[2])


class SourceIdentity(unittest.TestCase):

    def test_the_commit_and_tree_are_full_length(self):
        source = manifest.source_identity(ROOT)
        self.assertRegex(source["commit"], r"\A[0-9a-f]{40}\Z")
        self.assertRegex(source["tree"], r"\A[0-9a-f]{40}\Z")
        self.assertEqual(source["repository"], "GiraffeTechnology/8415ex")

    def test_the_worktree_state_is_reported_either_way(self):
        source = manifest.source_identity(ROOT)
        self.assertIn(source["worktreeClean"], (True, False))

    def test_the_runtime_names_no_third_party_dependency(self):
        runtime = manifest.runtime_identity()
        self.assertIn("standard library only", runtime["thirdPartyDependencies"])
        self.assertRegex(runtime["python"], r"\A3\.\d+\.\d+\Z")


class Inventory(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.built = manifest.build(ROOT, run_id="local-test",
                                   commands=[{"command": "probe", "exitCode": 0}])

    def test_every_tracked_file_is_listed_with_bytes_and_a_digest(self):
        self.assertGreater(self.built["fileCount"], 20)
        for entry in self.built["files"]:
            self.assertRegex(entry["sha256"], r"\A[0-9a-f]{64}\Z")
            self.assertGreaterEqual(entry["bytes"], 0)

    def test_a_listed_digest_matches_the_file_on_disk(self):
        entry = next(item for item in self.built["files"]
                     if item["path"] == "scenarios/manifest.py")
        data = (Path(ROOT) / entry["path"]).read_bytes()
        self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(entry["bytes"], len(data))

    def test_the_totals_match_the_inventory(self):
        self.assertEqual(self.built["fileCount"], len(self.built["files"]))
        self.assertEqual(self.built["totalBytes"],
                         sum(entry["bytes"] for entry in self.built["files"]))

    def test_the_scope_denies_deployment_and_publication(self):
        self.assertIn("no deployment", self.built["scope"])
        self.assertIn("no published package", self.built["scope"])

    def test_the_scenarios_package_is_inventoried(self):
        paths = {entry["path"] for entry in self.built["files"]}
        for name in ("scenarios/demos.py", "scenarios/paths.py", "scenarios/harness.py",
                     "scenarios/STORYBOARD.md"):
            self.assertIn(name, paths)


if __name__ == "__main__":
    unittest.main()
