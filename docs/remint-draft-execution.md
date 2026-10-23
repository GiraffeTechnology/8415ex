# Edited replacement terms and the original durable remint gate

The trusted application port `RemintDraftEditorBinding.draft_specifications`
returns the complete old declaration and proposed replacement from the same
original reader invocation and editor validation. These are private typed
objects. Existing `draft` results and rendered pages retain their prior shape;
no old declaration or private identity is added to HTTP output.

`invoke_draft_remint` joins that pair to `invoke_checkpointed_remint` on the
same serialized access and receipt. The original application supplies the
exact previously bound operation scope, expected revision, declaration verifier,
original bill resolver, enquiry/execution ports and history store. The complete
edited history must match the original operation digest. A stale preview digest
cannot authorize a different proposal.

The original declaration verifier still validates the proposed declaration.
Unsigned editing is not a signature, metadata verification, execution authority
or a source of native operation identities. The original gateway retains its
Holder possession/Holder=Owner, authority, gas, contract and journal semantics.
This composition adds no human approval or cleanup, refund, custody or global
readiness condition. It does not select a provider, wallet, contract or store.

The editor and durable call share the existing reentrant access lock. Existing
complete history persistence, pre-effect snapshot and durable UNKNOWN claim
precede the original effect. Lost replies retain their original enquiry-only
recovery. Current declaration availability is not required by the separate
existing read-only operation-observation path.

No HTTP execution endpoint or submit control is enabled by this stage. The
existing preview remains unsigned and non-executing. The original host can use
the port when its actual operation, verifier and runtime bindings are present;
their installed identity and live outcome remain separate evidence.

Six synthetic contracts cover the exact edited history, one source read,
stale-digest refusal, foreign access/receipt refusal, missing-source isolation,
lost-reply no-replay, and the unchanged non-executing preview. Author execution
is NOT_RUN. Existing exact-source review/CI, actual UI submission wiring,
installed runtime, signing and atomic native burn/mint acceptance remain open.
