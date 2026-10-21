# EIA reference feed in the original catalogue

`compose_eia_reference_catalogue` connects the existing fixed daily EIA WTI
HTML reader to `CommodityReferenceFeed` and the original
`EmptyCatalogueServer`. It returns that same server type, retaining the
existing market/reference endpoints, empty directory and optional scenario
and collateral selection pages.

The host provides the complete fixed source policy and its existing verifier,
the source calendar, polling/freshness/skew settings, all reader transport
options, the port and declared commit/tree. This adapter provides no production
defaults for those inputs. The synthetic test calendar is not evidence of the
actual source calendar. The policy callback retains its existing role; this
adapter does not create an additional user approval.

Composition performs no source request, starts no polling thread and does not
claim a quote is available. Explicit serving uses the already existing
`serve_reference_catalogue` lifecycle, which starts the original feed and
requests cleanup on exit. A failed server composition requests feed cleanup
while preserving the original failure. Source unavailability remains visible
through the original feed and does not block read-only HTTP serving.

The HTML source URL is fixed. The independent bulk reader is a separate explicit
supply choice and is not selected as a fallback. Daily precision, publication
date, source response digest and unavailable/stale behavior remain those of
the existing reader and feed. No NFT price, order, currency, wallet,
authorization or financial operation is created.

Seven synthetic composition definitions are included. They have not been run
by the source author. This adapter is source wiring, not evidence that a
production host has loaded a policy, started a feed or served a live quote.
