# Bounded EIA WTI source transport

EIAWTISpotReader fetches only the fixed HTTPS daily WTI page identified by the
existing decoder. The original host explicitly supplies a socket timeout, a
non-secret user agent, minimum request spacing and failure backoff. These are
host configuration choices, not claimed EIA rate limits or publication promises.
The source is daily spot USD per barrel; it is never an NFT executable quote.

Requests use GET, identity encoding, no ambient proxy or cookie jar, and no
credentials. Redirects are not followed. The returned URL, status, content type
and byte bound are checked before decoding. The socket timeout is not a universal
wall-clock deadline for every platform's DNS or transport implementation.

A validated response can supply ETag and Last-Modified conditional validators.
A subsequent 304 returns a detached copy of that same source observation and
response digest, without inventing a newer source date or a parser-level fetch
time. A 304 without validated cached data is unavailable. Invalid responses leave
the previous cache intact, but raise rather than returning old data as a fresh
network success. The original reference feed retains and labels its own last
successful observation. A revalidated cache can still be stale by source age.

The reader serializes attempts. Calls made before the explicit spacing or
failure delay expire do not touch transport. HTTP 429/503 Retry-After values in
seconds or HTTP-date form are respected without shortening them to the host
spacing; extremely large delays stop further requests from that reader. Failed
network or parse attempts use the explicit failure delay. Errors expose fixed
codes instead of transport exception details. No retry loop or fallback source
is created.

This module starts no thread, scheduler, service, database or network request at
construction. The original host may connect it to CommodityReferenceFeed using
the complete fixed series policy and independently verified cadence, freshness
and source-time-zone semantics. Configure that feed's poll spacing consistently
with the reader. Do not treat source publication frequency or public availability
as evidence of unrestricted access, continuous refresh acceptance or rights to
third-party materials. Retain [EIA source attribution](https://www.eia.gov/dnav/pet/hist/RWTCD.htm)
and [reuse guidance](https://www.eia.gov/about/copyrights_reuse.php).

Eleven synthetic bounded-response-port regressions are authored and NOT_RUN by
the author. They cover exact GET, cache isolation, conditional response, absent
cache, spacing, numeric/date/large server delays, sanitized failures, invalid
responses, policy drift and recovery. No local product imports, syntax/type
checks, tests, builds or packaging were run. Live reader, continuous integration,
deployment and financial/chain acceptance remain separate.
