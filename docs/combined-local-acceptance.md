# Combined local acceptance

This combination retains the accepted evidence/publication implementation and
joins the already submitted local delivery, route contracts, HTTP console,
standalone package and captured-material exporter. It is local simulation only.

## Source composition

- Accepted evidence baseline: d2885abe83cc6f4a95fa53d43a168c96ec60323b
- Package/console lineage: c3d8007486473acd23b5f645d8c3437e1d8b9ea5
- Captured-material exporter: 5ffc39ad12ee9e8514698b3cd713521122c6e702

The package lineage includes the joining-contract and service-boundary tests and
the latest console early-EOF refusal. The exporter branched before that refusal;
its three added files are joined without replacing the newer console. Existing
scenario source and evidence validation remain the accepted versions. Both
workflow responsibilities survive: integration discovery and externally captured
final CLI status/full logs. No additional trigger or permission is required.

The current checkout's `git rev-parse HEAD` and `HEAD^{tree}` identify the new
combination. Its results must not be labelled with any of the input commits or
replaced by a concatenation of their earlier green logs.

## Focused reproduction on Linux

Run from a clean, committed checkout using the standard library:

    python3 -B -m unittest exchange.tests.test_delivery exchange.tests.test_stage5 exchange.tests.test_stage5_routes -v
    python3 -B -m unittest discover -s integration -t . -v

The combined-flow test builds from the exact committed source archive. It imports
the builder from that archive, verifies and launches the resulting standalone
zipapp as a real child process, captures six distinct scenario records through
loopback HTTP, checks replay does not create another run, and imports the
exporter from that same zipapp. Export does not execute the scenarios again.
Every captured record and exported member must retain the same source identity,
run identity, observations and failures. Archive member sizes and hashes are
verified against the actual bytes.

To retain the new combined-flow artifacts, set `EX_COMBINED_EVIDENCE_DIR` to a
fresh directory outside the source repository when running the combined-flow
test. Do not treat an output directory's existence as a successful result;
check the process exit, test log and verified member digests.

The ordinary scenario CLI still requires clean source and output destinations
outside its source roots. Its published outputs describe calculation only;
external process capture supplies final status and full stream evidence. Read
`scenarios/README.md` for rollback, provenance and historical-citation limits.

## Acceptance limits

The local HTTP journey is not browser rendering, a real wallet/provider or chain
acceptance. The server binds loopback and retains bounded RAM state, not durable
process recovery. Exported slides/captions/scenes are editable rendering inputs,
not an accepted PPTX or film. A source label and archive hash do not independently
establish execution; the fresh subprocess receipts and observations are separate.

All thirteen real-evidence slots and T-35 through T-38 remain NOT_RUN. No
production deployment, credentials, signing or real transaction is performed.
This combination targets the existing Stage4 stack only and does not authorize
moving an older restricted stack into another branch or merging it to main.
