"""Pass one original editor pair through the existing checkpointed remint gate."""
from .checkpointed_operation import CheckpointedOperationBridge, CheckpointedOperationRefused
from .checkpointed_remint import invoke_checkpointed_remint
from .remint_draft_workbench import RemintDraftEditorBinding


def invoke_draft_remint(bridge, editor, binding, expected_revision,
                       verify_declaration, resolve_original_bill_link,
                       enquire_original, execute_original, *, history_store,
                       draft_options=None):
    """Original application composition only; no HTTP or signing authority.

    binding is the original operation scope for the exact reviewed history.
    Changed terms must satisfy that same original digest, declaration verifier,
    bill resolver and durable journal. No operation identity is allocated here.
    """
    if (type(bridge) is not CheckpointedOperationBridge
            or type(editor) is not RemintDraftEditorBinding
            or editor.access is not bridge.access
            or type(binding) is not dict
            or binding.get("receiptId") != editor.receipt_id):
        raise CheckpointedOperationRefused("same original editor, receipt and checkpoint access required")
    if draft_options is not None and type(draft_options) is not dict:
        raise CheckpointedOperationRefused("original typed draft options required")
    with bridge.access._lock:
        old, replacement = editor.draft_specifications(**dict(draft_options or {}))
        return invoke_checkpointed_remint(bridge, binding, expected_revision,
            old, replacement, verify_declaration, resolve_original_bill_link,
            enquire_original, execute_original, history_store=history_store)
