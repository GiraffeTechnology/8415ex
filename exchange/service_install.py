"""Offline full-source installation; never configures hosts, credentials or stores."""
import hashlib
import json
from pathlib import Path
import shutil
import re
import stat
from .demo_package import read_archive
from .delivery import git_tree


def install_source(data, *, sha256, tree, target, commit):
    if type(commit) is not str or not re.fullmatch("[0-9a-f]{40}", commit):
        raise ValueError("EX_INSTALL_COMMIT_REFUSED")
    if type(data) is not bytes or hashlib.sha256(data).hexdigest() != sha256:
        raise ValueError('EX_INSTALL_DIGEST_REFUSED')
    files = read_archive(data)
    if git_tree(files) != tree or 'exchange/service_runtime.py' not in files:
        raise ValueError('EX_INSTALL_SOURCE_REFUSED')
    if any(p in ('.git', 'INSTALLING', 'INSTALL-RECEIPT.json') or p.startswith('.git/') for p in files):
        raise ValueError('EX_INSTALL_METADATA_REFUSED')
    target = Path(target)
    if not target.is_absolute() or target.parent.resolve() != target.parent or not target.parent.is_dir():
        raise ValueError('EX_INSTALL_TARGET_REFUSED')
    # Exclusive fresh version directory. No existing release or state is changed.
    target.mkdir(mode=0o700, exist_ok=False)
    try:
        (target / 'INSTALLING').write_text('incomplete\n')
        for name, raw in files.items():
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with path.open('xb') as stream:
                stream.write(raw)
            path.chmod(0o600)
        receipt = {'schema': '8415ex-installed-source/1', 'sourceArchiveSha256': sha256,
                   'sourceCommit': commit, 'sourceTree': tree, 'sourceFiles': len(files), 'stateInitialized': False,
                   'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}}
        (target / 'INSTALL-RECEIPT.json').write_text(json.dumps(receipt, sort_keys=True)+'\n')
        (target / 'INSTALLING').unlink()
        return receipt
    except BaseException:
        shutil.rmtree(target)
        raise


def verify_installation(root, *, commit, tree):
    root = Path(root)
    if not root.is_absolute() or root.resolve() != root or not root.is_dir():
        raise ValueError('EX_INSTALL_PATH_REFUSED')
    if (root / 'INSTALLING').exists() or (root / 'INSTALLING').is_symlink():
        raise ValueError('EX_INSTALL_INCOMPLETE')
    receipt_path = root / 'INSTALL-RECEIPT.json'
    if not stat.S_ISREG(receipt_path.lstat().st_mode):
        raise ValueError('EX_INSTALL_PATH_REFUSED')
    receipt = json.loads(receipt_path.read_text())
    if receipt.get('sourceCommit') != commit or receipt.get('sourceTree') != tree:
        raise ValueError('EX_INSTALL_VERSION_REFUSED')
    expected = receipt.get('files')
    if type(expected) is not dict or not expected:
        raise ValueError('EX_INSTALL_INVENTORY_REFUSED')
    # Check the whole immutable inventory, not only is_file() entries: that
    # silently ignores linked directories, dangling links and special files.
    # The original private/quiescent-directory requirement still applies.
    from .delivery import safe_path
    directories = set()
    for name in expected:
        if not safe_path(name):
            raise ValueError('EX_INSTALL_PATH_REFUSED')
        directories.update(str(p) for p in Path(name).parents if str(p) != '.')
    actual, actual_directories = set(), set()
    for path in root.rglob('*'):
        name = str(path.relative_to(root))
        mode = path.lstat().st_mode
        if stat.S_ISREG(mode):
            actual.add(name)
        elif stat.S_ISDIR(mode):
            actual_directories.add(name)
        else:
            raise ValueError('EX_INSTALL_PATH_REFUSED')
    if actual_directories != directories or actual != set(expected) | {'INSTALL-RECEIPT.json'}:
        raise ValueError('EX_INSTALL_INVENTORY_REFUSED')
    files = {}
    for name, digest in expected.items():
        path = root / name
        if path.resolve() != path or not path.is_file():
            raise ValueError('EX_INSTALL_PATH_REFUSED')
        files[name] = path.read_bytes()
        if hashlib.sha256(files[name]).hexdigest() != digest:
            raise ValueError('EX_INSTALL_CONTENT_REFUSED')
    if git_tree(files) != tree:
        raise ValueError('EX_INSTALL_TREE_REFUSED')
    return receipt
