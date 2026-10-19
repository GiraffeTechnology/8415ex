"""Read original operation outcomes alongside retained EX preimage availability."""
from .checkpointed_operation import CheckpointedOperationBridge, CheckpointedOperationRefused
from .durable_operation import _scope as original_operation_scope
from .remint_execution import observe_remint


def observe_checkpointed_operation(bridge, binding, enquire_original, *, remint_history=None):
    """Private installed reader port, with no claim, save, replay or reconciliation.

    Native enquiry runs first. A missing or unreadable historical snapshot must
    not suppress that query. Current live EX schema, sessions and replacement
    declarations are not consulted. This does not mount a public HTTP endpoint.
    """
    if type(bridge) is not CheckpointedOperationBridge:
        raise CheckpointedOperationRefused("original checkpoint bridge required")
    scope = original_operation_scope(binding)
    if scope["action"] == "remint":
        original = observe_remint(bridge.journal, scope, enquire_original,
                                  history_store=remint_history)
    else:
        if remint_history is not None:
            raise CheckpointedOperationRefused("remint history belongs to remint observations only")
        original = bridge.journal.observe(scope, enquire_original)
    view = {"status": "ABSENT", "generation": None, "digest": None}
    try:
        saved = bridge.checkpoint.read(bridge.pre_effect_scope(scope))
        if saved is not None:
            receipt = saved["facts"].receipts.get(scope["receiptId"])
            if (receipt is None or receipt.asset.chain_id != scope["chainId"]
                    or receipt.asset.contract != scope["contract"]
                    or str(receipt.asset.token_id) != scope["tokenId"]):
                raise CheckpointedOperationRefused("retained preimage asset differs from original operation")
            # Expose availability metadata only. Full snapshots include private
            # authorization/session facts and do not belong in this summary.
            view = {"status": "FOUND", "generation": saved["generation"],
                    "digest": saved["digest"]}
    except Exception:
        # Keep native observation and UNKNOWN evidence. Never expose the raw
        # storage error, return partial decoded facts, or try to repair here.
        view = {"status": "UNAVAILABLE", "generation": None, "digest": None}
    return {"operation": original, "preEffectCheckpointView": view,
            "checkpointMeaning": "retained EX facts before the native gate, not its outcome",
            "crossStoreAtomicity": False, "executionAuthorized": False,
            "completeRecovery": False, "nativeGateInvoked": False, "replayAllowed": False}
