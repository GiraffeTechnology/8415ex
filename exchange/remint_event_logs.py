"""Decode fixed EXNFT0Remint ABI logs through original installed Keccak."""
import re
from .receipt_gas_observer import _quantity
from .remint_read_results import decode_remint_declaration


class RemintLogRefused(ValueError):
    pass


SIGNATURES = {
    "Transfer": b"Transfer(address,address,uint256)",
    "NFT0Declared": b"NFT0Declared(uint256,bytes32,bytes32,bytes32,bytes32[])",
    "NFT0Reminted": b"NFT0Reminted(bytes32,uint256,uint256,address,bytes32)",
}
TRANSFER_TOPIC = bytes.fromhex("ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef")


def _word(value, *, nonzero=False):
    if (type(value) is not str or re.fullmatch(r"0x[0-9a-f]{64}", value) is None
            or nonzero and int(value[2:], 16) == 0):
        raise RemintLogRefused("Original canonical ABI word required")
    return bytes.fromhex(value[2:])


def _address(value, *, zero=False):
    if (type(value) is not str or re.fullmatch(r"0x[0-9a-f]{40}", value) is None
            or not zero and int(value[2:], 16) == 0):
        raise RemintLogRefused("Original canonical address required")
    return value


def _address_word(raw, *, zero=False):
    if raw[:12] != bytes(12):
        raise RemintLogRefused("Canonical ABI address padding required")
    return _address("0x" + raw[12:].hex(), zero=zero)


def _token(raw):
    value = int.from_bytes(raw, "big")
    if value == 0:
        raise RemintLogRefused("Original positive token required")
    return str(value)


class RemintEventLogDecoder:
    """Callable for RemintReceiptObserver; no RPC, receipt or ABI authenticity claim.

    The application supplies its original contract and installed Keccak-256 port.
    The original receipt verifier/deployment evidence must authenticate that this
    exact contract actually uses this ABI. Topic derivation is not that proof.
    """
    def __init__(self, contract, keccak256):
        self.contract = _address(contract)
        if not callable(keccak256):
            raise RemintLogRefused("Original Keccak port required")
        topics = {}
        try:
            for name, signature in SIGNATURES.items():
                value = keccak256(signature)
                if type(value) is not bytes or len(value) != 32 or value == bytes(32):
                    raise ValueError("Keccak word required")
                topics[name] = value
            if topics["Transfer"] != TRANSFER_TOPIC or len(set(topics.values())) != 3:
                raise ValueError("Original distinct Keccak topics required")
        except Exception:
            raise RemintLogRefused("Original Keccak topic derivation unavailable") from None
        self._topics = {value: name for name, value in topics.items()}

    def __call__(self, log, context):
        try:
            required = {"chainId", "contract", "transactionHash", "blockHash",
                        "blockNumber", "logIndex"}
            if (type(context) is not dict or set(context) != required
                    or type(context["chainId"]) is not int or context["chainId"] != 11155111
                    or context["contract"] != self.contract
                    or type(log) is not dict or log.get("address") != self.contract
                    or log.get("removed") is not False):
                raise ValueError("Original log context required")
            for key in ("transactionHash", "blockHash"):
                _word(context[key], nonzero=True)
                if log.get(key) != context[key]:
                    raise ValueError("Original transaction/block differs")
            for key in ("blockNumber", "logIndex"):
                if (type(context[key]) is not int or not 0 <= context[key] < 2**256
                        or _quantity(log.get(key)) != context[key]):
                    raise ValueError("Original log index/block differs")
            topics = log.get("topics")
            if type(topics) is not list or len(topics) > 4:
                raise ValueError("Bounded exact topics required")
            words = [_word(value) for value in topics]
            encoded = log.get("data")
            if (type(encoded) is not str or len(encoded) > 2 + 262144*2
                    or re.fullmatch(r"0x(?:[0-9a-f]{2})*", encoded) is None):
                raise ValueError("Bounded complete log data required")
            raw = bytes.fromhex(encoded[2:])
            name = self._topics.get(words[0]) if words else None
            if name is None:
                return None
            if name == "Transfer":
                if len(words) != 4 or raw:
                    raise ValueError("Exact original Transfer ABI required")
                return {"event":name, "from":_address_word(words[1], zero=True),
                        "to":_address_word(words[2], zero=True), "tokenId":_token(words[3])}
            if name == "NFT0Reminted":
                if len(words) != 4 or len(raw) != 64 or words[1] == bytes(32):
                    raise ValueError("Exact original remint ABI required")
                _word("0x"+raw[32:].hex(), nonzero=True)
                return {"event":name, "operationId":"0x"+words[1].hex(),
                    "oldTokenId":_token(words[2]), "newTokenId":_token(words[3]),
                    "holder":_address_word(raw[:32]), "billKey":"0x"+raw[32:].hex()}
            # Non-indexed data head: termsHash, currencyDeclarationHash,
            # allowedCurrencies offset=96. Indexed token and bill are topics.
            if (len(words) != 3 or len(raw) < 160 or len(raw) % 32
                    or int.from_bytes(raw[64:96], "big") != 96):
                raise ValueError("Exact original declaration ABI required")
            count = int.from_bytes(raw[96:128], "big")
            if count == 0 or count > (len(raw)-128)//32 or len(raw) != 128+32*count:
                raise ValueError("Complete exact event currency array required")
            declaration = ((32).to_bytes(32, "big") + words[2] + raw[:64]
                           + (128).to_bytes(32, "big") + raw[96:])
            value = decode_remint_declaration(declaration)
            return {"event":name, "tokenId":_token(words[1]), **value}
        except Exception:
            raise RemintLogRefused("Original remint log decoding unavailable") from None
