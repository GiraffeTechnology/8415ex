"""Compose existing optional UI routes on one checkpoint-loaded workbench."""
from .checkpoint_workbench_composition import compose_checkpoint_workbench
from .collateral_workbench import mount_collateral_selection
from .market_scenario_workbench import mount_market_scenarios
from .remint_draft_workbench import RemintDraftEditorBinding, mount_remint_draft


def compose_recovered_workbench_ui(checkpoint, scope, runtime, receipt_id, *,
        read_draft_specifications=None, collateral_selection=False,
        scenario_selection=False, **original_options):
    """Construct without serving, executing, initializing or saving state.

    Optional pages need only their actual original input. An absent unsigned
    draft reader leaves that editor unmounted; it does not disable other pages.
    Original runtime/gateway and the original checkpoint loader stay in charge.
    """
    if type(collateral_selection) is not bool or type(scenario_selection) is not bool:
        raise ValueError("explicit selector options required")
    if read_draft_specifications is not None and not callable(read_draft_specifications):
        raise ValueError("original declaration reader required when supplied")
    loaded = compose_checkpoint_workbench(checkpoint, scope, runtime, receipt_id,
                                          **original_options)
    server = loaded.server
    try:
        # The original editor installs its base handler. Mount it first, then
        # wrap that handler with the independent selectors so no route is lost.
        if read_draft_specifications is not None:
            editor = RemintDraftEditorBinding(loaded.checkpoint.access, receipt_id,
                                             read_draft_specifications)
            mount_remint_draft(server, editor)
        if collateral_selection:
            mount_collateral_selection(server)
        if scenario_selection:
            mount_market_scenarios(server)
    except Exception:
        server.server_close()
        raise
    return loaded
