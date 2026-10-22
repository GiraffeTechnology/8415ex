# Visible gas quote context

The gas confirmation summary now shows the original quote time, supplied fee
scope, sample count, sample time window and median algorithm beside the existing
cap/P50 ETH and USD values, action list, network, FX source/time and expiry.
These values appear before the collapsed raw-sample evidence and before consent
in all six supported locales. Time values retain explicit UTC epoch-second
labels; quote, sample-window, FX and expiry instants remain distinct.

Scope and action identifiers are displayed as supplied by the typed original
quote. The UI does not infer aggregate or per-action coverage, conditional
coverage, fee allocation, a new sample population or an additional gas amount.
Raw sample identities, fees, blocks, source references and hashes remain in the
existing evidence table. Source text is HTML-escaped.

This is a presentation extension to EX-GAS-04 and EX-GAS-06. Existing quote
validation, exact amounts, same-instant FX, digest, wallet session bindings,
confirmation POST fields and validity boundaries are unchanged. Reading this
page neither calls the wallet nor freezes, signs, sends or authorizes anything.
The displayed context is not accepted back as new browser-supplied authority.

Eight authored contract definitions cover the six locales, separate time
fields, supplied scope, escaping, exact cap/P50 values, immutable quote/form
bindings and existing validity/POST refusal behavior. They have not been run
by the author. Runtime, browser, wallet, funds and chain acceptance remain
separate from this source change.
