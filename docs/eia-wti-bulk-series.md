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
