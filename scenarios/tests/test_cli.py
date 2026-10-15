"""One run, one identity, and both of its outputs derived from that run.

The text summary and the canonical JSON record are two renderings of a single
execution, written in one invocation under one run id. Two invocations are two
runs: their observations are never mixed, and nothing presents them as one.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from scenarios import cli

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
        self.assertEqual(record["exitCode"], 0 if record["allLocalPassed"] else 1)

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


if __name__ == "__main__":
    unittest.main()
