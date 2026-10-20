# Single-load original workbench command composition

`compose_checkpointed_command_workbench` calls the existing recovered UI factory
once, then passes its actual loaded serialized EX access and existing primary
gateway to the original application's port builder. This avoids constructing a
command bridge against an old in-memory EX or loading a second checkpoint copy
whose observations could diverge from the pages.

The builder returns the installed `resolve_command`, `enquire_original` and
`execute_original` callbacks. It may explicitly provide `fallback_gateway` when
the original fallback needs binding to the restored access; otherwise the
existing primary gateway remains the fallback. These are trusted application
ports, never HTTP-selected URLs, wallets, accounts or callback names. The host
must bind them to actual original operation/journal mappings and current native
authority. No mapping, endpoint or economic parameter is selected here.
The trusted builder constructs callbacks only; it must not query or execute a
native effect while assembling them.

The primary command surface receives the original checkpointed bridge and
durable workbench gateway. Other NFT detail bindings retain their individual
original gateways, all using the same restored access. Existing unsigned draft,
review, gas, registration, collateral and scenario routes remain on the original
server. An unavailable draft source does not become a global command gate.

Schema initialization on the original operation journal is explicit host work,
not an automatic migration performed by this factory. Construction does not
start serving, enquire or execute a native operation, save a checkpoint or
initialize missing state. Invalid port construction closes the new socket and
propagates without retry. Existing source/runtime and original UNKNOWN
reconciliation contracts remain authoritative.

Seven synthetic regression definitions are authored and not run: exactly one
load and shared writer, original claim/pre-effect command path, locally missing
draft data, preserved registration fallback, independent detail gateways,
resource closure on bad port construction and absent-checkpoint refusal. This
is source integration, not evidence of installed native bindings, actual wallet
execution, browser acceptance or complete persistent recovery.
