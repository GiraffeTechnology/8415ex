# Synchronous original task-journal get wire adapter

`OriginalTaskJournalWire` implements the get-only wire portion of ArtFi commit
`5e7cc4cd482be71431d904439ef79d1ab5d7eade`,
`apps/web/src/lib/nft/task-journal.ts` (blob
`b132ef9c67bee3af14541bf9b110a0985f3da4e0`). It composes with the existing
`OriginalTaskJournalReader`; the latter still enforces expected chain and wallet.

The host explicitly supplies the installed HTTPS endpoint ending in
`/internal/v1/nft/operations`, peer identity, original synchronous mTLS transport,
and original synchronous `with_capability(scope, use)` held-grant entry. The
adapter constructs POST bytes and Go/JS canonical request digests, fixes `get`,
sets empty plan digest, and calls the transport at most once inside the gate.
The callback cannot be reused after gate completion. Responses are validated
before returning from the gate, and the gate cannot substitute different data.

The transport contract accepts `endpoint` and keyword arguments `method`,
`headers`, `body` (bytes), `timeout=8.0`, `max_bytes=65536`, `redirect='error'`.
It returns `JournalHTTPResponse(status, body, url)`. It MUST enforce the deadline
and bounded read during I/O, use the original mutually authenticated TLS identity,
refuse redirects and report the actual response URL. The adapter additionally
checks elapsed time, final URL and byte size; it cannot interrupt a blocking
host-supplied synchronous callable or prove its TLS configuration from its shape.

`with_capability` MUST enter/reuse the real grant gate, mint an action/request
bound capability and retain the SAME gate until the callback settles. No issuer,
credential, certificate, bearer fallback, network client, journal database or
create/update path is introduced here. Injected functions are trusted original
runtime capabilities, NOT proof of installed authorization. Missing functions
fail UNBOUND; merely providing fixtures never establishes a deployed binding.

Errors do not echo upstream payloads or tokens. Duplicate JSON keys, invalid
UTF-8, non-finite JSON, foreign operation/principal and secret-bearing payloads
are refused. No retry, alternate endpoint or session substitution occurs.

Local tests cover canonical bytes, exact request/scope, original reader joining,
held-gate sequencing, no/late/double callback, capability bounds, input refusal,
timeout/redirect/size/encoding, upstream error redaction and foreign/secret data.
These are deterministic local contract tests, not live mTLS, grant or chain
acceptance. Actual host origin/peer and installed gate/transport are still needed.
