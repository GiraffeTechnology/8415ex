# Native HTTP health observation

The existing native and integrated workbench GET handlers mount `/healthz`.
The route takes no query parameters and retains the existing exact Host check,
loopback binding, no-store policy and response security headers. No new public
origin, proxy rule, port, credential, process or deployment is selected here.

A successful response observes that this HTTP handler answered. It exposes only
valid declared commit/tree identities and booleans for the supplied command
gateway, reference feed, gas page and registration-source components. Invalid
or missing source declarations remain UNVERIFIED. Arbitrary source metadata,
receipt IDs, accounts, sessions, endpoint URLs and controller diagnostics are
excluded. The route does not read the domain, render a gas quote, call a Wallet,
probe capabilities, poll a feed or reconcile/send a transaction.

HTTP 200 and configured component presence do not prove a ready original runtime,
provider behavior, a persistent restart, source files matching the declared Git
identity, chain execution or full deployment acceptance. Operations must still
bind the actual served source/artifact and static resources to independently
verified private evidence and perform the applicable authorized QA. A successful
response from a fixture process remains a fixture response.

The route is source-prepared only. The five new behavior definitions have not
been executed by the original developer. Existing Control2 QA/review and the
original EX SIN-2 deployment ownership remain unchanged.
