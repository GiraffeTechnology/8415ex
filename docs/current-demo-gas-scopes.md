# Current demonstration gas scopes

DEMO-05 now starts the existing simulated direct return with zero intermediate
fixture ceilings and the original return bearer's fixture ceiling already
available. It completes the single D-to-A return without topping up B/C or
changing a ceiling during recovery, refunds each original buyer separately,
and checks that another completion observation repeats no refund or return.
The existing final-buyer gas responsibility is preserved.

The local `_budgets` values are legacy gas-unit ceilings. They are not ordinary
wallet ETH balances, a real maximum-gas prepayment, a P50/cap quote, a signature
or a chain receipt. Setup labels their unit and marks ordinary-wallet ETH
balances NOT_OBSERVED. Actual zero-ETH intermediate-wallet execution, original
buyer-confirmed prepayment, real consumption/unfreeze and restart/chain evidence
remain NOT_RUN. The simulation does not establish current T-20..23 acceptance.

A shortfall of the actual return bearer's available budget is a different
condition from intermediate wallets lacking gas. Existing domain behavior and
shortfall/refund/resumption tests remain. An explicit negative control starts
D's fixture ceiling at zero, checks the named blocked state without custody or
forced sale, then changes that negative fixture's ceiling and checks keyed
resumption without duplicate movements. That top-up is not the main DEMO-05
flow, a new business prerequisite or a new Wallet permission request.

DEMO-03 also separates a fixed original-currency principal refund from actual
ETH gas consumption and unused-gas unfreeze. Its real accounting evidence stays
NOT_RUN because simulation counts do not prove actual debits. It no longer
treats whether gas may reduce the principal as an open product decision. Current
D-04 only leaves allocation of one genuinely shared operation pending; that
narrow pending issue does not reopen confirmed full-principal/separate-ETH
accounting.

This changes the demonstration contract and its explanations, without changing
the domain ledger, gas gate, payment adapter, return adapter, grants, native
operations or actual execution. It grants no permission to trade without the
confirmed principal and maximum-gas freezes. It leaves all six scenario IDs and
main registration sources intact and keeps real evidence separate from local
assertion counts.

Three new synthetic definitions cover completion without increasing ceilings,
the independent negative return-bearer shortfall/resumption, and explicit
unobserved-ETH/native evidence. Existing scenario tests are aligned with the
current gas scope and fixed principal rule. Author execution is NOT_RUN; the
original independent Linux CI/scenario/domain checks and review are required.
No wallet, RPC, signing or chain operation was performed.
