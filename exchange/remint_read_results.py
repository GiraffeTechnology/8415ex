"""Decode the original EXNFT0Remint read ABI without issuing any call.

Callers retain the original chain, contract, requested key, block and response
binding. These byte decoders cannot authenticate that binding or authorize an
effect, a replay, a funds release or a declaration-history rewrite.
"""
import re


class RemintReadResultRefused(ValueError):
    pass


def _bytes(value, maximum_bytes):
    if type(maximum_bytes) is not int or maximum_bytes < 32:
        raise RemintReadResultRefused("Explicit positive response bound required")
    if type(value) is bytes:
        raw = value
    elif type(value) is str:
        if (not value.startswith("0x") or len(value) > 2 + maximum_bytes * 2
                or re.fullmatch(r"0x(?:[0-9a-fA-F]{2})*", value) is None):
            raise RemintReadResultRefused("Bounded complete ABI response required")
        raw = bytes.fromhex(value[2:])
    else:
        raise RemintReadResultRefused("Bytes or complete hexadecimal response required")
    if len(raw) > maximum_bytes or len(raw) % 32:
        raise RemintReadResultRefused("Bounded whole ABI words required")
    return raw


def decode_remint_declaration(value, *, maximum_bytes=1024 * 1024):
    """Decode declarationOf(uint256): one dynamic Declaration tuple.

    declarationOf remains readable for a burned predecessor. A successful
    decoding is neither evidence that the token is live nor a signature check.
    Empty/reverted/truncated data is refused, never an absent declaration.
    """
    raw = _bytes(value, maximum_bytes)
    # Outer tuple offset, four tuple-head words and dynamic-array length.
    if len(raw) < 224:
        raise RemintReadResultRefused("Complete nonempty declaration required")
    number = lambda offset: int.from_bytes(raw[offset:offset + 32], "big")
    if number(0) != 32 or number(128) != 128:
        raise RemintReadResultRefused("Canonical declaration tuple offsets required")
    count = number(160)
    if count == 0 or count > (len(raw) - 192) // 32 or len(raw) != 192 + 32 * count:
        raise RemintReadResultRefused("Exact complete declaration array required")
    words = [raw[index:index + 32] for index in (32, 64, 96)]
    currencies = [raw[192 + 32 * index:224 + 32 * index] for index in range(count)]
    if (any(word == bytes(32) for word in words + currencies)
            or len(set(currencies)) != len(currencies)):
        raise RemintReadResultRefused("Original nonzero distinct declaration words required")
    return dict(zip(("billKey", "termsHash", "currencyDeclarationHash"),
                    ("0x" + word.hex() for word in words)),
                allowedCurrencies=["0x" + word.hex() for word in currencies])


def decode_remint_link(value, getter, *, maximum_bytes=32):
    """Decode one actual public mapping getter uint256 result.

    Zero is retained as zero-at-read. It does not independently prove absence,
    burn, finality, task completion or that another operation can be dispatched.
    All uint256 values are decimal strings, preserving JSON integer precision.
    """
    if type(getter) is not str or getter not in (
            "predecessorOf", "successorOf", "activeTokenForBill"):
        raise RemintReadResultRefused("Original remint mapping getter required")
    raw = _bytes(value, maximum_bytes)
    if len(raw) != 32:
        raise RemintReadResultRefused("Exactly one uint256 return word required")
    token = int.from_bytes(raw, "big")
    return {"getter": getter, "tokenId": str(token),
            "observation": "NONZERO_AT_READ" if token else "ZERO_AT_READ",
            "meaning": "Decoded original response only; request and block binding remain external",
            "replayAllowed": False}
