"""Immutable complete remint history on an explicitly initialized EX store.

This store records prepared non-secret declarations, not economic/chain success.
It neither changes the original native journal nor dispatches anything.
"""
from copy import deepcopy
import json
import sqlite3

from .durable_operation import _scope, _canonical, DurableOperationCommitUnknown
from .remint_terms import _encoded, _hash, RemintTermsRefused


class RemintHistoryStore:
    def __init__(self, connection):
        if not isinstance(connection, sqlite3.Connection) or connection.in_transaction:
            raise RemintTermsRefused("Clean dedicated EX history connection required")
        if not any(row[1] == "main" and row[2] for row in
                   connection.execute("PRAGMA database_list").fetchall()):
            raise RemintTermsRefused("File-backed EX history required")
        if connection.execute("PRAGMA synchronous").fetchone()[0] not in (2, 3):
            raise RemintTermsRefused("FULL or EXTRA history durability required")
        self.connection = connection

    @staticmethod
    def initialize(connection):
        """Explicit fresh schema creation only; never replace an existing table."""
        if not isinstance(connection, sqlite3.Connection) or connection.in_transaction:
            raise RemintTermsRefused("Clean dedicated EX history connection required")
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("CREATE TABLE ex_remint_histories ("
                "operation_id TEXT PRIMARY KEY, scope_json TEXT NOT NULL, "
                "history_json TEXT NOT NULL, history_digest TEXT NOT NULL)")
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise

    def _clean(self):
        if self.connection.in_transaction:
            raise RemintTermsRefused("Do not commit another owner's transaction")

    @staticmethod
    def _bound(scope, history):
        fields = {"schema", "billKey", "billSourceReference", "binding",
                  "oldDeclaration", "newDeclaration", "changes"}
        if (scope["action"] != "remint" or type(history) is not dict
                or set(history) != fields
                or history.get("schema") != "8415ex-remint-terms/1"
                or type(history.get("binding")) is not dict
                or type(history.get("oldDeclaration")) is not dict
                or type(history.get("newDeclaration")) is not dict
                or type(history.get("changes")) is not list
                or _hash(history) != scope["intentDigest"]):
            raise RemintTermsRefused("Exact verified remint history digest required")
        binding = history["binding"]
        required = {"oldAsset", "newAsset", "oldReceiptId", "newReceiptId",
                    "oldDeclarationDigest", "newDeclarationDigest"}
        if set(binding) != required:
            raise RemintTermsRefused("Complete old and replacement declaration binding required")
        for side in ("old", "new"):
            declaration = history[side + "Declaration"]
            receipt = declaration.get("receipt")
            if (declaration.get("schema") != "8415ex-mint-declaration/1"
                    or type(receipt) is not dict
                    or _hash(declaration) != binding[side + "DeclarationDigest"]
                    or _encoded(receipt.get("asset")) != _encoded(binding[side + "Asset"])
                    or receipt.get("receipt_id") != binding[side + "ReceiptId"]):
                raise RemintTermsRefused("Complete declaration differs from original history binding")
        expected = {"chain_id": scope["chainId"], "contract": scope["contract"],
                    "token_id": int(scope["tokenId"])}
        if (_encoded(history["binding"].get("oldAsset")) != _encoded(expected)
                or history["binding"].get("oldReceiptId") != scope["receiptId"]):
            raise RemintTermsRefused("History does not identify the original operation asset")

    def _read(self, scope):
        row = self.connection.execute("SELECT scope_json,history_json,history_digest "
            "FROM ex_remint_histories WHERE operation_id=?",
            (scope["nativeOperationId"],)).fetchone()
        if row is None:
            return None
        if row[0] != _canonical(scope) or row[2] != scope["intentDigest"]:
            raise RemintTermsRefused("Original operation history conflict")
        history = json.loads(row[1])
        self._bound(scope, history)
        if row[1] != _encoded(history):
            raise RemintTermsRefused("Stored history is not its exact canonical declaration")
        return {"history": history, "historyDigest": row[2],
                "businessAcceptance": "NOT_ESTABLISHED", "replayAllowed": False}

    def read(self, binding):
        scope = _scope(binding)
        self._clean()
        return self._read(scope)

    def save(self, binding, history):
        """Persist trusted preparation before an effect; identical retries only.

        Callers must use the original MintSpecification/schema/privacy verifier.
        A digest or this row alone proves neither source authenticity nor success.
        """
        scope = _scope(binding)
        detached = deepcopy(history)
        self._bound(scope, detached)
        self._clean()
        c = self.connection
        c.execute("BEGIN IMMEDIATE")
        try:
            existing = self._read(scope)
            if existing is not None:
                if _encoded(existing["history"]) != _encoded(detached):
                    raise RemintTermsRefused("Immutable original history conflict")
                c.rollback()
                return existing
            c.execute("INSERT INTO ex_remint_histories VALUES (?,?,?,?)",
                      (scope["nativeOperationId"], _canonical(scope),
                       _encoded(detached), scope["intentDigest"]))
            try:
                c.commit()
            except Exception:
                raise DurableOperationCommitUnknown(
                    "History commit unknown; reopen/read original history before execution") from None
            return self._read(scope)
        finally:
            if c.in_transaction:
                c.rollback()
