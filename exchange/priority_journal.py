"""Durable server admission order, separate from wallet/financial journals."""
from copy import deepcopy
import json
import re
import sqlite3

from .model import TradeIntent


class PriorityPersistenceRefused(ValueError):
    pass


class PriorityCommitUnknown(RuntimeError):
    pass


def _scope(value):
    if (type(value) is not dict or set(value) !=
            {"receiptId", "chainId", "contract", "tokenId", "currency", "generation"}
            or any(type(value[k]) is not str or
                   not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value[k])
                   for k in ("receiptId", "currency"))
            or type(value["chainId"]) is not int or value["chainId"] != 11155111
            or type(value["contract"]) is not str
            or not re.fullmatch(r"0x[0-9a-f]{40}", value["contract"])
            or value["contract"] == "0x" + "0" * 40
            or type(value["tokenId"]) is not str
            or not re.fullmatch(r"0|[1-9][0-9]{0,77}", value["tokenId"])
            or int(value["tokenId"]) >= 2 ** 256
            or type(value["generation"]) is not int
            or not 0 <= value["generation"] < 2 ** 63 - 1):
        raise PriorityPersistenceRefused("Exact original book scope required")
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _storage(connection):
    if not isinstance(connection, sqlite3.Connection) or connection.in_transaction:
        raise PriorityPersistenceRefused("Clean dedicated SQLite connection required")
    if (not any(row[1] == "main" and row[2] for row in connection.execute("PRAGMA database_list"))
            or connection.execute("PRAGMA synchronous").fetchone()[0] not in (2, 3)
            or connection.execute("PRAGMA journal_mode").fetchone()[0].lower()
                not in ("delete", "truncate", "persist", "wal")):
        raise PriorityPersistenceRefused("Durable file-backed FULL/EXTRA journal required")


class DurablePriorityStore:
    def __init__(self, connection):
        _storage(connection)
        self.connection = connection

    @staticmethod
    def initialize(connection):
        _storage(connection)
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("CREATE TABLE ex_priority_entries (book_scope TEXT NOT NULL, "
                "intent_id TEXT NOT NULL,intent_digest TEXT NOT NULL,signer TEXT NOT NULL,"
                "nonce TEXT NOT NULL,sequence INTEGER NOT NULL,"
                "PRIMARY KEY(book_scope,intent_id),UNIQUE(book_scope,sequence),"
                "UNIQUE(book_scope,signer,nonce))")
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def _read(self, encoded):
        rows = self.connection.execute("SELECT intent_id,intent_digest,signer,nonce,sequence "
            "FROM ex_priority_entries WHERE book_scope=? ORDER BY sequence", (encoded,)).fetchall()
        result = []
        for expected, (intent_id, digest, signer, nonce, sequence) in enumerate(rows, 1):
            if (type(sequence) is not int or sequence != expected
                    or type(intent_id) is not str
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", intent_id)
                    or type(digest) is not str or not re.fullmatch(r"0x[0-9a-f]{64}", digest)
                    or type(signer) is not str or not re.fullmatch(r"0x[0-9a-f]{40}", signer)
                    or type(nonce) is not str or not re.fullmatch(r"0|[1-9][0-9]*", nonce)):
                raise PriorityPersistenceRefused("Stored admission order is inconsistent")
            result.append({"intentId": intent_id, "intentDigest": digest, "signer": signer,
                           "nonce": nonce, "sequence": sequence})
        return result

    def read(self, scope):
        encoded = _scope(scope)
        if self.connection.in_transaction:
            raise PriorityPersistenceRefused("Do not read through another owner's transaction")
        return deepcopy(self._read(encoded))

    def admit(self, scope, intent):
        scope = deepcopy(scope)
        encoded = _scope(scope)
        if (not isinstance(intent, TradeIntent) or intent.counterparty is not None
                or (intent.asset.chain_id, intent.asset.contract, str(intent.asset.token_id), intent.quote_asset)
                   != (scope["chainId"], scope["contract"], scope["tokenId"], scope["currency"])):
            raise PriorityPersistenceRefused("Order differs from original book scope")
        _storage(self.connection)
        c = self.connection
        c.execute("BEGIN IMMEDIATE")
        try:
            rows = self._read(encoded)
            for row in rows:
                if row["intentId"] == intent.intent_id:
                    if (row["intentDigest"], row["signer"], row["nonce"]) != (intent.digest, intent.signer, str(intent.nonce)):
                        raise PriorityPersistenceRefused("Original admitted order identity conflict")
                    c.rollback()
                    return row["sequence"]
                if (row["signer"], row["nonce"]) == (intent.signer, str(intent.nonce)):
                    raise PriorityPersistenceRefused("Nonce already belongs to another admitted order")
            sequence = len(rows) + 1
            c.execute("INSERT INTO ex_priority_entries VALUES (?,?,?,?,?,?)",
                      (encoded, intent.intent_id, intent.digest, intent.signer, str(intent.nonce), sequence))
            try:
                c.commit()
            except Exception:
                raise PriorityCommitUnknown("Admission commit unknown; read same original order") from None
            return sequence
        finally:
            if c.in_transaction:
                c.rollback()
