"""Conservative EX transport-attempt barrier, never a native funds journal.

The host explicitly supplies a dedicated store. No production path is chosen.
An attempt is permanent: recover/observe/status remain the original server's
responsibility, and this module cannot authorize a second execution.
"""
import hashlib
import json
import sqlite3


class WalletExecutionAttempts:
    def __init__(self, path):
        if not isinstance(path, str) or not path or path == ":memory:":
            raise ValueError("dedicated persistent attempt path required")
        self.path = path
        with sqlite3.connect(self.path, timeout=5) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("CREATE TABLE IF NOT EXISTS ex_wallet_execution_attempts ("
                       "operation_key TEXT PRIMARY KEY, request_digest TEXT NOT NULL)")

    def claim(self, binding, request):
        # Include the original actor/server/chain/task/operation identity. Budget
        # revision changes or a changed child must never create another send slot.
        identity = {key: binding[key] for key in ("origin", "tenant", "account", "chainId")}
        identity.update(taskDigest=request["taskDigest"], operationId=request["operationId"])
        encode = lambda row: json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        key = hashlib.sha256(encode(identity)).hexdigest()
        digest = hashlib.sha256(encode(request)).hexdigest()
        with sqlite3.connect(self.path, timeout=5) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT request_digest FROM ex_wallet_execution_attempts WHERE operation_key=?", (key,)).fetchone()
            if existing is not None:
                return False
            db.execute("INSERT INTO ex_wallet_execution_attempts VALUES (?, ?)", (key, digest))
        # Commit has completed before the caller may touch the execute transport.
        return True
