# Explicit EIA daily WTI bulk-series decoding

The EIA [Open Data index](https://www.eia.gov/opendata/index.php) links a
[bulk manifest](https://www.eia.gov/opendata/bulk/manifest.txt) and the
[petroleum ZIP](https://www.eia.gov/opendata/bulk/PET.zip). The
[developer page](https://www.eia.gov/developer/) describes bulk downloads as
available without an API key. The index lists two daily bulk update windows;
those windows describe distribution updates, not daily observation times.

`parse_eia_wti_bulk_series` decodes one explicitly selected NDJSON series line.
It requires PET.RWTC.D, daily frequency, the Cushing WTI spot identity and
dollars per barrel. It retains the source's attribution, copyright and
offset-bearing update timestamp. Current official series metadata identifies
Thomson-Reuters as both source and copyright holder. Dataset-level public access
does not erase that series-level metadata. This decoder makes no permission
decision.

Source dates retain calendar-day precision. The update timestamp is not used
as an observation timestamp or invented publication date. The SHA-256 covers
the selected line, explicitly labelled by `responseDigestScope`; it does not
claim to identify the complete ZIP or manifest. A caller must retain those
transport identities separately.

Dates must strictly descend and match the declared range. Null observations
are missing, not zero. Historical negative values remain valid input, while a
latest reported nonpositive price cannot enter the existing positive reference
contract; it is never replaced by an older positive price. Duplicate object
fields, changed units/frequency/market, malformed dates and nonfinite values
are rejected.

This is a separate explicit supply-format decoder. It neither downloads nor
extracts ZIP files, selects a fallback, registers keys, starts workers nor
changes service configuration. Archive transport, bounded extraction, source
policy and feed integration remain separate work. No complete historical
dataset is embedded. Reference prices do not set NFT order prices or execute
financial operations.

Eleven synthetic regression definitions accompany this stage. They have not been
run by the source author; CI and review must establish the executable result.

## Requirement and evidence mapping

| Requirement | Exact source and configuration | Exact tests and evidence | Verdict |
| --- | --- | --- | --- |
| T-71; EX-PRICE-01, EX-PRICE-02 | `exchange/eia_wti_bulk_series.py:parse_eia_wti_bulk_series`; explicitly selected PET.RWTC.D NDJSON bytes with fixed daily WTI scope, original attribution and offset-bearing update metadata. Archive selection, source calendar, transport and continuous polling are separate host inputs. | `integration/test_eia_wti_bulk_series.py:WTIBulkSeriesTests` (11 cases). Original source `cf2e8dcf32652298e00b5756d5e2296078ec2353`: [Bootstrap 39575901767](https://github.com/GiraffeTechnology/8415ex/actions/runs/39575901767), joined Stage 5 integration log, and retained exact source/run evidence. All 11 named cases were observed passing in that run. | Original candidate synthetic decoder CI: PASS. Current-main integration candidate: NOT_RUN pending its own checks. No live acquisition or continuous-feed acceptance follows. |
| T-72; EX-PRICE-02, EX-PRICE-03, EX-PRICE-04 | Returned sourceAsOf/date precision, sourceUpdatedAt, sourceCopyright/upstreamSource and line-scoped digest are distinct. The decoder refuses changed scope, malformed dates, nonfinite/nonnumeric values and a nonpositive latest reported price; null is missing. | Same exact 11-case module covers identity/precision, missing values, nonpositive latest, malformed scope/calendar/range, attribution/offset, numeric bounds, duplicate fields and bounded input. Retain the exact tested source/base and test log with the run archive. | Synthetic parsing only. Feed freshness, source transport, displayed evidence, unavailable/recovery browser states and deployed-host evidence remain NOT_RUN/NOT_VERIFIED. |

The original [contract CI run 39575901539](https://github.com/GiraffeTechnology/8415ex/actions/runs/39575901539)
also passed its actual checks; it is not execution evidence for this Python
decoder. Neither CI run certifies the later integration candidate or live data.
