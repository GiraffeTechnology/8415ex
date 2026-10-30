# Durable existing simulation workbench

`python3 -B -m exchange.persistent_simulation_serve` composes the already supported
loopback simulation workbench, original fixed scenario producers, a private
SQLite history store and an optional original EIA reference feed. It is not a
new mock protocol or a substitute for native providers.

Supply an explicit private `--state` path, `--port`, and exact `--commit` and
`--tree`. The directory must already be private and owned by the service user.

From the exact source checkout, run:

```sh
simulation_state_dir="$(mktemp -d)"
python3 -B -m exchange.persistent_simulation_serve \
  --state "$simulation_state_dir/history.sqlite" --port 0 \
  --commit "$(git rev-parse HEAD)" --tree "$(git rev-parse HEAD^{tree})"
```

Keep this explicit state directory for the next invocation to recover history;
creating a different temporary directory starts a separate local history.

New history files are created exclusively with mode 0600. An existing unrelated,
unsafe or corrupt database is refused, never initialized over or silently reset.
Scenario records commit before HTTP redirects report success. The most recent
16 remain in the original in-memory view; older IDs can still be read from
durable history. Original records retain their original source identities.
No historical record is rewritten to the running code version.

The persisted records are canonical LOCAL_SIMULATION outputs, not fabricated
HTTP results. Only the original strict public projection reaches the browser.
All chain, provider, signature and transaction acceptance slots remain NOT_RUN.
SQLite uses full synchronization and bounded capacity; save/recovery errors are
reported as unavailable rather than successful durable execution.

Host, same-origin, CSRF, fixed-scenario selection and response projections are
unchanged. No new public listener, proxy trust, Wallet session, signer, native
registration, grant or authority is created. The native read fixture remains
separate from scenario execution and its command gateway remains unavailable.
Durable scenario history is not a claim that native positions or commands are
persisted or accepted.

Optional `--reference-config` and `--reference-config-sha256` reuse the original
fixed-source EIA configuration decoder, bounded HTTPS reader and reference-feed
lifecycle. Source failures remain unavailable/stale/unknown. External reference
observations never become executable order prices; simulation prices retain
their existing explicitly synthetic meaning. No API key or provider identity is
invented and no policy is changed to make a source appear fresh.

Native Wallet/Oracle/held-capability integration still uses its own original
contracts. Missing native sources do not prevent this existing simulation
profile from starting, and a simulation success does not verify those sources.
