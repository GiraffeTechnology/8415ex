# Unsigned intent review workspace

This initial UI slice supports PRD section 11, EX-MATCH-01 and EX-AUTH-02, with partial source coverage for T-09 and T-26. It does not establish their acceptance. It adds only new files and preserves the submitted workbench and domain code.

## Composition

The integration owner can construct IntentWorkbenchServer with the existing RuntimeBinding, port and exact commit/tree. It uses the original authorization page and adds /intent-draft and /intent-preview. It starts no runtime, wallet or provider itself. No deployment parameter is invented.

A seller or buyer enters one independent proposed intent. The receipt determines asset and chain; quantity is one whole warehouse receipt. Price is integer smallest-unit text, expiry is Unix seconds, and counterparty remains optional under the original model. No price, counterpart or pairing is selected automatically. The preview uses TradeIntent.signed_terms and its existing local domain digest. This digest is not represented as a wallet signing ABI, signature or authorization.

The form is an optional human review aid, not an extra approval gate. It never requests a signature, grants authority, submits an intent, matches orders, locks funds or trades. It does not check current expiry, nonce availability, wallet authority or execution eligibility. These facts remain explicit in the output. Existing wallet and execution boundaries remain authoritative; buyers bear corresponding gas under the PRD.

## Input boundary

POST accepts bounded URL-encoded single fields, same-origin requests and the existing server request token. Asset, units, signature and outcome overrides are refused. Domain validation remains delegated to the original model. HTML output escapes the request token and observed data. Decimal, exponent, signed, whitespace and non-ASCII integer inputs are refused rather than rounded. Input length bounds are transport bounds, not new business defaults.

## Verification handoff

Six unittest methods are authored in integration/test_intent_workspace.py. They cover unchanged domain state, independent buy/sell terms, integer representation, extra and duplicate fields, escaping, and origin/token refusal. They have NOT_RUN status. Bear owns ordinary tests, submitted-source repairs, integration, CI, review and merge.

The proposed Linux command for Bear is: python3 -B -m unittest integration.test_intent_workspace. Run against the exact submitted commit and record command, working directory, UTC start/end, exit, raw log and SHA-256. Actual browser navigation, original-wallet signing, matching, funding, provider operations, deployment and chain acceptance are NOT_RUN. Synthetic review output cannot stand in for those results or full T-09/T-26 acceptance.

## Remaining product dependencies

Complete signed intent submission needs the existing approved wallet contract and execution binding, not a fabricated adapter. Real deployment and Sepolia verification require exact existing service, asset, provider and custody references. Missing dependencies apply only to their respective steps. This source does not configure credentials or transact. Final artifacts must be archived under the approved giraffe project prefix and authenticated readback verified before archival success is claimed.
