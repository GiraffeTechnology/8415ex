"""Verify a fixed offline service bundle and test its exact source tree."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tarfile
import time
import zipfile

OUTER = 'd1392a7084780693dd27d68cc47957a952addcb5e23084936a4e2c546d3c301e'
INNER = 'd274c0c6718717c431d38328637ef91f71f59eaeeaeac2ec7fd34201d8b39483'
TREE = 'dbb6eb8381be6814ee6881484642e4a6565d2ab6'
ORIGIN = '8fababe4febc344ad8f07db54a44cc2c0714bedd'
NAMES = {'source.zip', 'install.py', 'RELEASE.json', 'SERVICE-READINESS.md', 'SERVICE-GAPS.json', 'SHA256SUMS'}
evidence = Path('/evidence')
evidence.mkdir(exist_ok=True)
result = {'pullRequestHeadSHA': os.environ.get('PR_HEAD_SHA'), 'testedMergeSHA': os.environ.get('TESTED_MERGE_SHA'), 'packageSHA256': OUTER, 'sourceArchiveSHA256': INNER, 'embeddedOriginCommit': ORIGIN,
          'embeddedSourceTree': TREE, 'productionAcceptance': 'NOT_RUN', 'runs': []}

def check(ok, message):
    if not ok:
        raise ValueError(message)

def run(args, cwd, name):
    start = time.time()
    with (evidence / (name + '.log')).open('wb') as log:
        value = subprocess.run(args, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, timeout=600)
    result['runs'].append({'command': args, 'exitCode': value.returncode,
                          'seconds': round(time.time() - start, 3), 'log': name + '.log'})
    return value.returncode

try:
    raw = Path(sys.argv[1]).read_bytes()
    check(len(raw) == 1843200 and hashlib.sha256(raw).hexdigest() == OUTER, 'outer identity mismatch')
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        members = archive.getmembers()
        check(len(members) == 6 and {m.name for m in members} == NAMES, 'outer member mismatch')
        check(all(m.isfile() and m.size <= 2000000 and m.mode == 0o600 for m in members), 'unsafe outer member')
        files = {m.name: archive.extractfile(m).read() for m in members}
    sums = files['SHA256SUMS'].decode().splitlines()
    expected = sorted(hashlib.sha256(files[n]).hexdigest() + '  ' + n for n in NAMES - {'SHA256SUMS'})
    check(sorted(sums) == expected, 'member checksum mismatch')
    source = files['source.zip']
    check(len(source) == 1823457 and hashlib.sha256(source).hexdigest() == INNER, 'source identity mismatch')
    manifest = json.loads(files['RELEASE.json'])
    check(manifest['commit'] == ORIGIN and manifest['tree'] == TREE, 'source pin mismatch')
    check(manifest['productionReady'] is False and manifest['mergeToMain'] == 'HOLD', 'scope mismatch')
    root = Path('/tmp/source'); root.mkdir(mode=0o700)
    source_files = {}
    with zipfile.ZipFile(io.BytesIO(source)) as archive:
        infos = archive.infolist()
        check(len(infos) <= 2048 and sum(i.file_size for i in infos) <= 64000000, 'source budget exceeded')
        seen = set()
        for item in infos:
            name = item.filename.rstrip('/') if item.is_dir() else item.filename
            parts = name.split('/')
            check(name not in seen and all(p not in ('', '.', '..', '.git') for p in parts)
                  and '\\' not in name and ':' not in name and not name.startswith('/'), 'unsafe source path')
            seen.add(name)
            mode = item.external_attr >> 16
            check(not stat.S_ISLNK(mode) and (item.is_dir() or stat.S_IFMT(mode) in (0, stat.S_IFREG)), 'source type refused')
            if item.is_dir():
                continue
            data = archive.read(item)
            source_files[name] = data
            target = root / PurePosixPath(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream: stream.write(data)
            target.chmod(0o644)
    check(len(source_files) == 698, 'source inventory mismatch')
    # This temporary verification commit is not the origin commit and is never pushed.
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    subprocess.run(['git', '-C', str(root), 'add', '--all'], check=True)
    actual_tree = subprocess.check_output(['git', '-C', str(root), 'write-tree'], text=True).strip()
    check(actual_tree == TREE, 'independent Git tree mismatch')
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Package verification',
                    '-c', 'user.email=verification@localhost', 'commit', '-qm', 'Verify exact embedded source'], check=True)
    result['temporaryVerificationCommit'] = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    result['verifiedSourceFiles'] = len(source_files)
    # Installer verifies a separate fresh target; it does not initialize state or start a service.
    bundle = Path('/tmp/bundle'); bundle.mkdir()
    for name, data in files.items(): (bundle / name).write_bytes(data)
    check(run([sys.executable, '-B', str(bundle / 'install.py'), '--target', '/tmp/installed'], str(bundle), 'install') == 0, 'installation failed')
    receipt = json.loads(Path('/tmp/installed/INSTALL-RECEIPT.json').read_text())
    check(receipt['sourceTree'] == TREE and receipt['sourceCommit'] == ORIGIN
          and receipt['sourceFiles'] == 698 and receipt['stateInitialized'] is False, 'installation receipt mismatch')
    failures = []
    for name, directory in [('ci', 'ci/tests'), ('domain', 'exchange/tests'),
                            ('integration', 'integration'), ('scenarios', 'scenarios/tests')]:
        args = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', directory]
        if name != 'ci': args += ['-t', '.']
        args += ['-v']
        if run(args, str(root), name): failures.append(name)
    check(not failures, 'offline suites failed: ' + ', '.join(failures))
    result['status'] = 'PASS_OFFLINE_ONLY'
except Exception as exc:
    result['status'] = 'FAIL'
    result['error'] = str(exc)
    raise
finally:
    (evidence / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2), flush=True)
    for record in result['runs']:
        print('Log tail: ' + record['log'], flush=True)
        print('\n'.join((evidence / record['log']).read_text(errors='replace').splitlines()[-12:]), flush=True)
