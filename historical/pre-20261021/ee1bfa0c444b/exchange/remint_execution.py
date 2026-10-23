"""Compose verified remint terms with the existing durable EX operation gate.

The installed original gateway still owns holder/owner, session/grant, ETH gas,
contract execution and original history persistence. No default gateway exists.
"""
from copy import deepcopy
from .durable_operation import DurableEXOperationJournal
from .remint_terms import prepare_remint_terms, RemintTermsRefused


def observe_remint(journal, binding, enquire_original):
    """Enquire an original remint without old declaration/schema availability.

    Observation grants no retry, financial release or terminal reconciliation.
    The original source still authenticates the exact requested operation.
    """
    if (not isinstance(journal, DurableEXOperationJournal)
            or type(binding) is not dict or binding.get("action") != "remint"):
        raise RemintTermsRefused("Original durable remint operation binding required")
    return journal.observe(binding, enquire_original)


def invoke_remint(journal, binding, expected_revision, old, replacement,
                  verify_declaration, resolve_original_bill_link,
                  enquire_original, execute_original):
    """Invoke one original checked gateway, keeping UNKNOWN on lost replies.

    All callbacks are trusted installed application ports, never request-body
    callbacks. The original gateway must durably retain the supplied history
    alongside its native operation before effect execution. A returned response
    does not establish burn/mint success or authorize local reconciliation.
    """
    if not isinstance(journal, DurableEXOperationJournal):
        raise RemintTermsRefused("Original durable EX operation journal required")
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
        return execute_original(checked_scope, deepcopy(prepared["history"]))

    observed = journal.invoke_once(scope, expected_revision, enquire_original, dispatch)
    return {"historyDigest": prepared["historyDigest"],
            "operation": observed, "businessAcceptance": "NOT_ESTABLISHED",
            "replayAllowed": False}
