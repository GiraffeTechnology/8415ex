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

Nine synthetic composition definitions are included. They have not been run
by the source author. This adapter is source wiring, not evidence that a
production host has loaded a policy, started a feed or served a live quote.

## Requirement and evidence mapping

| Requirement | Exact implementation and configuration | Synthetic cases | Execution and artifact verdict |
| --- | --- | --- | --- |
| T-71; EX-SCOPE-15, EX-PRICE-01, EX-PRICE-02 | `exchange/eia_reference_catalogue.py:compose_eia_reference_catalogue` connects the existing `EIAWTISpotReader`, `CommodityReferenceFeed`, and `exchange/reference_catalogue_runtime.py:serve_reference_catalogue`. Host inputs are the fixed source policy and verifier, sourceTimezone, pollSeconds, maxSourceAgeSeconds, maxClockSkewSeconds, reader timeout/spacing/backoff/transport, and original server port/commit/tree. | `integration/test_eia_reference_catalogue.py:EIAReferenceCatalogueTests`: no eager fetch/thread; explicit refresh; original lifecycle; composition failure cleanup; invalid clocks rejected before bind; falsey callable clock retained. | Run the exact candidate through Bootstrap checks' joined Stage 5 integration step. Retain the tested source SHA and synthetic merge/base identity, runner metadata, full test log and retained run evidence. New clock regressions: NOT_RUN until that candidate's actual CI result. Live continuous acquisition and host installation: NOT_VERIFIED. |
| T-72; EX-PRICE-02, EX-PRICE-03, EX-PRICE-04 | Existing feed and reader preserve fixed provider/scope, sourceAsOf/date precision, publicationDate, rawResponseSHA256, fetchedAt and unavailable/stale state. This adapter retains the original endpoints and does not supply prices or choose a calendar. | Same exact test module: source-evidence refresh, unavailable source without blocking HTTP, changed series/source refused, original policy/calendar preserved. | Synthetic transport responses are not live source or rendered-page acceptance. Retain the candidate CI log and associated source archive; a real host run must additionally bind the actual policy/configuration, served source identity, successful and failing source responses, endpoint/browser evidence and acquisition interval. Those runtime/browser verdicts remain NOT_RUN/NOT_VERIFIED. |

The earlier candidate `2ebe03c4e48e810bbf9aad28be6c1aa2f56917d5` has
[Bootstrap run 39579277338](https://github.com/GiraffeTechnology/8415ex/actions/runs/39579277338)
and [contract run 39579277403](https://github.com/GiraffeTechnology/8415ex/actions/runs/39579277403).
Those run links identify only that original source and do not certify the clock
repair candidate, production source availability or complete T-71/T-72 acceptance.
