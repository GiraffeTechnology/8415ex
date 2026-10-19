# Complete mint specification facts

A receipt declaration alone omits its commodity template, bill terms, original
document and controlled access mapping identifiers, registration deadline and
comparison, issuer, registrar and voucher format. This codec preserves every field
of the existing MintSpecification and its nested original types. It composes the
receipt facts codec with the bounded operational container codec and refuses model
field drift, extra or missing fields and noncanonical encodings.

Original constructors recheck declared commodity fields, required template fields,
registration path, deadline and LT/LTE semantics. Ordered original currency terms
remain inside the receipt. Opaque mapping identifiers are facts, not storage
credentials or a claim that a controlled document has been read or verified.

The codec never calls metadata(), an external verifier, MintDeclarationBook.admit,
a signer or an adapter. Decoded provenance_verified and execution_authorized are
false. A digest, valid constructor or successful decode cannot replace original
schema, privacy, storage or Oracle provenance checks. It neither reconstructs the
mint uniqueness indexes nor installs live Exchange state. Full aggregate recovery,
native journal reconciliation and mutation transaction wiring remain unfinished.

Eight synthetic regression definitions cover exact terms, equality boundaries,
verifier noninvocation, detached records, schema drift, original constructor
refusal and malformed inputs. They have not run. Source preparation performs no
local product imports, syntax/type checks, tests, builds or packaging.
