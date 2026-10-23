# Original operation enquiry after workbench recovery

A restored workbench can now mount the existing `/operation-observation` route
without an available current replacement draft. The host calls
`compose_recovered_operation_observation` with its original checkpoint, instance
scope, runtime and receipt, plus `OriginalOperationObservationInputs` containing
the original journal, operation binding and read-only native enquiry. Optional
retained remint history remains the original store.

The constructor restores once through the existing recovered remint composition.
Its observation bridge uses that exact restored access and checkpoint scope.
Construction does not call the enquiry, claim an operation, persist a snapshot,
reconcile UNKNOWN, execute a gate or create a replacement store. A mismatched
receipt refuses mounting and closes only the newly constructed listening socket.
All original stores and ports remain caller-owned.

Existing remint action and draft options may still be supplied independently.
No draft reader is needed for enquiry. Missing observation configuration produces
a route-local unavailable response; it does not disable market pages or other
configured routes. Failed current draft reads likewise do not remove the
independently configured original-operation enquiry.

The existing observation handler supplies six-language navigation, exact Host
checks and finite identity-free local/native/history/checkpoint observations.
HTTP cannot select an operation, journal or provider. POST remains refused. A
native report, absent local record or retained preimage does not prove execution,
settlement or finality, and permits neither replay nor funds release.

This source increment supports EX-REMINT-04/05, EX-INV-04, EX-NFR-09/11 and the
recovery/UI portions of T-66/67/77/80/83/84. Six composition contracts are authored
in `integration/test_recovered_operation_observation.py`. Author execution,
runtime mounting, browser interaction, deployment and native/chain acceptance
remain NOT_RUN; existing workflow checks and independent exact-head review remain
required. Actual installed store, scope, runtime and enquiry inputs must be
supplied by the original application. This module invents no live inputs.
