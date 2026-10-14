"""Source and package manifest for a local run.

The manifest binds a result to the exact source it came from: the commit, the
tree, whether the worktree was clean, the runtime, and every tracked file with
its byte count and digest. It records what was built and run, never that a
deployment happened.
"""
import hashlib
import platform
import subprocess
import sys
from pathlib import Path

REPOSITORY = "GiraffeTechnology/8415ex"


def _git(*args, root="."):
    result = subprocess.run(("git", *args), capture_output=True, text=True, cwd=root, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def source_identity(root="."):
    """The exact source a run is bound to."""
    status = _git("status", "--porcelain", root=root)
    return {
        "repository": REPOSITORY,
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD", root=root),
        "commit": _git("rev-parse", "HEAD", root=root),
        "tree": _git("rev-parse", "HEAD^{tree}", root=root),
        "worktreeClean": status == "",
        "dirtyFileCount": 0 if status == "" else len(status.splitlines()) if status else None,
    }


def runtime_identity():
    """The runtime a run actually used."""
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "thirdPartyDependencies": "none; standard library only",
    }


def file_inventory(root=".", paths=None):
    """Every tracked file with its byte count and digest."""
    listed = paths if paths is not None else (_git("ls-files", root=root) or "").splitlines()
    base = Path(root)
    inventory = []
    for name in sorted(listed):
        target = base / name
        if not target.is_file():
            continue
        data = target.read_bytes()
        inventory.append({"path": name, "bytes": len(data),
                          "sha256": hashlib.sha256(data).hexdigest()})
    return inventory


def build(root=".", commands=(), run_id=None, artifacts=()):
    """One manifest covering source, runtime, files, commands and artifacts."""
    inventory = file_inventory(root)
    return {
        "schema": "8415ex-local-manifest/1",
        "runId": run_id,
        "source": source_identity(root),
        "runtime": runtime_identity(),
        "fileCount": len(inventory),
        "totalBytes": sum(entry["bytes"] for entry in inventory),
        "files": inventory,
        "commands": list(commands),
        "artifacts": list(artifacts),
        "scope": ("local source and run identity only; it records no deployment, no chain "
                  "execution and no published package"),
    }


def digest_of(path):
    data = Path(path).read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
