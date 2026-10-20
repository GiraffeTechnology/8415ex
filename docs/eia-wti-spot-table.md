# Fixed daily WTI spot source decoding

This decoder reads the single daily Cushing WTI FOB spot table from the
[EIA original series page](https://www.eia.gov/dnav/pet/hist/RWTCD.htm).
Its canonical EIA Open Data series identifier is `PET.RWTC.D`, as listed in the
[EIA petroleum dashboard](https://www.eia.gov/opendata/petroleum_dashboard.php).
It fixes USD per barrel, the original specification and market, and the weekday
columns. It does not treat a nearby chart, futures value or last number on a
page as this series. The source's day precision remains a date; the original
publication date and full response digest are returned separately.

The parser walks complete increasing source weeks, including December/January
boundaries. Blank weekdays and EIA missing-value markers do not become zero.
The latest reported record retains its actual observation date. Historical
negative values are accepted as source history. If the latest report is
nonpositive, decoding refuses it for the existing positive-price feed contract;
an older positive record is never substituted silently.

The original source page identifies a daily series rather than a per-second
market. Its own publication and next-release dates remain source facts. This
module has no transport, polling interval, retry, cache, credential, database or
service lifecycle. It does not claim source access limits or ongoing refresh
have been verified. The original host must supply its bounded permitted reader,
source cadence and freshness policy before connecting the existing
CommodityReferenceFeed. Source-time zone interpretation stays explicit in that
policy; the parser does not invent an intraday timestamp.

EIA's [reuse guidance](https://www.eia.gov/about/copyrights_reuse.php) permits
reuse of government data with source acknowledgment, while separately protecting
third-party material and marks. Retain EIA attribution and publication date.
This decoder contains no EIA logo, photograph, fetched historical dataset or
live price fixture. A one-off verified source response is transport evidence,
not proof of continuous refresh or deployment.

Eleven synthetic regression definitions cover source and weekday identity,
missing observations, year boundaries, historical negatives, nonpositive latest
records, duplicate/reversed weeks, malformed decimals, publication consistency,
incomplete input and byte limits. They are authored and NOT_RUN by the author.
No local product imports, syntax checks, tests, builds or packaging were run.
This reference component never changes quotes, signed currencies, principal,
ETH gas, matching, grants or native execution.
