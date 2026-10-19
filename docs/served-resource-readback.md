# Served resource readback

`exchange.deployment_readback` performs a bounded GET of the existing health
route and all seven approved market assets. The caller must supply the exact
existing origin, declared commit/tree, asset manifest and timeout. This module
selects no host, port, provider, service, account or credential, and performs no
deployment, adapter discovery, signing, broadcasting or business command.

The health response must match the declared source and retain its original
observation scope. Each approved asset must match its complete expected byte
length and SHA256. Redirects, authentication challenges, different final paths,
unexpected content types, compressed responses, missing or ambiguous lengths,
non-`no-store` cache policy and incomplete reads are refused. Error output uses
fixed codes and does not echo response bodies.

The successful result says `httpReadbackPassed: true`. It separately keeps
installed-source identity unverified, provider and chain execution unevaluated,
operations readiness unverified, browser journey acceptance unevaluated and
complete product acceptance open. A matching health declaration does not prove
that the declared source is the installed artifact. The original deployment,
provider, installed artifact and actual UI/business evidence remain necessary.

The included asset manifest contains only the already approved seven static
asset paths, sizes and hashes. It contains no deployment address or credential.
Run only through the original approved remote execution and role boundaries;
do not run this validation on the local machine or Windows. The CLI emits its
JSON result on stdout; the original operator retains it with the exact inputs
and execution evidence.

Nine synthetic regression methods cover complete byte readback, declaration
mismatch, altered/truncated assets, redirects and authentication refusal,
manifest scope, readiness overclaim, HTTP metadata ambiguity, response privacy
and input/result snapshot separation. These are definitions, not executed tests.
