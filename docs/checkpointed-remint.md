# Remint history and EX pre-effect snapshot composition

`invoke_checkpointed_remint` composes the original `invoke_remint` with the
published snapshot bridge's access object, store and operation-specific key.
It preserves the original terms verifier, original bill resolver, scope checks,
enquiry, receipt revision CAS and single durable UNKNOWN claim. It does not call
`bridge.invoke`, so it does not nest or duplicate operation claims.

For a newly claimed operation the sequence is: original durable claim, original
complete remint history save, one immutable EX snapshot capture and write-once
save, then the original checked gateway. The captured receipt must equal the old
declaration receipt. Replacement NFTs may retain the stable receipt identifier;
the original remint terms contract continues to require a different NFT asset.
No additional remint qualification or business cleanup prerequisite is added.

The same serialized access lock covers this sequence. The installed host must
use that same access instance for all participating EX writers and observations.
Raw Exchange references and a second wrapper remain outside this boundary.

A history failure never reaches snapshot capture or the native gateway. A
snapshot refusal or uncertain acknowledgement never reaches the native gateway;
the original claim remains UNKNOWN and any retained history is preserved. A
native timeout retains the claim, history and snapshot. Existing claims use the
original enquiry path without a second pre-effect save or native replay.
Original `observe_remint` remains available without current snapshot schema or
replacement terms, and grants no retry, release or terminal reconciliation.

This is source composition, not an installed gateway, execution authorization,
cross-database transaction, atomic native burn/mint proof or complete recovery.
The original gateway still owns Holder=Owner checks, signatures, grants, gas,
funds, nonce and actual atomic execution. CTYun transaction submission and chain
writes remain prohibited; no real transaction is part of these synthetic test
definitions. Eight new regression definitions have not been executed locally.
