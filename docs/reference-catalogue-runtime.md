# Original reference catalogue lifecycle

compose_reference_catalogue attaches an existing CommodityReferenceFeed to the
original EmptyCatalogueServer. The host still selects the complete source
policy, reader, existing listen port and source identity. Construction binds the
original server but does not fetch a price, start a worker or create credentials.
The original collateral and scenario options are preserved.

serve_reference_catalogue explicitly starts that feed and runs the existing
HTTP loop. Source start is asynchronous. Initial missing data and subsequent
source unavailability remain normal read-only page states. The host must not
share this owned lifecycle with a separate service that expects the same feed
to keep running.

Every exit path closes the original HTTP resource and requests feed shutdown,
including source-start, HTTP-serving and server-close failures. Feed shutdown
retains the existing stop-event and bounded worker join. This prevents another
poll but is not evidence that an already pending source request has drained;
there is no process kill, retry or fabricated stopped result. External callers
use the original HTTP server shutdown contract when ending a running loop.

This is callable composition, not an installation script or an automatic CLI
configuration. It does not select a production source policy, cadence, freshness,
source time zone, port or provider. Actual deployment and continuous-feed
acceptance still require the original concrete configuration and served evidence.
Existing empty-catalogue operation without a source remains available through
its original entry point.

Six synthetic definitions use the actual catalogue class and source-feed type
with controlled lifecycle methods. They cover construction without reads,
ordered start/serve/close, failure cleanup and missing/foreign feed rejection.
They are authored and NOT_RUN by the author. No local product imports, syntax
checks, tests, builds or packaging were run; this stage neither moves funds nor
starts a live source or service.
