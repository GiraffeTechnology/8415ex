# EX consumer of the original Oracle projection API

This stage consumes the existing Oracle application read boundary under /v1/oracle/projection. It builds on PR54's exact PrincipalBinding. It does not call Kit directly, register a voucher, change holder/finality, emit ReleaseAuthority or dispatch principal/gas actions.

## Existing interface

The original Oracle ProjectionSource port declares registerId, entryCount, currentEntry, entryAt, entryAsOf, holderAsOf and isFinalAsOf. ProjectionEntry contains version, holder, effectiveAt, supersededAt, recordCommitment, previousCommitment and registryReference. Unsigned integer fields are canonical decimal strings.

The application-projection-api implementation exposes these GET routes:

| Route suffix after tokenId | Used response fields |
| --- | --- |
| none | tokenId, source, registerId, entryCount |
| entry/version/{version} | tokenId, source, entry |
| holder/as-of/{instant} | tokenId, source, instant, holder |
| finality/as-of/{instant} | tokenId, source, instant, final |

source is chainId, contract and registerId. Error responses and missing source configuration remain refusals; no local simulated response is substituted. The join accepts no write method.

OracleProjectionJoin receives the original installed read(method, path) transport and an explicit expected Oracle source identity. No URL, RPC, credentials, actor, new provider or default deployment configuration is constructed. The installed transport must authenticate origin and source/artifact identity and enforce its original timeout and raw byte bounds. Each decoded response additionally has a 64 KiB bound and exact expected fields.

## Cross-system identity and stable read

The whole NFT chain/contract/tokenId, receipt/global leg/transfer and native operation/journal come from PrincipalBinding. Token ID alone is insufficient identity. The configured Oracle contract identifies the actual projection source; it is not silently assumed equal to the NFT collection contract. The installed verify_mapping callback must prove the precise relationship between both identities and the original canonical record.

A request pins the required version and recordCommitment, plus an as-of instant and cutoff. The consumer reads count, exact version, holder/finality as of that instant, then count again. If the count changed, it retries the entire read once. Continued churn fails closed. Every response must independently carry the expected source and token. No mixed-source response can survive the count check.

The selected entry must match version/commitment and cover the requested half-open interval: effectiveAt <= asOf, and asOf < supersededAt unless supersededAt is zero. Holder-as-of must agree with that entry. final is a separate strict boolean. Metadata count must cover the requested version.

A stable count detects an append during the read. It is not block finality, protection against same-count reorganization, legal finality or an atomic financial gate. The installed original verifier must authenticate canonical source/store/block evidence, registry/version/commitment chain and actual EX asset/global-leg/native-operation correspondence before the join is accepted.

## Authority remains with the original source

verify_mapping(binding, facts) is a required internal installation port. It must verify the actual canonical mapping, including registryReference resolution and commitment provenance. Accepting public JSON or treating registryReference as a record does not implement this port. The callback receives a detached copy and must return exact True.

The output preserves effectiveAt. It has no observation-clock fallback. withinCutoff reports only the numeric effectiveAt <= supplied cutoff comparison; it does not resolve races at the business cutoff or establish refund eligibility. The original Oracle/native atomic condition must decide those actions. No late-registration grace or second holder/business receipt is introduced.

Holder-as-of, final-as-of and the on-chain tradeable owner are distinct. The consumer never reads the position route as proof of registration. registeredHolderIsBuyer and finalAsOf remain separate output fields. Neither a true comparison nor a true finalAsOf turns the read into settlement authority: atomicSettlementAuthority is always false, and fundsDispatched, holderWritten and finalityWritten remain false.

## Integration handoff and remaining execution

EX now has a concrete consumer for the existing route/DTO contract. Original installation still must supply:

- Reviewed Oracle served source/artifact and authenticated read transport.
- Actual source chain/contract/registerId, preserving the separate Sepolia binding.
- Canonical NFT/receipt/global-leg/transfer to registry version/commitment and native operation/journal mapping.
- Original atomic registration/cutoff/return conditions consumed by the native financial writer.
- Runtime wiring and actual UI/Agent/chain/readback evidence.

These requirements constrain the corresponding live join and financial action. They do not block unrelated initial source stages or require a new whole-project READY.

Twelve synthetic tests are authored, NOT_RUN: route/identity schema, separated holder/finality/cutoff, source collisions, append retry and continuous churn, exact version/commitment/interval, uint precision and booleans, source refusal, missing canonical mapping, mismatched holder/instant, detached evidence and byte bounds. Independent QA command after exact source preparation: python -m unittest integration.test_oracle_projection_join -v.

No compiler/import, unit suite, HTTP service call, database, signing, transaction, deployment or full v1.2 acceptance was executed by this stage. It supplies no mock acceptance result and does not replace the original Oracle writer.
