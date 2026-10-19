"""Mount original workbench controllers using one existing serialized EX access."""
from copy import deepcopy

from .serialized_exchange_access import SerializedExchangeAccess
from .remint_review import RemintReviewBinding
from .remint_review_workbench import RemintReviewWorkbenchServer


def compose_serialized_workbench(access, receipt_id, *, gas_page,
        registration_sources, current_time, commit, tree, runtime_options=None,
        detail_receipts=(), remint_review=None, reference_feed=None, port=0):
    """Construct, but do not start, the existing native HTTP server.

    detail_receipts contains original (receipt_id, RuntimeBinding options) pairs.
    Controllers and installed gateway/readers are passed through unchanged. This
    selects no wallet, signer, provider, tenant, deployment path or native state.
    """
    if type(access) is not SerializedExchangeAccess:
        raise ValueError("one existing original serialized access required")
    binding = access.bind_runtime(receipt_id, **dict(runtime_options or {}))
    details = tuple(access.bind_runtime(rid, **dict(options))
                    for rid, options in detail_receipts)
    review = remint_review
    if review is not None:
        if type(review) is not RemintReviewBinding:
            raise ValueError("original remint review binding required")
        original_reader = review.read_original_pair

        def read_pair(old_id, replacement_id):
            with access._lock:
                # Capture both versions and detach them before another EX
                # writer can change a callback-returned mutable projection.
                return deepcopy(original_reader(old_id, replacement_id))

        review = RemintReviewBinding(review.receipt_id,
                                     review.replacement_receipt_id, read_pair)
    server = RemintReviewWorkbenchServer(binding, gas_page=gas_page,
        registration_sources=registration_sources, current_time=current_time,
        commit=commit, tree=tree, port=port, detail_bindings=details,
        reference_feed=reference_feed, remint_review=review)
    # The original constructor stamps its primary binding. Stamp the same
    # actual host-supplied source on each directory binding as well.
    for detail in details:
        detail.run.update(server.source)
    return server
