"""The manifest must bind a run to the exact source it came from.

It also has to fail closed: a root that is not a repository, a Git invocation
that failed and an enumeration that returned nothing must each be reported as
an error, never as a clean, empty or consistent source.
"""
import hashlib
import subprocess
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

    def test_the_reported_root_is_the_tree_this_code_executed_from(self):
        source = manifest.source_identity(ROOT)
        self.assertTrue(source["executedSourceConfirmed"])
        self.assertEqual(source["executedFrom"], manifest.executed_source_root())
        self.assertEqual(source["errors"], [])
        self.assertTrue(source["ok"])

    def test_a_root_outside_this_repository_is_refused_not_reported_clean(self):
        source = manifest.source_identity("/tmp")
        self.assertFalse(source["ok"])
        self.assertFalse(source["executedSourceConfirmed"])
        self.assertIsNone(source["commit"])
        self.assertIsNone(source["worktreeClean"], "an unreadable status is never clean")
        self.assertTrue(source["errors"])

    def test_another_repository_cannot_stand_in_for_the_executed_source(self):
        other = "/tmp/ex-other-repo-for-this-test"
        subprocess.run(("rm", "-rf", other), check=False)
        subprocess.run(("git", "init", "--quiet", other), check=False)
        (Path(other) / "a.md").write_text("a\n", encoding="utf-8")
        subprocess.run(("git", "-C", other, "add", "a.md"), check=False)
        subprocess.run(("git", "-C", other, "-c", "user.name=t", "-c", "user.email=t@t",
                        "commit", "--quiet", "-m", "x"), check=False)
        source = manifest.source_identity(other)
        self.assertFalse(source["ok"])
        self.assertFalse(source["executedSourceConfirmed"])
        self.assertTrue(any("outside the reported repository" in error
                            for error in source["errors"]))

    def test_a_failed_git_call_is_an_error_rather_than_an_empty_answer(self):
        value, error = manifest._git("rev-parse", "--verify",
                                     "no-such-ref-for-this-test", root=ROOT)
        self.assertIsNone(value)
        self.assertIn("exited", error)


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

    def test_the_inventory_accounts_for_every_enumerated_path(self):
        inventory = manifest.file_inventory(ROOT)
        self.assertTrue(inventory["ok"])
        self.assertEqual(inventory["enumerated"],
                         len(inventory["files"]) + len(inventory["missing"])
                         + len(inventory["unreadable"]))
        self.assertEqual(self.built["enumeratedCount"], self.built["fileCount"])

    def test_a_failed_enumeration_is_never_a_complete_inventory(self):
        inventory = manifest.file_inventory("/tmp")
        self.assertFalse(inventory["ok"])
        self.assertEqual(inventory["files"], [])
        self.assertEqual(inventory["enumerationState"], "not-a-repository")
        self.assertIsNotNone(inventory["error"])

    def test_a_tracked_path_missing_from_the_worktree_is_reported(self):
        inventory = manifest.file_inventory(ROOT, paths=["scenarios/manifest.py",
                                                         "no-such-tracked-file.py"])
        self.assertFalse(inventory["ok"])
        self.assertEqual([entry["path"] for entry in inventory["missing"]],
                         ["no-such-tracked-file.py"])

    def test_a_manifest_is_consistent_only_with_a_sound_source_and_inventory(self):
        self.assertEqual(self.built["consistent"],
                         bool(self.built["source"]["ok"] and self.built["inventoryOk"]))
        broken = manifest.build("/tmp", run_id="local-test")
        self.assertFalse(broken["consistent"])
        self.assertFalse(broken["inventoryOk"])


if __name__ == "__main__":
    unittest.main()
