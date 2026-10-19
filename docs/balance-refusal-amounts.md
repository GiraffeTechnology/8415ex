# Explain insufficient selected-currency principal and ETH gas separately

Existing admission decisions remain unchanged. When the original balance row has
passed every existing scope, unit, reservation, freshness and verifier check,
insufficient gas reports exact available ETH, original bound gas, required amount
and shortfall in wei. Selected-currency principal reports its own available units,
original bound principal, required principal and shortfall in base units. When
ETH covers both obligations, the combined refusal explains the remaining principal
and unfunded gas rather than counting one available wei twice.

Warnings include those exact numbers so the existing Exchange refusal detail can
surface them before forming a trade. Unverified or unavailable balance rows still
return an unverified refusal without fabricated zero balances or untrusted amounts.
No conversion, substitute currency or financial effect is introduced. Sufficient
already-bound gas still covers only its original obligation, including when free
ETH is zero; a new trade cannot borrow that binding.

Seven authored regression definitions use explicit synthetic verified rows and the
existing transfer refusal path. They remain NOT_RUN pending approved remote Linux
QA. This is diagnostic and API-source work, not proof of a live native reader,
reservation writer, signed transaction, deployment or real UI/chain acceptance.
The original native execution gateway still must recheck liabilities atomically.
