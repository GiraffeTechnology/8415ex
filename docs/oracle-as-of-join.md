# Select the original Oracle record at an explicit instant

The existing Oracle application already exposes
`GET /v1/oracle/projection/{tokenId}/entry/as-of/{instant}`; see its
[pinned original implementation](https://github.com/GiraffeTechnology/Oracle/blob/f1c25bd7e34b42a2f7175ca028aaa5dad59c1417/src/services/application-projection-api.js).
This stage adds that exact read route to the existing EX bounded HTTP transport
and an `inspect_as_of(binding, as_of, cutoff)` entry on `OracleProjectionJoin`.
It creates no Oracle instance, provider, endpoint configuration or write route.

The original API selects the record covering the requested instant. EX checks
the exact source/token/instant identity and half-open effective interval, then
reuses its existing version/commitment/holder/finality join. The complete
selected entry must remain identical during those joined reads before the
original canonical mapping callback runs. Existing bounded append-churn
handling remains in place; there is no unbounded retry or newest-record
fallback.

This removes the need to guess a version or commitment before asking the
original source which record covered an instant. It does not remove the
existing trusted mapping verifier. A registry-reference locator, public
projection entry, current NFT owner or finality boolean alone does not
authenticate the original EX asset/segment/native-operation/journal mapping.

The as-of instant and registration cutoff remain separate inputs and facts.
The result still explicitly grants no atomic-settlement authority, dispatches
no funds, and writes neither holder nor finality. A missing/refused/unavailable
record fails the join; it is not relabelled as absence, rejected registration
or permission to return control.

Acceptance mapping: EX-ARCH-01 / T-46 reuses the actual existing Oracle source
contract while preserving separate principal, canonical-registration and
native-journal authority. Nine synthetic read/transport definitions accompany
this stage and have not been run by the source author. Actual configured
origin, canonical mapping, original provider and runtime acceptance remain
separate evidence.
