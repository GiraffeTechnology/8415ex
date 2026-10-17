# Original workbench runtime observations

This initial feature adds measured call duration, call-exception ratio, in-flight
calls, and current pending/overdue registration counts to the existing workbench.
It implements runtime observation support, not a performance acceptance report.
No throughput or latency SLA is assumed. No product tests were run by the author.

## Compose with the existing host

Use `ObservedRuntimeBinding` and `ObservedWorkbenchServer` from
`exchange.runtime_metrics` in the host that already creates the original Exchange
and checked wallet/task-journal gateway. Pass the same exchange, receipt id,
authorization ids, source identity and gateway. Do not construct a second ledger,
provider, signing service, journal or scenario runtime for this feature.

```python
binding = ObservedRuntimeBinding(
    existing_exchange, receipt_id,
    authorization_ids=original_authorization_ids,
    run=original_run_identity,
    gateway=original_checked_gateway,
)
server = ObservedWorkbenchServer(binding, port=approved_port,
                                 commit=full_commit, tree=full_tree)
```

The original loopback host policy, port policy, form fields, CSRF checks and
command path remain in WorkbenchServer/WorkbenchHandler. Existing original
wallet and journal authorization checks must still be provided by the host.
With no gateway, actions remain NOT_CONFIGURED. Metrics never enable an action.
The added panel appears on `/queue` and `/evidence`; `/api/snapshot` exposes the
same counters in `performance`. Reading them dispatches no operation.

## Interpret the observations

- `returned` means only that the original method returned. A pending, unknown or
  rejected result remains that result; no success counter is inferred.
- `raisedRatio` counts method exceptions divided by completed method calls.
  It is not a business failure ratio or a confirmed chain-failure count.
- Timings use a monotonic clock and milliseconds. The nearest-rank p95, mean,
  min and max use only the bounded recent window for that method. Lifetime
  counts and window counts are separate. An invalid clock reading records
  `untimed`, without inventing zero duration or preventing the operation.
- `activeCalls` and `highWaterCalls` describe calls observed by this process.
  Pending and overdue registration counts come from the current domain view;
  they are not a durable executor backlog, load-generator result or throughput.
- Counters reset on process restart. They do not supply durable recovery,
  outcome reconciliation, authority, deployment readiness or chain acceptance.
- Arguments, receipt contents, journal keys, exception messages, transaction
  results and credentials are not retained by the metrics collector.
- Observations do not alter the original business revision, invoke retries or
  transform exceptions. The original gateway is called once per wrapper call.

## Independent Linux QA handoff

Authored tests: `integration/test_runtime_metrics.py` (8 methods). Suggested
focused command for the independent test owner on the exact candidate:

```sh
python3 -B -m unittest integration.test_runtime_metrics
```

This is an unexecuted command suggestion. Preserve raw logs, exact source
commit/tree, host/runtime, start/end UTC, exit code, and artifact SHA-256 when QA
runs it. Existing workbench regressions should be selected by the test owner.
The author did not import or compile these modules, start the workbench, invoke a
gateway, run tests, inspect CI, or measure product performance for this batch.
Browser rendering, live workload observations, deployment, wallet/provider
execution, chain acceptance and final product acceptance remain NOT_RUN.
