# Explicit manifest-aware EIA bulk reader

`EIAWTIBulkReader` supplies the existing reference feed's callable-reader
interface for the explicitly selected EIA petroleum bulk URL. The caller
provides the complete fixed WTI policy, request spacing, timeout, failure delay
and printable non-secret user agent. Construction starts no request or worker.
The existing bounded HTML reader remains a separate source-format choice;
neither reader invokes the other as a failure fallback.

Each eligible read retrieves the small official HTTPS manifest. Only its PET
distribution is considered; the URL, public-access marker, dataset identity and
offset-bearing update timestamp must match the fixed contract. A fingerprint
of the complete PET metadata controls archive reuse. Changes to another
dataset do not cause a petroleum download. A changed PET record triggers a
complete bounded ZIP read and CRC/selected-series verification before the
cache or fingerprint is replaced.

An unchanged PET record returns a copy of the original decoded observation.
It does not advance its source date or source update timestamp. Freshness
remains the reference feed's responsibility. The dataset update time describes
distribution metadata, not the WTI observation or a guaranteed publication SLA.

The reader reuses the existing trusted response-port, clock, request-spacing
and failure-backoff implementation. Default transport disables environment
proxies and redirects, uses standard HTTPS verification and sends no API key,
cookie or authorization header. Both requests have explicit socket timeouts,
identity content encoding, status, final-URL, MIME and byte limits. HTTP 429/503
Retry-After delays are retained without shortening. An error retains the old
cache internally but raises unavailable rather than claiming a successful
fresh fetch.

Non-secret transport diagnostics retain the manifest hash, dataset update
time and independent complete archive/member identities for successful
downloads, including cache reuse. The reader binds the observation's raw-response
hash to the complete downloaded ZIP, matching its source URL and the existing
feed's response-evidence field. The selected-line hash remains separate in
transport diagnostics; the archive selector's lower-level line-scoped result
is not passed through under an archive-scoped label.
Source attribution and copyright are not replaced by dataset public access.
This reader makes no licensing decision and does not configure production,
start a scheduler or change NFT prices, orders, wallets or financial state.

Ten synthetic transport regression definitions are included and have not
been executed by the source author. Actual continuous feed configuration and
host acceptance remain separate from these source definitions.

## Requirement and evidence mapping

| Requirement | Exact source/configuration | Exact tests and run evidence | Verdict |
| --- | --- | --- | --- |
| T-71; EX-SCOPE-15, EX-PRICE-01, EX-PRICE-02 | `exchange/eia_wti_bulk_reader.py:EIAWTIBulkReader` with host-supplied bounded transport, cadence/backoff and fixed PET.RWTC.D policy. It uses the repaired `exchange/eia_wti_bulk_archive.py` and current original reader/feed contracts; construction never starts polling. | `integration/test_eia_wti_bulk_reader.py:BulkReaderTests`, ten definitions in Bootstrap checks' joined Stage 5 integration run. Retain candidate head and tested merge/base identity, runner metadata, complete test log and exact source/archive artifacts. | Current integrated candidate synthetic CI NOT_RUN pending actual checks; continuous host/source acceptance NOT_VERIFIED. |
| T-72; EX-PRICE-02, EX-PRICE-03, EX-PRICE-04 | Source dates/update timestamps, archive/member/line/manifest hashes and cache reuse stay distinct. Every manifest JSON constant is finite; invalid input fails without accepting a new archive, source marker or quote. Failed reads preserve old cache only internally and report unavailable. | Exact tests cover unchanged/changed PET metadata, failed archive cache retention, origin/MIME/size refusal, provider Retry-After, sanitized diagnostics and nonfinite manifest constants rejected before archive acquisition. | Synthetic transport only; source timezone/freshness policy, live endpoint/browser unavailable/recovery states, deployment identity and actual acquisition intervals remain NOT_RUN/NOT_VERIFIED. |
