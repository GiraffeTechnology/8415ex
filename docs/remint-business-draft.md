# Original public business fields in the replacement draft

This stage extends the original unsigned remint form, stacked on the currency
selection stage. It adds commodity name, exact goods quantity and unit, receipt
and bill numbers, issuer, registrar, storage location, trading cutoff,
registration deadline and the original LT/LTE comparison. Six-language labels
show the old public value beside each proposed field. UTC cutoffs remain exact
Unix-second integers; no display timezone is guessed.

The host still supplies both typed declarations and the replacement identity.
Complete posted scalar groups feed the existing edit_remint_draft function;
WarehouseReceipt and MintSpecification retain original quantity, identifier,
mint/cutoff and comparison rules. Canonical integer parsing avoids floats,
rounding or JavaScript precision loss. Domain refusals become the existing
generic localized refusal without leaking private constructor diagnostics.
A legacy post with no new business fields continues using the original seed;
partial groups, duplicates and unknown fields are refused.

The editor does not expose or accept asset addresses, origin accounts, receipt
IDs, token IDs, document/access mappings, currency-set references, source readers
or grants. Business text retains the existing wallet-address exclusion and HTML
escaping. Posting a draft changes neither the old NFT nor the seed; reopening
the page restores original inputs. The proposal remains unsigned, not metadata
verified, not persisted and not executed. It adds no approval prerequisite.

This provides scalar business editing within EX-REMINT-03 / T-65. Template and
voucher definitions, public attribute structure and controlled mapping edits
are not replaced with free-form JSON here; their original typed/source/privacy
contracts and actual native wiring remain separate. No claim of complete
remint or current installed UI acceptance follows.

Seven regression definitions cover six locales/privacy, typed nonmutation,
preview/reset, exact numeric/time/identifier rules, partial/duplicate/private
inputs, original CSRF/origin checks and prior currency-only posts. Author
tests, imports, syntax/type checks, browser execution and builds are NOT_RUN.
The preceding stage must be reviewed/combined first; QA uses the accurate
combined source, without inheriting a predecessor's checks or acceptance.
