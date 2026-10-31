"""Deterministic, hash-pinned local simulation zipapp; no installer writes."""
import argparse
import hashlib
import io
import json
import re
import stat
import sys
import zipfile
from .delivery import git_tree

MAX_ARCHIVE = 16 * 1024 * 1024
MAX_CONTENT = 8 * 1024 * 1024
# Bounded full-source capacity, independent of the two generated kit members.
# The current committed source exceeds 512 files; byte budgets stay unchanged.
MAX_MEMBERS = 1024
# Directory metadata has its own finite budget; it is not executable source.
MAX_DIRECTORIES = 128
MANIFEST = "DEMO-KIT-MANIFEST.json"
BOOTSTRAP = b"""import hashlib, os, sys
sys.dont_write_bytecode = True
expected = os.environ.get('EX_DEMO_SHA256', '')
if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
    raise SystemExit('EX_DEMO_SHA256 must be a separately verified lowercase SHA-256')
with open(sys.argv[0], 'rb') as stream:
    archive = stream.read(16 * 1024 * 1024 + 1)
if len(archive) > 16 * 1024 * 1024 or hashlib.sha256(archive).hexdigest() != expected:
    raise SystemExit('demo archive digest mismatch')
from exchange.demo_package import run_archive
raise SystemExit(run_archive(archive, expected, sys.argv[1:]))
"""

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

def read_archive(data, *, generated_kit=False):
    if type(generated_kit) is not bool:
        raise ValueError("explicit archive kind required")
    # Only the verifier can spend the two fixed generated launcher/manifest slots.
    maximum_files = MAX_MEMBERS + (2 if generated_kit else 0)
    if not isinstance(data, bytes) or not data or len(data) > MAX_ARCHIVE:
        raise ValueError("bounded archive bytes required")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = archive.infolist()
            if len(members) > maximum_files + MAX_DIRECTORIES:
                raise ValueError("too many archive members")
            seen, result, total = set(), {}, 0
            directory_count = file_count = 0
            for member in members:
                path = member.filename.rstrip("/")
                parts = path.split("/")
                if (not path or path.startswith("/") or "\\" in path or ":" in path
                        or any(part in ("", ".", "..") for part in parts)):
                    raise ValueError("unsafe archive path")
                if path in seen:
                    raise ValueError("duplicate archive member")
                seen.add(path)
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode) or member.flag_bits & 1:
                    raise ValueError("link or encrypted member refused")
                if member.is_dir():
                    directory_count += 1
                    if directory_count > MAX_DIRECTORIES:
                        raise ValueError("too many archive directories")
                    continue
                file_count += 1
                if file_count > maximum_files:
                    raise ValueError("too many archive members")
                if stat.S_IFMT(mode) not in (0, stat.S_IFREG):
                    raise ValueError("non-regular member refused")
                total += member.file_size
                if total > MAX_CONTENT or member.file_size > MAX_CONTENT:
                    raise ValueError("archive content limit")
                result[path] = archive.read(member)
            if generated_kit and (MANIFEST not in result or "__main__.py" not in result):
                raise ValueError("fixed generated kit members required")
            return result
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as error:
        raise ValueError("invalid archive") from error

def pack(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for path, data in sorted(files.items()):
            member = zipfile.ZipInfo(path, (1980, 1, 1, 0, 0, 0))
            member.create_system = 3
            member.external_attr = 0o100644 << 16
            member.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(member, data, compresslevel=9)
    return output.getvalue()

def build(source_zip, commit, tree):
    if any(not isinstance(v, str) or re.fullmatch(r"[0-9a-f]{40}", v) is None
           for v in (commit, tree)):
        raise ValueError("full source commit and tree required")
    source = read_archive(source_zip)
    if MANIFEST in source or "__main__.py" in source:
        raise ValueError("source uses reserved kit path")
    if git_tree(source) != tree:
        raise ValueError("source tree mismatch")
    for required in ("exchange/__init__.py", "exchange/demo_ui.py",
                     "exchange/demo_package.py", "scenarios/__init__.py", "scenarios/demos.py"):
        if required not in source:
            raise ValueError("required runtime source missing")
    manifest = {"schema": "8415ex-local-demo-kit/1", "scope": "LOCAL_SIMULATION",
                "commit": commit, "tree": tree, "realAcceptance": "NOT_RUN",
                "files": {p: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                          for p, data in sorted(source.items())}}
    data = pack(dict(source, **{MANIFEST: canonical(manifest), "__main__.py": BOOTSTRAP}))
    # Generated metadata also consumes the same member and byte budgets.
    verify(data, hashlib.sha256(data).hexdigest())
    return data

def verify(data, expected_sha256):
    if (not isinstance(expected_sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None
            or not isinstance(data, bytes)
            or hashlib.sha256(data).hexdigest() != expected_sha256):
        raise ValueError("demo archive digest mismatch")
    members = read_archive(data, generated_kit=True)
    if members.pop("__main__.py", None) != BOOTSTRAP:
        raise ValueError("kit bootstrap mismatch")
    try:
        manifest = json.loads(members.pop(MANIFEST))
    except (KeyError, ValueError, UnicodeError) as error:
        raise ValueError("kit manifest missing or invalid") from error
    if (not isinstance(manifest, dict) or manifest.get("schema") != "8415ex-local-demo-kit/1"
            or manifest.get("scope") != "LOCAL_SIMULATION"
            or manifest.get("realAcceptance") != "NOT_RUN"
            or not isinstance(manifest.get("commit"), str)
            or re.fullmatch(r"[0-9a-f]{40}", manifest["commit"]) is None
            or not isinstance(manifest.get("tree"), str)
            or re.fullmatch(r"[0-9a-f]{40}", manifest["tree"]) is None):
        raise ValueError("kit identity refused")
    expected_files = {p: {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}
                      for p, b in sorted(members.items())}
    if manifest.get("files") != expected_files or git_tree(members) != manifest["tree"]:
        raise ValueError("kit source manifest mismatch")
    return manifest

def run_archive(data, expected_sha256, argv=None):
    manifest = verify(data, expected_sha256)
    parser = argparse.ArgumentParser(description="Hash-pinned LOCAL SIMULATION; no real provider")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--port", type=int, default=8415)
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        raise ValueError("invalid loopback port")
    if args.verify:
        print(canonical(manifest).decode())
        return 0
    from .demo_ui import main as demo_main
    return demo_main(["--port", str(args.port), "--commit", manifest["commit"],
                      "--tree", manifest["tree"]])

def main(argv=None, input_stream=None, output_stream=None):
    parser = argparse.ArgumentParser(description="Build or inspect a local demo kit without extraction")
    parser.add_argument("command", choices=("build", "verify"))
    parser.add_argument("--commit")
    parser.add_argument("--tree")
    parser.add_argument("--sha256")
    args = parser.parse_args(argv)
    raw = (input_stream or sys.stdin.buffer).read(MAX_ARCHIVE + 1)
    output = output_stream or sys.stdout.buffer
    try:
        result = build(raw, args.commit, args.tree) if args.command == "build" else canonical(verify(raw, args.sha256))
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    output.write(result)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
