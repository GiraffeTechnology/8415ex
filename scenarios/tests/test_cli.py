"""One run, one identity, and both of its outputs derived from that run.

The text summary and the canonical JSON record are two renderings of a single
execution, written in one invocation under one run id. Two invocations are two
runs: their observations are never mixed, and nothing presents them as one.
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scenarios import cli, execution

ROOT = str(Path(__file__).resolve().parents[2])


class OneRunOneIdentity(unittest.TestCase):

    def test_a_run_id_is_never_repeated_by_a_second_run(self):
        identities = {cli._run_id() for _ in range(50)}
        self.assertEqual(len(identities), 50)

    def test_both_outputs_of_one_invocation_carry_the_same_run_id(self):
        with tempfile.TemporaryDirectory() as directory:
            json_path = os.path.join(directory, "run.json")
            text_path = os.path.join(directory, "run.txt")
            cli.main(["run-all", "--root", ROOT, "--json-out", json_path,
                      "--text-out", text_path])
            record = json.loads(Path(json_path).read_text(encoding="utf-8"))
            text = Path(text_path).read_text(encoding="utf-8")
        self.assertIn(record["runId"], text)
        self.assertIn(record["scenarioReport"]["deterministicDigest"], text)
        self.assertIn(str(record["resourceObservation"]["elapsedMs"]), text)
        # The file carries the sealed calculation record; what became of the
        # outputs is known only after they were written, so the file states
        # that its own delivery status was not captured in process.
        self.assertEqual(record["calculationExitCode"],
                         0 if record["calculationPassed"] else 1)
        self.assertEqual(record["outputDeliveryStatus"], "NOT_CAPTURED_IN_PROCESS")
        self.assertEqual(sorted(record["outputDeliveryPlan"]),
                         sorted([json_path, text_path]))

    def test_two_invocations_are_two_runs_with_their_own_observations(self):
        first, second = cli._bundle(ROOT), cli._bundle(ROOT)
        self.assertNotEqual(first["runId"], second["runId"])
        for key in ("startedAt", "runId"):
            self.assertIn(key, first)
        # The deterministic digest is over the fixtures, so it does match; the
        # wall-clock observations are per run and are never shared.
        self.assertEqual(first["scenarioReport"]["deterministicDigest"],
                         second["scenarioReport"]["deterministicDigest"])
        self.assertIsNot(first["resourceObservation"], second["resourceObservation"])

    def test_the_summary_is_derived_from_the_bundle_it_is_given(self):
        bundle = cli.seal(cli._bundle(ROOT), 0)
        text = cli.summary_text(bundle)
        self.assertIn(bundle["runId"], text)
        self.assertIn(bundle["source"]["commit"], text)
        self.assertIn(bundle["source"]["tree"], text)
        for record in bundle["commands"]:
            self.assertIn(record["command"], text)

    def test_an_unexecuted_command_is_shown_without_an_exit_code(self):
        text = cli.summary_text(cli.seal(cli._bundle(ROOT), 0))
        for line in text.splitlines():
            if "NOT-RUN" in line:
                self.assertIn("no exit code recorded", line)


class CalculationVersusDelivery(unittest.TestCase):
    """Item 3: a calculation that succeeded is not a command that succeeded.

    The outputs are delivered by the same process that computed them, so that
    process can report what it delivered. It cannot report its own final exit
    status, because that is not known until it has already stopped running, and
    these tests pin both halves of that distinction.
    """

    def _invoke(self, json_out, text_out):
        """Run the real CLI as a subprocess and read what it actually did."""
        argv = (sys.executable, "-B", "-m", "scenarios.cli", "run-all",
                "--json", "--json-out", json_out, "--text-out", text_out)
        observed = execution.capture_cli(argv, root=ROOT)
        return observed

    def test_a_delivery_failure_is_not_a_successful_command(self):
        """Both write-failure paths, through a real process."""
        for failing in ("json", "text"):
            with self.subTest(failing=failing):
                with tempfile.TemporaryDirectory() as directory:
                    json_out = os.path.join(directory, "run.json")
                    text_out = os.path.join(directory, "run.txt")
                    # A directory cannot receive a file write.
                    os.mkdir(json_out if failing == "json" else text_out)
                    observed = self._invoke(json_out, text_out)
                    self.assertEqual(observed["outcome"], "failed")
                    self.assertNotEqual(observed["exitCode"], 0)
                    self.assertIn("output delivery failed", observed["stderr"]["tail"])
                    # Neither output is published, so the pair cannot disagree.
                    self.assertFalse(os.path.isfile(json_out))
                    self.assertFalse(os.path.isfile(text_out))
                    self.assertEqual(
                        [name for name in os.listdir(directory) if "staging" in name],
                        [], "a failed delivery left a staging file behind")

    def test_the_record_never_claims_the_whole_command_succeeded(self):
        with tempfile.TemporaryDirectory() as directory:
            json_out = os.path.join(directory, "run.json")
            os.mkdir(json_out)
            argv = (sys.executable, "-B", "-m", "scenarios.cli", "run-all",
                    "--json", "--json-out", json_out,
                    "--text-out", os.path.join(directory, "run.txt"))
            finished = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                                      env={**os.environ,
                                           "PYTHONDONTWRITEBYTECODE": "1"})
            record = json.loads(finished.stdout)
        self.assertFalse(record["allLocalPassed"])
        self.assertEqual(record["exitCode"], 1)
        failed = [entry for entry in record["outputDelivery"] if not entry["ok"]]
        self.assertEqual(len(failed), 2, "one failure withholds the whole delivery")
        self.assertTrue(any("delivery" in reason for reason in record["blocking"]))

    def test_the_self_record_does_not_claim_its_own_final_exit(self):
        bundle = cli.seal(cli._bundle(ROOT), 0)
        self_record = bundle["commands"][0]
        self.assertEqual(self_record["finalProcessStatus"], "NOT_CAPTURED_IN_PROCESS")
        self.assertIn("calculation", self_record["scope"])
        self.assertIn("captured externally", self_record["detail"])

    def test_the_external_observer_reports_the_real_outer_status(self):
        with tempfile.TemporaryDirectory() as directory:
            observed = self._invoke(os.path.join(directory, "run.json"),
                                    os.path.join(directory, "run.txt"))
        self.assertEqual(observed["scope"], "final-outer-process")
        self.assertIn("not the observed process", observed["observedBy"])
        self.assertTrue(observed["executed"])
        self.assertIsInstance(observed["exitCode"], int)
        self.assertEqual(observed["argv"][-6:-4], ["run-all", "--json"])

    def test_a_calculation_pass_is_recorded_separately_from_the_command(self):
        with tempfile.TemporaryDirectory() as directory:
            json_out = os.path.join(directory, "run.json")
            os.mkdir(json_out)
            argv = (sys.executable, "-B", "-m", "scenarios.cli", "run-all",
                    "--json", "--json-out", json_out,
                    "--text-out", os.path.join(directory, "run.txt"))
            finished = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                                      env={**os.environ,
                                           "PYTHONDONTWRITEBYTECODE": "1"})
            record = json.loads(finished.stdout)
        self.assertIn("calculationPassed", record)
        # Whatever the calculation decided, a withheld delivery is not a pass.
        self.assertFalse(record["allLocalPassed"])


class TransactionalDelivery(unittest.TestCase):
    """The delivery helper publishes every output or none of them."""

    def test_both_outputs_are_published_together(self):
        with tempfile.TemporaryDirectory() as directory:
            first = os.path.join(directory, "a.json")
            second = os.path.join(directory, "b.txt")
            records = cli.deliver_outputs([(first, "one\n"), (second, "two\n")],
                                          "run-1")
            self.assertTrue(all(entry["ok"] for entry in records))
            self.assertEqual(Path(first).read_text(encoding="utf-8"), "one\n")
            self.assertEqual(Path(second).read_text(encoding="utf-8"), "two\n")
            self.assertEqual(records[0]["bytes"], 4)
            self.assertRegex(records[0]["sha256"], r"\A[0-9a-f]{64}\Z")
            self.assertEqual([name for name in os.listdir(directory)
                              if "staging" in name], [])

    def test_one_bad_destination_withholds_the_other_output(self):
        for bad_index in (0, 1):
            with self.subTest(bad=bad_index):
                with tempfile.TemporaryDirectory() as directory:
                    paths = [os.path.join(directory, "a.json"),
                             os.path.join(directory, "b.txt")]
                    os.mkdir(paths[bad_index])
                    records = cli.deliver_outputs(
                        [(paths[0], "one\n"), (paths[1], "two\n")], "run-1")
                    self.assertFalse(any(entry["ok"] for entry in records))
                    stages = {entry["path"]: entry["stage"] for entry in records}
                    self.assertEqual(stages[paths[bad_index]], "destination")
                    self.assertEqual(stages[paths[1 - bad_index]], "withheld")
                    self.assertFalse(os.path.isfile(paths[1 - bad_index]))
                    self.assertEqual([name for name in os.listdir(directory)
                                      if "staging" in name], [])

    def test_a_missing_parent_directory_is_refused_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = os.path.join(directory, "nope", "a.json")
            good = os.path.join(directory, "b.txt")
            records = cli.deliver_outputs([(missing, "one\n"), (good, "two\n")],
                                          "run-1")
            self.assertFalse(any(entry["ok"] for entry in records))
            self.assertFalse(os.path.isfile(good))

    def test_an_unrequested_output_is_simply_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            only = os.path.join(directory, "a.json")
            records = cli.deliver_outputs([(only, "one\n"), (None, "two\n")],
                                          "run-1")
            self.assertEqual(len(records), 1)
            self.assertTrue(records[0]["ok"])

    def test_two_outputs_may_not_name_the_same_destination(self):
        """They carry different content; only one could survive there."""
        with tempfile.TemporaryDirectory() as directory:
            same = os.path.join(directory, "both.out")
            records = cli.deliver_outputs([(same, "JSON\n"), (same, "TEXT\n")],
                                          "run-same")
            self.assertFalse(any(entry["ok"] for entry in records))
            self.assertTrue(any("same destination" in (entry["error"] or "")
                                for entry in records))
            # Nothing was published, so no file holds one output while the
            # record describes two.
            self.assertFalse(os.path.exists(same))
            self.assertEqual([name for name in os.listdir(directory)
                              if "staging" in name], [])

    def test_the_same_destination_by_a_different_spelling_is_also_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            plain = os.path.join(directory, "a.out")
            indirect = os.path.join(directory, ".", "a.out")
            records = cli.deliver_outputs([(plain, "one\n"), (indirect, "two\n")],
                                          "run-dotted")
            self.assertFalse(any(entry["ok"] for entry in records))
            self.assertFalse(os.path.exists(plain))

    def test_a_write_that_fails_part_way_leaves_nothing_behind(self):
        """A disk-full write, and an error the helper does not expect."""
        class Exploding:
            def __str__(self):
                raise OSError(28, "No space left on device")

        with tempfile.TemporaryDirectory() as directory:
            target = os.path.join(directory, "a.json")
            with self.assertRaises(TypeError):
                # The content is not a string, so the write raises something
                # deliver_outputs does not catch. The cleanup must still run.
                cli.deliver_outputs([(target, Exploding())], "run-partial")
            self.assertEqual([name for name in os.listdir(directory)
                              if "staging" in name], [],
                             "a staging file survived an unexpected failure")
            self.assertFalse(os.path.exists(target))

    def test_a_failed_staging_write_leaves_no_staging_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = os.path.join(directory, "a.json")
            readonly = os.path.join(directory, "sub")
            os.mkdir(readonly)
            records = cli.deliver_outputs(
                [(target, "one\n"), (os.path.join(readonly), "two\n")], "run-mixed")
            self.assertFalse(any(entry["ok"] for entry in records))
            self.assertEqual([name for name in os.listdir(directory)
                              if "staging" in name], [])
            self.assertFalse(os.path.exists(target))

    def test_publishing_replaces_an_existing_file_atomically(self):
        with tempfile.TemporaryDirectory() as directory:
            target = os.path.join(directory, "a.json")
            Path(target).write_text("old\n", encoding="utf-8")
            records = cli.deliver_outputs([(target, "new\n")], "run-2")
            self.assertTrue(records[0]["ok"])
            self.assertEqual(Path(target).read_text(encoding="utf-8"), "new\n")


class EvidenceRecord(unittest.TestCase):
    """The validator guards the delivery; it does not sit beside it."""

    def test_the_sealed_evidence_record_is_accepted(self):
        """Accepted on a clean tree; a dirty tree is refused for that reason.

        This suite is run against uncommitted work during development, and the
        source rules deliberately refuse a dirty tree, so the only reason
        tolerated here is that one. Any other reason is a real defect.
        """
        bundle = cli.seal(cli._bundle(ROOT), 0)
        checked = bundle["evidenceValidation"]
        if bundle["source"]["worktreeClean"] is True:
            self.assertTrue(checked["accepted"], checked["reasons"])
            self.assertGreater(checked["canonicalBytes"], 0)
        else:
            self.assertEqual(list(checked["reasons"]), ["EX_EVIDENCE_DIRTY_WORKTREE"])

    def test_the_record_carries_this_run_identity_and_digest(self):
        bundle = cli.seal(cli._bundle(ROOT), 0)
        evidence = bundle["evidence"]
        self.assertEqual(evidence["runId"], bundle["runId"])
        self.assertEqual(evidence["commit"], bundle["source"]["commit"])
        self.assertEqual(evidence["tree"], bundle["source"]["tree"])
        self.assertEqual(evidence["scenarioDigest"],
                         bundle["scenarioReport"]["deterministicDigest"])
        self.assertEqual(evidence["commands"], bundle["commands"])
        self.assertEqual(evidence["finishedAt"], bundle["finishedAt"])
        self.assertEqual(evidence["transactionHashes"], "NOT_RUN")

    def test_a_refused_evidence_record_blocks_the_run(self):
        bundle = cli._bundle("/tmp")
        self.assertFalse(bundle["evidenceValidation"]["accepted"])
        self.assertTrue(any("evidence record was refused" in reason
                            for reason in bundle["blocking"]))
        self.assertFalse(bundle["allLocalPassed"])


class ExitStatus(unittest.TestCase):

    def test_the_bundle_names_what_blocks_a_local_pass(self):
        bundle = cli._bundle(ROOT)
        self.assertEqual(bundle["allLocalPassed"], bundle["blocking"] == [])
        if bundle["blocking"]:
            self.assertIn("not a local pass", bundle["meaning"])

    def test_a_broken_source_identity_blocks_a_local_pass(self):
        bundle = cli._bundle("/tmp")
        self.assertFalse(bundle["allLocalPassed"])
        self.assertTrue(any("source identity" in reason for reason in bundle["blocking"]))
        self.assertTrue(any("inventory" in reason for reason in bundle["blocking"]))

    def test_the_exit_code_is_recorded_only_after_it_is_known(self):
        bundle = cli._bundle(ROOT)
        self.assertNotIn("exitCode", bundle)
        self.assertNotIn("finishedAt", bundle)
        cli.seal(bundle, 1)
        self.assertEqual(bundle["exitCode"], 1)
        self.assertEqual(bundle["commands"][0]["exitCode"], 1)


class ArtifactLegSurvivesDelivery(unittest.TestCase):
    """The delivered file must be navigable from its own root.

    The index is rebuilt when the run is sealed. A rebuild that forgot the
    declared output plan would drop the artifact leg from the only copy a
    reviewer ever reads, so the guarantee is checked on the published file
    rather than on the in-memory bundle.
    """

    @staticmethod
    def _resolve(document, pointer):
        current = document
        for part in pointer.strip("/").split("/"):
            current = current[int(part)] if isinstance(current, list) else current[part]
        return current

    def test_the_published_record_names_the_file_it_was_published_to(self):
        with tempfile.TemporaryDirectory() as directory:
            json_out = os.path.join(directory, "run.json")
            text_out = os.path.join(directory, "run.txt")
            cli.main(["run-all", "--root", ROOT, "--json",
                      "--json-out", json_out, "--text-out", text_out])
            published = json.loads(Path(json_out).read_text(encoding="utf-8"))
        index = published["evidenceIndex"]
        self.assertEqual([slot["path"] for slot in index["artifacts"]],
                         [json_out, text_out])
        self.assertEqual(published["outputDeliveryPlan"], [json_out, text_out])

    def test_every_row_pointer_resolves_that_row_in_the_published_file(self):
        with tempfile.TemporaryDirectory() as directory:
            json_out = os.path.join(directory, "run.json")
            cli.main(["run-all", "--root", ROOT, "--json", "--json-out", json_out])
            published = json.loads(Path(json_out).read_text(encoding="utf-8"))
        rows = published["evidenceIndex"]["rows"]
        self.assertTrue(rows)
        for row in rows:
            reference, = row["artifactReferences"]
            with self.subTest(case=row["case"]):
                self.assertEqual(reference["path"], json_out)
                resolved = self._resolve(published, reference["pointerInArtifact"])
                self.assertEqual(resolved["case"], row["case"])

    def test_the_published_record_still_does_not_claim_its_own_delivery(self):
        with tempfile.TemporaryDirectory() as directory:
            json_out = os.path.join(directory, "run.json")
            cli.main(["run-all", "--root", ROOT, "--json", "--json-out", json_out])
            published = json.loads(Path(json_out).read_text(encoding="utf-8"))
        # The file exists, which is exactly why the record inside it must not
        # say so: it was serialised before the write was attempted.
        self.assertEqual(published["outputDeliveryStatus"],
                         "NOT_CAPTURED_IN_PROCESS")
        self.assertEqual(published["evidenceIndex"]["artifactDeliveryStatus"],
                         "NOT_CAPTURED_IN_PROCESS")


class ReuseMapIsPartOfTheRun(unittest.TestCase):

    def test_the_bundle_carries_the_reuse_map(self):
        bundle = cli._bundle(ROOT)
        self.assertEqual(bundle["reuse"]["schema"], "8415ex-reuse-map/1")
        self.assertTrue(bundle["reuse"]["allAdaptersSimulated"])
        self.assertTrue(bundle["reuse"]["adaptersRecordedInThisRun"],
                        "the map reads the adapters from this run's scenarios")

    def test_the_subcommand_fails_when_the_map_stops_accounting_for_the_source(self):
        from scenarios import reuse
        original = reuse.DOMAIN_REUSE
        reuse.DOMAIN_REUSE = tuple(entry for entry in original
                                   if entry["module"] != "exchange.ids")
        quiet = io.StringIO()
        try:
            with contextlib.redirect_stdout(quiet):
                incomplete = cli.main(["reuse", "--root", ROOT])
        finally:
            reuse.DOMAIN_REUSE = original
        self.assertEqual(incomplete, 1)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["reuse", "--root", ROOT]), 0)


if __name__ == "__main__":
    unittest.main()
