"""Bounded discovery of persisted UNKNOWN operations for original enquiry.

No admission, wallet session, fee reservation or execution callback is accepted.
This is an internal application port; callers must authenticate their reader.
"""
import re

from .durable_operation import DurableEXOperationJournal, DurableOperationRefused


def enquire_pending_operations(journal, enquire_original, *, after=None, limit=50):
    """Read one page of persisted claims, then enquire their original identities.

    The cursor is an operation identifier, not authorization or a permanent
    watermark. Start subsequent sweeps from the beginning: new identifiers may
    sort before a previous cursor. This function never marks outcomes terminal.
    A concurrently reconciled claim is omitted from enquiry. Native failures
    are isolated per operation; storage/binding failures refuse the whole page.
    """
    if (not isinstance(journal, DurableEXOperationJournal)
            or not callable(enquire_original)
            or type(limit) is not int or not 1 <= limit <= 100
            or (after is not None and
                (type(after) is not str or
                 not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", after)))):
        raise DurableOperationRefused("Bounded original-operation recovery reader required")
    if journal.connection.in_transaction:
        raise DurableOperationRefused("Do not read through another owner's transaction")
    # Fetch one additional identifier to report continuation without requiring
    # a count or unbounded materialization. This reader issues only SELECTs;
    # its trusted original enquiry binding must remain read-only as well.
    rows = journal.connection.execute(
        "SELECT native_operation_id,receipt_id FROM ex_operation_claims "
        "WHERE status='UNKNOWN' AND native_operation_id>? "
        "ORDER BY native_operation_id LIMIT ?", (after or "", limit + 1)).fetchall()
    selected = rows[:limit]
    claims = []
    for operation_id, receipt_id in selected:
        claim = journal.lookup(operation_id)
        if claim is None or claim["scope"]["receiptId"] != receipt_id:
            raise DurableOperationRefused("Stored recovery index conflicts with operation binding")
        if claim["status"] == "UNKNOWN":
            claims.append(claim)
    results = []
    for claim in claims:
        scope = claim["scope"]
        try:
            observation = journal.observe(scope, enquire_original)
        except DurableOperationRefused:
            # Local identity corruption/conflict is not a native outage.
            raise
        except Exception:
            results.append({"nativeOperationId": scope["nativeOperationId"],
                            "status": "ORIGINAL_ENQUIRY_UNAVAILABLE",
                            "nativeGateInvoked": False, "replayAllowed": False})
        else:
            results.append({"nativeOperationId": scope["nativeOperationId"],
                            "status": "ORIGINAL_ENQUIRY_RETURNED",
                            "observation": observation,
                            "nativeGateInvoked": False, "replayAllowed": False})
    return {"operations": results,
            "nextCursor": selected[-1][0] if len(rows) > limit else None,
            "newSweepsStartAtBeginning": True,
            "nativeGateInvoked": False, "replayAllowed": False}
