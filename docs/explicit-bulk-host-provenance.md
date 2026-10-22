# Explicit bulk host and source-provenance composition

The explicit bulk host now composes the original catalogue/feed with the
archive-correlated source metadata and the six-language provenance view.
The existing HTML host loader still accepts only its original HTML source.
The separate bulk loader accepts only its explicit fixed bulk source; neither
selects the other as a fallback.

Configuration parsing retains the complete externally supplied byte digest,
fixed source and scope, original reader intervals, calendar/time-zone status
and strict unknown-field handling. No worker, network request or service starts
during composition. The host's existing lifecycle remains responsible for
starting and closing the selected feed.

Only metadata matching the displayed archive digest accompanies a retained
price. Complete archive, selected series-line and manifest digests remain
distinct, as do series update, distribution update, observation and fetch
times. Original attribution is displayed as source metadata and establishes
neither independent display permission nor an executable NFT order price.

Four new synthetic composition definitions connect explicit CLI parsing to the
latest feed and HTTP provenance views, preserve metadata across an unchanged
manifest, verify that page reads do not fetch source data, and suppress
attribution when the retained archive/cache identity conflicts. Author product
execution is NOT_RUN. No live configuration switch, bulk activation, new
provider fetch, fallback, polling change or successful reference is claimed.
