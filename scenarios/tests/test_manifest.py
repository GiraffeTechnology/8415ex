"""The manifest must bind a run to the exact source it came from.

It also has to fail closed: a root that is not a repository, a Git invocation
that failed and an enumeration that returned nothing must each be reported as
an error, never as a clean, empty or consistent source.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
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


class LoadedModuleProvenance(unittest.TestCase):
    """Item 4: every loaded project module, not just this package."""

    def test_every_loaded_project_module_is_recorded_with_its_bytes(self):
        provenance = manifest.loaded_module_provenance(ROOT)
        self.assertTrue(provenance["ok"], provenance["foreign"])
        self.assertGreater(provenance["moduleCount"], 0)
        for entry in provenance["modules"]:
            with self.subTest(module=entry["module"]):
                self.assertTrue(entry["inside"])
                self.assertGreater(entry["bytes"], 0)
                self.assertRegex(entry["sha256"], r"\A[0-9a-f]{64}\Z")
                self.assertEqual(
                    hashlib.sha256(Path(entry["path"]).read_bytes()).hexdigest(),
                    entry["sha256"])

    def test_the_domain_package_is_covered_not_only_this_one(self):
        """A run that imports the domain must account for the domain."""
        import exchange  # noqa: F401  imported for its side effect on sys.modules
        provenance = manifest.loaded_module_provenance(ROOT)
        self.assertIn("exchange", provenance["packages"])
        self.assertIn("scenarios", provenance["packages"])

    def test_a_module_loaded_from_another_tree_is_foreign(self):
        """The reviewed defect: a foreign domain copy passed unnoticed.

        Run in a subprocess, because the point is a different import path and
        this interpreter must keep its own.
        """
        with tempfile.TemporaryDirectory() as directory:
            foreign = os.path.join(directory, "foreign")
            shutil.copytree(os.path.join(ROOT, "exchange"),
                            os.path.join(foreign, "exchange"))
            program = (
                "import sys; sys.path.insert(0, %r)\n"
                "import exchange\n"
                "from scenarios import manifest\n"
                "identity = manifest.source_identity('.')\n"
                "print(identity['ok'], identity['foreignModules'])\n" % foreign)
            finished = subprocess.run(
                (sys.executable, "-B", "-c", program), cwd=ROOT,
                capture_output=True, text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("False", finished.stdout)
        self.assertIn("exchange", finished.stdout)

    def test_the_identity_names_the_foreign_path_in_its_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            foreign = os.path.join(directory, "foreign")
            shutil.copytree(os.path.join(ROOT, "exchange"),
                            os.path.join(foreign, "exchange"))
            program = (
                "import sys; sys.path.insert(0, %r)\n"
                "import exchange\n"
                "from scenarios import manifest\n"
                "print((manifest.source_identity('.')['errors'] or [''])[0])\n" % foreign)
            finished = subprocess.run(
                (sys.executable, "-B", "-c", program), cwd=ROOT,
                capture_output=True, text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertIn("was loaded from", finished.stdout)
        self.assertIn("outside", finished.stdout)


class SnapshotReconciliation(unittest.TestCase):
    """Item 4: the source must not move while the run is running."""

    def _repository(self, directory):
        """A small real repository, so the snapshots are real readings."""
        subprocess.run(("git", "init", "--quiet", directory), check=True)
        target = Path(directory, "a.py")
        target.write_text("VALUE = 1\n", encoding="utf-8")
        for args in (("add", "a.py"),
                     ("-c", "user.name=t", "-c", "user.email=t@t",
                      "commit", "--quiet", "-m", "first")):
            subprocess.run(("git", "-C", directory, *args), check=True)
        return target

    def test_two_readings_of_an_unchanged_source_reconcile(self):
        before = manifest.snapshot(ROOT)
        after = manifest.snapshot(ROOT)
        outcome = manifest.reconcile(before, after)
        self.assertTrue(outcome["consistent"], outcome["reasons"])
        self.assertEqual(outcome["differences"], [])

    def test_a_file_changed_between_snapshots_fails_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            target = self._repository(directory)
            before = manifest.snapshot(directory)
            target.write_text("VALUE = 2\n", encoding="utf-8")
            after = manifest.snapshot(directory)
            outcome = manifest.reconcile(before, after)
        self.assertFalse(outcome["consistent"])
        changed = {entry["field"] for entry in outcome["differences"]}
        self.assertIn("inventoryDigest", changed)
        self.assertIn("worktreeClean", changed)

    def test_head_moving_between_snapshots_fails_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            target = self._repository(directory)
            before = manifest.snapshot(directory)
            target.write_text("VALUE = 3\n", encoding="utf-8")
            subprocess.run(("git", "-C", directory, "add", "a.py"), check=True)
            subprocess.run(("git", "-C", directory, "-c", "user.name=t",
                            "-c", "user.email=t@t", "commit", "--quiet",
                            "-m", "second"), check=True)
            after = manifest.snapshot(directory)
            outcome = manifest.reconcile(before, after)
        self.assertFalse(outcome["consistent"])
        changed = {entry["field"] for entry in outcome["differences"]}
        self.assertIn("commit", changed)
        self.assertIn("tree", changed)

    def test_an_earlier_clean_reading_cannot_carry_a_later_manifest(self):
        """The exact shape the finding describes."""
        with tempfile.TemporaryDirectory() as directory:
            target = self._repository(directory)
            clean = manifest.snapshot(directory)
            self.assertTrue(clean["worktreeClean"])
            target.write_text("VALUE = 99\n", encoding="utf-8")
            dirty = manifest.snapshot(directory)
        self.assertFalse(dirty["worktreeClean"])
        self.assertNotEqual(clean["inventoryDigest"], dirty["inventoryDigest"])
        self.assertFalse(manifest.reconcile(clean, dirty)["consistent"])

    def test_the_run_reports_its_own_reconciliation(self):
        from scenarios import cli
        bundle = cli._bundle(ROOT)
        reconciliation = bundle["sourceReconciliation"]
        self.assertTrue(reconciliation["consistent"], reconciliation["reasons"])
        self.assertEqual(reconciliation["before"]["commit"],
                         reconciliation["after"]["commit"])
        self.assertEqual(reconciliation["before"]["moduleDigest"],
                         reconciliation["after"]["moduleDigest"])

    def test_an_inconsistent_reconciliation_blocks_a_local_pass(self):
        from scenarios import cli
        bundle = cli._bundle(ROOT)
        moved = dict(bundle["sourceReconciliation"]["after"],
                     commit="f" * 40)
        outcome = manifest.reconcile(bundle["sourceReconciliation"]["before"], moved)
        self.assertFalse(outcome["consistent"])
        self.assertTrue(any("commit changed" in reason for reason in outcome["reasons"]))


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
