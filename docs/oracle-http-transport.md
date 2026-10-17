# Original Oracle HTTP read transport

PR55 supplied the EX projection consumer but required an installed read transport. This increment provides OracleHTTPTransport, a synchronous standard-library implementation of its existing read(method, path) port. It issues real HTTP only when called. Import and construction do not discover a service or make a network connection.

## Explicit original deployment configuration

The origin is required; there is no default URL, environment discovery, RPC, wallet identity or new deployment parameter. Installation must pass the existing approved Oracle origin and original optional path prefix. The constructor rejects credentials in URLs, queries, fragments, control characters, ambiguous path segments and invalid ports. HTTPS uses the platform default trust store with certificate validation and hostname checks enabled. Plain HTTP is allowed only for explicit loopback origins.

This is a direct standard-library connection. It does not read or modify global proxy settings, install a CA, weaken TLS or create credentials. If the original deployment needs a reviewed alternate transport, PR55's injection port remains available; this module is not permission to bypass an access refusal or change the established route.

TLS authenticates the configured network endpoint. It does not prove which product commit is served. Exact served source/artifact identity and the Oracle source/asset/native-journal correspondence still require original installation and canonical evidence.

## Read-only route and HTTP handling

Only the already verified Oracle application routes needed by the join are reachable: projection metadata, entry/version, holder/as-of and finality/as-of under /v1/oracle/projection. Token and instant/version arguments are canonical uint256/uint64 decimal strings. Version zero, writes, queries, unrelated routes and path substitution are refused before connection.

No redirect is followed, no retry is made, no cookie or authorization header is constructed. Each call creates and closes its own connection. Request headers ask for application/json with identity encoding. The client refuses incompatible content type/charset, compression, conflicting or duplicate content lengths, simultaneous length and transfer framing, and unsupported transfer encoding.

Declared and streamed response size cannot exceed 65536 bytes. A declared length must be satisfied. Bodies use strict UTF-8 and must decode to JSON objects; duplicate object keys, NaN/Infinity and floating-point literals are refused. Integer strings preserve the Oracle DTO precision. Non-success HTTP status is preserved with its JSON body for the consuming join to refuse; a server error never becomes a local registration result.

Network/parser failures expose only a static product error, not origin, raw response bytes or underlying private exception text. Response and connection resources are closed on success and failure. Financial effects are absent.

## Time bounds

timeout_ms is an exact integer from 1 to 30000, default 5000. A monotonic deadline reduces the remaining socket timeout before connection, request, response headers and each bounded read1 call. Exhausted time refuses the read. This avoids resetting a full timeout for every streamed fragment.

Platform DNS resolution inside connection setup is synchronous. Its existing host resolver bound remains an installation requirement; this implementation does not claim a process-wide hard DNS cancellation deadline. No resolver, network policy or global timeout is changed by this stage.

## Composition and evidence

The actual composition is OracleProjectionJoin(explicit_source, OracleHTTPTransport(original_origin), original_mapping_verifier). The join still independently validates every source/token/version/commitment/instant response and rejects a changing projection after one complete retry. The mapping verifier must resolve actual original records. registryReference stays a locator, and read facts never become atomic release/refund authority.

Twelve mock-socket regression methods are authored, NOT_RUN. They cover no-I/O construction and TLS defaults, route/prefix and identity headers, origin/write/route refusal, redirects and closure, JSON/framing/encoding errors, length/body bounds and truncation, deadlines, preserved HTTP errors and sanitized exceptions, and the actual HTTP transport composed with PR55 through five synthetic responses. Fake responses prove no live availability or service identity.

Independent QA command after accurate source preparation: python -m unittest integration.test_oracle_http_transport -v. The EX author did not run compilation/import, tests, real HTTP, CI, signing, transactions or deployment. Required actual origin/served binding, installed canonical mapping and native principal/gas writer, full UI/chain/scenario acceptance and authenticated project archive readback remain OPEN. Independent source work does not wait for this PR's CI.
