"""Compose original read-only contract ports into one remint history snapshot.

No endpoint, provider, account, signer or transport is selected. The installed
original ports authenticate provider responses and implement the exact ABI.
"""
from copy import deepcopy
import json
import re
from .remint_history_workbench import RemintHistoryUnavailable
from .remint_read_results import decode_remint_declaration, decode_remint_link


def _same(left, right):
    # JSON identity preserves integer/string/boolean distinctions recursively.
    encode = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"),
                                      allow_nan=False)
    return encode(left) == encode(right)


def _word(value):
    if (type(value) is not str or re.fullmatch(r"0x[0-9a-f]{64}", value) is None
            or int(value[2:], 16) == 0):
        raise ValueError("Original nonzero word required")
    return value


class RemintHistorySnapshotReader:
    """Adapter for installed original block and ABI-read ports, never request callbacks.

    read_original_block receives the fixed chain/contract request and returns
    {binding, block}. call_original_at_block receives the same fixed scope,
    exact block, function signature and arguments and returns {binding, data}.
    The ports must really pin each call to that block hash and authenticate the
    response. Echoing this shape is not independent authentication or proof.
    No construction, failure or incomplete observation dispatches an effect.
    """
    def __init__(self, contract, bill_key, read_original_block, call_original_at_block):
        if (type(contract) is not str or re.fullmatch(r"0x[0-9a-f]{40}", contract) is None
                or int(contract[2:], 16) == 0
                or not callable(read_original_block) or not callable(call_original_at_block)):
            raise ValueError("Explicit original contract and read ports required")
        self.contract, self.bill_key = contract, _word(bill_key)
        self.read_original_block = read_original_block
        self.call_original_at_block = call_original_at_block

    def __call__(self, scope):
        try:
            if (type(scope) is not dict or set(scope) != {"chainId", "contract", "billKey", "tokenId"}
                    or type(scope["chainId"]) is not int or scope["chainId"] != 11155111
                    or scope["contract"] != self.contract or scope["billKey"] != self.bill_key
                    or type(scope["tokenId"]) is not str
                    or re.fullmatch(r"[1-9][0-9]{0,77}", scope["tokenId"]) is None
                    or int(scope["tokenId"]) >= 2**256):
                raise ValueError("Original fixed remint read scope required")
            requested = deepcopy(scope)
            header_request = {"chainId": 11155111, "contract": self.contract}
            header = deepcopy(self.read_original_block(deepcopy(header_request)))
            if (type(header) is not dict or set(header) != {"binding", "block"}
                    or not _same(header["binding"], header_request)):
                raise ValueError("Original header response binding differs")
            block = header["block"]
            if type(block) is not dict or set(block) != {"number", "hash", "timestamp"}:
                raise ValueError("Complete original observed block required")
            for key in ("number", "timestamp"):
                if type(block[key]) is not int or not 0 <= block[key] < 2**256:
                    raise ValueError("Original block integers required")
            _word(block["hash"])

            def call(signature, argument):
                binding = {"chainId": 11155111, "contract": self.contract,
                           "block": deepcopy(block), "function": signature,
                           "arguments": [argument]}
                response = deepcopy(self.call_original_at_block(deepcopy(binding)))
                if (type(response) is not dict or set(response) != {"binding", "data"}
                        or not _same(response["binding"], binding)):
                    raise ValueError("Original ABI call response binding differs")
                return response["data"]

            declaration = call("declarationOf(uint256)", requested["tokenId"])
            if decode_remint_declaration(declaration)["billKey"] != self.bill_key:
                raise ValueError("Selected declaration belongs to another original bill")
            previous = call("predecessorOf(uint256)", requested["tokenId"])
            following = call("successorOf(uint256)", requested["tokenId"])
            predecessor = decode_remint_link(previous, "predecessorOf")["tokenId"]
            successor = decode_remint_link(following, "successorOf")["tokenId"]
            active = call("activeTokenForBill(bytes32)", self.bill_key)
            decode_remint_link(active, "activeTokenForBill")
            # Zero is an actual scalar observation. Never query a fabricated
            # token zero or replace a failed read with a zero result.
            previous_reverse = (call("successorOf(uint256)", predecessor)
                                if predecessor != "0" else None)
            next_reverse = (call("predecessorOf(uint256)", successor)
                            if successor != "0" else None)
            if previous_reverse is not None:
                decode_remint_link(previous_reverse, "successorOf")
            if next_reverse is not None:
                decode_remint_link(next_reverse, "predecessorOf")
            return {"scope": requested, "observedBlock": deepcopy(block),
                    "declaration": declaration, "predecessor": previous,
                    "successor": following, "active": active,
                    "predecessorReverse": previous_reverse,
                    "successorReverse": next_reverse}
        except Exception:
            # No partial snapshot, error echo, retry, latest-block fallback,
            # replacement source or state/journal mutation can escape.
            raise RemintHistoryUnavailable("Original pinned history snapshot unavailable") from None
