"""Run the original saved-state UI on its existing foreground HTTP server."""
from .recovered_workbench_ui import compose_recovered_workbench_ui


def serve_recovered_workbench_ui(checkpoint, scope, runtime, receipt_id,
                                 **original_options):
    """Load once and serve once; retain the original store and runtime ownership.

    The host supplies the same inputs as compose_recovered_workbench_ui,
    including its actual listen port, source identity and configured adapters.
    This entry neither initializes missing state nor starts or stops an
    externally owned reference feed, gateway, database or wallet connection.
    """
    loaded = compose_recovered_workbench_ui(
        checkpoint, scope, runtime, receipt_id, **original_options)
    try:
        loaded.server.serve_forever()
    finally:
        # Close only the socket created by this composition, including when
        # the original foreground loop exits through an interrupt or error.
        loaded.server.server_close()
    return loaded
