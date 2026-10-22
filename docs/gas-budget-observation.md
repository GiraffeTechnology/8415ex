# Original gas-budget observation on the confirmation page

The existing `GasConfirmationPage` accepts an optional installed
`read_original_budget(budget_id)` callback. The existing application owns its
session/source binding. It returns the original `GasBudgetBook.snapshot`
shape; an isolated reference journal's recovery envelope must be unwrapped
by its original adapter. This feature creates no database or replacement store.

The six-language read-only panel shows the recorded confirmed maximum,
consumed gas, pending/UNKNOWN upper-bound reservations, unused maximum and
the original unused-ETH release proposal. Every amount stays in ETH wei,
separate from selected-currency principal and USD disclosure. Unused maximum
includes pending reservations and is not available ETH.

The view requires the current original budget ID, quote digest and cap to
match. Exact integer values must agree with the original accounting identity.
An open projection has no release proposal; a closed projection must have
zero pending reservations and propose only its unused remainder. A projection
is not proof that a Wallet debit or unfreeze happened. Failed-receipt gas
remains consumed. UNKNOWN reservations cannot be made available by rendering.

Private parties, journal/source details, errors and extra snapshot fields are
not displayed. Missing, conflicting or unavailable observations show a fixed
localized message. They leave the existing quote form and confirmation
contract intact. Rendering never reserves, reconciles, closes, releases,
signs or sends. Submission never invokes this optional observation reader.
The original buyer confirmation fields, cap, P50, consent and CSRF checks
remain unchanged.

This panel supplements a valid quote page; it is not the independent
original-operation recovery query and adds no declaration/history/budget
availability prerequisite to recovery. With no callback, existing behavior
is preserved. Source wiring does not supply an authenticated live budget
or prove funds, Wallet, chain, browser or full product acceptance.

Eight synthetic definitions cover pending UNKNOWN retention, failed gas and
unused proposals, duplicate accounting, six-language privacy, unavailable
source isolation, inconsistent snapshots, unchanged confirmation inputs and
expiry. EX has not run these definitions or product checks.
