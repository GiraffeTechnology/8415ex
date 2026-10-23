# Original saved-state foreground service entry

`serve_recovered_workbench_ui` in `exchange.recovered_workbench_serve` connects
the existing checkpoint UI composition to its original HTTP serving loop.
The original application calls this entry with the same checkpoint, scope,
runtime, receipt and keyword options used by `compose_recovered_operation_observation`.
The actual existing listen port, source commit/tree, gas page, registration
sources, gateway and optional readers come from that application's configuration.

The entry loads the original saved generation once and runs the resulting
server once in the foreground. It returns the loaded composition when the loop
returns normally. Interrupts and other loop errors propagate after the composed
server socket is closed. The original application retains ownership of its
store, runtime controllers, wallet connections and reference-feed lifecycle.

No database initialization, empty-state replacement, checkpoint migration,
provider selection, reference refresh, transaction retry or background worker
is added. A missing checkpoint fails through the original loader before a
server loop begins. An omitted optional draft reader leaves that editor absent
without preventing the other original routes from being served. The entry now
mounts the original remint action and operation-enquiry compositions on that same
restored access. `remint_action_inputs` and `operation_observation_inputs` are
independent original host inputs, both optional. An absent action or enquiry
configuration produces an unavailable response only for its own route. Current
draft availability is not an enquiry prerequisite; HTTP cannot supply operation
scope, journals, native ports or deployment configuration.

This is a callable application entry, not a new configuration format or a
replacement command for an existing installation. It does not infer private
runtime objects from command-line strings. An original host must pass its
actual configured objects. The existing explicit empty-catalogue entry remains
a distinct read-only composition.

Four synthetic contracts exercise a real recovered HTTP page, foreground
interrupt and error cleanup, original-store retention, and missing-checkpoint
refusal. They do not select a live provider or call a native wallet. Author
execution is NOT_RUN; applicable exact-source checks belong to the existing
review workflow. Published source and a declared source identity do not
establish an installed service, public route, original live API/store binding
or native financial/chain acceptance.
\nFour additional foreground contracts in
`integration/test_recovered_operation_serve.py` cover actual enquiry without a
current draft, shared restored access for action and enquiry, route-local missing
configuration and generic native-enquiry failures. These authored contracts are
NOT_RUN by the author. Existing interrupt, loop-error and store-ownership
contracts remain applicable. The caller still owns every external service and
must supply its actual original bindings; no deployed service is switched by
this source change.\n