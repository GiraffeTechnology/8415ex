# Explicit bulk-source host entry

`python3 -B -m exchange.eia_bulk_reference_serve` provides a separate host
entry for the existing fixed daily WTI petroleum bulk composition. It requires
the same explicit host arguments as the HTML entry: empty catalogue, complete
configuration path and externally supplied SHA-256, port, source commit and tree.
The existing collateral/scenario flags are forwarded unchanged.

The host file keeps the original version-1 shape: exactly `version`, `policy`
and `reader`. The policy must explicitly identify the existing fixed PET.zip
source and daily WTI scope. Reader timeouts, user agent, minimum spacing and
failure backoff remain host inputs. The original complete configuration
decoding is shared; no URL is loaded from a callback, browser field or fallback.

The existing `load_eia_reference_config` still accepts the original HTML source
only. The new `load_eia_bulk_reference_config` accepts the existing bulk source
only. Neither loader auto-detects or switches a source. Duplicate/unknown keys,
nonfinite numbers, incomplete source calendars or polling faster than reader
spacing are refused before binding. Unknown calendar is an explicit supported
state and never fabricates a source timezone or freshness.

As before, the external lowercase SHA-256 must match the complete raw host
configuration before composition. The host file does not certify itself.
The equality callback binds this exact configuration snapshot, not independent
source rights, provider approval or current source availability.

Source code availability is not operator activation. This stage does not
rewrite a service, config, port, proxy or scheduler, perform a live bulk read,
or change the installed HTML entry. No production calendar, timing, endpoint,
credential or execution parameter is guessed. The ordinary original catalogue
serving lifecycle starts the selected feed only when the explicit entry is run.

Eight authored synthetic definitions cover fixed-source separation, original
fields and unknown calendar, unknown/executable and duplicate fields, numeric
bounds/cadence, exact config identity, malformed digests, explicit forwarding
and missing-argument refusal. EX has not run those definitions or product
checks. Actual host selection, acquisition, attribution/display policy,
browser and continuous reference acceptance remain separate evidence.
