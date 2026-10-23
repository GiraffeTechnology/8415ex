# Bounded original Wallet response and direct-return composition

The complete candidate retains the original decreasing response budget and
bounded JSON framing in the Wallet client. Connection, headers and body reads
use the original monotonic budget rather than restarting a timeout for each
packet. Synchronous DNS still depends on the original resolver's bound.
TLS checks, the original origin and CookieJar rules remain intact.

The existing reserved direct-return task continues forwarding its original four
execute fields and expected budget revision. It adds no status, native-absence,
prepare, reserve, approval or extra login preflight. Original session and
execution authorization checks remain at their existing boundaries.

An uncertain execute result or invalid response does not reset the original
durable attempt. Reconstructing the application task cannot send that same
operation again. Duplicate/ambiguous framing is refused before response cookies
replace prior cookies. There is no redirect, retry, alternate origin or proxy.

Two synthetic integration definitions exercise the original mocked unknown
response through the actual budgeted client and reserved task, and an ambiguous
execute response with unchanged cookies, exact request fields and no resend.
Author product execution is NOT_RUN. This composition creates no real Wallet
request, session, credential, reservation, signature or transaction and does
not establish native outcome or current runtime/financial/chain acceptance.
