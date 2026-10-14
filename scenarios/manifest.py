"""Source and package manifest for a local run.

The manifest binds a result to the exact source it came from: the repository
root actually imported, the commit, the tree, whether the worktree was clean,
the runtime, and every tracked file with its byte count and digest. It records
what was built and run, never that a deployment happened.

Everything here fails closed. A Git invocation that failed, a root that is not
a repository, an enumeration that returned nothing, and a tracked file that is
missing or unreadable are each reported as an explicit error. None of them is
read as "clean", "empty" or "consistent".
"""
import hashlib
import platform
import subprocess
import sys
from pathlib import Path

from .observations import tracked_files

REPOSITORY = "GiraffeTechnology/8415ex"

#: The package whose location proves which source tree actually executed.
EXECUTED_PACKAGE = "scenarios"


def _git(*args, root="."):
    """Run one Git command and keep its status.

    Returns ``(value, error)``. A non-zero status or a failed invocation yields
    ``(None, reason)``; it is never collapsed into an empty string, because an
    empty string is also the answer that means "clean".
    """
    try:
        result = subprocess.run(("git", *args), capture_output=True, text=True,
                                cwd=root, check=False)
    except OSError as problem:
        return None, f"git {' '.join(args)}: {problem}"
    if result.returncode != 0:
        return None, (f"git {' '.join(args)} exited {result.returncode}: "
                      f"{result.stderr.strip() or 'no stderr'}")
    return result.stdout, None


def executed_source_root():
    """The directory the running code was actually imported from."""
    return str(Path(__file__).resolve().parents[1])


def source_identity(root="."):
    """The exact source a run is bound to, or an explicit failure.

    ``ok`` is true only when the branch, commit, tree and worktree status were
    all read successfully. ``worktreeClean`` is ``None`` when the status could
    not be established: it is never defaulted to true.
    """
    errors = []

    def read(*args):
        value, error = _git(*args, root=root)
        if error is not None:
            errors.append(error)
        return value

    branch = read("rev-parse", "--abbrev-ref", "HEAD")
    commit = read("rev-parse", "HEAD")
    tree = read("rev-parse", "HEAD^{tree}")
    status = read("status", "--porcelain")
    toplevel = read("rev-parse", "--show-toplevel")

    if status is None:
        clean, dirty_count, dirty = None, None, None
    else:
        lines = [line for line in status.splitlines() if line.strip()]
        clean, dirty_count, dirty = not lines, len(lines), [line[3:] for line in lines[:50]]

    resolved_root = str(Path(root).resolve())
    executed_root = executed_source_root()
    identity = {
        "repository": REPOSITORY,
        "requestedRoot": resolved_root,
        "gitToplevel": toplevel.strip() if isinstance(toplevel, str) else None,
        "executedFrom": executed_root,
        "branch": branch.strip() if isinstance(branch, str) else None,
        "commit": commit.strip() if isinstance(commit, str) else None,
        "tree": tree.strip() if isinstance(tree, str) else None,
        "worktreeClean": clean,
        "dirtyFileCount": dirty_count,
        "dirtyFiles": dirty,
    }
    # The reported root must be the tree the running code came from, or the
    # identity describes one source while another one executed.
    if identity["gitToplevel"] is not None:
        top = str(Path(identity["gitToplevel"]).resolve())
        if top != str(Path(executed_root).resolve()):
            errors.append(f"executed source {executed_root} is outside the reported "
                          f"repository {top}")
        if top != resolved_root and resolved_root != str(Path(executed_root).resolve()):
            errors.append(f"requested root {resolved_root} is not the repository root {top}")
    identity["errors"] = errors
    identity["ok"] = (not errors and identity["commit"] is not None
                      and identity["tree"] is not None and clean is not None)
    identity["executedSourceConfirmed"] = (
        identity["gitToplevel"] is not None
        and str(Path(identity["gitToplevel"]).resolve()) == str(Path(executed_root).resolve()))
    return identity


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
    """Every tracked file with its byte count and digest, or an explicit failure.

    A failed enumeration, a tracked path missing from the worktree and a file
    that could not be read are all reported. None of them is skipped silently,
    so an empty or short inventory can never be read as a complete one.
    """
    if paths is not None:
        listed, state, error = tuple(paths), "supplied", None
    else:
        enumeration = tracked_files(root)
        listed = enumeration["files"]
        state, error = enumeration["state"], enumeration["error"]
    base = Path(root)
    inventory, missing, unreadable = [], [], []
    for name in sorted(listed):
        target = base / name
        if not target.is_file():
            missing.append({"path": name, "reason": "tracked but missing from the worktree"})
            continue
        try:
            data = target.read_bytes()
        except OSError as problem:
            unreadable.append({"path": name, "reason": str(problem)})
            continue
        inventory.append({"path": name, "bytes": len(data),
                          "sha256": hashlib.sha256(data).hexdigest()})
    enumerated = len(listed)
    return {
        "enumerationState": state,
        "error": error,
        "enumerated": enumerated,
        "files": inventory,
        "missing": missing,
        "unreadable": unreadable,
        "ok": (error is None and enumerated > 0 and not missing and not unreadable
               and len(inventory) == enumerated),
    }


def build(root=".", commands=(), run_id=None, artifacts=()):
    """One manifest covering source, runtime, files, commands and artifacts."""
    inventory = file_inventory(root)
    source = source_identity(root)
    files = inventory["files"]
    return {
        "schema": "8415ex-local-manifest/2",
        "runId": run_id,
        "source": source,
        "runtime": runtime_identity(),
        "fileCount": len(files),
        "enumeratedCount": inventory["enumerated"],
        "totalBytes": sum(entry["bytes"] for entry in files),
        "files": files,
        "missingFiles": inventory["missing"],
        "unreadableFiles": inventory["unreadable"],
        "enumerationState": inventory["enumerationState"],
        "inventoryError": inventory["error"],
        "inventoryOk": inventory["ok"],
        "consistent": bool(source["ok"] and inventory["ok"]),
        "commands": list(commands),
        "artifacts": list(artifacts),
        "scope": ("local source and run identity only; it records no deployment, no chain "
                  "execution and no published package"),
    }


def digest_of(path):
    data = Path(path).read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
