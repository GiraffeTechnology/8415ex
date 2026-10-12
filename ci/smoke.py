"""A harmless fixture. Its manifest is a claim, never trusted CI attestation."""

import argparse
import hashlib
import json
from pathlib import Path

from ci.evidence import EvidenceError, validate_identity

PAYLOAD = b"8415ex bootstrap smoke artifact v1\n"


def run_smoke(output_dir, identity, mode):
    validate_identity(identity)
    if mode not in {"success", "failure"}:
        raise EvidenceError("mode must be success or failure")
    path = Path(output_dir)
    if not path.is_absolute():
        raise EvidenceError("output directory must be absolute")
    if not path.is_dir() or path.is_symlink():
        raise EvidenceError("output directory must already exist and not be a symlink")
    if path.resolve() != path:
        raise EvidenceError("output directory must be canonical without symlink ancestors")
    if any(path.iterdir()):
        raise EvidenceError("output directory must be empty")

    # Exclusive file creation never overwrites an earlier run's evidence.
    if mode == "success":
        with (path / "smoke.txt").open("xb") as handle:
            handle.write(PAYLOAD)
        artifacts = [{
            "path": "smoke.txt",
            "sha256": hashlib.sha256(PAYLOAD).hexdigest(),
            "size_bytes": len(PAYLOAD),
        }]
    else:
        artifacts = []
    manifest = {
        "schema_version": 1,
        "fixture": "8415ex/bootstrap-smoke",
        "identity": identity,
        "outcome": mode,
        "artifacts": artifacts,
    }
    with (path / "smoke-manifest.json").open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return 0 if mode == "success" else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--tree-sha", required=True)
    parser.add_argument("--config-sha256", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", choices=("success", "failure"), required=True)
    args = parser.parse_args(argv)
    identity = {
        "repository": args.repository,
        "commit_sha": args.commit_sha,
        "tree_sha": args.tree_sha,
        "config_sha256": args.config_sha256,
        "run_id": args.run_id,
    }
    try:
        return run_smoke(args.output_dir, identity, args.mode)
    except (EvidenceError, OSError) as exc:
        parser.exit(2, f"smoke fixture error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
