"""Candidate receipts describe recorded observations, never a later checkout."""
import contextlib
import copy
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scenarios import cli, decisions, manifest, receipt


RECORDED = cli._bundle(str(Path(__file__).resolve().parents[2]))

def bundle():
    b = copy.deepcopy(RECORDED)
    b.update({'runId': 'recorded-run', 'source': {'commit': 'a'*40, 'tree': 'b'*40,
            'ancestry': {'head': 'a'*40, 'parents': [], 'base': None,
                         'diffRange': None, 'errors': []}},
            'commands': [], 'manifest': {}, 'startedAt': '2026-10-15T00:00:00Z',
            'allLocalPassed': True, 'runtime': {'platform': 'Linux-recorded'},
            'openDecisions': decisions.register(), 'blocking': [],
            'sourceReconciliation': {'before': {}}, 'matrix': {}})
    b['source'] = dict(RECORDED['source'], **b['source'])
    b['manifest'].pop('source', None)
    b['source']['requestedRoot'] = str(Path(__file__).resolve().parents[2])
    return b


class ReceiptBoundaries(unittest.TestCase):
    def test_old_bundle_never_queries_current_git(self):
        b = bundle()
        with patch.object(manifest, 'parent_identity', side_effect=AssertionError('live Git')):
            got = receipt.build(b)['groups']['1-source']
        self.assertEqual(got['commit'], 'a'*40)
        self.assertEqual(got['parents'], [])

    def test_missing_ancestry_is_explicit_not_backfilled(self):
        b = bundle(); del b['source']['ancestry']
        with patch.object(manifest, 'parent_identity', side_effect=AssertionError('live Git')):
            got = receipt.build(b)['groups']['1-source']
        self.assertEqual(got['ancestryStatus'], 'NOT_RECORDED')
        self.assertIsNone(got['diffRange'])

    def test_mismatched_ancestry_refused(self):
        b = bundle(); b['source']['ancestry']['head'] = 'c'*40
        with self.assertRaises(ValueError): receipt.build(b)

    def test_scope_survives_projection(self):
        b = bundle(); cli.seal(b, 0)
        got = receipt.build(b)['groups']['4-results']['commands'][0]
        self.assertEqual(got['scope'], 'calculation-only-before-publication')
        self.assertEqual(got['finalProcessStatus'], 'NOT_CAPTURED_IN_PROCESS')
        self.assertIn('executed', got)

    def test_recorded_decisions_not_current_register(self):
        b = bundle(); b['openDecisions'] = {'historical': True}
        with patch.object(decisions, 'register', side_effect=AssertionError('current register')):
            self.assertEqual(receipt.build(b)['groups']['2-requirements']['openDecisions'],
                             {'historical': True})

    def test_no_invented_platform_or_continuation(self):
        b = bundle(); b['runtime'] = {'platform': 'OtherOS'}
        r = receipt.build(b)['groups']
        self.assertNotIn('no other platform', r['3-environment']['platformConstraint'])
        self.assertEqual(r['9-blockers']['independentWorkContinued'], 'NOT_RECORDED')

    def test_private_identity_not_echoed_and_snapshot_not_mutated(self):
        b = bundle(); old = copy.deepcopy(b)
        r = receipt.build(b, requirements_identity='PRIVATE_SYNTHETIC_SENTINEL')
        self.assertNotIn('PRIVATE_SYNTHETIC_SENTINEL', json.dumps(r))
        self.assertEqual(b, old)
        self.assertEqual(r['groupsPresent'], 9)
        self.assertEqual(r['groups']['7-chain']['chainId'], 'NOT_RUN')

    def test_cli_rejects_ignored_output_flags(self):
        for command in ('receipt', 'decisions'):
            with patch.object(cli, '_bundle') as run, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as raised:
                    cli.main([command, '--json-out', '/tmp/unused-receipt.json'])
                self.assertEqual(raised.exception.code, 2)
                run.assert_not_called()

    def test_receipt_cli_labels_command_and_publication(self):
        b = bundle()
        with patch.object(cli, '_bundle', return_value=b), \
             patch.object(manifest, 'snapshot', return_value={}), \
             patch.object(manifest, 'reconcile', return_value={'consistent': True}), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cli.main(['receipt']), 0)
        r = json.loads(out.getvalue())
        self.assertIn(' receipt', r['groups']['4-results']['commands'][0]['command'])
        self.assertEqual(r['publication']['finalProcessStatus'], 'NOT_CAPTURED_IN_PROCESS')

    def test_receipt_cli_detects_source_change_before_print(self):
        with patch.object(cli, '_bundle', return_value=bundle()), \
             patch.object(manifest, 'snapshot', return_value={}), \
             patch.object(manifest, 'reconcile', return_value={'consistent': False}), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(['receipt']), 1)

    def test_receipt_stdout_failure_returns_failure(self):
        with patch.object(cli, '_bundle', return_value=bundle()), \
             patch.object(manifest, 'snapshot', return_value={}), \
             patch.object(manifest, 'reconcile', return_value={'consistent': True}), \
             patch('builtins.print', side_effect=[OSError('write failed'), None]):
            self.assertEqual(cli.main(['receipt']), 1)

    def test_artifact_missing_is_not_claimed_delivered(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = receipt.build(bundle(), artifacts=[str(Path(tmp)/'missing')])
        artifact = r['groups']['5-artifacts']['artifacts'][0]
        self.assertIsNone(artifact['sha256'])
        self.assertIn('error', artifact)
        self.assertEqual(artifact['builtBy'], 'NOT_RECORDED')
        self.assertEqual(artifact['storedAt'], 'NOT_PROVIDED')

    def test_recorded_source_cannot_disagree_with_snapshot_or_package(self):
        for location in ('before', 'after', 'manifest'):
            b = bundle()
            observed = {'commit': 'c'*40, 'tree': 'd'*40}
            if location == 'manifest': b['manifest']['source'] = observed
            else: b['sourceReconciliation'][location] = observed
            with self.assertRaisesRegex(ValueError, 'disagrees'):
                receipt.build(b)

    def test_bundle_detects_transient_source_identity_change(self):
        root = str(Path(__file__).resolve().parents[2])
        original = manifest.source_identity
        calls = 0
        def observed(*args, **kwargs):
            nonlocal calls
            calls += 1
            value = original(*args, **kwargs)
            # snapshot A, bundle identity B, package/snapshot A.
            if calls == 2:
                value['commit'] = 'c'*40
                value['tree'] = 'd'*40
            return value
        with patch.object(manifest, 'source_identity', side_effect=observed):
            b = cli._bundle(root)
        self.assertFalse(b['allLocalPassed'])
        self.assertTrue(any('disagrees' in why for why in b['blocking']))
        with self.assertRaises(ValueError): receipt.build(b)

    def test_register_preserves_sixteen_published_decisions_without_current_acceptance(self):
        r = decisions.register()
        self.assertEqual([d['id'] for d in r['decisions']], [f'D-{n:02}' for n in range(1,17)])
        self.assertEqual(r['publishedBaselineVersion'], '1.5')
        self.assertEqual(r['currentCompletePRDVersion'], '1.5')
        self.assertTrue(r['completeCurrentContractLoaded'])
        self.assertEqual(r['productStatus'], 'OPEN')
        self.assertEqual(r['acceptedCases'], [])
        self.assertEqual(r['globalBlockers'], [])
        self.assertEqual(decisions.reported_locally(), {})

    def test_parent_identity_pins_head_and_base_to_immutable_commits(self):
        with tempfile.TemporaryDirectory() as tmp:
            def git(*args):
                return subprocess.check_output(['git', '-C', tmp, *args], stderr=subprocess.DEVNULL).decode().strip()
            git('init'); git('config', 'user.name', 'Local Fixture'); git('config','user.email','fixture@example.invalid')
            git('commit', '--allow-empty','-m','one'); first = git('rev-parse','HEAD')
            git('commit', '--allow-empty','-m','two'); second = git('rev-parse','HEAD')
            result = manifest.parent_identity(tmp, base=first, head=second)
            self.assertEqual(result['head'], second)
            self.assertEqual(result['base'], first)
            self.assertEqual(result['parents'], [first])
            self.assertEqual(result['diffRange'], first+'..'+second)
            recorded = bundle()
            recorded['source'] = {'commit': second, 'ancestry': result}
            git('commit', '--allow-empty','-m','third')
            got = receipt.build(recorded, tmp)['groups']['1-source']
            self.assertEqual(got['commit'], second)
            self.assertEqual(got['parents'], [first])
            self.assertEqual(got['diffRange'], first+'..'+second)
            default = manifest.parent_identity(tmp, head=second)
            self.assertEqual(default['base'], first)
            self.assertEqual(default['basePolicy'], 'first-parent')
            root = manifest.parent_identity(tmp, head=first)
            self.assertEqual(root['parents'], [])
            self.assertIsNone(root['diffRange'])
            bad = manifest.parent_identity(tmp, base='missing-base', head=second)
            self.assertTrue(bad['errors'])
            self.assertIsNone(bad['diffRange'])
