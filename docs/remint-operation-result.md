# Original remint operation result

`decode_remint_operation_result` decodes the existing
`EXNFT0Remint.operationResult(bytes32)` static return tuple:
`(bytes32 digest, uint256 newTokenId)`. Its input is exactly 64 raw bytes or
the corresponding JSON-RPC hex value. Partial data, trailing data, dynamic
wrappers, inconsistent empty fields and conflicting digests are refused.
The token ID remains an exact decimal string, including uint256 maximum.

The expected digest must come from the installed original exact-operation
binding: the contract uses
`keccak256(abi.encode(msg.sender, oldTokenId, replacement))`. The decoder does
not calculate it or convert an EX history SHA, native operation name or
transaction hash into it. The original reader still binds the approved
chain, deployed contract, operation ID, block and authenticated response.
This decoder makes no RPC call and supplies none of those inputs.

A matching nonzero record is reported as `RECORDED`; this means only that the
provided tuple contains the expected digest and a nonzero successor token.
It does not establish a successful/final receipt, current owner, effective
holder, declaration/asset links, refunds, ETH cost, or business acceptance.

A zero tuple is `NOT_RECORDED_AT_READ`. It is not authenticated absence of
a native pending operation and must never be passed as a `None` absence
response to a once-only execution gate. Original transaction and journal
reconciliation remain necessary. Neither result permits replay, nonce or
reservation release, or another mint. Original independent recovery enquiry
does not require declarations, history availability or this decoder.

The synthetic definitions cover exact tuple and JSON-RPC forms, zero results,
uint256 limits, conflicting digests, malformed lengths/types, inconsistent
records and malformed expected digests. They are authored definitions;
compiler/test execution and real source, receipt, Wallet, financial and chain
acceptance are not established by this source stage.
