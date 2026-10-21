# Optional source response evidence

The original CommodityReferenceFeed now retains a supplied source publication
date and the complete raw response SHA-256 as an optional sourceEvidence object.
The original observation date, date precision, fetch time, source age and state
remain distinct. A source URL supplied by a reader must match the original
policy URL. A digest must be lower-case SHA-256 text; a publication date must be
a calendar date no earlier than the source observation in the configured source
time zone and no later than the completed fetch date plus configured clock skew
in that same zone.

These are optional observation fields. An existing reader without them keeps its
existing behavior, and the UI says they were not provided. A digest records byte
identity; it is not a signature, independent provider attestation, display right,
freshness verdict or execution authorization. The feed does not infer missing
evidence or publish any raw response or unrelated nested reader fields.

The existing six-language provenance display includes both values from the same
snapshot. A malformed later observation retains the previous source evidence
with the original unavailable/retained-value state. A valid HTTP 304 can renew
the successful fetch time while preserving the original source date, publication
date and response identity; a revalidated source can still be stale.

Eight synthetic definitions cover preservation and detachment, old readers,
invalid evidence and retained state, date/source URL binding, six languages,
narrow display and the conditional-reader/feed composition. They are authored
and NOT_RUN by the author. No local product imports, syntax/type checks, tests,
builds or packaging were performed. No transport, scheduler, service, financial
action or existing source policy is started or changed by this stage.
