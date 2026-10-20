"""Connect original command ports after exactly one EX checkpoint load."""
from .checkpointed_operation import CheckpointedOperationBridge
from .checkpointed_workbench_gateway import CheckpointedWorkbenchGateway
from .durable_operation import DurableEXOperationJournal
from .recovered_workbench_ui import compose_recovered_workbench_ui


def compose_checkpointed_command_workbench(checkpoint, scope, runtime, receipt_id, *,
        operation_journal, make_original_ports, **original_ui_options):
    """Construct without serving, creating schema, executing or saving state.

    The trusted application's port builder receives the actual loaded access
    and existing primary gateway. It must bind original callbacks to that access,
    rather than capture an old in-memory EX or load a second checkpoint copy.
    That builder constructs callbacks without enquiring or executing effects.
    Missing native parameters are never selected by this composition.
    """
    if not isinstance(operation_journal, DurableEXOperationJournal) or not callable(make_original_ports):
        raise ValueError("original operation journal and application port builder required")
    loaded = compose_recovered_workbench_ui(checkpoint, scope, runtime, receipt_id,
                                           **original_ui_options)
    server = loaded.server
    try:
        original_gateway = server.binding.gateway
        ports = make_original_ports(loaded.checkpoint.access, original_gateway)
        required = {"resolve_command", "enquire_original", "execute_original"}
        if (type(ports) is not dict or not required <= set(ports)
                or set(ports) - required - {"fallback_gateway"}):
            raise ValueError("exact original command ports required")
        bridge = CheckpointedOperationBridge(loaded.checkpoint.access, checkpoint,
                                             operation_journal, scope)
        gateway = CheckpointedWorkbenchGateway(bridge,
            resolve_command=ports["resolve_command"], enquire_original=ports["enquire_original"],
            execute_original=ports["execute_original"],
            fallback_gateway=ports.get("fallback_gateway", original_gateway))
        # Only the primary command surface is selected here. Detail readers
        # retain their original individual gateways and the same loaded access.
        server.binding.gateway = gateway
    except Exception:
        server.server_close()
        raise
    return loaded
