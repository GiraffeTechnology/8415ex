# Optional pages on the recovered original workbench

`compose_recovered_workbench_ui` extends the existing checkpoint workbench
composition. The original loader reads the saved generation and creates one
serialized EX access; primary, detail and optional unsigned-editor bindings all
share that same access. Original runtime controllers, gas/source pages, review,
gateway, clock and source identity are forwarded unchanged.

When an original declaration reader is supplied, the existing unsigned draft
editor is mounted first. The existing collateral and scenario selectors then
wrap that handler, retaining its GET/POST behavior and navigation. Reversing
this order would let the editor replace the selector handlers. An omitted draft
reader leaves the editor unmounted; its absence or later unavailability is not
a new readiness or execution gate for the other pages.

Construction does not start serving, read a declaration, call a gateway, save a
checkpoint, initialize missing state, restore wallet authority or change native
effects. Missing checkpoints retain the original unavailable result rather than
becoming empty fixtures. A mounting failure closes the constructed HTTP socket
and propagates without retry. The application still supplies the actual runtime
bindings; this composition neither selects deployment parameters nor proves
installed/native recovery or real remint acceptance.

Seven synthetic regression definitions cover one restored access/no mount-time
effects, six-language route coexistence, original unsigned preview, locally
unavailable/omitted declaration readers, unchanged gateway and invalid/missing
inputs. These definitions have not been run. Actual current-source CI, browser,
persistent recovery and native business execution require separate evidence.
