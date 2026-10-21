# Original reader transport observation in the reference feed

The EIA catalogue composition now supplies the existing reader's
`transport_observation` port to the same CommodityReferenceFeed. A refresh captures
that metadata after its original read returns or raises. Snapshot/API/market
fragment reads never call the observer, start another fetch, reset a reader,
bypass Retry-After or change polling/backoff. Composition remains inactive until
the original serving lifecycle starts.

This optional port preserves feeds that do not provide it. The snapshot's
`transportObservation.value` accepts only the existing bounded diagnostic shapes:
HTTP 200 read byte count plus raw-response SHA-256, HTTP 304 plus the retained
response digest, or a finite source-unavailability code and retained-source
boolean. Unexpected fields, arbitrary error text, headers, URLs, malformed
quantities and unknown codes produce `diagnostic-unavailable`. Observer failures
do not discard a valid reference price or leak the exception. Returned objects
are detached.

The field explicitly sets `attemptCorrelation=NOT_ESTABLISHED`. The existing
reader can defer a call before updating its last transport metadata, so that
metadata can describe an earlier read. Capturing it after a refresh does not
prove an HTTP outcome for that particular attempt. A diagnostic HTTP 200 also
does not prove that the feed accepted a price, that its source date is fresh,
or that an NFT order or financial operation is executable. Source/fetch times,
precision, unknown calendar, retained values and source evidence keep their
existing meanings. No provider SLA or extra approval is introduced.

This advances EX-PRICE-02/03 and T-71/72 observation wiring. It makes future
original-reader state visible without extra source requests; it cannot
retroactively explain a past process's failed fetch. There is no new endpoint,
credential, scheduler, provider fallback, order gate or financial write. The
existing reference JSON carries this optional field; no technical diagnostic
text is added to the six-language market interface.

Eight synthetic definitions cover no eager calls or snapshot polling, private
error/metadata exclusion, observer failure with a good price, invalid price with
HTTP success, retained values and detached metadata, not-modified evidence,
optional-port compatibility, and original EIA composition with no extra request
during reader spacing. Author execution is NOT_RUN. Exact-head CI/review and
actual provider, runtime, source-change and recovery acceptance remain required;
this document supplies no passing result.
