# Unsigned replacement business term editing

`edit_remint_draft` edits the original typed `MintSpecification` replacement
supplied by the installed application. Specification updates cover its template,
complete bill terms, commodity attributes, issuer/registrar/storage terms,
controlled document mappings, registration cutoff/comparison and voucher format.
Receipt business updates cover commodity description/quantity/unit, receipt
number, registration path, trade cutoff and the new NFT's currency declaration.
The original typed constructors continue to validate their existing contracts.

The original NFT specification and replacement seed are not mutated. New terms
can add, delete or revise complete business clauses or optional attributes while
retaining required fields. Updating a replacement NFT currency set does not
change the old NFT's immutable currency set. Identity and custody fields such as
asset, receipt ID, mint timestamp and origin account stay with the application
seed and cannot be overwritten through the business editing groups.

The result contains the complete typed proposed specification, detached
original-to-proposed change records and local fact hashes. These hashes identify
encoded draft facts; they are not a signing ABI, verified document digest,
authorization, submission result or proof of a real minted asset. The editor
does not allocate or predict the on-chain replacement token ID.

This optional internal editor adds no approval, holder qualification, cleanup or
execution prerequisite. It performs no metadata verification, signature request,
claim, admission, fund reservation or native execution. The existing original
remint preparation/gateway remains responsible for its actual complete document
binding and original execution conditions. Empty edits are valid unsigned
drafts, including before a replacement NFT identity is established.

This stage supplies the typed editing operation; it does not claim a mounted
complete editing UI, verified signed source, active replacement NFT, transaction
or full remint acceptance. Original identity-excluding presentation, immutable
old history and actual native result binding remain necessary integration work.
Eight synthetic regression definitions have not been executed locally.
