# Bounded petroleum archive selection

The official EIA [bulk format documentation](https://www.eia.gov/opendata/v1/bulkfiles.php)
describes a ZIP containing newline-delimited JSON. This stage consumes already
received bytes from an explicitly selected source. It does not download a file
or silently replace the existing HTML reader.

`select_eia_wti_bulk_archive` accepts at most 64 MiB of compressed input and
exactly one regular `PET.txt` member. Only stored and deflated compression are
accepted. The declared and actual member length are bounded to 512 MiB,
individual lines to 4 MiB, and the stream to one million lines. The member is
read to EOF, including CRC verification, even after finding the selected series.
No archive path is extracted to the filesystem.

Exactly one PET.RWTC.D line must occur. Category objects and other series do not
become reference prices. Duplicate fields, duplicate selected series, malformed
trailing content, changed member names and incomplete/corrupt archives fail the
whole read. The selected line passes through the existing daily WTI decoder.

The returned observation keeps its selected-line SHA-256 and explicit digest
scope. A separate `archiveEvidence` object records complete compressed-byte and
uncompressed-member hashes, sizes and line count. The source-series update
timestamp and attribution remain distinct from transport acquisition time,
manifest modification time and archive identity. None of these hashes proves
redistribution rights or executable-price validity.

Transport timeouts, official manifest identity, update spacing, HTTP caching,
source display policy and continuous lifecycle integration remain the caller's
responsibility. This stage starts no worker and modifies no HTTP service,
wallet, order, NFT or financial state. Ten synthetic regression definitions
are included; their execution remains pending CI and review.
