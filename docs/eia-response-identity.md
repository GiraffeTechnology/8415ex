# Complete EIA response identity

The fixed EIA HTML reader now checks the response representation framing before
parsing or replacing its successful cache. One decimal Content-Length must be
within the existing 2 MiB limit and match the complete returned byte count.
Duplicate length/transfer headers, simultaneous length and transfer encoding,
malformed lengths and unsupported transfer encodings refuse the response.
The original HTTP port remains responsible for decoding chunk framing; a normal
chunked or close-delimited representation remains supported within the byte cap.

A page can remain valid HTML after truncation. Parsing that page alone does not
prove that its digest identifies the complete declared representation. A length
mismatch therefore cannot become a new price or rawResponseSHA256. The old price,
digest, ETag and Last-Modified remain intact; existing failure backoff and later
conditional 304/recovery behavior continue. No source series, quote value, unit,
calendar, provider cadence or financial action is changed.

This implements EX-PRICE-02/03 and T-72 representation provenance and failure
recovery. Six synthetic response-port definitions exercise complete, mismatched,
duplicate/ambiguous, oversized and recovery cases. They do not make live network
requests, and author execution is NOT_RUN. The existing integration CI discovers
the module. Actual feed, source rights, deployment and browser acceptance remain
separate; this stage makes no new timeout or complete-product claim.
