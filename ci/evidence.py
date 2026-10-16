"""Pure evidence validation; this module grants no reporting or execution authority."""

import hashlib
import re
from datetime import datetime

REPOSITORY = "GiraffeTechnology/8415ex"
CHECK_NAME = "8415ex/bootstrap"
IDENTITY_FIELDS = (
    "repository", "commit_sha", "tree_sha", "config_sha256", "run_id",
)
REQUIRED_STAGES = ("unit-tests", "smoke")
TERMINAL_OUTCOMES = {"success", "failure", "timeout", "cancelled"}
STAGE_OUTCOMES = {"passed", "failed", "timeout", "cancelled", "not_run"}


class EvidenceError(ValueError):
    """Evidence is malformed, stale, incomplete or inconsistent."""


def _require(condition, message):
    if not condition:
        raise EvidenceError(message)


def _text(value, name):
    _require(isinstance(value, str) and bool(value.strip()), f"{name} is required")
    return value


def _digest(value, length, name):
    _require(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{" + str(length) + r"}", value),
        f"{name} must be a full lowercase hexadecimal digest",
    )


def validate_identity(identity):
    _require(isinstance(identity, dict), "identity must be an object")
    _require(set(identity) == set(IDENTITY_FIELDS), "identity fields are incomplete or unknown")
    _require(identity["repository"] == REPOSITORY, "unexpected repository")
    _digest(identity["commit_sha"], 40, "commit_sha")
    _digest(identity["tree_sha"], 40, "tree_sha")
    _digest(identity["config_sha256"], 64, "config_sha256")
    run_id = _text(identity["run_id"], "run_id")
    _require(
        re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id),
        "run_id must be a bounded identifier",
    )


def validate_object(reference):
    """Validate a private-store evidence reference, not its existence or permissions."""
    _require(isinstance(reference, dict), "object reference must be an object")
    _require(
        set(reference) == {"bucket", "key", "object_id", "sha256"},
        "object reference fields are incomplete or unknown",
    )
    _require(reference["bucket"] == "giraffe", "unexpected storage bucket")
    key = _text(reference["key"], "object key")
    _require(
        not key.startswith("/") and all(part not in {"", ".", ".."} for part in key.split("/")),
        "object key must be a canonical relative key",
    )
    _text(reference["object_id"], "object_id")
    _digest(reference["sha256"], 64, "object sha256")


def verify_sha256(data, expected):
    """Compare independently retrieved bytes with a declared SHA-256."""
    _require(isinstance(data, bytes), "data must be bytes")
    _digest(expected, 64, "sha256")
    _require(hashlib.sha256(data).hexdigest() == expected, "object checksum mismatch")


def _utc_timestamp(value, name):
    _text(value, name)
    _require(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", value),
             f"{name} must be an ISO-8601 UTC timestamp ending in Z")
    try:
        timestamp = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise EvidenceError(f"{name} is not an ISO-8601 timestamp") from exc
    return timestamp


def validate_result(result, *, expected_identity, current_run_id, expected_prefix):
    """Validate terminal evidence against an independently trusted current run.

    Callers must enforce freshness atomically when publishing. This pure function
    cannot authenticate an executor, inspect storage backing, or prevent a race.
    """
    validate_identity(expected_identity)
    prefix = _text(expected_prefix, "expected project prefix")
    prefix = prefix[:-1] if prefix.endswith("/") else prefix
    _require(
        not prefix.startswith("/") and all(part not in {"", ".", ".."} for part in prefix.split("/")),
        "expected project prefix must be canonical and nonempty",
    )
    _require(isinstance(result, dict), "result must be an object")
    _require(
        set(result) == {
            "schema_version", "check_name", "identity", "outcome",
            "started_at", "finished_at", "source_object", "log_object",
            "stages", "artifacts",
        },
        "result fields are incomplete or unknown",
    )
    _require(type(result["schema_version"]) is int and result["schema_version"] == 1,
             "unsupported schema version")
    _require(result["check_name"] == CHECK_NAME, "unexpected check name")
    validate_identity(result["identity"])
    _require(result["identity"] == expected_identity, "result identity mismatch")
    _require(expected_identity["run_id"] == current_run_id, "obsolete run")
    outcome = result["outcome"]
    _require(isinstance(outcome, str) and outcome in TERMINAL_OUTCOMES,
             "terminal outcome is required")
    started = _utc_timestamp(result["started_at"], "started_at")
    finished = _utc_timestamp(result["finished_at"], "finished_at")
    _require(finished >= started, "finished_at precedes started_at")
    validate_object(result["source_object"])
    validate_object(result["log_object"])
    for reference in (result["source_object"], result["log_object"]):
        _require(reference["key"].startswith(prefix + "/"), "object is outside the expected project prefix")

    stages = result["stages"]
    _require(isinstance(stages, dict) and set(stages) == set(REQUIRED_STAGES),
             "all required stages must be recorded exactly once")
    outcomes = []
    for name in REQUIRED_STAGES:
        stage = stages[name]
        _require(isinstance(stage, dict) and set(stage) == {"outcome", "exit_code"},
                 f"{name} stage fields are invalid")
        state, code = stage["outcome"], stage["exit_code"]
        _require(isinstance(state, str) and state in STAGE_OUTCOMES,
                 f"{name} outcome is invalid")
        if state == "passed":
            _require(type(code) is int and code == 0, f"{name} passed without exit zero")
        elif state == "failed":
            _require(type(code) is int and code != 0, f"{name} failed without a nonzero exit")
        else:
            _require(code is None, f"{name} needs a null exit code")
        outcomes.append(state)

    artifacts = result["artifacts"]
    _require(isinstance(artifacts, list), "artifacts must be a list")
    for artifact in artifacts:
        validate_object(artifact)
        _require(artifact["key"].startswith(prefix + "/"), "artifact is outside the expected project prefix")
    if outcome == "success":
        _require(all(state == "passed" for state in outcomes),
                 "success requires every required stage to pass")
        _require(bool(artifacts), "success requires an artifact")
    else:
        required_state = {"failure": "failed", "timeout": "timeout", "cancelled": "cancelled"}[outcome]
        _require(required_state in outcomes, "terminal outcome lacks matching stage evidence")
