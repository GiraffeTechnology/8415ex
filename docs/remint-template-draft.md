# Original template and voucher choices in the unsigned draft

The existing remint editor optionally consumes
read_replacement_choices(receipt_id), forwarded by recovered workbench composition
as read_draft_replacement_choices. It returns at most 31 alternatives, each a
tuple of a nonsecret public label and a complete original MintSpecification.
The original seed is included automatically as the default. Callbacks are
read only inside the existing serialized access; construction calls none.

Alternatives may differ only in the commodity template, registration voucher
and matching path, and their public attribute defaults. Original receipt/asset,
account, mint time, scalar fields, currency set/reference and private
document/access mappings remain fixed to the host seed. The request cannot
supply a template JSON, provider, ABI, account, mapping or grant.

A six-language separate POST form loads a selected original draft. It clearly
states that loading resets unsaved proposed edits to the selected defaults.
The response uses that template's attribute names and required fields; subsequent
ordinary preview posts retain the selected choice. It does not reinterpret old
template attributes as fields of the new schema. GET returns the original seed.

Choice keys hash public template/voucher descriptions only, allowing the same
choice to survive source list reordering while a changed public definition has
a different key. This is consistency metadata, not a private fact hash, Wallet
signing digest, source attestation, metadata proof or approval. Duplicate public
definitions and unknown/stale keys are refused. The page never exposes private
declaration objects or raw diagnostics.

Original complete-body, field-count, Origin/CSRF, escaping/privacy and typed
declaration rules remain. Without the optional reader the existing editor is
unchanged; other pages and already-authorized execution gain no prerequisite.
No preview is saved; no grant, signature, provider request, burn, mint or funds
effect occurs. Controlled mapping changes and native atomic execution still
belong to the original implementation and cannot be fabricated by this form.

This stage is stacked after currency, scalar and attribute editing. Eight
regression definitions cover six locales/privacy, original typed selection,
choice/preview/reset, changed and duplicate keys, fixed identity/mapping/scalar
boundaries, original HTTP protection, legacy absence and no construction-time
callback. Author tests, imports, syntax/type/browser/build execution are NOT_RUN.
Review/repair predecessors, reconcile the actual combined source and retarget
before current-head CI/review. Real host option bindings and full native/UI
acceptance remain OPEN.
