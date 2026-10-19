# CI bootstrap

This bootstrap uses Python 3.10+ and its standard library. It does not select the application stack or implement trading, settlement, wallet connections, or an alternative ArtFi module.

## Fixed checks

Run from an exact, independently verified repository commit. GitHub Actions CI and other execution paths follow the current [AGENTS.md](../AGENTS.md) instructions. Record the actual executor. Storage persistence and product acceptance remain separate outcomes; this fixture does not verify mounts.

The controller supplies an existing canonical `APPROVED_TEST_ROOT`. The tests fail if `BOOTSTRAP_TEST_ROOT` is missing; they never silently choose the system temporary directory. Python bytecode writes are disabled.

```sh
BOOTSTRAP_TEST_ROOT="$APPROVED_TEST_ROOT" python3 -B -m unittest discover -s ci/tests -v
```

The controller creates a fresh empty canonical `APPROVED_OUTPUT_DIR` in the explicit selected workspace before each smoke invocation, and supplies the identities below from trusted state:

```sh
python3 -B -m ci.smoke \
  --repository GiraffeTechnology/8415ex \
  --commit-sha "$COMMIT_SHA" \
  --tree-sha "$TREE_SHA" \
  --config-sha256 "$CONFIG_SHA256" \
  --run-id "$RUN_ID" \
  --output-dir "$APPROVED_OUTPUT_DIR" \
  --mode success
```

- `COMMIT_SHA` and `TREE_SHA`: full lowercase 40-character Git identities independently resolved from the requested repository.
- `CONFIG_SHA256`: SHA-256 of the reviewed controller configuration, including the fixed commands, runtime, storage and isolation policy. It is not a self-approved repository setting.
- `RUN_ID`: a controller-issued identifier unique to this attempt, including retries.
- `--mode failure`: the deliberate negative probe; returns exit code 1 and writes a failure manifest with no success artifact.
- Invalid input or filesystem errors return exit code 2. Success returns 0.
- A repeated invocation cannot overwrite an existing output. Use a fresh output directory and unique run ID for a new attempt.

The smoke command writes only inside its explicit output directory:
- `smoke.txt`: deterministic harmless bytes, success only.
- `smoke-manifest.json`: schema version, fixture name, supplied run identity, fixture outcome, and relative artifact path / byte count / SHA-256.

## Result contract

`ci.evidence.validate_result` validates a terminal result against an independently supplied `expected_identity`, `current_run_id`, and `expected_prefix`. Its required fields are:

- `schema_version`: integer 1.
- `check_name`: `8415ex/bootstrap`.
- `identity`: exactly `repository`, `commit_sha`, `tree_sha`, `config_sha256`, and `run_id`.
- `outcome`: `success`, `failure`, `timeout`, or `cancelled`.
- `started_at` / `finished_at`: ordered ISO-8601 UTC timestamps ending in Z.
- `source_object` / `log_object`: private persisted object references.
- `stages`: exactly `unit-tests` and `smoke`, each recording an `outcome` and `exit_code`.
- `artifacts`: a list of private persisted object references; success requires at least one.

Every object reference contains exactly `bucket` (`giraffe`), canonical relative `key`, nonempty `object_id`, and lowercase `sha256`. Bucket names are case-sensitive: the verified bucket is `giraffe`; `Giraffe` is not accepted. The controller requires an endpoint and project prefix. No endpoint, prefix, credential or storage mount is configured here. The controller must pass its independently authorized project prefix as the required `expected_prefix` argument. The validator rejects source, log and artifact keys outside that exact directory prefix, including similarly named sibling prefixes. A single trailing slash is accepted; empty, absolute or traversal prefixes are rejected. The controller must still independently verify object identity, private access and downloaded bytes; prefix validation does not establish bucket permissions. `verify_sha256` checks bytes already obtained through an authorized route.

Stage outcomes are `passed` (exit 0), `failed` (nonzero integer exit), or `timeout`, `cancelled`, `not_run` (null exit). A success result requires both required stages to pass. Each negative terminal result requires corresponding negative stage evidence. Pending is a controller lifecycle state and cannot be accepted as terminal evidence. Missing stages, obsolete attempts, mismatched identities and incomplete artifacts cannot pass.

The synthetic examples in `ci/tests/test_evidence.py` describe the version-one contract; their identities and storage references are deliberately fictitious and must never be used as execution evidence.

## Trust boundary and acceptance

Repository code, test results and the smoke manifest are untrusted claims. The external controller owns the reviewed policy, resolves and verifies the source snapshot, records exact executed arguments and Python version, enforces limits, independently verifies outputs, and persists source / redacted logs / artifacts / evidence in approved private storage. This bootstrap has no third-party dependencies or dependency lockfile.

Only the trusted controller may report to GitHub. Repository execution must not receive status-writing, repository-management, storage-management or deployment credentials. Import this validator into a controller only from a separately reviewed, pinned version; executing a candidate's validator does not make the candidate trustworthy.

The freshness check is a pure comparison, not an atomic publication mechanism. The controller must serialize or compare-and-swap the current run when posting results so an older retry cannot overwrite a newer result. It must recheck the candidate commit before accepting a result. It is also responsible for starting pending status and recording interrupted attempts truthfully.

Do not call the CI foundation complete until the actual approved route demonstrates:
1. Exact GitHub source SHA/tree bound to a verified private source object.
2. Recorded execution identity and explicit writable paths, with local synthetic results distinguished from infrastructure and production acceptance.
3. A deliberate failed run and a succeeding run, with truthful same-SHA GitHub feedback.
4. Rejection of stale, mismatched, interrupted, timed-out and cancelled results.
5. Persisted logs, manifests and matching source/artifact checksums.
6. Any separately authorized merge followed by validation of the actual merged commit.

These files configure no runner, credentials, permissions, production service or deployment. Unit-test success alone would not establish any of the infrastructure acceptance claims above.
