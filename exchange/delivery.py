"""Portable deterministic source/evidence archives; performs no deployment."""
import hashlib
import io
import json
import re
import zipfile
from pathlib import PurePosixPath

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def require(condition, message):
    if not condition:
        raise ValueError(message)

def identity(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None

def safe_path(path):
    return (isinstance(path, str) and bool(path) and not path.startswith("/")
            and "\\" not in path and ":" not in path
            and all(part not in ("", ".", "..") for part in path.split("/")))

def git_tree(files):
    """Hash complete regular-file source trees; no repository or Git write."""
    root = {}
    for path, data in files.items():
        require(safe_path(path), "unsafe source path")
        require(isinstance(data, bytes), "source bytes required")
        node = root
        parts = path.split("/")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
            require(isinstance(node, dict), "file/directory collision")
        require(parts[-1] not in node, "duplicate source path")
        node[parts[-1]] = data
    def obj(kind, value):
        return hashlib.sha1(kind.encode() + b" " + str(len(value)).encode() + b"\0" + value).digest()
    def walk(node):
        entries = []
        for name, value in node.items():
            directory = isinstance(value, dict)
            mode = b"40000" if directory else b"100644"
            digest = walk(value) if directory else obj("blob", value)
            entries.append(((name + ("/" if directory else "")).encode(),
                            mode + b" " + name.encode() + b"\0" + digest))
        return obj("tree", b"".join(value for _, value in sorted(entries)))
    return walk(root).hex()

def validate_evidence(evidence, logs):
    require(isinstance(evidence, dict), "evidence mapping required")
    require(evidence.get("kind") == "LOCAL_SIMULATION", "local evidence kind required")
    require(identity(evidence.get("commit")) and identity(evidence.get("tree")),
            "full string commit and tree required")
    require(isinstance(evidence.get("runs"), list) and evidence["runs"], "actual runs required")
    require(isinstance(logs, dict), "logs mapping required")
    for run in evidence["runs"]:
        require(isinstance(run, dict), "run mapping required")
        require(identity(run.get("testedTree")), "tested tree required")
        require(isinstance(run.get("command"), str) and bool(run["command"].strip()), "command required")
        require(type(run.get("exitCode")) is int, "integer exit code required")
        require(run.get("status") == ("passed" if run["exitCode"] == 0 else "failed"),
                "exit and status disagree")
        require(isinstance(run.get("log"), str) and run["log"] in logs, "raw log required")
        require(isinstance(logs[run["log"]], bytes), "log bytes required")
        require(run.get("logSHA256") == sha256(logs[run["log"]]), "raw log hash mismatch")
        from datetime import datetime
        try:
            start = datetime.fromisoformat(run["startUTC"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(run["endUTC"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError, AttributeError):
            raise ValueError("actual start/end UTC required") from None
        require(start.utcoffset() is not None and start.utcoffset().total_seconds() == 0
                and end.utcoffset() is not None and end.utcoffset().total_seconds() == 0
                and end >= start, "ordered UTC instants required")
    require(isinstance(evidence.get("notRun"), list) and evidence["notRun"], "unexecuted obligations required")
    require(all(isinstance(item, dict) and item.get("status") == "NOT_RUN"
                and isinstance(item.get("obligation"), str) and item["obligation"].strip()
                for item in evidence["notRun"]), "explicit NOT_RUN obligations required")
    # A schema and byte binding are not independent proof that a producer ran a command.
    return True

def build_bundle(files, evidence, logs):
    """Return zip bytes. Callers choose an approved destination; no disk writes."""
    validate_evidence(evidence, logs)
    require(files and git_tree(files) == evidence["tree"], "complete source tree mismatch")
    members = {"source/" + path: data for path, data in files.items()}
    members["evidence/run.json"] = canonical(evidence)
    for name, data in logs.items():
        require(safe_path(name), "unsafe log path")
        members["logs/" + name] = data
    manifest = {"schemaVersion": 1, "commit": evidence["commit"], "tree": evidence["tree"],
                "members": {name: {"bytes": len(data), "sha256": sha256(data)}
                            for name, data in sorted(members.items())}}
    members["manifest.json"] = canonical(manifest)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(members.items()):
            item = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            archive.writestr(item, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return output.getvalue()

def verify_bundle(data):
    """Verify bytes and source tree in memory; never extract untrusted paths."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), "duplicate archive member")
        require(all(safe_path(name) for name in names), "unsafe archive path")
        require(sum(item.file_size for item in archive.infolist()) <= 16 * 1024 * 1024,
                "archive exceeds local preparation bound")
        manifest = json.loads(archive.read("manifest.json"))
        require(isinstance(manifest, dict) and manifest.get("schemaVersion") == 1, "manifest schema")
        inventory = manifest.get("members")
        require(isinstance(inventory, dict) and set(inventory) == set(names) - {"manifest.json"},
                "manifest inventory mismatch")
        members = {}
        for name, expected in inventory.items():
            require(isinstance(expected, dict), "member metadata required")
            member = archive.read(name)
            require(type(expected.get("bytes")) is int and expected["bytes"] == len(member),
                    "member size mismatch")
            require(expected.get("sha256") == sha256(member), "member hash mismatch")
            members[name] = member
        evidence = json.loads(members["evidence/run.json"])
        logs = {name[5:]: value for name, value in members.items() if name.startswith("logs/")}
        validate_evidence(evidence, logs)
        require(manifest.get("commit") == evidence["commit"] and manifest.get("tree") == evidence["tree"],
                "manifest identity mismatch")
        files = {name[7:]: value for name, value in members.items() if name.startswith("source/")}
        require(files and git_tree(files) == evidence["tree"], "archive source tree mismatch")
        require(all(name.startswith(("source/", "logs/")) or name == "evidence/run.json"
                    for name in members), "unexpected archive member")
        return {"verified": True, "kind": evidence["kind"], "commit": evidence["commit"],
                "tree": evidence["tree"], "files": len(files), "sha256": sha256(data),
                "meaning": "byte/source binding only; not independent execution or deployment acceptance"}
