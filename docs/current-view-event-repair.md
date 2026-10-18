# Repair current receipt rendering and audit vocabulary

Approved remote QA of the preceding candidate found a receipt-page KeyError:
the page still read the removed physical-exit eligibility fields. Render the
existing bill-of-lading contract, immutable price currencies and separate ETH
gas scope. Ordinary continuous transfer does not require owner and holder to
agree. Holder remint remains a distinct atomic operation with its own current
holder-possession and owner-equality checks. Retained physical records are
labelled historical and cannot be resumed.

The event contract now includes the recorded trading-resumed event and current
currency admission, ETH admission and remint audit requirements. Their missing
timeline integrations are explicit interface gaps, never fabricated events or
successful coverage. Retired physical events are excluded from current source
requirements; retained historical records can still be read and replayed once,
with an explicit non-executable retired label. Current source emitting them
continues to be a conformance failure. Unknown event names remain findings.

Replace the obsolete event-count threshold with the explicit current source
vocabulary. Keep independent expected audit-group names and negative assertions
that retired events cannot satisfy current remint coverage. Add regression
definitions for bill-contract rendering without a retired gate, continuous
transfer with holder lag, escaped bill terms, explicit unmapped requirements,
and retained retired history. Successor tests are NOT_RUN until approved remote
QA; prior failure evidence is retained. No deployed UI or real-chain acceptance
is inferred from rendering or local event replay.
