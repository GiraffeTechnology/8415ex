"""Conservative EX transport-attempt barrier, never a native funds journal.

The host explicitly supplies a dedicated store. No production path is chosen.
An attempt is permanent: recover/observe/status remain the original server's
responsibility, and this module cannot authorize a second execution.
"""
import hashlib
import json
import sqlite3
from pathlib import Path


class WalletExecutionAttempts:
    def __init__(self, path):
        if not isinstance(path, str) or not path or path == ":memory:":
            raise ValueError("dedicated persistent attempt path required")
        self.path = path
        with sqlite3.connect(self.path, timeout=5) as db:
            db.execute("PRAGMA synchronous=FULL")
            db.execute("CREATE TABLE IF NOT EXISTS ex_wallet_execution_attempts ("
                       "operation_key TEXT PRIMARY KEY, request_digest TEXT NOT NULL)")

    @classmethod
    def open_existing(cls, path):
        """Bind a supplied original store without creating a file or schema.

        This pins a private, quiescent local file, not its business authority.
        Missing/replaced stores require original-owner reconciliation, never an
        empty replacement that would lose already-attempted operation barriers.
        """
        if type(path) is not str:
            raise ValueError("existing canonical attempt path required")
        file = Path(path)
        if not file.is_absolute() or file.resolve() != file or not file.is_file():
            raise ValueError("existing canonical attempt path required")
        info = file.stat()
        instance = cls.__new__(cls)
        instance.path = str(file)
        instance._original_file = (info.st_dev, info.st_ino)
        db = instance._connect_existing(readonly=True)
        db.close()
        return instance

    def _connect_existing(self, *, readonly=False):
        file = Path(self.path)
        if (file.resolve() != file or not file.is_file()
                or (file.stat().st_dev, file.stat().st_ino) != self._original_file):
            raise ValueError("original attempt store missing or replaced")
        # URI mode prevents sqlite3's default create-on-open behavior.
        db = sqlite3.connect(file.as_uri() + ("?mode=ro" if readonly else "?mode=rw"),
                             uri=True, timeout=5)
        try:
            if (file.stat().st_dev, file.stat().st_ino) != self._original_file:
                raise ValueError("original attempt store changed while opening")
            kind = db.execute("SELECT type FROM sqlite_master WHERE name=?",
                              ('ex_wallet_execution_attempts',)).fetchone()
            columns = db.execute("PRAGMA table_info(ex_wallet_execution_attempts)").fetchall()
            triggers = db.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' AND tbl_name=?",
                                  ('ex_wallet_execution_attempts',)).fetchone()
            if (triggers is not None or kind != ('table',) or [(r[1], r[2], r[3], r[5]) for r in columns] !=
                    [('operation_key', 'TEXT', 0, 1), ('request_digest', 'TEXT', 1, 0)]):
                raise ValueError("original attempt schema unavailable; no initialization")
            return db
        except BaseException:
            db.close()
            raise

    def claim(self, binding, request):
        # Include the original actor/server/chain/task/operation identity. Budget
        # revision changes or a changed child must never create another send slot.
        identity = {key: binding[key] for key in ("origin", "tenant", "account", "chainId")}
        identity.update(taskDigest=request["taskDigest"], operationId=request["operationId"])
        encode = lambda row: json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        key = hashlib.sha256(encode(identity)).hexdigest()
        digest = hashlib.sha256(encode(request)).hexdigest()
        db = (self._connect_existing() if hasattr(self, '_original_file')
              else sqlite3.connect(self.path, timeout=5))
        try:
            with db:
                return self._claim(db, key, digest)
        finally:
            db.close()

    @staticmethod
    def _claim(db, key, digest):
        db.execute("PRAGMA synchronous=FULL")
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT request_digest FROM ex_wallet_execution_attempts WHERE operation_key=?", (key,)).fetchone()
        if existing is not None:
            return False
        db.execute("INSERT INTO ex_wallet_execution_attempts VALUES (?, ?)", (key, digest))
        stored = db.execute("SELECT request_digest FROM ex_wallet_execution_attempts WHERE operation_key=?", (key,)).fetchone()
        if stored != (digest,):
            raise ValueError("original attempt barrier was not retained")
        # The caller commits the context before returning this result.
        return True
