# Original bound-remint HTTP action

`mount_remint_draft_action` adds `/remint-action` to the existing remint
workbench handler before serving. It retains the original routes, server,
serialized access and receipt. Its optional `RemintDraftActionBinding` is
configured by the original application with an existing operation scope,
expected journal revision, reviewed draft options, verifier, original bill
resolver, enquiry/execution ports and history store. No operation ID, provider,
wallet, contract, account or store is selected by the page.

GET displays the complete existing editor projection over one detached original
read. Its preview controls are disabled on this action page; editing remains
at the original draft route. The action form carries only CSRF, locale, original
revision and a local full-facts stale-form hash. This hash is not a declaration
signature, signing ABI or native operation digest. The private typed declarations
and original operation/journal identities are not rendered.

POST requires the original exact Host/Origin and CSRF context, an unambiguous
bounded four-field form, and the same current full proposal and original
revision. It passes the detached original pair through the existing edited-draft
and checkpointed-remint flow. Existing declaration verification, original
history digest, bill mapping, durable UNKNOWN claim, complete history and
pre-effect snapshot remain authoritative. The original gateway retains actual
Holder possession/Holder=Owner, session/grant, gas, signing and atomic burn/mint
checks. These are the original operation semantics, not another human approval,
cleanup or global-readiness condition.

A lost native reply is reported as unknown without exposing its raw error.
The same bound form re-enters the existing original enquiry/no-replay path;
it does not manufacture a new native operation. Original result enquiry stays
separate and must not require current draft availability. A response of 202
means that the original gateway returned an observation, not burn/mint finality
or product acceptance. Existing declaration-source failure affects this action
only; other read routes remain available. Mounting without a configured action
returns unavailable for this route and does not initialize replacement state.

Eight synthetic HTTP contracts cover the six locale projections, exact native
flow, stale form/original digest, CSRF/origin, unavailable source, lost-reply
no-replay and existing-route preservation. Author execution is NOT_RUN.
The source enables an action only when explicitly mounted with its actual
original operation binding. This stage makes no installation, public-domain,
signature, funds or chain-acceptance claim.
