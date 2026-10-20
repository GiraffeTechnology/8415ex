"""Explicit lifecycle for the original catalogue and its host-owned feed."""
from .catalogue_serve import EmptyCatalogueServer
from .reference_feed import CommodityReferenceFeed


def compose_reference_catalogue(reference_feed, **server_options):
    """Bind the original server without fetching or starting a worker.

    The host supplies the existing feed, complete verified source policy and
    original server options. No endpoint, credential, port or receipt is chosen.
    Ownership of the feed stays with the host until explicit serving begins.
    """
    if not isinstance(reference_feed, CommodityReferenceFeed):
        raise ValueError("original reference feed required")
    if "reference_feed" in server_options:
        raise ValueError("one original reference feed required")
    return EmptyCatalogueServer(reference_feed=reference_feed, **server_options)


def serve_reference_catalogue(server):
    """Run the original server and request source stop on every exit path.

    start() is asynchronous: missing or unavailable source data does not gate
    the read-only HTTP pages. close() retains the original bounded worker join;
    it requests stop and prevents another poll, but does not assert that an
    already pending source request has finished. No process is killed.
    """
    if not isinstance(server, EmptyCatalogueServer):
        raise ValueError("original catalogue server required")
    feed = server.reference_feed
    if not isinstance(feed, CommodityReferenceFeed):
        raise ValueError("original attached reference feed required")
    try:
        feed.start()
        server.serve_forever()
    finally:
        try:
            server.server_close()
        finally:
            feed.close()
