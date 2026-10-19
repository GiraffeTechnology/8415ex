"""Private aggregate checkpoint bytes; not a domain codec or execution authority."""
import base64
import hashlib
import json
import re
import sqlite3


class CheckpointRefused(ValueError):
    pass


class CheckpointCommitUnknown(RuntimeError):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _identity(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value) is not None


class AggregateCheckpointStore:
    """One SQLite row atomically contains the caller's complete component set.

    No database path is selected or opened. Original codecs must preserve all
    domain facts and UNKNOWN claims. This store neither serializes an Exchange
    nor restores one, reconciles native effects, or dispatches any operation.
    Source identities and SHA256 detect mismatches; they do not authenticate
    source provenance or protect against a writer who controls the database.
    """

    MAX_COMPONENT = 16 * 1024 * 1024
    MAX_TOTAL = 64 * 1024 * 1024
    MAX_ENCODED = 90 * 1024 * 1024

    def __init__(self, connection, *, components, source_commit, source_tree):
        if not isinstance(connection, sqlite3.Connection):
            raise CheckpointRefused("caller-owned SQLite connection required")
        if (type(components) not in (tuple, list) or not components or len(components) > 64
                or any(type(name) is not str or not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", name)
                       for name in components) or len(set(components)) != len(components)
                or not _identity(source_commit) or not _identity(source_tree)):
            raise CheckpointRefused("exact component names and source identities required")
        self.connection = connection
        self.components = tuple(sorted(components))
        self.source = {"commit": source_commit, "tree": source_tree}
        self._boundary()

    @staticmethod
    def initialize(connection):
        # Explicit new schema only, never silently migrate or replace old state.
        if not isinstance(connection, sqlite3.Connection) or connection.in_transaction:
            raise CheckpointRefused("clean caller-owned connection required")
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute("CREATE TABLE ex_aggregate_checkpoint ("
                "scope TEXT PRIMARY KEY, generation INTEGER NOT NULL, "
                "payload TEXT NOT NULL, digest TEXT NOT NULL)")
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def _boundary(self):
        db = self.connection
        if db.in_transaction:
            raise CheckpointRefused("another transaction must not be committed")
        if not any(row[1] == "main" and row[2] for row in db.execute("PRAGMA database_list")):
            raise CheckpointRefused("file-backed storage required")
        mode = db.execute("PRAGMA journal_mode").fetchone()[0]
        if str(mode).lower() not in ("delete", "truncate", "persist", "wal"):
            raise CheckpointRefused("persistent rollback journal or WAL required")
        if db.execute("PRAGMA synchronous").fetchone()[0] not in (2, 3):
            raise CheckpointRefused("FULL or EXTRA synchronous mode required")

    @staticmethod
    def _scope(scope):
        if type(scope) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", scope):
            raise CheckpointRefused("exact original aggregate scope required")

    def _encode(self, values):
        if type(values) is not dict or set(values) != set(self.components):
            raise CheckpointRefused("complete exact component set required")
        total, encoded = 0, {}
        for name in self.components:
            raw = values[name]
            if type(raw) is not bytes or len(raw) > self.MAX_COMPONENT:
                raise CheckpointRefused("bounded immutable component bytes required")
            total += len(raw)
            if total > self.MAX_TOTAL:
                raise CheckpointRefused("aggregate byte limit exceeded")
            encoded[name] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                             "base64": base64.b64encode(raw).decode("ascii")}
        return _canonical({"schema": "8415ex-private-aggregate/1", "source": self.source,
                           "components": encoded})

    def _read(self, scope):
        row = self.connection.execute("SELECT generation,payload,digest FROM "
            "ex_aggregate_checkpoint WHERE scope=?", (scope,)).fetchone()
        if row is None:
            return None
        generation, payload, digest = row
        try:
            if (type(generation) is not int or not 1 <= generation < 2 ** 63
                    or type(payload) is not str or len(payload) > self.MAX_ENCODED
                    or hashlib.sha256(payload.encode()).hexdigest() != digest):
                raise ValueError()
            value = json.loads(payload)
            if (set(value) != {"schema", "source", "components"}
                    or value["schema"] != "8415ex-private-aggregate/1"
                    or value["source"] != self.source
                    or type(value["components"]) is not dict
                    or set(value["components"]) != set(self.components)):
                raise ValueError()
            decoded = {}
            for name, item in value["components"].items():
                if type(item) is not dict or set(item) != {"bytes", "sha256", "base64"}:
                    raise ValueError()
                raw = base64.b64decode(item["base64"], validate=True)
                if type(item["bytes"]) is not int or len(raw) != item["bytes"]:
                    raise ValueError()
                if hashlib.sha256(raw).hexdigest() != item["sha256"]:
                    raise ValueError()
                decoded[name] = raw
            if self._encode(decoded) != payload:
                raise ValueError()
        except (ValueError, TypeError, KeyError, OverflowError):
            raise CheckpointRefused("stored aggregate is inconsistent") from None
        return {"scope": scope, "generation": generation, "components": decoded,
                "digest": digest, "executionAuthorized": False}

    def read(self, scope):
        self._scope(scope)
        self._boundary()
        return self._read(scope)

    def save(self, scope, values, *, expected_generation):
        self._scope(scope)
        if type(expected_generation) is not int or not 0 <= expected_generation < 2 ** 63 - 1:
            raise CheckpointRefused("exact bounded previous generation required")
        payload = self._encode(values)
        digest = hashlib.sha256(payload.encode()).hexdigest()
        self._boundary()
        db = self.connection
        db.execute("BEGIN IMMEDIATE")
        try:
            previous = self._read(scope)
            actual = previous["generation"] if previous else 0
            if actual != expected_generation:
                raise CheckpointRefused("stale checkpoint generation")
            generation = actual + 1
            if previous is None:
                db.execute("INSERT INTO ex_aggregate_checkpoint VALUES(?,?,?,?)",
                           (scope, generation, payload, digest))
            else:
                db.execute("UPDATE ex_aggregate_checkpoint SET generation=?,payload=?,digest=? WHERE scope=?",
                           (generation, payload, digest, scope))
        except Exception:
            db.rollback()
            raise
        try:
            db.commit()
        except Exception as error:
            # Do not automatically retry after an uncertain commit or dispatch.
            raise CheckpointCommitUnknown("checkpoint commit outcome unknown; reconcile original store") from error
        return {"scope": scope, "generation": generation, "digest": digest,
                "executionAuthorized": False}
