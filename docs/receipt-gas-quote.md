# Original gas receipt samples to explicit quotes

`quote_from_original_receipts` joins the original authenticated receipt sample
adapter to the existing `GasQuote` and six-language confirmation page.
The installed host supplies every original quote field explicitly: quote and
budget identities, scope/actions, Sepolia chain, maximum wei cap, sample window,
quote/expiry times and same-instant original ETH/USD rate metadata.

The bridge chooses none of those values and provides no defaults. It preserves
the complete supplied population, including consumed gas from failed mined
transactions, and uses the existing exact P50 calculation. A cap below that P50,
an invalid rate or missing field fails; no cap is raised or source substituted.
A verifier receives the complete original population once. A source fixture or
shape check does not establish real source authority or applicability.

Private attempts, proof references, transaction identities and raw receipt data
remain in the original verification boundary. Only the existing public sample
labels, exact fees, observation times, blocks, source labels and digests enter
the quote. Quote fields are captured before a callback can mutate caller input.

Composition performs no RPC, source discovery, sampling, clock read, policy
selection, buyer confirmation, freeze, debit, release or transaction. The host's
existing quote source authenticity, live scope and current-state checks remain
separate. Rendering the confirmation page does not perform its submit action.

Eight synthetic definitions join original receipt observations, exact quote
construction and six-language disclosure, including a half-wei median and the
original mocked mined-failure reader. Author execution is NOT_RUN. Source or
fixture composition does not establish current financial, browser, native or
chain acceptance, or choose any real cap, sample population or exchange rate.
