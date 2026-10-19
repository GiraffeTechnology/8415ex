"""Compose verified remint terms with the existing durable EX operation gate.

The installed original gateway still owns holder/owner, session/grant, ETH gas,
contract execution and its native operation journal. EX owns its declaration
history persistence. No default gateway exists.
"""
from copy import deepcopy
import sqlite3
from .durable_operation import DurableEXOperationJournal
from .remint_terms import prepare_remint_terms, RemintTermsRefused
from .remint_history import RemintHistoryStore


def observe_remint(journal, binding, enquire_original, *, history_store=None):
    """Enquire an original remint without old declaration/schema availability.

    Observation grants no retry, financial release or terminal reconciliation.
    The original source still authenticates the exact requested operation.
    """
    if (not isinstance(journal, DurableEXOperationJournal)
            or type(binding) is not dict or binding.get("action") != "remint"):
        raise RemintTermsRefused("Original durable remint operation binding required")
    if history_store is not None and not isinstance(history_store, RemintHistoryStore):
        raise RemintTermsRefused("Explicit original EX history store required")
    scope = deepcopy(binding)
    observed = journal.observe(scope, enquire_original)
    history_view = {"status": "NOT_CONFIGURED", "record": None}
    if history_store is not None:
        try:
            record = history_store.read(scope)
            history_view = {"status": "FOUND" if record is not None else "ABSENT",
                            "record": record}
        except (RemintTermsRefused, sqlite3.Error, ValueError):
            # A local history fault must not hide the original operation query.
            # Never serve partial/corrupt terms, raw DB errors or infer finality.
            history_view = {"status": "UNAVAILABLE", "record": None}
    return dict(observed, historyView=history_view,
                businessAcceptance="NOT_ESTABLISHED", replayAllowed=False)


def invoke_remint(journal, binding, expected_revision, old, replacement,
                  verify_declaration, resolve_original_bill_link,
                  enquire_original, execute_original, *, history_store):
    """Invoke one original checked gateway, keeping UNKNOWN on lost replies.

    All callbacks are trusted installed application ports, never request-body
    callbacks. EX durably retains the complete history before effect execution;
    the original gateway retains its own native operation journal. A response
    does not establish burn/mint success or authorize local reconciliation.
    """
    if not isinstance(journal, DurableEXOperationJournal):
        raise RemintTermsRefused("Original durable EX operation journal required")
    if not isinstance(history_store, RemintHistoryStore):
        raise RemintTermsRefused("Explicit durable complete remint history store required")
    if not callable(enquire_original) or not callable(execute_original):
        raise RemintTermsRefused("Original enquiry and checked remint gateway required")
    prepared = prepare_remint_terms(old, replacement, verify_declaration,
                                    resolve_original_bill_link)
    scope = deepcopy(binding)
    asset = prepared["history"]["binding"]["oldAsset"]
    required = {"action": "remint", "receiptId": old.receipt.receipt_id,
                "chainId": asset["chain_id"], "contract": asset["contract"],
                "tokenId": str(asset["token_id"]),
                "intentDigest": prepared["historyDigest"]}
    if type(scope) is not dict or any(type(scope.get(key)) is not type(value)
                                     or scope.get(key) != value
                                     for key, value in required.items()):
        raise RemintTermsRefused("Original operation does not bind the exact remint history")

    # DurableEXOperationJournal validates the complete native operation scope,
    # enquires first, and commits UNKNOWN before entering this closure once.
    # Its existing/reconciled paths never call execute_original again.
    def dispatch(checked_scope):
        # Failure or ambiguous commit cannot fall through to the original gate.
        # The durable claim already prevents another effect while recovery reads
        # the exact native operation and this immutable history.
        history_store.save(checked_scope, prepared["history"])
        return execute_original(checked_scope, deepcopy(prepared["history"]))

    observed = journal.invoke_once(scope, expected_revision, enquire_original, dispatch)
    return {"historyDigest": prepared["historyDigest"],
            "operation": observed, "businessAcceptance": "NOT_ESTABLISHED",
            "replayAllowed": False}
