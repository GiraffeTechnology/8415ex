"""EX operation claims across process restarts; never a financial writer.

The original native journal remains authoritative for effects and reconciliation.
Only non-secret identities/digests are stored. No database is opened on import.
"""
from copy import deepcopy
import hashlib
import json
import re
import sqlite3


class DurableOperationRefused(ValueError):
    pass


class DurableOperationCommitUnknown(RuntimeError):
    pass


class DurableNativeOutcomeUnknown(RuntimeError):
    pass


_FIELDS = {"receiptId", "chainId", "contract", "tokenId", "globalLegId",
           "action", "nativeOperationId", "intentDigest", "journalReference"}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _scope(value):
    if type(value) is not dict or set(value) != _FIELDS:
        raise DurableOperationRefused("Exact non-secret operation binding required")
    result = deepcopy(value)
    for field in ("receiptId", "nativeOperationId", "journalReference"):
        if type(result[field]) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", result[field]):
            raise DurableOperationRefused("Invalid operation identity")
    if (type(result["chainId"]) is not int or result["chainId"] != 11155111
            or type(result["contract"]) is not str
            or not re.fullmatch(r"0x[0-9a-f]{40}", result["contract"])
            or result["contract"] == "0x" + "0" * 40
            or type(result["tokenId"]) is not str
            or not re.fullmatch(r"0|[1-9][0-9]{0,77}", result["tokenId"])
            or int(result["tokenId"]) >= 2 ** 256
            or type(result["globalLegId"]) is not int or result["globalLegId"] < 0
            or result["action"] not in ("trade", "release", "refund", "rollback", "remint")
            or type(result["intentDigest"]) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", result["intentDigest"])):
        raise DurableOperationRefused("Invalid original EX scope")
    return result


class DurableEXOperationJournal:
    """Use a dedicated caller-owned durable SQLite connection, synchronous FULL.

    A claim advances the local EX receipt revision and persists UNKNOWN before
    the caller can enter its ORIGINAL native execution gate. This local CAS is
    not the Oracle/native atomic read-and-act condition and grants no authority.
    Reopening this journal never dispatches or automatically retries anything.
    """
    def __init__(self, connection):
        if not isinstance(connection, sqlite3.Connection):
            raise DurableOperationRefused("Explicit dedicated SQLite connection required")
        self.connection = connection
        self._clean()
        databases = connection.execute("PRAGMA database_list").fetchall()
        if not any(row[1] == "main" and row[2] for row in databases):
            raise DurableOperationRefused("A memory database is not restart persistence")
        if connection.execute("PRAGMA synchronous").fetchone()[0] not in (2, 3):
            raise DurableOperationRefused("Existing store must use FULL or EXTRA synchronous mode")

    @staticmethod
    def initialize(connection):
        if not isinstance(connection, sqlite3.Connection) or connection.in_transaction:
            raise DurableOperationRefused("Clean dedicated connection required")
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("CREATE TABLE ex_operation_receipt_heads ("
                               "receipt_id TEXT PRIMARY KEY, revision INTEGER NOT NULL)")
            connection.execute("CREATE TABLE ex_operation_claims ("
                               "native_operation_id TEXT PRIMARY KEY, receipt_id TEXT NOT NULL, "
                               "scope_json TEXT NOT NULL, scope_digest TEXT NOT NULL, "
                               "claimed_revision INTEGER NOT NULL, status TEXT NOT NULL, "
                               "proof_reference TEXT, outcome TEXT)")
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def _clean(self):
        if self.connection.in_transaction:
            raise DurableOperationRefused("Do not commit another owner's transaction")

    def _lookup(self, operation_id):
        row = self.connection.execute("SELECT scope_json,scope_digest,claimed_revision,status,"
            "proof_reference,outcome FROM ex_operation_claims WHERE native_operation_id=?",
            (operation_id,)).fetchone()
        if row is None:
            return None
        scope = _scope(json.loads(row[0]))
        encoded = _canonical(scope)
        if (row[0] != encoded or row[1] != hashlib.sha256(encoded.encode()).hexdigest()
                or scope["nativeOperationId"] != operation_id
                or type(row[2]) is not int or row[2] < 1
                or row[3] not in ("UNKNOWN", "RECONCILED")
                or (row[3] == "UNKNOWN" and (row[4] is not None or row[5] is not None))
                or (row[3] == "RECONCILED" and
                    (type(row[4]) is not str or row[5] not in ("applied", "not-applied")))):
            raise DurableOperationRefused("Stored operation binding is inconsistent")
        return {"scope": scope, "scopeDigest": row[1], "claimedRevision": row[2],
                "status": row[3], "proofReference": row[4], "outcome": row[5],
                "dispatchAuthorized": False, "replayAllowed": False}

    def lookup(self, operation_id):
        self._clean()
        return self._lookup(operation_id)

    def revision(self, receipt_id):
        self._clean()
        row = self.connection.execute("SELECT revision FROM ex_operation_receipt_heads "
                                      "WHERE receipt_id=?", (receipt_id,)).fetchone()
        return row[0] if row else 0

    def claim(self, binding, expected_revision):
        scope = _scope(binding)
        if type(expected_revision) is not int or not 0 <= expected_revision < 2 ** 63 - 1:
            raise DurableOperationRefused("Exact bounded EX revision required")
        self._clean()
        c = self.connection
        c.execute("BEGIN IMMEDIATE")
        committed = False
        try:
            previous = self._lookup(scope["nativeOperationId"])
            if previous is not None:
                if previous["scope"] != scope:
                    raise DurableOperationRefused("Original operation identity conflict")
                c.rollback()
                return dict(previous, disposition="EXISTING_RECONCILE_ONLY")
            c.execute("INSERT OR IGNORE INTO ex_operation_receipt_heads VALUES (?,0)",
                      (scope["receiptId"],))
            updated = c.execute("UPDATE ex_operation_receipt_heads SET revision=revision+1 "
                                "WHERE receipt_id=? AND revision=?",
                                (scope["receiptId"], expected_revision))
            if updated.rowcount != 1:
                raise DurableOperationRefused("EX receipt revision changed; reread authority")
            encoded = _canonical(scope)
            c.execute("INSERT INTO ex_operation_claims VALUES (?,?,?,?,?,?,NULL,NULL)",
                      (scope["nativeOperationId"], scope["receiptId"], encoded,
                       hashlib.sha256(encoded.encode()).hexdigest(), expected_revision + 1, "UNKNOWN"))
            # A commit exception never permits the caller to dispatch. Reopen
            # and look up the SAME original native operation before proceeding.
            try:
                c.commit()
                committed = True
            except Exception:
                raise DurableOperationCommitUnknown("Claim commit outcome unknown; lookup original operation") from None
            return dict(self._lookup(scope["nativeOperationId"]), disposition="NEW_DURABLE_CLAIM")
        finally:
            if not committed and c.in_transaction:
                c.rollback()

    def observe(self, binding, enquire_original):
        """Read the same original operation without claiming or executing.

        Recovery must remain available when old mint declarations have become
        unavailable after a burn. It needs the original operation identity,
        not another admission, grant, declaration or fee reservation.
        """
        scope = _scope(binding)
        if not callable(enquire_original):
            raise DurableOperationRefused("Original operation enquiry required")
        existing = self.lookup(scope["nativeOperationId"])
        if existing is not None and existing["scope"] != scope:
            raise DurableOperationRefused("Original operation identity conflict")
        observed = enquire_original(deepcopy(scope))
        return {"disposition": "READ_ONLY_ORIGINAL_ENQUIRY",
                "localClaim": existing, "nativeObservation": observed,
                "nativeGateInvoked": False, "replayAllowed": False}

    def invoke_once(self, binding, expected_revision, enquire_original, dispatch_original):
        """Enter only an already installed ORIGINAL checked native gateway.

        These callbacks are trust-bound application ports, never user-provided
        HTTP form values. Native source membership, authorization, fees, funds,
        nonce and atomic read-and-act remain that gateway's responsibility.
        No lookup error or unknown commit can fall through to a dispatch.
        """
        scope = _scope(binding)
        if not callable(enquire_original) or not callable(dispatch_original):
            raise DurableOperationRefused("Original enquiry and checked execution gateway required")
        existing = self.lookup(scope["nativeOperationId"])
        if existing is not None:
            if existing["scope"] != scope:
                raise DurableOperationRefused("Original operation identity conflict")
            observed = enquire_original(deepcopy(scope))
            return {"disposition": "EXISTING_RECONCILE_ONLY", "nativeObservation": observed,
                    "nativeGateInvoked": False, "replayAllowed": False}
        # Inspect the original journal before creating a local operation. None
        # must mean authenticated absence; a timeout/refusal must raise instead.
        observed = enquire_original(deepcopy(scope))
        claimed = self.claim(scope, expected_revision)
        if observed is not None or claimed["disposition"] != "NEW_DURABLE_CLAIM":
            if observed is None:
                observed = enquire_original(deepcopy(scope))
            return {"disposition": "EXISTING_RECONCILE_ONLY", "nativeObservation": observed,
                    "nativeGateInvoked": False, "replayAllowed": False}
        try:
            result = dispatch_original(deepcopy(scope))
        except Exception:
            # Keep UNKNOWN. There is no automatic recovery, resend, refund or
            # extra fee. Reopen and enquire this exact original operation.
            raise DurableNativeOutcomeUnknown("Original native outcome unknown; enquire same operation") from None
        # HTTP success is not authenticated economic/finality proof. The local
        # row stays UNKNOWN until explicit original-proof reconciliation.
        return {"disposition": "ORIGINAL_GATE_RETURNED", "nativeObservation": result,
                "nativeGateInvoked": True, "replayAllowed": False}

    def reconcile(self, binding, outcome, proof_reference, verify_original):
        scope = _scope(binding)
        if (outcome not in ("applied", "not-applied") or not callable(verify_original)
                or type(proof_reference) is not str
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", proof_reference)):
            raise DurableOperationRefused("Original authoritative reconciliation proof required")
        self._clean()
        c = self.connection
        c.execute("BEGIN IMMEDIATE")
        try:
            existing = self._lookup(scope["nativeOperationId"])
            if existing is None or existing["scope"] != scope:
                raise DurableOperationRefused("No matching original claim")
            if verify_original(deepcopy(scope), outcome, proof_reference) is not True:
                raise DurableOperationRefused("Original native outcome unverified")
            if existing["status"] == "RECONCILED":
                if (existing["outcome"], existing["proofReference"]) != (outcome, proof_reference):
                    raise DurableOperationRefused("Conflicting terminal reconciliation")
                c.rollback()
                return existing
            c.execute("UPDATE ex_operation_claims SET status=?,proof_reference=?,outcome=? "
                      "WHERE native_operation_id=? AND status=?",
                      ("RECONCILED", proof_reference, outcome, scope["nativeOperationId"], "UNKNOWN"))
            try:
                c.commit()
            except Exception:
                raise DurableOperationCommitUnknown("Reconciliation commit unknown; lookup original operation") from None
            return self._lookup(scope["nativeOperationId"])
        finally:
            if c.in_transaction:
                c.rollback()
