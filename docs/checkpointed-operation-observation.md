# Original operation enquiry with retained preimage availability

`observe_checkpointed_operation` is an internal installed reader composition.
It first calls the existing original operation observation path. Remint uses
`observe_remint`, preserving optional complete history availability. Other
original operation kinds use the original durable journal's `observe` method.
Original identity conflicts and native enquiry failures retain their behavior.

Only after the original enquiry returns does the reader inspect the existing
operation-specific snapshot key. A readable checkpoint with the same original
receipt and NFT asset is reported as FOUND with its generation and digest.
Missing historical preimages are ABSENT, and storage, decoding or binding faults
are UNAVAILABLE without raw diagnostics or partial facts. Neither case hides
the original observation or creates a new prerequisite for querying UNKNOWN.

The checkpoint summary does not include raw snapshot bytes, decoded private
authorization/session facts or a new execution decision. It is availability
evidence about retained EX facts before the native gate, not proof of a native
outcome, current authorization, transaction finality or complete recovery.
The two independent stores are not presented as an atomic combined read.

No current live Exchange capture, replacement mint declaration, session refresh,
claim, checkpoint save, history repair, native execution, reconciliation or
nonce/reservation release occurs here. No public HTTP route or service is
created. The installed application supplies its existing authenticated original
reader and the same explicit bridge/store bindings; no provider is guessed.

Eight synthetic regression definitions cover no-write absence, metadata-only
availability, legacy UNKNOWN, unavailable storage/history, native failure,
identity conflict and continued readback after live schema changes. These
definitions have not been run locally and establish no installed acceptance.
