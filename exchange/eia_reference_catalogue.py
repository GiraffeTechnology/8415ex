"""Compose the existing EIA reader, reference feed and catalogue server."""
from copy import deepcopy

from .eia_wti_spot_reader import EIAWTISpotReader
from .eia_wti_spot_table import SCOPE, SOURCE_URL
from .reference_feed import CommodityReferenceFeed
from .reference_catalogue_runtime import compose_reference_catalogue


def compose_eia_reference_catalogue(*, policy, verify_policy, reader_options,
                                    feed_clock=None, **server_options):
    """Return the original catalogue with its explicitly configured EIA feed.

    All transport settings, source calendar, cadence, freshness bounds and
    server identities/port are host-owned inputs. No request or worker starts
    here. Use the existing serve_reference_catalogue lifecycle when serving.
    """
    if (type(policy) is not dict or policy.get("sourceURL") != SOURCE_URL
            or any(policy.get(key) != value for key, value in SCOPE.items())):
        raise ValueError("fixed EIA daily WTI HTML source policy required")
    if type(reader_options) is not dict:
        raise ValueError("explicit original reader options required")
    if "reference_feed" in server_options:
        raise ValueError("one original EIA reference feed required")
    if feed_clock is not None and not callable(feed_clock):
        raise ValueError("callable feed clock required")
    reader = EIAWTISpotReader(**dict(reader_options))
    # Preserve explicitly supplied callable clocks even when they are falsey.
    clock = (lambda: feed_clock()) if feed_clock is not None else None
    feed = CommodityReferenceFeed(deepcopy(policy), reader, verify_policy,
                                  clock=clock)
    try:
        return compose_reference_catalogue(feed, **server_options)
    except BaseException as primary:
        try:
            feed.close()
        except BaseException:
            note = getattr(primary, "add_note", None)
            if callable(note):
                note("reference feed cleanup also failed during composition")
        raise
