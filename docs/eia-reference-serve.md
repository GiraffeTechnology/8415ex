# Host entry for the original EIA reference catalogue

`python -m exchange.eia_reference_serve` uses the existing EIA catalogue
composition and serving lifecycle. Its required arguments are
`--empty-catalogue`, `--reference-config`, `--port`, `--commit` and `--tree`.
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

Eight synthetic configuration/CLI definitions accompany this stage and have
not been run by the source author. The synthetic test calendar is not a
production source-calendar assertion.
