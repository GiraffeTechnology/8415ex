# Original commodity attributes in the unsigned remint editor

The same replacement-draft page now renders the original replacement template's
applicable public attribute names and proposed values, alongside the complete
original public attributes. Group labels are supplied in all six supported
languages. Attribute-specific names stay the host's original template names;
the editor does not invent translations or let the request choose a schema.

A complete posted attribute group uses ordinal fields bound to that current
template. Nonempty values add or change the corresponding public attribute;
an empty optional value removes it from the new draft. Original
MintSpecification required-field rules still refuse removal of a required
attribute. Surviving seed order is preserved and newly populated fields append
in template order. Old receipt/declaration/seed/history are not changed.
A legacy post without an attribute group still uses the original seed values.

The input path accepts at most 64 template attribute fields and retains the
original full-body byte bound, exact field counts, same-origin and CSRF rules.
Partial, duplicate, unknown or request-selected template fields are refused.
Private source failures remain localized unavailable observations. Existing
business-text wallet-address exclusions and HTML escaping apply to original
and proposed public names/values. No raw metadata object, access/document
mapping, account, token identity, grant, signing ABI or native journal is
rendered or selected by the form.

The editor delegates to the same edit_remint_draft and typed constructors.
It does not persist a preview, run metadata verification, authorize, sign,
submit, burn, mint or convert funds. Existing native execution is not made
conditional on use of this optional editing page.

This stage is stacked on the original scalar and currency draft stages.
Seven authored regression definitions cover six-language rendering, optional
remove/required change, add/order preservation, required/partial/unknown and
duplicate refusals, escaping/privacy, preview/reset/legacy behavior, and the
original CSRF/source boundaries. Author tests/imports/syntax/type/browser/build
execution are NOT_RUN. Review predecessors and their actual fixes before
retargeting and verifying the final combined head. Template/voucher selection,
controlled mappings and actual native atomic remint remain separate; full
product acceptance stays OPEN.
