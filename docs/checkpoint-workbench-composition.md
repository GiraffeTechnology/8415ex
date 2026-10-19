# Workbench composition from a saved EX generation

`compose_checkpoint_workbench` connects the original checkpoint loader to the
existing serialized workbench factory. It constructs one restored access object
and uses it for the primary binding and every explicitly selected detail binding.
The original gas controller, registration-source controller, gateway options,
remint reader and reference feed are passed through unchanged. The application
supplies its current source identity and existing port configuration.

Missing saved state is reported as unavailable; no sample receipt or successful
empty recovery is substituted. Selected receipt identities must exist in that
same saved state before a socket is bound. Construction does not start serving,
enquire a command or execute a wallet operation. Current deployment source labels
remain distinct from the checkpoint's recorded source identity. Construction is
not evidence that either is the actual externally served artifact.

The returned value retains both the original server and the loaded checkpoint
observation. Its saved generation is not an execution lease. Future domain
commands still use the existing gateway and its execution contract; the
application must separately compose durable writes and original journal
reconciliation. No automatic queued operation or historical session is resumed.

Seven synthetic definitions cover an UNKNOWN direct-boundary return over the six
locale routes, refresh after explicit original-outcome enquiry without resending, shared detail bindings, the
untouched original gateway, missing state and an unknown selected receipt. They
have not been run. Source preparation does not establish browser, installed
server, actual-wallet or complete recovery acceptance.
