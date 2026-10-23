# Recovered workbench remint action

`compose_recovered_remint_action` connects the existing bound-remint HTTP
action to the existing checkpoint-loaded workbench. Its action bridge and
unsigned editor use the same newly restored serialized access, selected
receipt and original lock. The original checkpoint object and returned scope
are reused for the pre-effect snapshot; the operation journal and complete
history store remain the exact application-supplied objects.

The original host supplies `OriginalRemintActionInputs`: its existing journal,
history store, operation binding and expected revision, declaration verifier,
bill resolver, native enquiry/execution ports, and optional reviewed draft
options. It also supplies the existing declaration reader and all normal
workbench options. No operation identity, path, provider, account, contract,
signer or scope is selected by this composition. Construction loads the
original checkpoint, binds a listening socket and installs routes; it does not
start serving, read declarations, enquire about native results, initialize
stores, claim operations or execute a native effect.

The normal draft route remains the unsigned editor. The bound action route
shows the configured exact proposal and passes a valid submission through the
existing original digest, durable claim, history and pre-effect snapshot flow.
The original gateway still owns actual business eligibility and atomic
burn/mint. A returned observation is separate from chain confirmation.

Omitting action configuration leaves only `/remint-action` unavailable.
An unavailable declaration reader likewise affects its dependent pages.
Neither case disables the market or independent selectors. Invalid configured
action/receipt wiring closes the newly created socket while preserving the
caller-owned runtime and stores. An absent original checkpoint still follows
the existing loader's unavailable result; no empty replacement store is made.

Six synthetic contracts cover exact restored identity and lazy construction,
six-language navigation, original preimage/history before native execution,
route-local missing inputs, invalid configuration before loading, and socket
cleanup without closing original storage. Author execution is NOT_RUN.
This is source composition, not evidence of installed inputs, live signing,
deployment, public-domain reachability or full PRD acceptance.
