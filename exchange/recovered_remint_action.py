"""Wire an original bound remint action to one recovered workbench instance."""
from dataclasses import dataclass

from .checkpointed_operation import CheckpointedOperationBridge
from .recovered_workbench_ui import compose_recovered_workbench_ui
from .remint_draft_action import RemintDraftActionBinding, mount_remint_draft_action


@dataclass(frozen=True)
class OriginalRemintActionInputs:
    """Existing host configuration, never values supplied by an HTTP form.

    All stores, operation identity and ports already belong to the original
    application. This record creates no journal, operation, grant or default.
    """
    journal: object
    history_store: object
    binding: dict
    expected_revision: int
    verify_declaration: object
    resolve_original_bill_link: object
    enquire_original: object
    execute_original: object
    draft_options: object = None


def compose_recovered_remint_action(checkpoint, scope, runtime, receipt_id, *,
        remint_action_inputs=None, **original_options):
    """Construct before serving, using the exact restored access and editor.

    Missing action configuration affects only this action route. Configured
    actions use the already supplied original declaration reader; configuration
    is not read from HTTP and construction never dispatches the native gate.
    """
    if remint_action_inputs is not None:
        if type(remint_action_inputs) is not OriginalRemintActionInputs:
            raise ValueError("original remint action inputs required")
        if not callable(original_options.get("read_draft_specifications")):
            raise ValueError("original draft reader required for configured action")
    loaded = compose_recovered_workbench_ui(checkpoint, scope, runtime, receipt_id,
                                            **original_options)
    try:
        action = None
        if remint_action_inputs is not None:
            inputs = remint_action_inputs
            bridge = CheckpointedOperationBridge(loaded.checkpoint.access,
                checkpoint, inputs.journal, loaded.checkpoint.scope)
            action = RemintDraftActionBinding(bridge, loaded.server.draft_editor,
                inputs.binding, inputs.expected_revision, inputs.verify_declaration,
                inputs.resolve_original_bill_link, inputs.enquire_original,
                inputs.execute_original, history_store=inputs.history_store,
                draft_options=inputs.draft_options)
        mount_remint_draft_action(loaded.server, action)
    except BaseException:
        # This composition owns only the newly constructed listening socket.
        # Original stores, journal, runtime and gateways remain caller-owned.
        loaded.server.server_close()
        raise
    return loaded
