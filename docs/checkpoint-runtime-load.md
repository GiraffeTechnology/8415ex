# Loading an original checkpoint generation

`load_exchange_checkpoint` connects the existing complete-snapshot checkpoint
reader to EX fact rehydration. It reads exactly one row through the original
store's source identity, component digest and durable-storage checks. That same
row's immutable bytes are reconstructed into a new serialized Exchange access.
The returned observation retains the original scope, generation, digest and
configured source identity; no second read silently substitutes another version.

The application supplies the existing checkpoint adapter and a fresh current
runtime template. A missing row returns `None`. No database is opened or
initialized by this loader, no fallback source is selected, and no current
writer is replaced. Errors propagate without retry. The observed generation is
not a lease: later writes still use the original generation CAS. Rehydration
does not restore historical wallet connections or dispatch a queued operation.

Six synthetic regression definitions cover missing state, a reopened file-backed
database, an actual child interpreter reading the saved facts, mismatched source
identity, foreign transactions and a corrupt payload. They have not been run.
The child definition deliberately has no native payment or asset-control ports
and only reads reconstructed observations. It therefore cannot demonstrate
native effect reconciliation or complete business restart, and no such acceptance
is claimed. Native journals and the current application's original execution
ports remain separate integration responsibilities.
