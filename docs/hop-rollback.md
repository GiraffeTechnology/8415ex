# Reverse-chain suffix rollback

Rollback follows the accepted trade suffix in reverse. For an unfinished
`A -> B -> C -> D` chain with effective holder A, the asset path is
`D -> C -> B -> A`. With AB registered and settled, only `D -> C -> B` is
returned. Each hop has an independent operation key and result; a complete
suffix does not require one atomic blockchain transaction. Atomic old-token
burn/new-token mint remains a separate, unchanged remint requirement.

The original authority's interval binding and retained chain generation identify
the return sequence. Each planned hop retains its transfer occurrence, source
and destination account and occurrence, and stable key. `hopCursor` counts only
confirmed asset hops. Equal account addresses at different chain occurrences do
not justify skipping the reverse path. The asset-control adapter is queried
before a submission; UNKNOWN stops asset-hop advancement, while a later enquiry
can apply the same original result without resending that hop.

`advance_rollback(..., max_asset_hops=1)` allows a caller to advance one confirmed
asset hop and expose partial progress. Omitting that limit retains the existing
method's ability to process successive evidenced steps within one call; those
steps still represent separate operations. A failed hop retains all previously
confirmed hops. A subsequent call continues at the same pending occurrence.
The report includes the sequence, planned path, confirmed cursor and per-hop
result/reference. Asset recovery is complete only after every asset hop is done;
overall rollback additionally requires every original refund step to be done.

Original per-segment principal refunds, allowed settlement currency, retained
registered/settled prefix and buyer ETH responsibility remain. An intermediate
account is not asked for another unreserved ETH payment solely because the
asset passes through it. This model preserves the existing configured return
obligation's budget fixture; it does not implement a new actual gas allocation
or replace the existing wallet reservation and actual-receipt accounting.

Historical single-return state is retained for enquiry. This implementation does
not silently submit its old direct-to-boundary operation under the new meaning;
the existing operation outcome and sequence need explicit technical migration.
It introduces no human approval step and does not reopen a closed sequence.
Original late-registration conflict handling and fresh-chain history remain.

Eleven additional synthetic definitions cover the planned path, partial progress,
prefix protection, UNKNOWN enquiry, interrupted continuation, duplicate calls,
snapshot retention, result substitution, required result references, historical-state preservation and a
bounded per-call hop count. Existing domain tests retain their refund, funding,
prefix and no-repeat assertions; obsolete single-return assertions are replaced
with the corresponding three-hop path assertions. These definitions have not
been run for this source. Snapshot codec retention alone is not a complete live
restart proof, deployed-wallet integration or chain acceptance.
