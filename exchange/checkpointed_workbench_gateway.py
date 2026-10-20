"""Bind original workbench commands to original durable native operations."""
from copy import deepcopy
import hashlib
import json
import re

from .checkpointed_operation import CheckpointedOperationBridge
from .durable_operation import DurableEXOperationJournal, _scope
from .public_workbench import command_result
from .workbench import ACTIONS


class WorkbenchGatewayRefused(ValueError):
    pass


class WorkbenchBindingCommitUnknown(OSError):
    pass


NATIVE_ACTIONS = {"reconcile-payment": ("release", "refund"),
                  "resume-payment": ("release", "refund"),
                  "advance-rollback": ("refund", "rollback")}


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class CheckpointedWorkbenchGateway:
    """Trusted application composition, never an HTTP-selected native mapping.

    The original resolver supplies an actual scope for a new command. Existing
    correlations recover without that resolver or mint declarations. Original
    native enquiry must raise for an unavailable result; only authenticated
    absence is None. The original execution callback retains all authority,
    funds, ETH, nonce and atomic domain checks. This class grants none of them.
    """
    @staticmethod
    def initialize(journal):
        if not isinstance(journal, DurableEXOperationJournal):
            raise WorkbenchGatewayRefused("original operation journal required")
        journal._durable_write_boundary()
        connection = journal.connection
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("CREATE TABLE ex_workbench_command_bindings ("
                "instance_scope TEXT NOT NULL, journal_key TEXT NOT NULL, receipt_id TEXT NOT NULL, "
                "ui_action TEXT NOT NULL, payload_digest TEXT NOT NULL, scope_json TEXT NOT NULL, "
                "scope_digest TEXT NOT NULL, PRIMARY KEY(instance_scope,journal_key))")
            connection.commit()
        except Exception:
            if connection.in_transaction:
                connection.rollback()
            raise

    def __init__(self, bridge, *, resolve_command, enquire_original, execute_original,
                 fallback_gateway=None):
        if (not isinstance(bridge, CheckpointedOperationBridge)
                or any(not callable(port) for port in
                       (resolve_command, enquire_original, execute_original))):
            raise WorkbenchGatewayRefused("original bridge and installed application ports required")
        if fallback_gateway is not None and any(not callable(getattr(fallback_gateway, name, None))
                                                for name in ("enquire", "dispatch")):
            raise WorkbenchGatewayRefused("original fallback gateway required when supplied")
        self.bridge = bridge
        self.resolve_command = resolve_command
        self.enquire_original = enquire_original
        self.execute_original = execute_original
        self.fallback_gateway = fallback_gateway
        self.connection = bridge.journal.connection
        bridge.journal._clean()
        # Initialization is explicit host schema work, never an import-time or
        # constructor migration or an inferred production database path.
        self.connection.execute("SELECT instance_scope,journal_key,receipt_id,ui_action,"
            "payload_digest,scope_json,scope_digest FROM ex_workbench_command_bindings LIMIT 0")

    @staticmethod
    def _context(key, context):
        if (type(context) is not dict or context.get("journalKey") != key
                or type(key) is not str or not re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", key)
                or type(context.get("action")) is not str or context.get("action") not in ACTIONS
                or type(context.get("receiptId")) is not str or not context["receiptId"]
                or type(context.get("payloadDigest")) is not str
                or not re.fullmatch(r"[0-9a-f]{64}", context["payloadDigest"])):
            raise WorkbenchGatewayRefused("original workbench command context required")
        return context["action"]

    def _lookup(self, context, *, in_write=False):
        if not in_write:
            self.bridge.journal._clean()
        row = self.connection.execute("SELECT receipt_id,ui_action,payload_digest,scope_json,scope_digest "
            "FROM ex_workbench_command_bindings WHERE instance_scope=? AND journal_key=?",
            (self.bridge.checkpoint_scope, context["journalKey"])).fetchone()
        if row is None:
            return None
        try:
            scope = _scope(json.loads(row[3]))
            encoded = _json(scope)
        except Exception:
            raise WorkbenchGatewayRefused("stored command binding is inconsistent") from None
        if (tuple(row[:3]) != (context["receiptId"], context["action"], context["payloadDigest"])
                or row[3] != encoded or row[4] != hashlib.sha256(encoded.encode()).hexdigest()
                or scope["receiptId"] != row[0]
                or scope["action"] not in NATIVE_ACTIONS.get(row[1], ())):
            raise WorkbenchGatewayRefused("original command identity conflict")
        return scope

    def _bind(self, context, scope):
        self.bridge.journal._durable_write_boundary()
        connection = self.connection
        try:
            connection.execute("BEGIN IMMEDIATE")
            existing = self._lookup(context, in_write=True)
            if existing is not None:
                if existing != scope:
                    raise WorkbenchGatewayRefused("original native scope changed")
                connection.rollback()
                return existing
            encoded = _json(scope)
            connection.execute("INSERT INTO ex_workbench_command_bindings VALUES (?,?,?,?,?,?,?)",
                (self.bridge.checkpoint_scope, context["journalKey"], context["receiptId"],
                 context["action"], context["payloadDigest"], encoded,
                 hashlib.sha256(encoded.encode()).hexdigest()))
            try:
                connection.commit()
            except Exception:
                raise WorkbenchBindingCommitUnknown("Original command binding commit unknown") from None
            return scope
        finally:
            if connection.in_transaction:
                connection.rollback()

    def _fallback(self):
        if self.fallback_gateway is None:
            raise WorkbenchGatewayRefused("original gateway for this action is not configured")
        return self.fallback_gateway

    def enquire(self, key, context):
        action = self._context(key, context)
        if action not in NATIVE_ACTIONS:
            return self._fallback().enquire(key, deepcopy(context))
        with self.bridge.access._lock:
            scope = self._lookup(context)
            if scope is None:
                return None
            result = self.bridge.journal.observe(scope, self.enquire_original)
            if result["localClaim"] is None and result["nativeObservation"] is None:
                # A crash between correlation commit and claim is pre-effect.
                # The same request may continue through original invoke_once;
                # no previous native dispatch was authorized by this mapping.
                return None
            return command_result(result["nativeObservation"])

    def dispatch(self, action, payload, context):
        selected = self._context(context.get("journalKey") if type(context) is dict else None, context)
        if (action != selected or type(payload) is not dict
                or hashlib.sha256(_json(payload).encode()).hexdigest() != context["payloadDigest"]):
            raise WorkbenchGatewayRefused("original command payload conflict")
        if action not in NATIVE_ACTIONS:
            return self._fallback().dispatch(action, deepcopy(payload), deepcopy(context))
        with self.bridge.access._lock:
            scope = self._lookup(context)
            if scope is None:
                scope = _scope(self.resolve_command(action, deepcopy(payload), deepcopy(context)))
                if (scope["receiptId"] != context["receiptId"]
                        or scope["action"] not in NATIVE_ACTIONS[action]):
                    raise WorkbenchGatewayRefused("original native command mapping conflicts")
                scope = self._bind(context, scope)
            result = self.bridge.invoke(scope,
                expected_operation_revision=self.bridge.journal.revision(scope["receiptId"]),
                enquire_original=self.enquire_original,
                execute_original=self.execute_original)
            return command_result(result["operation"]["nativeObservation"])
