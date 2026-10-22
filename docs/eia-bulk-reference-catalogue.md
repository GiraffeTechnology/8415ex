# Explicit daily WTI bulk catalogue composition

`compose_eia_bulk_reference_catalogue` joins the existing
`EIAWTIBulkReader`, reference feed, catalogue and serving lifecycle.
The host must explicitly select the existing fixed EIA PET.zip source policy,
reader settings, source calendar, cadence/freshness rules, port and served
source identities. Construction makes no request and starts no worker.

This is a separate programmatic composition. It does not alter the HTML
composition, command-line configuration, service or proxy and never falls back
after an HTML error. It creates no credentials or scheduler and performs no
financial operation. Host activation is separate from source availability.

The original reader already fetches the fixed public manifest before the
petroleum archive, skips archive downloads when the manifest's PET entry is
unchanged, and verifies the bounded complete archive through the existing
decoder. This stage adds a read-only retained-evidence accessor. It preserves
the original archive hash, selected-line hash, manifest hash, dataset update
time, series update time, upstream attribution and copyright from that
successful source record. The feed attaches them only when the archive hash
matches the price observation. A cache race or unavailable/mismatched metadata
cannot label a retained value as fresh.

A date-only source remains date-only. Dataset/series update timestamps,
fetch time, publication time, source-calendar knowledge and freshness are
different facts. A failed later read retains only the corresponding old value
and source evidence with unavailable status. Neither source attribution nor
public access establishes redistribution rights, independent verification,
a new provider approval, or an executable whole-NFT price.

The existing HTML host entry remains unchanged and is not switched by this
stage. Actual host source selection, acquisition, rights/display policy,
browser presentation and continuous-feed acceptance require their own
original evidence; no production calendar or interval is invented here.

Eight synthetic definitions cover construction without requests/workers,
complete attribution and hash scope, manifest reuse, failed archive retention,
mismatched cache evidence, explicit selection, serving lifecycle and cleanup/
clock contracts. They have not been run by EX. No live bulk acquisition,
deployment, Wallet, financial or chain acceptance is claimed.

The source distribution URLs and field interpretation are inherited from the
existing [bulk reader documentation](eia-wti-bulk-series.md) and
[archive integrity contract](eia-wti-bulk-archive.md).
