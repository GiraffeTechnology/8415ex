# Native unsigned bill-term editor

`mount_remint_draft` attaches a six-language `/remint-draft` entry to the original
constructed remint-capable workbench before its host starts serving. It retains
the original gas, registration and read-only remint routes. The main receipt and
editor use the same existing serialized EX access. Construction does not select
a provider, wallet, account, contract, replacement identity or deployment path.

The installed application supplies original typed current/replacement
specifications and their nonsecret business text. The reader captures and
detaches the pair under the same access lock. The page displays the complete
original bill text, an editable complete proposed bill text and an explicitly
unsigned preview. Users can add, delete or change paragraphs without rewriting
the original specification or seed. Each POST uses the original bound reader;
request data cannot select a receipt, asset, source or authorization.

POST accepts only the existing same-origin, CSRF-protected, bounded plain form
with `csrf`, `lang` and `billTerms`. Unsupported fields, framing, locales or
incomplete bodies are refused before editing. Errors are generic and do not
echo private diagnostics or request tokens. Source unavailability is localized
and serves no partial original terms. The business text is escaped and checked
against the existing address/control-character display exclusion. Raw models,
account/asset addresses, mapping references and fact hashes are not rendered.

The editor reuses the original typed draft operation. It does not sign, persist
a changed source document, submit, claim, reserve funds, burn or mint. An unsigned
preview is neither verified legal text nor an execution result. This optional
editing aid is not an additional approval or qualification step for an already
authorized Wallet action. Original Holder possession and Holder=Owner execution
conditions remain in the original checked native path.

This stage mounts the complete `bill_terms` text field. The structured commodity,
currency and cutoff fields supported by the typed editor are not yet form
controls here; complete editing UI and actual native result binding remain open.
Ten synthetic loopback regression definitions have not been run locally. No
production served version, real signed document or real transaction is claimed.
