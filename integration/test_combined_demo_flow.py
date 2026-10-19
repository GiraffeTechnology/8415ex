"""Committed-source package → HTTP capture → material export, all local only.

Requires the joined source to be committed. No installed checkout imports are
allowed in child processes; every producer is loaded from the source archive or
its verified zipapp. This is not browser, deployment, signing or chain evidence.
"""
from datetime import datetime, timezone
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import sys
import tempfile
import unittest
from urllib.parse import urlencode, urlsplit
import zipfile


ROOT = Path(__file__).resolve().parents[1]

# -I removes cwd/PYTHONPATH; explicitly import only the archive under test.
BUILD = """
import importlib.util, runpy, sys
archive = sys.argv.pop(1)
sys.path.insert(0, archive)
origin = importlib.util.find_spec('exchange.demo_package').origin
assert origin.startswith(archive + '/'), origin
runpy.run_module('exchange.demo_package', run_name='__main__')
"""
EXPORT = """
import sys
from unittest.mock import patch
archive = sys.argv[1]
sys.path.insert(0, archive)
from exchange import demo_materials, demo_ui
from scenarios import harness
assert demo_materials.__file__.startswith(archive + '/')
assert harness.__file__.startswith(archive + '/')
def forbidden(*args, **kwargs):
    raise AssertionError('export must consume captured records without rerunning scenarios')
with patch.object(harness.Scenario, 'run', forbidden), \
     patch.object(harness, 'run_all', forbidden), \
     patch.object(demo_ui, 'run_all', forbidden):
    raise SystemExit(demo_materials.main())
"""


class CombinedCommittedDemoFlow(unittest.TestCase):
    def command(self, argv, *, cwd=ROOT, data=None, env=None):
        result = subprocess.run(argv, cwd=cwd, input=data, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=env, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors='replace'))
        return result.stdout

    def test_exact_committed_package_captures_and_exports_six_runs(self):
        started = datetime.now(timezone.utc).isoformat()
        evidence_directory = os.environ.get('EX_COMBINED_EVIDENCE_DIR')
        if evidence_directory:
            evidence_directory = Path(evidence_directory).resolve()
            self.assertNotEqual(evidence_directory, ROOT)
            self.assertNotIn(ROOT, evidence_directory.parents, 'Evidence must stay outside source tree')
        # Never assign a new identity to old evidence or silently use dirty files.
        status = self.command(['git', 'status', '--porcelain', '--untracked-files=all'])
        self.assertEqual(status, b'', 'Commit the joined candidate before source-bound acceptance')
        commit = self.command(['git', 'rev-parse', 'HEAD']).decode().strip()
        tree = self.command(['git', 'rev-parse', commit + '^{tree}']).decode().strip()
        source = self.command(['git', 'archive', '--format=zip', commit])
        with zipfile.ZipFile(io.BytesIO(source)) as archive:
            source_members = {name: archive.read(name) for name in archive.namelist()
                              if not name.endswith('/')}
        self.assertEqual(source_members['integration/test_combined_demo_flow.py'],
                         Path(__file__).read_bytes())
        with tempfile.TemporaryDirectory(prefix='ex-combined-demo-') as directory:
            directory = Path(directory)
            source_path = directory / 'source.zip'
            source_path.write_bytes(source)
            build_argv = [sys.executable, '-I', '-B', '-c', BUILD, str(source_path),
                          'build', '--commit', commit, '--tree', tree]
            package = self.command(build_argv, cwd=directory, data=source)
            self.assertEqual(package, self.command(build_argv, cwd=directory, data=source))
            package_path = directory / 'demo.pyz'
            package_path.write_bytes(package)
            digest = hashlib.sha256(package).hexdigest()
            env = dict(os.environ, EX_DEMO_SHA256=digest)
            manifest = json.loads(self.command(
                [sys.executable, '-I', '-B', str(package_path), '--verify'],
                cwd=directory, env=env))
            self.assertEqual((manifest['commit'], manifest['tree']), (commit, tree))
            self.assertEqual(manifest['realAcceptance'], 'NOT_RUN')
            self.assertEqual(set(manifest['files']), set(source_members))
            with zipfile.ZipFile(io.BytesIO(package)) as archive:
                for name, payload in source_members.items():
                    self.assertEqual(archive.read(name), payload)
                    self.assertEqual(manifest['files'][name], {
                        'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()})
            # Port zero avoids reservation races. -u exposes the real bound port.
            with tempfile.TemporaryFile() as errors:
                process = subprocess.Popen(
                    [sys.executable, '-I', '-B', '-u', str(package_path), '--port', '0'],
                    cwd=directory, env=env, stdout=subprocess.PIPE, stderr=errors)
                try:
                    with selectors.DefaultSelector() as selector:
                        selector.register(process.stdout, selectors.EVENT_READ)
                        self.assertTrue(selector.select(10), 'zipapp did not announce its loopback address')
                        announcement = process.stdout.readline().decode()
                    match = re.match(r'http://127\.0\.0\.1:(\d+)/ ', announcement)
                    self.assertIsNotNone(match, announcement)
                    port = int(match.group(1))
                    origin = 'http://127.0.0.1:' + str(port)

                    def request(method, path, body=None):
                        headers = {'Host': '127.0.0.1:' + str(port)}
                        if method == 'POST':
                            headers.update({'Origin': origin,
                                            'Content-Type': 'application/x-www-form-urlencoded'})
                        connection = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
                        try:
                            connection.request(method, path, body, headers)
                            response = connection.getresponse()
                            return response.status, dict(response.getheaders()), response.read()
                        finally:
                            connection.close()

                    status, _, home = request('GET', '/')
                    self.assertEqual(status, 200)
                    token = re.search(rb'name="csrf" value="([^"]+)"', home).group(1).decode()
                    scenario_ids = re.findall(rb'<option value="(DEMO-\d+)"', home)
                    self.assertEqual(scenario_ids, [f'DEMO-{n:02}'.encode() for n in range(1, 7)])
                    records, captures = [], {}
                    for raw_id in scenario_ids:
                        scenario_id = raw_id.decode()
                        status, headers, _ = request('POST', '/simulate', urlencode(
                            {'csrf': token, 'scenario': scenario_id}))
                        self.assertEqual(status, 303)
                        location = headers['Location']
                        evidence_path = '/evidence?' + urlsplit(location).query
                        status, _, captured = request('GET', evidence_path)
                        self.assertEqual(status, 200)
                        record = json.loads(captured)
                        self.assertEqual((record['source']['commit'], record['source']['tree']),
                                         (commit, tree))
                        self.assertEqual(record['evidenceKind'], 'SIMULATION_PUBLIC_PROJECTION')
                        self.assertEqual(record['schema'], '8415ex-public-demo/2')
                        self.assertNotIn('accounts', record['report']['scenarios'][0]['setup'])
                        self.assertEqual(set(record['realEvidence'].values()), {'NOT_RUN'})
                        result = record['report']['scenarios'][0]
                        self.assertEqual(result['scenarioId'], scenario_id)
                        self.assertTrue(record['report']['allPassed'], result)
                        self.assertTrue(result['passed'], result)
                        self.assertTrue(result['steps'])
                        self.assertTrue(result['setup']['prices'])
                        self.assertTrue(result['setup']['gasConditions'])
                        self.assertGreater(result['counts']['passed'], 0)
                        self.assertGreater(result['counts']['not-run'], 0)
                        for step in (0, len(result['steps'])):
                            status, _, page = request('GET', location + '&step=' + str(step))
                            self.assertEqual(status, 200)
                            self.assertIn(record['runId'].encode(), page)
                            self.assertIn(b'NOT_RUN', page)
                        self.assertEqual(request('GET', evidence_path)[2], captured)
                        captures[evidence_path] = captured
                        records.append(record)
                    self.assertEqual(len({r['runId'] for r in records}), 6)
                    export_argv = [sys.executable, '-I', '-B', '-c', EXPORT, str(package_path)]
                    inputs = json.dumps(records).encode()
                    materials = self.command(export_argv, cwd=directory, data=inputs)
                    self.assertEqual(materials, self.command(export_argv, cwd=directory, data=inputs))
                    with zipfile.ZipFile(io.BytesIO(materials)) as archive:
                        material_manifest = json.loads(archive.read('manifest.json'))
                        self.assertEqual(material_manifest['source'], records[0]['source'])
                        self.assertEqual(set(archive.namelist()),
                                         set(material_manifest['files']) | {'manifest.json'})
                        for name, binding in material_manifest['files'].items():
                            payload = archive.read(name)
                            self.assertEqual(binding, {'bytes': len(payload),
                                                       'sha256': hashlib.sha256(payload).hexdigest()})
                        for record in records:
                            name = record['report']['scenarios'][0]['scenarioId']
                            self.assertEqual(json.loads(archive.read('evidence/' + name + '.json')),
                                             record)
                        scenes = json.loads(archive.read('scenes.json'))
                        self.assertEqual(scenes['source'], records[0]['source'])
                        self.assertEqual({s['runId'] for s in scenes['scenes'] if 'runId' in s},
                                         {r['runId'] for r in records})
                        self.assertIn('Rendered PPTX', material_manifest['notRun'])
                        self.assertIn('Rendered video', material_manifest['notRun'])
                        self.assertIn('Deployment and chain', material_manifest['notRun'])
                    # Replay and export must neither mutate captures nor create new runs.
                    for path, captured in captures.items():
                        self.assertEqual(request('GET', path)[2], captured)
                    status, _, home = request('GET', '/')
                    self.assertEqual(status, 200)
                    self.assertEqual(set(re.findall(rb'<li><a href="/run\?id=([^"]+)"', home)),
                                     {r['runId'].encode() for r in records})
                    self.assertIsNone(process.poll())
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                    process.stdout.close()
            if evidence_directory:
                evidence_directory.mkdir(parents=True, exist_ok=True)
                artifacts = {'source.zip': source, 'demo.pyz': package,
                             'captured-records.json': inputs, 'materials.zip': materials,
                             'package-manifest.json': json.dumps(manifest, sort_keys=True).encode()}
                for record, captured in zip(records, captures.values()):
                    name = record['report']['scenarios'][0]['scenarioId']
                    artifacts['http-' + name + '.json'] = captured
                receipt = {
                    'schema': '8415ex-combined-local-test/1',
                    'source': {'commit': commit, 'tree': tree},
                    'startedAt': started,
                    'finishedAt': datetime.now(timezone.utc).isoformat(),
                    'outcome': 'passed', 'evidenceKind': 'LOCAL_SIMULATION',
                    'python': sys.version,
                    'scenarioPosts': 6, 'capturedRunIds': [r['runId'] for r in records],
                    'checks': ['committed git archive', 'isolated archive imports',
                               'repeatable package bytes', 'zipapp subprocess verification',
                               'six actual loopback HTTP simulations',
                               'unchanged replay and capture records',
                               'export with scenario runner forbidden',
                               'repeatable material bytes and member digests'],
                    'notRun': material_manifest['notRun'],
                    'files': {name: {'bytes': len(payload),
                                     'sha256': hashlib.sha256(payload).hexdigest()}
                              for name, payload in sorted(artifacts.items())}}
                # Refuse overwrites so an earlier run cannot silently be relabelled.
                for name in (*artifacts, 'receipt.json'):
                    self.assertFalse((evidence_directory / name).exists(), name)
                for name, payload in artifacts.items():
                    with (evidence_directory / name).open('xb') as stream:
                        stream.write(payload)
                with (evidence_directory / 'receipt.json').open('x') as stream:
                    json.dump(receipt, stream, sort_keys=True, indent=2)
                    stream.write('\n')
