"""Explicit existing bulk-reader/feed/catalogue composition; never a fallback."""
from copy import deepcopy

from .eia_wti_bulk_reader import EIAWTIBulkReader
from .eia_wti_bulk_series import BULK_URL
from .eia_wti_spot_table import SCOPE
from .reference_feed import CommodityReferenceFeed
from .reference_catalogue_runtime import compose_reference_catalogue


class EIABulkReferenceFeed(CommodityReferenceFeed):
    """Retain source attribution only when it matches the displayed archive."""
    def __init__(self, policy, reader, verify_policy, *, clock=None):
        self._bulk_reader = reader
        super().__init__(policy, reader, verify_policy, clock=clock)

    def snapshot(self):
        value = super().snapshot()
        if value.get("price") is None:
            return value
        digest = value.get("sourceEvidence", {}).get("rawResponseSHA256")
        try:
            evidence = self._bulk_reader.cached_source_evidence()
            if (type(evidence) is not dict or evidence.get("sha256") != digest
                    or any(type(evidence.get(key)) is not str or not evidence[key]
                           for key in ("upstreamSource", "sourceCopyright", "sourceUpdatedAt",
                                       "datasetUpdatedAt", "manifestSHA256", "selectedLineSHA256"))):
                raise ValueError("matching original archive attribution required")
        except Exception:
            # A concurrent cache change or metadata failure cannot attach another
            # archive's attribution to a retained price or invent display rights.
            return dict(value, status="unavailable", retainedValue=True,
                        sourceAttributionStatus="unavailable")
        selected = {key: evidence[key] for key in (
            "sha256", "selectedLineSHA256", "manifestSHA256", "datasetUpdatedAt",
            "sourceUpdatedAt", "upstreamSource", "sourceCopyright")}
        return dict(value, sourceAttributionStatus="recorded",
                    sourceEvidence=dict(value["sourceEvidence"],
                        responseDigestScope="complete-petroleum-archive",
                        bulkSource=deepcopy(selected)))


def compose_eia_bulk_reference_catalogue(*, policy, verify_policy, reader_options,
                                        feed_clock=None, **server_options):
    """Compose the original catalogue/lifecycle with an explicit bulk source.

    No requests, workers, credentials, calendar, intervals, port or served
    identities are selected here. The original host chooses and verifies them.
    The HTML composition and its installed configuration are unchanged.
    """
    if (type(policy) is not dict or policy.get("sourceURL") != BULK_URL
            or any(policy.get(key) != val for key, val in SCOPE.items())):
        raise ValueError("fixed explicit daily EIA bulk policy required")
    if type(reader_options) is not dict:
        raise ValueError("explicit original reader options required")
    if "reference_feed" in server_options:
        raise ValueError("one original reference feed required")
    if feed_clock is not None and not callable(feed_clock):
        raise ValueError("callable original feed clock required")
    reader = EIAWTIBulkReader(**dict(reader_options))
    clock = (lambda: feed_clock()) if feed_clock is not None else None
    feed = EIABulkReferenceFeed(deepcopy(policy), reader, verify_policy, clock=clock)
    try:
        return compose_reference_catalogue(feed, **server_options)
    except BaseException as primary:
        try:
            feed.close()
        except BaseException:
            note = getattr(primary, "add_note", None)
            if callable(note):
                note("bulk reference feed cleanup also failed during composition")
        raise
