"""Mount original-operation enquiry on the same recovered workbench instance."""
from dataclasses import dataclass

from .checkpointed_operation import CheckpointedOperationBridge
from .checkpointed_operation_page import (CheckpointedOperationObservationBinding,
                                          mount_checkpointed_operation_observation)
from .recovered_remint_action import compose_recovered_remint_action


@dataclass(frozen=True)
class OriginalOperationObservationInputs:
    """Installed original stores and enquiry; no HTTP-selected operation scope."""
    journal: object
    binding: dict
    enquire_original: object
    remint_history: object = None


def compose_recovered_operation_observation(checkpoint, scope, runtime, receipt_id, *,
        operation_observation_inputs=None, **original_options):
    """Restore once and compose lazy enquiry without requiring current drafts.

    Original remint action/editor options remain independently optional. This
    constructor never enquires, claims, saves, reconciles or executes an operation.
    Stores and native ports remain owned by the original application.
    """
    if operation_observation_inputs is not None and (
            type(operation_observation_inputs) is not OriginalOperationObservationInputs
            or not callable(operation_observation_inputs.enquire_original)):
        raise ValueError("original operation observation inputs required")
    loaded = compose_recovered_remint_action(checkpoint, scope, runtime, receipt_id,
                                             **original_options)
    try:
        observation = None
        if operation_observation_inputs is not None:
            inputs = operation_observation_inputs
            bridge = CheckpointedOperationBridge(loaded.checkpoint.access,
                checkpoint, inputs.journal, loaded.checkpoint.scope)
            observation = CheckpointedOperationObservationBinding(bridge,
                inputs.binding, inputs.enquire_original,
                remint_history=inputs.remint_history)
        mount_checkpointed_operation_observation(loaded.server, observation)
    except BaseException:
        # Own only the newly constructed socket; never close original stores.
        loaded.server.server_close()
        raise
    return loaded
