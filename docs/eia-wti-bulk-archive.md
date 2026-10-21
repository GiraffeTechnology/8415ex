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
wallet, order, NFT or financial state. Fifteen synthetic regression definitions
are included; their execution remains pending CI and review.

## Physical member verification and requirement mapping

Before NDJSON selection, the local header's full flags, compression method,
member name, CRC and size declarations must agree with the central entry.
Optional data-descriptor headers may defer ordinary sizes with zero fields;
ZIP64 local-size sentinels are rejected rather than treated as ordinary sizes.
The complete stored payload or raw deflate stream is independently consumed in
bounded chunks. Deflate must reach its physical endpoint with no unused
compressed bytes; the actual uncompressed size and CRC must match the complete
member. A central-directory valid-prefix claim cannot hide duplicate series,
malformed suffixes or bytes following a completed deflate stream. Every NDJSON
line, including unselected series and categories, rejects nonfinite constants.

| Requirement | Exact source/configuration | Exact tests/run/artifacts | Verdict |
| --- | --- | --- | --- |
| T-71; EX-PRICE-01, EX-PRICE-02 | `exchange/eia_wti_bulk_archive.py:select_eia_wti_bulk_archive` and `_verify_member_stream`, with explicit received PET.zip bytes; fixed member/series and archive/member/line bounds. No URL, transport or polling configuration is invented. | `integration/test_eia_wti_bulk_archive.py:WTIBulkArchiveTests`, all 15 definitions through Bootstrap checks' joined Stage 5 integration step; retain exact source SHA, tested base/merge identity, runner and complete integration log/source archive. | Revised candidate synthetic execution NOT_RUN until current CI. Actual continuous source/host acceptance NOT_VERIFIED. |
| T-72; EX-PRICE-02, EX-PRICE-03, EX-PRICE-04 | Complete archive/member/selected-line identities remain separate from sourceAsOf and sourceUpdatedAt. Structural or any-line JSON failure refuses the complete read; it never supplies zero or a replacement price. | Existing 10 cases plus nonfinite unselected lines, hidden duplicate/malformed member suffixes, post-deflate bytes, inconsistent local headers and valid multi-chunk/data-descriptor streams. | Synthetic integrity checks only; live unavailable/recovery display, freshness policy and browser/served evidence remain NOT_RUN/NOT_VERIFIED. |
