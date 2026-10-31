# Original service host entry

`exchange.original_service_host.create_original_service_binding()` is the
zero-argument export required by the existing pinned `8415ex-host/1` loader.
It delegates to `compose_production_service`; it does not replace that library
with a simulated runtime or turn missing inputs into an empty successful host.

The application integration owner supplies the reviewed, installed source
module `exchange.original_provider_bindings` with
`load_original_host_inputs() -> OriginalHostInputs`. This is a source-owned
composition contract, not a JSON module path, dynamic discovery API, new
authentication system, or instruction for an end user to write host code.
The module must be included in the independently approved installed source.
Source identity and callable shape do not themselves prove business authority.

`OriginalHostInputs` supplies the existing validated production configuration,
existing aggregate store, `RuntimeCapabilities`, `NativeAuthorityPorts`, deferred
profile/verifier, original mint verifier, actual request authenticator, original
journal transport and same-held-capability function, gas page and registration
sources. Optional feature arguments retain the existing composition's allowlist.
The source owner must identify actual provider implementations and their
approved runtime references. No provider binding is included merely because
this entry point compiles or its boundary tests pass.

The existing constructor continues to enforce source/scope/components,
generation/digest, a genuine receipt, current grants and sessions, the identical
mint verifier, original journal authority and an existing-only attempt store.
Missing provider code reports `EX_SERVICE_HOST_INPUTS_UNAVAILABLE`; wrong bundle
types and failed construction are refused without printing provider exceptions.
`original_host_requirements()` lists static input names without reading config,
credentials, process environment, databases or remote services.

For an admitted installed candidate, the ordinary outer host configuration pins
the absolute installed path of this module, its SHA256, and that candidate's
exact commit/tree. Do not point an unchanged older installation at a new file
or call the constructor library itself a complete host. The unchanged loader
still verifies installation identity and the final binding before serving.

The new tests use isolated synthetic authorities only to verify this adapter's
refusal and propagation boundaries. They are not deployment, provider authority,
live-chain, or complete product acceptance. The adapter does not initialize a
database, issue credentials, restore snapshot sessions, create grants, log in,
broadcast, bind a listener, or enable public access.
