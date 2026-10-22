# Verified local demo package

This is a standard-library Python zipapp for the existing LOCAL SIMULATION console. It needs Python3.10 or newer and no pip installation, extraction, public listener, provider or credential. It does not install a production service, persist business state, sign, send or prove real browser acceptance.

## Build from the exact reviewed source on Linux

Use an existing approved Linux source root and output area. All output, caches and temporary storage must follow that area's existing storage policy. Do not substitute a server system directory or create an environment.

```sh
SOURCE_HEAD=$(git rev-parse HEAD)
SOURCE_TREE=$(git rev-parse 'HEAD^{tree}')
git diff --exit-code
git diff --cached --exit-code
git archive --format=zip "$SOURCE_HEAD" | python3 -B -m exchange.demo_package build --commit "$SOURCE_HEAD" --tree "$SOURCE_TREE" > "$APPROVED_OUTPUT/demo.pyz"
sha256sum "$APPROVED_OUTPUT/demo.pyz"
```

Require successful pipeline statuses; a shell redirection can leave an empty output on failure. Do not publish that file. The builder returns nonzero with no archive bytes for a refused input. The caller owns staging/publication policy; this tool promises no multi-file atomic installation. Record full commit/tree, command, runtime, exits, time, bytes and SHA256. Confirm the declared commit-to-tree relationship independently in Git; the offline package proves its source tree, not the remote commit object's authenticity. Build twice on the same runtime to compare bytes; do not assume compression bytes match across every runtime version.

The input source ZIP is capped at16MiB/512 members/8MiB uncompressed. Duplicate, unsafe, encrypted, symlink and non-regular members are refused; reserved launcher/manifest paths and missing runtime entries are refused. All source members are retained verbatim, including source tests/docs, with deterministic member metadata. The manifest binds each size/hash and the full Git tree; generated launcher and manifest are additional members. The verifier permits only those two fixed generated paths in addition to the512 source files (514 regular files total); source input is still limited to512. Directory metadata retains its separate128-entry budget. The16MiB archive and8MiB content limits apply to both source and generated kit archives.

## Verify before launch

Use the SHA256 from the independently trusted exact-version delivery receipt, not a hash supplied by an untrusted archive itself. On the approved Linux runtime:

```sh
EX_DEMO_SHA256="$VERIFIED_RECEIPT_SHA256" python3 -B "$APPROVED_OUTPUT/demo.pyz" --verify
EX_DEMO_SHA256="$VERIFIED_RECEIPT_SHA256" python3 -B "$APPROVED_OUTPUT/demo.pyz" --port 8415
```

The launcher refuses an absent/mismatching external digest before importing application modules. It disables bytecode writes; package verification reads ZIP members without extracting them. It then checks the exact launcher, manifest inventory, hashes, LOCAL_SIMULATION/NOT_RUN labels and reconstructed tree. The only launch options are verify and port. Users cannot override commit/tree labels or set a public host. Choose an already approved free port without altering other services. Visit the printed loopback URL in an already approved browser path; no tunnel, firewall or public binding is created here.

A successful verify prints the manifest without starting the server. Running starts the existing six-scenario console; stop with Ctrl-C to release its listener. Its16-run RAM history is lost on shutdown. Reusing an old package means reusing its exact old source and evidence; never relabel it as a later commit. Recovery is to verify and use the retained exact package, not restore credentials or replay unknown financial operations.

## Validation boundaries

Run only affected package checks after changes:

```sh
python3 -B -m unittest integration.test_demo_package -v
```

Tests cover deterministic bytes, source inventory, digest-first refusal, content/bootstrap/manifest tampering, dangerous paths, duplicate members, links, expansion limits, bootstrap verification and fixed launch identity. In-process bootstrap mocks prove that bounded entry behavior; they are not a fresh installed process or a real browser. Separate delivery evidence may exercise the actual ZIP importer over an anonymous locked-memory file, with its exact source/hash and cleanup recorded; that is not installation on a persistent production target. Real deployment, provider/UI signing, chain, durable recovery and final acceptance remain NOT_RUN.
