# Allowed-currency editing for an unsigned replacement

The original remint draft editor now accepts an optional host-owned
read_currency_choices(receipt_id) callback. The recovered workbench composition
passes it through as read_draft_currency_choices on the same loaded EX access.
Construction performs no callback, wallet operation, save or mint. Without the
callback the existing text-only editor and form contract remain available;
other original pages and authorized execution do not gain a new prerequisite.

The callback returns a tuple of up to 32 unique original public currency codes.
Codes follow the existing identifier shape and exclude wallet-address text.
They are labels from the original application's mapping, not invented token
contracts, chain IDs, exchange rates or currency-set references. The replacement
seed's existing choices must still be represented. Missing or inconsistent
host choices produce the existing localized unavailable response.

The six-language form shows the original allowed set and checkboxes for the
proposed new NFT. A preview requires one or more unique offered codes and
preserves their submitted order. It delegates to edit_remint_draft and the
original typed receipt/specification constructors. The original receipt and
replacement seed are unchanged; no minted NFT's allowed set is modified.
GET restores the host's current seed rather than persisting a posted draft.

The existing same-origin, CSRF, complete bounded form and identity-excluding
rules remain. Form fields cannot choose a source, account, replacement asset,
grant or currency-set reference. Neither this optional preview nor a list of
codes proves currency network/unit mappings or native authority. Original
metadata/schema verification, signature scope, ETH gas and atomic remint remain
the original execution path's work. This page is not an approval gate and never
signs, submits, burns, mints, converts funds or rewrites history.

This closes the currency-selection portion of EX-REMINT-03 / T-65 in the draft
UI. Complete field editing, actual installed source bindings, native execution
and independent six-language visual/interaction acceptance remain separate.
Seven new regression definitions cover locale/choices, add/remove without
mutation, preview/reset, invalid input, unavailable source, legacy form and
recovered composition. Author product tests, syntax checks and browser execution
are NOT_RUN. Full delivery remains OPEN.
