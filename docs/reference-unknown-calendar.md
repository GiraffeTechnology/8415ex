# Date-only references with an unknown source calendar

A provider may publish a real daily price and calendar date without specifying
the observation's time zone. The host can explicitly set the existing
`sourceTimezone` policy to `unknown`. This is not an alias for UTC, a guessed
market time zone or a fabricated midnight timestamp.

For date-only records, the original feed retains the price, date precision,
provider, market, unit, source evidence and actual fetch times. The snapshot's
time zone and numeric delay bounds are null, with freshness `unknown`.
Advancing the fetch clock cannot turn this uncertainty into fresh or stale
evidence. Fetch/parse failures still produce `unavailable` and retain the
identifiable previous value. Explicit timestamps continue to use their own
UTC observation instant; existing configured IANA-calendar behavior is
unchanged.

A date more than one civil day beyond the UTC fetch date plus configured clock
skew is impossible for a contemporary civil source calendar and is refused.
This broad date sanity bound assigns no exact observation instant. Publication
dates must still be real, no earlier than the observation date and no later
than the same broad fetch-date bound. Scope, positive-price and source-identity
checks remain unchanged.

The existing six-language provenance fields already render missing time zone
and numeric delay metadata with localized missing-value text. No fake zero or
Python null representation is displayed. Continuous reference configuration
can therefore represent absent metadata honestly rather than invent a zone
or suppress the real reference price.

Acceptance mapping: T-71 / EX-SCOPE-15 / EX-PRICE-01 / EX-PRICE-02 retain actual
source/fetch dates and their precision; T-72 / EX-PRICE-02 / EX-PRICE-03 /
EX-PRICE-04 retain unknown/unavailable classification and unchanged reference
scope. Ten synthetic definitions cover these source behaviors; they have
not been run by the source author and do not establish actual continuous
source or host acceptance.

The extra civil-day publication bound applies only to date-precision records
with an unknown source calendar. Exact UTC instants always retain the ordinary
fetch-date bound plus only the explicitly configured clock skew. An unknown
calendar setting cannot grant exact timestamps a next-day publication grace.

| Requirement | Exact implementation/configuration | Exact tests/run/artifacts | Verdict |
| --- | --- | --- | --- |
| T-71; EX-SCOPE-15, EX-PRICE-01, EX-PRICE-02 | `exchange/reference_feed.py:CommodityReferenceFeed`, explicit `sourceTimezone="unknown"` for missing source calendar metadata, or an existing IANA zone. Exact instants continue using UTC; host cadence/skew/freshness inputs stay explicit. | `integration/test_reference_unknown_calendar.py:UnknownCalendarTests`, ten definitions through the standard Bootstrap checks integration step. Retain exact head/base/tested-merge identity, runner, full logs and source archive. | Current repair candidate synthetic CI NOT_RUN. Host installation/actual continuous source NOT_VERIFIED. |
| T-72; EX-PRICE-02, EX-PRICE-03, EX-PRICE-04 | Date-only unknown zone/delay remain null and freshness unknown; exact instants and known zones retain their normal age and publication bounds. Source identity, positive prices and unavailable/recovery behavior remain checked. | Existing eight cases plus exact-instant future publication refusal and 9/10-second explicit clock-skew boundary. Retain actual endpoint/browser/source acquisition and served/configuration artifacts separately. | Synthetic semantics only; UI/live-source/deployment and complete acceptance remain NOT_RUN/NOT_VERIFIED. |
