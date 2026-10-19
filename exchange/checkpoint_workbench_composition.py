"""Bind original workbench pages to the same checkpoint-loaded EX instance."""
from dataclasses import dataclass

from .checkpoint_runtime_load import load_exchange_checkpoint
from .serialized_workbench_composition import compose_serialized_workbench


class CheckpointWorkbenchUnavailable(ValueError):
    pass


@dataclass(frozen=True)
class LoadedCheckpointWorkbench:
    server: object
    checkpoint: object


def compose_checkpoint_workbench(checkpoint, scope, runtime, receipt_id, *,
        gas_page, registration_sources, current_time, commit, tree,
        runtime_options=None, detail_receipts=(), remint_review=None,
        reference_feed=None, port=0):
    """Construct the existing server, but never start it or dispatch a command.

    The application supplies its original controllers, gateway options, source
    identity and listen port. No receipt, tenant, endpoint or wallet is guessed.
    Missing saved state is unavailable, rather than a synthetic empty success.
    """
    loaded = load_exchange_checkpoint(checkpoint, scope, runtime)
    if loaded is None:
        raise CheckpointWorkbenchUnavailable("original checkpoint is absent")
    details = tuple((rid, dict(options)) for rid, options in detail_receipts)
    # Fail an inaccurate receipt selection before the server binds its socket.
    # This is original data lookup, not a new execution approval condition.
    loaded.access.receipt(receipt_id)
    for rid, _ in details:
        loaded.access.receipt(rid)
    server = compose_serialized_workbench(loaded.access, receipt_id,
        gas_page=gas_page, registration_sources=registration_sources,
        current_time=current_time, commit=commit, tree=tree,
        runtime_options=runtime_options, detail_receipts=details,
        remint_review=remint_review, reference_feed=reference_feed, port=port)
    return LoadedCheckpointWorkbench(server=server, checkpoint=loaded)
