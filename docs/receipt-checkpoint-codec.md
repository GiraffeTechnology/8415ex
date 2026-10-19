# Receipt declaration checkpoint codec

This stage encodes and reconstructs the existing WarehouseReceipt and nested
Asset declaration as canonical private bytes. Every current dataclass field is
covered, including the original NFT0 currency list in its original order and its
reference. Empty legacy currency facts and an absent reference remain empty;
decoding never supplies replacement trading terms. Integer identities and goods
quantities are not converted through floating point.

Decoding requires the exact version, exact field membership, canonical ASCII
JSON, a bounded byte length, and successful original domain validation. Duplicate
keys, floats, boolean integer substitutions, unknown fields and schema drift are
refused. A changed domain dataclass requires an explicit codec revision. There
is no dynamic module loading, pickle, network access, database opening or write.

The decoded value is a declaration, not evidence of current owner, holder,
registration, signature validity or trading eligibility. The result explicitly
reports execution_authorized=false. Its provenance still depends on the caller's
source-bound checkpoint and original authoritative observations. Checksums alone
do not authenticate data against an actor able to rewrite the store.

This is one component codec, not a complete Exchange snapshot or restore. No
authorization/session, intent, escrow, rollback, registration observation, native
adapter or UNKNOWN operation is reconstructed. It is not yet wired into
AggregateCheckpointStore or a running service. No production data or runtime
parameters are selected. Full atomic mutation and domain recovery remain open.

Six synthetic regression methods are authored for full-field round trips,
legacy absence, large integers, schema/duplicate fields, domain/type refusal and
bounded canonical input. They have not been run. No local or Windows product
validation is performed. Publication, permitted QA/CI and runtime acceptance
remain separate steps.
