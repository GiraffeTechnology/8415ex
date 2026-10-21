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
scope. Eight synthetic definitions cover these source behaviors; they have
not been run by the source author and do not establish actual continuous
source or host acceptance.
