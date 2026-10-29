"""Join original remint history and a retained EX preimage before its native gate."""
from .checkpointed_operation import CheckpointedOperationBridge, CheckpointedOperationRefused
from .durable_operation import DurableNativeOutcomeUnknown
from .exchange_fact_snapshot import decode_exchange_snapshot
from .remint_execution import invoke_remint


def invoke_checkpointed_remint(bridge, binding, expected_revision, old, replacement,
                              verify_declaration, resolve_original_bill_link,
                              enquire_original, execute_original, *, history_store):
    """Installed composition only; reuse invoke_remint's single original claim.

    Original terms validation, bill binding and durable history save happen in
    invoke_remint. This decorates its checked gateway, without invoking another
    operation journal. All participating EX access must share bridge.access.
    """
    if type(bridge) is not CheckpointedOperationBridge or not callable(execute_original):
        raise CheckpointedOperationRefused("original checkpoint bridge and checked remint gateway required")
    saved = None
    snapshot_error = None

    def checkpoint_then_execute(scope, history):
        nonlocal saved, snapshot_error
        try:
            raw = bridge.access.snapshot_bytes()
            facts = decode_exchange_snapshot(raw)
            receipt = facts.receipts.get(scope["receiptId"])
            # invoke_remint binds scope to the old declaration. Also bind that
            # same identity to the captured live EX, not merely caller terms.
            if (receipt is None or receipt.asset != old.receipt.asset
                    or receipt != old.receipt):
                raise CheckpointedOperationRefused("captured original receipt differs from remint declaration")
            saved = bridge.checkpoint.save(bridge.pre_effect_scope(scope), raw,
                                            expected_generation=0)
        except Exception as error:
            snapshot_error = error
            raise
        return execute_original(scope, history)

    with bridge.access._lock:
        if bridge.access.asset_lifecycle(old.receipt.receipt_id)["state"] != "ACTIVE":
            raise CheckpointedOperationRefused("pending or retired original generation cannot remint")
        try:
            result = invoke_remint(bridge.journal, binding, expected_revision,
                old, replacement, verify_declaration, resolve_original_bill_link,
                enquire_original, checkpoint_then_execute, history_store=history_store)
        except DurableNativeOutcomeUnknown:
            if snapshot_error is not None:
                # Preserve precise pre-effect refusal/commit uncertainty. The
                # original claim and saved history remain UNKNOWN evidence.
                raise snapshot_error from None
            raise
    return dict(result, preEffectCheckpoint=saved, executionAuthorized=False,
                completeRecovery=False)
