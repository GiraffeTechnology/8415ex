# Original operation enquiry after restart

The optional `/operation-observation` page queries one existing original
operation bound by the application. Unlike process-local recent gateway rows,
it calls the original durable journal observation path. Unlike a remint action
form, it needs no current mint declarations, draft, new fee reservation or
execution callback. The retained original operation identity must already be
available to the host; the browser cannot select or enumerate operations.

`CheckpointedOperationObservationBinding` receives the original checkpointed
bridge, exact operation scope, and installed read-only enquiry port. Optional
original remint history is specific to remint observations.
`mount_checkpointed_operation_observation` composes this reader with an
existing workbench before serving. Its access and receipt must match that
workbench. Omitted configuration leaves this page unavailable without blocking
other routes. No polling loop or scheduler is started.

GET with the exact original Host and one supported locale invokes the original
enquiry under the original serialized lock. The existing
`observe_checkpointed_operation` queries native state before trying retained
history or preimage metadata. Unavailable retained history, a missing old
preimage or an unsupported new live EX schema must not hide an otherwise
available native enquiry. Native failure is unavailable, never inferred
absence. POST and query-selected operation identities are refused.

The six-language page projects four independent finite observations: local EX
claim, reported native status, retained remint-history availability and
pre-effect-checkpoint availability. It never renders operation/scope identities,
wallet addresses, proof references, raw native errors, snapshots or history
contents. Unrecognised native status is unknown. No record returned by an
enquiry is distinct from no local claim. Local reconciliation does not upgrade
a native reply into settlement or finality.

This read never claims an operation, writes a checkpoint/history/journal,
reconciles UNKNOWN, sends, retries, releases funds or allocates a new operation.
The original gateway's authentication and scope authority remain its own.
The page is an observation, not burn/mint or full business acceptance.

Seven synthetic HTTP contracts cover locale/privacy and no writes, old UNKNOWN
with unavailable retained state and new live schema, native outage isolation,
read-only/HTTP scope refusal, optional/idempotent mount, original identity
conflicts, and separate local reconciliation/native absence. Author execution
is NOT_RUN. No installed reader, current provider response, deployment or
live-chain acceptance is claimed by this source increment.
