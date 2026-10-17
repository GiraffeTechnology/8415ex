# Price/time proposal contract

This initial source slice adds a receipt-local price/time proposal book. It ranks eligible asks by ascending limit, bids by descending limit, then accepted server sequence. Client timestamps and designated counterparties cannot change queue priority. Original intent validation and digest binding are rechecked on each proposal; a revoked, expired or changed intent is excluded. Only the current owner can offer the whole receipt and self bids are excluded.

## Deliberate integration boundary

This is a proposal, not an execution result. It never calls transfer, wallet freeze, registration or settlement, and never changes canonical ownership. It does not replace the existing explicit-pair match binding. The selected price limits and sequences are evidence for the subsequent canonical integration; execution price is intentionally absent until that integration applies the executable price rule. Do not pass this proposal to the existing executor or call the end-to-end matching requirement complete.

The lock serializes this book only. Head observations before and after selection do not create an atomic financial commit. Persistence, replay across process restarts, fill consumption, cancellation and canonical transaction-head binding remain integration work. Authorization restrictions are preserved: designated counterparties are refused rather than silently removed from signed terms. Grants requiring a designated party remain unavailable to this proposal interface until compatible existing authorization evidence is supplied.

## Gas and principal gates

This proposal provides no buyer spending permission. Execution must additionally bind the confirmed gas cap and statistical median disclosure, separate cap-sized gas prepayment from principal, and settle actual consumption with unused balance release. An unknown wallet or transaction outcome must be reconciled first. Neither this module nor the earlier single-estimate disclosure is evidence that those gates are implemented.

## Authored validation input

Eight unittest methods in integration/test_priority_exchange.py cover ranking, same-price FIFO, duplicate delivery, changed terms, nonce reuse, targeted-party refusal, live revocation/expiry, digest binding, non-crossing limits, changed owner and exact trusted clock. The fake original surface is an isolated unit fixture and provides no real signature or wallet attestation.

Proposed command for the existing validation owner: python -m unittest integration.test_priority_exchange -v

At initial submission these tests are authored, NOT_RUN. No hosted CI, installed service, provider, browser, deployment or chain acceptance is claimed. No existing implementation file is changed.
