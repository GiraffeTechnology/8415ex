"""Decode the existing EXNFT0Remint operationResult ABI, without executing it.

The installed original reader owns chain/contract/operation/block correlation.
A decoded result is neither a receipt nor permission to replay an UNKNOWN call.
"""
import re


class RemintResultRefused(ValueError):
    """An original result or expected operation digest is malformed/conflicting."""


_WORD = re.compile(r"0x[0-9a-f]{64}\Z")
_RESULT = re.compile(r"0x[0-9a-fA-F]{128}\Z")


def decode_remint_operation_result(raw_result, *, expected_digest):
    """Decode exactly (bytes32 digest, uint256 newTokenId).

    expected_digest is the original contract digest, keccak256(abi.encode(
    actor, oldTokenId, replacement)), supplied by the installed exact-operation
    binding. An EX history SHA, native operation string, or transaction hash is
    not a substitute. No digest is calculated or guessed here.

    The default zero tuple means only that this read contains no recorded
    result. It does not exclude a pending transaction or a different block,
    source or operation. Even a matching record does not prove receipt finality,
    original holder/owner authority, financial settlement or full acceptance.
    """
    if (type(expected_digest) is not str or not _WORD.fullmatch(expected_digest)
            or expected_digest == "0x" + "0" * 64):
        raise RemintResultRefused("Original nonzero contract operation digest required")
    if type(raw_result) is bytes:
        encoded = raw_result
    elif type(raw_result) is str and _RESULT.fullmatch(raw_result):
        encoded = bytes.fromhex(raw_result[2:])
    else:
        raise RemintResultRefused("Exact static operationResult ABI required")
    if len(encoded) != 64:
        raise RemintResultRefused("Exact two-word operationResult ABI required")
    digest = "0x" + encoded[:32].hex()
    token = int.from_bytes(encoded[32:], "big")
    empty_digest = digest == "0x" + "0" * 64
    if empty_digest != (token == 0):
        raise RemintResultRefused("Inconsistent original operation result")
    if not empty_digest and digest != expected_digest:
        raise RemintResultRefused("Original contract operation digest conflict")
    return {
        "status": "NOT_RECORDED_AT_READ" if empty_digest else "RECORDED",
        "digest": None if empty_digest else digest,
        "newTokenId": None if empty_digest else str(token),
        "sourceBinding": "REQUIRED_FROM_ORIGINAL_READER",
        "nativePendingAbsence": "NOT_ESTABLISHED",
        "receiptFinality": "NOT_ESTABLISHED",
        "businessAcceptance": "NOT_ESTABLISHED",
        "replayAllowed": False,
        "releaseAllowed": False,
    }
