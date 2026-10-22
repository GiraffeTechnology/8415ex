# Segment funds in the operations queue

The queue now includes the original reconciliation report for its exact ordered
global legs and observation time. Each row shows principal in the selected
original currency and smallest units, escrow state, payment outcome, reported
principal to the seller, reported principal to the original buyer, and consumed
ETH gas in wei. All six locales retain explicit unknown and unavailable states.

The renderer accepts only the original receipt/time binding and complete ordered
leg list already used by the queue. Missing, duplicated, reordered or unrelated
rows make this component unavailable; they do not disable or relabel the queue.
Missing/invalid amounts and units remain unknown; explicit valid zero remains
zero. A released/refunded status never supplies a missing net amount.

No currency conversion, cross-currency aggregation, principal-minus-gas result,
gas prepayment or shared-operation allocation is calculated here. ETH principal
and ETH gas still occupy distinct columns and units. The existing domain reader
reports these values; this UI does not establish native financial settlement,
Oracle outcome, historical finality, original-operation absence or safe replay.
No wallet names, addresses, seller/buyer positions, journal references, arbitrary
source fields or exception messages are exposed. The existing public projection
position mapping is not used or changed.

This stage addresses EX-SETTLE-06, EX-ROLLBACK-03 and EX-GAS-01/02/08 presentation.
It adds no writer, signer, API route, transaction, manual completion, retry
button or approval. It reuses the original reconciliation reader, not a new
Wallet API lookup. Eight authored definitions cover currency/unit separation,
privacy, receipt/time/leg correlation, unknown/zero handling and queue wiring.
Tests, browser and native financial acceptance have not been run by the author.
