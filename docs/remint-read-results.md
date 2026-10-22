# Original remint declaration and mapping return values

The original `EXNFT0Remint` contract retains `declarationOf(uint256)` after a predecessor is burned. Its declaration contains the stable bill key, terms hash, currency declaration hash and the ordered immutable currency words. `exchange/remint_read_results.py` decodes that exact dynamic-tuple return format without issuing an RPC.

The decoder requires canonical outer and array offsets, complete word framing, an exact array length, nonzero declaration words and distinct nonzero currency words. Empty, reverted, truncated, shifted, overlapping or trailing data is refused. The explicit response byte limit bounds the local decoder; it does not change the contract currency set. Original hashes remain distinct fields; no digest is invented from a label.

The same module decodes the original `predecessorOf`, `successorOf` and `activeTokenForBill` scalar returns. Token IDs use decimal strings to preserve the complete uint256 range through JSON. A zero result remains zero at the observed read; it is not a pending-task absence proof, permission to replay or a terminal financial decision.

The installed original reader must still bind every response to the correct chain, contract, requested token or bill key and block. Decoding alone does not authenticate that reader, correlate separate blocks, establish a burned/live NFT state or prove remint success. Complete declaration, bidirectional links, active mapping, operation result and original transaction/finality evidence remain separate observations. This module performs no state write, mint, burn, history rewrite, transaction dispatch or financial release and introduces no execution prerequisite.

This implements a read-interface part of EX-REMINT-04 and T-67. Eight synthetic regression definitions cover canonical declarations, ordered currencies, offsets, lengths, malformed inputs, bounds, mapping results and detached outputs. They have not been run by the author. Actual current-source validation, original deployed binding, browser integration and native chain acceptance remain outstanding.
