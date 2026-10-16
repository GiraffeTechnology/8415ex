"""Real command records: what was run, how it ended, and whether it ran at all.

A command record is produced from an execution that happened, or it says
NOT_RUN. There is no third shape. In particular:

* no record is written before the command's exit code is known, so a success
  code can never be pre-filled and then left standing by a later failure;
* a command that was not executed carries no exit code and no timing;
* a failure, an exception, a signal and a timeout stay distinguishable, because
  collapsing them loses the difference between "the suite failed" and "the suite
  never got to run".

Every executed record carries the UTC start and end, the working directory, the
exit code, and digests plus tails of the real stdout and stderr, so the record
can be checked against the captured log rather than believed.
"""
import hashlib
import os
import subprocess
import time
import uuid
from pathlib import Path

#: How much of each stream is kept inline. The digest covers the whole stream.
TAIL_BYTES = 4096

#: Nothing local is expected to take this long. A command that does is recorded
#: as a timeout, never as a failure and never as a pass.
DEFAULT_TIMEOUT_SECONDS = 1800


def _utc(stamp):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(stamp))


def _stream(raw):
    data = raw or b""
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "tail": data[-TAIL_BYTES:].decode("utf-8", "replace")}


def not_run(command, reason, cases=()):
    """A command this run did not execute. It carries no result of any kind."""
    return {"command": command, "outcome": "not-run", "exitCode": None,
            "startedAt": None, "finishedAt": None, "reason": reason,
            "cases": list(cases), "executed": False}


def pending(command, reason, cases=()):
    """A command that is expected to run later. Still no result."""
    return {"command": command, "outcome": "pending", "exitCode": None,
            "startedAt": None, "finishedAt": None, "reason": reason,
            "cases": list(cases), "executed": False}


def run_command(argv, root=".", timeout=DEFAULT_TIMEOUT_SECONDS, cases=(), env=None,
                raw_log_dir=None):
    """Execute one command and record only what actually happened."""
    command = " ".join(argv)
    environment = dict(os.environ)
    environment.setdefault("PYTHONDONTWRITEBYTECODE", "1")
    if env:
        environment.update(env)
    raw_streams = {}
    started = time.time()
    started_at = _utc(started)
    record = {"command": command, "argv": list(argv), "cwd": str(root),
              "cases": list(cases), "executed": True, "startedAt": started_at}
    try:
        completed = subprocess.run(argv, cwd=root, capture_output=True, check=False,
                                   timeout=timeout, env=environment)
    except subprocess.TimeoutExpired as expiry:
        raw_streams = {"stdout": expiry.stdout or b"", "stderr": expiry.stderr or b""}
        finished = time.time()
        record.update({"outcome": "timeout", "exitCode": None,
                       "timeoutSeconds": timeout,
                       "stdout": _stream(expiry.stdout), "stderr": _stream(expiry.stderr),
                       "detail": f"no exit code: the command was still running after "
                                 f"{timeout}s and was stopped"})
    except OSError as problem:
        finished = time.time()
        record.update({"outcome": "error", "exitCode": None,
                       "stdout": _stream(b""), "stderr": _stream(b""),
                       "detail": f"the command could not be started: {problem}"})
    else:
        raw_streams = {"stdout": completed.stdout, "stderr": completed.stderr}
        finished = time.time()
        status = completed.returncode
        if status == 0:
            outcome = "passed"
        elif status < 0:
            outcome = "signalled"
        else:
            outcome = "failed"
        record.update({"outcome": outcome, "exitCode": status,
                       "signal": -status if status < 0 else None,
                       "stdout": _stream(completed.stdout),
                       "stderr": _stream(completed.stderr)})
    record["finishedAt"] = _utc(finished)
    record["durationMs"] = int((finished - started) * 1000)
    if raw_log_dir is not None:
        # Only advertise files after the captured bytes have actually been saved.
        # Do not fabricate raw logs for an invocation that never started.
        directory = Path(raw_log_dir)
        prefix = "command-" + uuid.uuid4().hex
        record["rawLog"] = {}
        for name, data in raw_streams.items():
            target = directory / (prefix + "." + name + ".log")
            with target.open("xb") as handle:
                handle.write(data)
            record["rawLog"][name] = {"path": str(target.resolve()),
                                       "artifactPath": target.name, "bytes": len(data),
                                       "sha256": hashlib.sha256(data).hexdigest()}
    return record


def self_record(command, exit_code, started_at, finished_at, cases=(), detail=None):
    """The record for the run that is producing this bundle.

    It records a completed in-process calculation. Its caller must state that
    scope; this is never evidence of the process's eventual exit or delivery.
    """
    if exit_code is None:
        raise ValueError("a self record needs the final exit code; nothing is pre-filled")
    return {"command": command, "outcome": "passed" if exit_code == 0 else "failed",
            "exitCode": exit_code, "startedAt": started_at, "finishedAt": finished_at,
            "cases": list(cases), "executed": True, "selfReported": True,
            "detail": detail or ("this record describes a completed in-process calculation; "
                                 "it does not capture final process exit or delivery")}


def capture_cli(argv, root=".", timeout=DEFAULT_TIMEOUT_SECONDS, env=None, raw_log_dir=None):
    """Observe a command's final outer status from outside it.

    A process cannot record its own final exit status: it is not known until the
    process has ended, and the record it writes is already written by then. The
    authoritative final status of a CLI invocation therefore has to be captured
    by something that outlives it, which is what this does. It runs the command
    and returns the real argv, stdout, stderr, exit status and timing, with an
    explicit note of what the record covers.

    This observes an existing entry point; it is not a second runner, and it
    computes nothing of its own.
    """
    record = run_command(argv, root=root, timeout=timeout, env=env, raw_log_dir=raw_log_dir)
    record["scope"] = "final-outer-process"
    record["observedBy"] = "external observer, not the observed process"
    return record
