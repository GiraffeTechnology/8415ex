"""Failure-injection regressions for delivery and source observation boundaries."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scenarios import cli, manifest

ROOT = str(Path(__file__).resolve().parents[2])


class PublicationRecovery(unittest.TestCase):
    def test_second_replace_failure_restores_old_pair_or_removes_new_pair(self):
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as d:
                a, b = Path(d, 'a'), Path(d, 'b')
                if existing:
                    a.write_bytes(b'old-a\x00'); b.write_bytes(b'old-b\x00')
                replace = os.replace
                def fail_second(src, dst):
                    if '.staging-' in str(src) and str(dst) == str(b):
                        raise OSError('injected second publish failure')
                    return replace(src, dst)
                with patch.object(cli.os, 'replace', side_effect=fail_second):
                    result = cli.deliver_outputs([(a, 'new-a'), (b, 'new-b')], 'failure')
                self.assertFalse(any(r['ok'] for r in result))
                self.assertEqual(result[0]['stage'], 'rolled-back')
                self.assertEqual(result[1]['stage'], 'publish')
                if existing:
                    self.assertEqual(a.read_bytes(), b'old-a\x00')
                    self.assertEqual(b.read_bytes(), b'old-b\x00')
                else:
                    self.assertFalse(a.exists()); self.assertFalse(b.exists())
                self.assertFalse(any('staging-' in p.name or 'backup-' in p.name
                                     for p in Path(d).iterdir()))

    def test_failed_restore_is_reported_and_backup_kept(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d, 'a'), Path(d, 'b')
            a.write_text('old-a'); b.write_text('old-b')
            replace = os.replace
            def fail(src, dst):
                if str(dst) == str(b) or '.backup-' in str(src):
                    raise OSError('injected publication or restoration failure')
                return replace(src, dst)
            with patch.object(cli.os, 'replace', side_effect=fail):
                result = cli.deliver_outputs([(a, 'new-a'), (b, 'new-b')], 'restore')
            self.assertFalse(any(r['ok'] for r in result))
            self.assertEqual(result[0]['stage'], 'rollback-failed')
            self.assertTrue(result[0]['mayContainNewOutput'])
            self.assertEqual(Path(result[0]['recoveryBackup']).read_text(), 'old-a')
            self.assertEqual(a.read_text(), 'new-a')
            self.assertEqual(b.read_text(), 'old-b')

    def test_cleanup_failure_is_not_silently_successful(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d, 'a'); target.write_text('old')
            unlink = os.unlink
            def fail_backup(path, *args, **kwargs):
                if '.backup-' in str(path):
                    raise OSError('injected cleanup failure')
                return unlink(path, *args, **kwargs)
            with patch.object(cli.os, 'unlink', side_effect=fail_backup):
                result = cli.deliver_outputs([(target, 'new')], 'cleanup')
            self.assertFalse(result[0]['ok'])
            self.assertEqual(result[0]['stage'], 'published')
            self.assertEqual(target.read_text(), 'new')
            self.assertTrue(result[0]['cleanupErrors'])
            self.assertTrue(Path(result[0]['cleanupErrors'][0]['path']).exists())

    def test_existing_staging_is_not_clobbered(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d, 'a')
            stage = Path(str(target) + '.staging-existing'); stage.write_text('unrelated')
            result = cli.deliver_outputs([(target, 'new')], 'existing')
            self.assertFalse(result[0]['ok'])
            self.assertEqual(stage.read_text(), 'unrelated')
            self.assertFalse(target.exists())

    def test_source_outputs_and_symlink_parent_alias_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            alias = Path(d, 'alias'); alias.symlink_to(ROOT, target_is_directory=True)
            for target in (Path(ROOT, 'scenarios/cli.py'), alias / 'scenarios/cli.py'):
                before = target.read_bytes()
                result = cli.deliver_outputs([(target, 'bad')], 'source', root=ROOT)
                self.assertEqual(result[0]['stage'], 'source-protection')
                self.assertEqual(target.read_bytes(), before)
            # A dishonest --root cannot expose the actual imported source either.
            target = Path(ROOT, 'scenarios/cli.py')
            result = cli.deliver_outputs([(target, 'bad')], 'root', root=d)
            self.assertEqual(result[0]['stage'], 'source-protection')


class ProvenanceAndCalculation(unittest.TestCase):
    def test_m_entrypoint_is_present_with_truthful_disk_scope(self):
        completed = subprocess.run([sys.executable, '-B', '-m', 'scenarios.cli', 'manifest'],
                                   cwd=ROOT, capture_output=True, text=True)
        data = json.loads(completed.stdout)
        provenance = data['source']['moduleProvenance']
        main = [r for r in provenance['modules'] if r['module'] == '__main__']
        self.assertEqual(len(main), 1)
        self.assertEqual(main[0]['projectModule'], 'scenarios.cli')
        self.assertEqual(main[0]['relative'], 'scenarios/cli.py')
        self.assertFalse(provenance['executionBytesAttested'])
        self.assertIn('on-disk', provenance['scope'])

    def test_self_record_never_covers_unattempted_delivery(self):
        record = cli.seal(cli._bundle(ROOT), 0)['commands'][0]
        self.assertEqual(record['scope'], 'calculation-only-before-publication')
        self.assertIn('has not happened', record['detail'])

    def test_delivery_failure_preserves_calculation_record_and_changes_outer_result(self):
        bundle = cli._bundle(ROOT)
        bundle['allLocalPassed'] = True
        bundle['blocking'] = []
        with tempfile.TemporaryDirectory() as d, patch.object(cli, '_bundle', return_value=bundle):
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                code = cli.main(['run-all', '--root', ROOT, '--json', '--json-out', d])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(result['commands'][0]['exitCode'], 0)
        self.assertEqual(result['calculationExitCode'], 0)
        self.assertEqual(result['commands'], result['evidence']['commands'])
        self.assertEqual(result['commands'], result['manifest']['commands'])
        self.assertFalse(result['allLocalPassed'])
        self.assertEqual(result['meaning'], 'this run is not a local pass')
        self.assertEqual(result['outputDeliveryStatus'], 'failed')

    def test_delivery_time_source_change_is_in_final_reconciliation(self):
        bundle = cli._bundle(ROOT)
        before = manifest.snapshot(ROOT)
        changed = dict(before, inventoryDigest='changed')
        with patch.object(cli, '_bundle', return_value=bundle), \
             patch.object(manifest, 'snapshot', side_effect=[before, changed]), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            code = cli.main(['run-all', '--root', ROOT, '--json'])
        result = json.loads(output.getvalue())
        self.assertEqual(code, 1)
        self.assertFalse(result['finalSourceReconciliation']['consistent'])
        self.assertIn('source changed during output delivery', result['blocking'])


class ExternalLogs(unittest.TestCase):
    def test_full_raw_logs_are_saved_and_digest_matches(self):
        import hashlib
        from scenarios import execution
        with tempfile.TemporaryDirectory() as d:
            observed = execution.capture_cli(
                [sys.executable, '-B', '-c',
                 'import sys; print("x" * 6000); print("actual stderr", file=sys.stderr)'],
                root=ROOT, raw_log_dir=d)
            self.assertEqual(observed['exitCode'], 0)
            self.assertEqual(observed['scope'], 'final-outer-process')
            for name in ('stdout', 'stderr'):
                saved = observed['rawLog'][name]
                data = Path(saved['path']).read_bytes()
                self.assertEqual(saved['bytes'], len(data))
                self.assertEqual(saved['sha256'], hashlib.sha256(data).hexdigest())
                self.assertEqual(saved['sha256'], observed[name]['sha256'])
            self.assertGreater(observed['rawLog']['stdout']['bytes'], execution.TAIL_BYTES)

    def test_final_index_has_resolvable_current_command_and_observation_refs(self):
        bundle = cli.seal(cli._bundle(ROOT), 1)
        index = bundle['evidenceIndex']
        self.assertEqual(index['commands'], bundle['commands'])
        for case in ('T-39', 'T-40'):
            row = next(r for r in index['rows'] if r['case'] == case)
            self.assertTrue(row['commandReferences'])
            self.assertTrue(row['observationReferences'])
            for ref in row['commandReferences']:
                self.assertEqual(index['commands'][int(ref['commandRef'].split('/')[-1])]
                                 ['command'], ref['command'])
                self.assertEqual(ref['rawLogRefs'], {})
            for ref in row['observationReferences']:
                self.assertIn(ref['observationRef'].split('/')[-1], index['observations'])


class PublishedSummaryScope(unittest.TestCase):
    def test_prepublication_text_does_not_claim_delivery_pass(self):
        bundle = cli._bundle(ROOT)
        # A passing calculation means no blocking item as well as the verdict
        # fields: sealing compares the two, and a record saying it passed while
        # listing what blocked it is the contradiction it refuses. The worktree
        # is dirty while this suite runs from a working copy, so the list is
        # cleared here to express what the fixture means.
        bundle.update(calculationPassed=True, allLocalPassed=True, blocking=[],
                      outputDeliveryStatus="NOT_CAPTURED_IN_PROCESS")
        text = cli.summary_text(cli.seal(bundle, 0))
        self.assertIn("calculation passed: True", text)
        self.assertIn("publication not yet attempted", text)
        self.assertNotIn("local delivery passed: True", text)


class ObservedSourceIndex(unittest.TestCase):
    def test_external_index_keeps_observed_source_instead_of_rereading(self):
        from scenarios import evidence_index
        source = manifest.source_identity(ROOT)
        with patch.object(manifest, "source_identity", side_effect=AssertionError("must not reread")):
            index = evidence_index.build(root=ROOT, source=source)
        self.assertEqual(index["sourceIdentity"], source)
        for row in index["rows"]:
            self.assertEqual(row["sourceIdentity"]["commit"], source["commit"])
        source["commit"] = "changed-after-observation"
        self.assertNotEqual(index["sourceIdentity"]["commit"], source["commit"])
