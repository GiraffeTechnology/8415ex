# Direct-return crash-window regression definitions

The synthetic child fixture uses two separate file-backed SQLite databases:
one original EX checkpoint store and a deliberately fake external-effect
journal. Both use synchronous=FULL. The fixture accepts only an explicit
temporary test directory with its test-only marker; it selects no provider,
network, credential, live database or deployment target.

The original simulated payment and asset-control adapters create result records.
The fake journal commits each record before optionally ending the child with
os._exit(71), before the result updates EX or reaches the following checkpoint.
Another interpreter then loads the original checkpoint and queries these same
synthetic operation keys through the original rollback method. A duplicate send
of an already-recorded key raises instead of silently succeeding.

Four definitions cover a crash after a durable direct D-to-A return, a crash
after the first original-buyer refund, UNKNOWN observed across independent
processes until that same original observation changes, and completed-state
reload without another effect. The expected asset-control record is one direct
return, not a sequence of ordinary intermediate-wallet transfers.

These are synthetic process-boundary tests, not
native wallet or production journal evidence, actual transaction execution,
cross-database atomicity or full product acceptance. The fake record update used
to resolve UNKNOWN is confined to temporary test data and is not an operational
reconciliation method.

## Running the synthetic process regressions

From the checkout root, run the parent regression suite:

```sh
python3 -B -m unittest integration.test_direct_return_process_recovery
```

The suite creates an isolated temporary directory, writes its `TEST-ONLY.txt`
marker and initializes both synthetic databases before invoking the child.
The child protocol used by that suite is:

```sh
python3 -B -m integration.direct_return_process_fixture TEMPORARY_FIXTURE_DIRECTORY advance
```

Its two positional arguments are the initialized temporary fixture directory
and one of `advance`, `crash-payment`, `crash-asset` or `unknown-asset`.
A crash mode intentionally exits with code 71 immediately after its synthetic
record is committed. Successful `advance` emits the completion, owner, effect
counts and checkpoint generation as JSON. The child is a test helper, not a
service launcher; use the parent suite to prepare its temporary state. Never
point this fixture at application or native-journal databases.
