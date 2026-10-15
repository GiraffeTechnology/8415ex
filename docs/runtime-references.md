# Runtime reference descriptor

This optional initial module validates an explicit non-secret descriptor and
checks a proposed chain/token against it. It provisions nothing, loads no secret,
resolves no environment variable or provider URL, and never marks Ops READY.
It is not a gate on unrelated UI/model development.

RuntimeReferences.from_mapping requires exactly chain_id, test_token,
token_decimals, wallet_ref, journal_ref, oracle_ref, settlement_ref and
asset_control_ref. The original host must obtain values from its existing
approved records. No token address, precision, provider or journal is guessed
or supplied as a default. Opaque references identify the host's existing objects
and do not grant access to them. The caller owns validation of their provenance.

Only chain11155111 is accepted. token_decimals is an explicit unsigned-byte
precision descriptor, never a gas policy or commercial fee. guard_asset refuses
a mismatching chain/token before any caller-owned send path. A configuration
match does not authenticate an account, authorize a transfer, prove that token
is the designated test asset, or validate source/journal/segment authority.
Original wallet/Oracle/settlement checks still apply at execution.

identity returns only a hash of the non-secret descriptor and explicit
PRESENT_UNVERIFIED / NOT_VERIFIED / NOT_RUN status. It cannot produce deployment,
provider, chain or final acceptance. The developer has not compiled or executed
this module. Independent Linux QA and any deployment/chain work remain with the
original authorized QA/release owner after actual Ops READY evidence.
