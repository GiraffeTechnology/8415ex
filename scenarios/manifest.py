"""Source and package manifest for a local run.

The manifest reports a result alongside observed source identity: the repository
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
import time
from pathlib import Path

from .observations import tracked_files

REPOSITORY = "GiraffeTechnology/8415ex"

#: The package whose location proves which source tree actually executed.
EXECUTED_PACKAGE = "scenarios"

#: Every top-level package that belongs to this project. A run is only bound to
#: one source tree if all of them came from that tree: checking the scenarios
#: package alone leaves the domain free to be imported from somewhere else.
PROJECT_PACKAGES = ("scenarios", "exchange", "ci")


def loaded_module_provenance(root="."):
    """Loaded project module origins and their current on-disk file bytes.

    Walks the modules actually imported into this interpreter, keeps the ones
    belonging to this project, and records each one's resolved path, byte count
    and digest. A module loaded from outside ``root`` is foreign: the run is
    then executing a mixture of trees, and no single commit describes it.
    """
    base = Path(root).resolve()
    modules, foreign, unreadable = [], [], []
    for name, module in sorted(sys.modules.items()):
        spec_name = getattr(getattr(module, "__spec__", None), "name", None)
        project_name = spec_name if name == "__main__" and spec_name else name
        if project_name.split(".")[0] not in PROJECT_PACKAGES:
            continue
        origin = getattr(module, "__file__", None)
        if origin is None:
            # A namespace package carries no file of its own.
            continue
        resolved = Path(origin).resolve()
        entry = {"module": name, "projectModule": project_name, "path": str(resolved),
                 "measurement": "on-disk-file-at-observation-time"}
        try:
            data = resolved.read_bytes()
        except OSError as problem:
            entry.update({"bytes": None, "sha256": None, "error": str(problem)})
            unreadable.append(entry)
            modules.append(entry)
            continue
        entry.update({"bytes": len(data),
                      "sha256": hashlib.sha256(data).hexdigest(), "error": None})
        try:
            entry["relative"] = str(resolved.relative_to(base))
            entry["inside"] = True
        except ValueError:
            entry["relative"] = None
            entry["inside"] = False
            foreign.append(entry)
        modules.append(entry)
    return {
        "root": str(base),
        "scope": "loaded module origins and current on-disk file bytes",
        "executionBytesAttested": False,
        "limitations": ("does not attest already loaded code objects, bytecode caches, "
                        "import hooks, monkey patches or all executed bytes"),
        "packages": sorted({entry["projectModule"].split(".")[0] for entry in modules}),
        "modules": modules,
        "moduleCount": len(modules),
        "foreign": foreign,
        "unreadable": unreadable,
        "ok": not foreign and not unreadable and modules != [],
        "digest": hashlib.sha256(
            "\n".join(f"{entry['module']}:{entry['sha256']}" for entry in modules)
            .encode("utf-8")).hexdigest(),
    }


def snapshot(root="."):
    """The whole source identity at one instant, for before/after comparison."""
    source = source_identity(root)
    inventory = file_inventory(root)
    provenance = loaded_module_provenance(root)
    return {
        "takenAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "commit": source["commit"],
        "tree": source["tree"],
        "worktreeClean": source["worktreeClean"],
        "dirtyFileCount": source["dirtyFileCount"],
        "sourceOk": source["ok"],
        "inventoryOk": inventory["ok"],
        "fileCount": len(inventory["files"]),
        "inventoryDigest": hashlib.sha256(
            "\n".join(f"{entry['path']}:{entry['sha256']}"
                       for entry in inventory["files"]).encode("utf-8")).hexdigest(),
        "moduleDigest": provenance["digest"],
        "moduleProvenance": provenance,
        "moduleCount": provenance["moduleCount"],
        "provenanceOk": provenance["ok"],
        "foreignModules": [entry["module"] for entry in provenance["foreign"]],
    }


#: What must not change between the snapshots that bracket a run.
SNAPSHOT_INVARIANTS = ("commit", "tree", "worktreeClean", "inventoryDigest",
                       "moduleDigest", "fileCount")


def reconcile(before, after):
    """Compare two snapshots and report every difference.

    A run is bound to one source only if the source did not move while it ran.
    An earlier clean snapshot combined with a later, different manifest is two
    runs reported as one, so any difference here is a failure rather than a
    note.
    """
    differences = []
    for key in SNAPSHOT_INVARIANTS:
        if before.get(key) != after.get(key):
            differences.append({"field": key, "before": before.get(key),
                                "after": after.get(key)})
    reasons = [f"{entry['field']} changed during the run" for entry in differences]
    if not before.get("provenanceOk") or not after.get("provenanceOk"):
        reasons.append("a loaded project module came from outside this source tree")
    if not before.get("sourceOk") or not after.get("sourceOk"):
        reasons.append("the source identity could not be established")
    ordered = tuple(dict.fromkeys(reasons))
    return {"before": before, "after": after, "differences": differences,
            "reasons": ordered, "consistent": ordered == ()}


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
    # Every loaded project module must come from this tree, not just the one
    # this file happens to live in.
    provenance = loaded_module_provenance(root)
    identity["loadedModules"] = provenance["moduleCount"]
    identity["loadedPackages"] = provenance["packages"]
    identity["foreignModules"] = [entry["module"] for entry in provenance["foreign"]]
    identity["moduleDigest"] = provenance["digest"]
    identity["moduleProvenance"] = provenance
    for entry in provenance["foreign"]:
        errors.append(f"module {entry['module']} was loaded from {entry['path']}, "
                      f"outside {provenance['root']}")
    for entry in provenance["unreadable"]:
        errors.append(f"module {entry['module']} could not be read: {entry['error']}")
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
