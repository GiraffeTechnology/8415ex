# Host entry for the original EIA reference catalogue

`python3 -B -m exchange.eia_reference_serve` uses the existing EIA catalogue
composition and serving lifecycle. Its required arguments are
`--empty-catalogue`, `--reference-config`, `--reference-config-sha256`,
`--port`, `--commit` and `--tree`.
The existing scenario/collateral selection flags are forwarded unchanged.
No host address, port, source calendar or served version is chosen implicitly.

The host-owned UTF-8 JSON file has exactly three keys: integer `version` equal
to 1, `policy`, and `reader`. Policy contains the complete existing EIA fixed
scope, source URL, IANA `sourceTimezone`, `pollSeconds`,
`maxSourceAgeSeconds` and `maxClockSkewSeconds`. Reader contains only
`timeout_seconds`, `user_agent`, `minimum_fetch_seconds` and
`failure_backoff_seconds`. The original reader/feed validate transport values
and the calendar before the server binds. No production example with invented
calendar or timing values is supplied.

Configuration is bounded to 64 KiB. Duplicate and unknown fields are rejected.
Keys, cookies, authorization headers and executable callbacks are not supported
configuration fields. Source policy consistency against this host file is
checked without creating a new user approval or claiming independent
third-party display permission. Keep actual operational configuration in its
existing private host location.

Malformed or unreadable configuration fails before composition. Explicit
serving then starts the original feed through its existing lifecycle; source
unavailability is displayed through the existing read-only endpoints. The
entry does not install a service, change a proxy, create credentials or perform
financial actions. Host activation and actual served/source identity readback
remain separate deployment work.

Eleven synthetic configuration/CLI definitions accompany this stage and have
not been run by the source author. The synthetic test calendar is not a
production source-calendar assertion.

## Host policy contract and requirement mapping

The explicit private host file is the operator's source configuration, not an
independent provider approval, licensing certificate or proof of a source's
calendar/SLA. Its equality callback binds the composition to that exact
configuration snapshot; it must not be reported as independent provenance
verification. The original programmatic composition API remains available for
hosts that already supply their own verifier. No additional user approval is
created by this entry. Actual source/display-policy and runtime acceptance
remain NOT_VERIFIED until their own evidence exists.

Polling must be no faster than the configured minimum reader fetch spacing.
Invalid numeric spacing and nonfinite JSON constants fail before binding,
without advancing a cache or starting a worker.

| Requirement | Exact source/configuration | Exact cases/run/artifacts | Verdict |
| --- | --- | --- | --- |
| T-71; EX-SCOPE-15, EX-PRICE-01, EX-PRICE-02 | `exchange/eia_reference_serve.py:load_eia_reference_config/main` loads the bounded private host file and calls the original composition/lifecycle. Explicit policy/reader/port/source commit/tree and scenario/collateral flags are retained; pollSeconds must cover minimum_fetch_seconds. | `integration/test_eia_reference_serve.py:EIAReferenceServeTests`, eleven definitions via Bootstrap checks' joined Stage 5 integration step, plus the unmodified usage/documentation suite. Keep exact head/base/tested-merge and runner identity, full test logs and source archive. | Current repair candidate synthetic CI NOT_RUN. Host activation/continuous source and policy provenance NOT_VERIFIED. |
| T-72; EX-PRICE-02, EX-PRICE-03, EX-PRICE-04 | No default zone, invented price, freshness or transport input; actual original reader/feed retain evidence and unavailable states. The host may choose the feed's explicit unknown-calendar mode without claiming a measured zone or delay. | Existing fixed-scope/config/CLI refusal tests plus cadence consistency and nonfinite-config refusals. Keep actual served source/config identity and successful/error acquisition/endpoint/browser artifacts separately. | No deployment, live-source, browser or complete product acceptance follows from configuration validation or synthetic CI. |

The host supplies `--reference-config-sha256` from its separately controlled
deployment inputs. The CLI validates this lowercase SHA-256 and compares it
with the complete received configuration bytes before composition. The file
never selects or certifies its own expected digest. A changed file, malformed
digest or absent expected identity fails before binding; no callback is
loaded from JSON. This is technical configuration identity, not a new human
approval or evidence of independent provider permissions, source calendar or
display rights. Record that exact expected/actual configuration identity with
the served source and runtime evidence. The additional digest regression
checks altered bytes and malformed identities before any server is composed.
