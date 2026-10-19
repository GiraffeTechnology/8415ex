# Principal and gas reporting units

Rollback reports previously subtracted ETH gas wei from the quoted principal, even when the quote asset was a different token. A refunded leg now reports its complete principal amount as `netToOriginalBuyer`; consumed ETH remains a separate expense in `gasTotal` and is never restored by that report.

Both reconciliation and rollback rows expose `principalAsset` / `principalUnit` (`base-units`) and `gasAsset` / `gasUnit` (`ETH` / `wei`). Gas entries also name their chain and original buyer. Token decimals are not inferred from symbols or addresses. These fields describe the existing ledger records; they do not authenticate native execution or replace wallet receipts.

Four new model regression methods cover fees numerically larger than principal, unknown refunds, per-leg responsibility and explicit gas units. The existing rollback assertion now expects the full token principal instead of cross-currency subtraction. All affected tests are authored but NOT_RUN by this change. Required execution belongs on the approved verified remote Linux target; no local or Windows validation is performed.
