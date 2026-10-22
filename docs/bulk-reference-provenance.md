# Bulk source attribution in the existing provenance view

The existing six-language reference-field renderer now adds explicit bulk
source attribution fields when the original observation identifies the existing
fixed petroleum bulk source. HTML-source observations keep their original
17-field contract.

The optional fields distinguish upstream attribution, original copyright text,
series update time, distribution update time, complete-archive hash,
selected-series-line hash and manifest hash. Existing observation date,
date-only precision, source timezone, fetch time and last-success fields remain
separate. Offset-bearing source times are displayed unchanged; no publication
date, midnight timestamp, timezone or freshness is inferred from an update.

The renderer consumes an already installed trusted observation. It makes no
source request and authenticates no provider by itself. Attribution is displayed
only for the complete-archive digest scope, recorded source attribution and
a canonical archive hash matching the original price observation. Hash shapes
or a status string alone are not independent source authentication.

Missing or mismatched context renders fixed localized missing values. Only
explicit attribution fields are selected; arbitrary nested data, private
diagnostics and identity-bearing source text are not echoed. Dates require
their original timezone offset, hashes stay canonical, and text is bounded
and escaped. The original snapshot is unchanged.

Fixed translations are registered in the existing reviewed table classification.
The regression retains both non-English-prose detection and private-marker
checks. The English product documentation, signature/original-language and
identity-exclusion boundaries are unchanged.

This view does not select the bulk host entry, change service configuration,
create a fallback or establish redistribution/display rights, independent
approval, an executable NFT price, live acquisition or browser acceptance.
Its producer is the explicit bulk composition described in
[eia-bulk-reference-catalogue.md](eia-bulk-reference-catalogue.md).

Eight authored synthetic definitions cover locale completeness, original HTML
compatibility, archive binding, unavailable observations, time precision,
malformed/private fields, escaping/immutability and source classification.
EX has not run these definitions or product checks.
