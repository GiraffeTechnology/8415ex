"""Prepare fixed remint getter eth_call parameters; never contact a provider."""
from copy import deepcopy
import re


class RemintReadCallRefused(ValueError):
    pass


SIGNATURES = ("declarationOf(uint256)", "predecessorOf(uint256)",
              "successorOf(uint256)", "activeTokenForBill(bytes32)")


def _word(value, *, nonzero=False):
    if (type(value) is not str or re.fullmatch(r"0x[0-9a-f]{64}", value) is None
            or nonzero and int(value[2:], 16) == 0):
        raise RemintReadCallRefused("Original canonical word required")
    return bytes.fromhex(value[2:])


class RemintReadCallEncoder:
    """Application-installed original contract/Keccak and canonical-read policy.

    The host retains chain/provider/code authentication and request IDs. Neither
    an echoed binding nor encoded parameters prove the provider used that block.
    No request can choose another destination, signature, value or signer.
    """
    def __init__(self, contract, keccak256, *, require_canonical):
        if (type(contract) is not str or re.fullmatch(r"0x[0-9a-f]{40}", contract) is None
                or int(contract[2:], 16) == 0 or not callable(keccak256)
                or type(require_canonical) is not bool):
            raise RemintReadCallRefused("Original contract, Keccak and read policy required")
        self.contract, self.require_canonical = contract, require_canonical
        selectors = {}
        try:
            for signature in SIGNATURES:
                digest = keccak256(signature.encode("ascii"))
                if type(digest) is not bytes or len(digest) != 32:
                    raise ValueError("Original Keccak word required")
                selectors[signature] = digest[:4]
            if len(set(selectors.values())) != len(SIGNATURES):
                raise ValueError("Distinct original getter selectors required")
        except Exception:
            raise RemintReadCallRefused("Original selector derivation unavailable") from None
        self._selectors = selectors

    def __call__(self, binding):
        try:
            if (type(binding) is not dict
                    or set(binding) != {"chainId", "contract", "block", "function", "arguments"}
                    or type(binding["chainId"]) is not int or binding["chainId"] != 11155111
                    or binding["contract"] != self.contract
                    or type(binding["function"]) is not str
                    or binding["function"] not in self._selectors
                    or type(binding["arguments"]) is not list or len(binding["arguments"]) != 1):
                raise ValueError("Original fixed getter binding required")
            block = binding["block"]
            if type(block) is not dict or set(block) != {"number", "hash", "timestamp"}:
                raise ValueError("Complete original block required")
            for key in ("number", "timestamp"):
                if type(block[key]) is not int or not 0 <= block[key] < 2**256:
                    raise ValueError("Original block integer required")
            _word(block["hash"], nonzero=True)
            signature, value = binding["function"], binding["arguments"][0]
            if signature == "activeTokenForBill(bytes32)":
                argument = _word(value)
            else:
                if (type(value) is not str or re.fullmatch(r"0|[1-9][0-9]{0,77}", value) is None
                        or int(value) >= 2**256):
                    raise ValueError("Canonical original uint256 text required")
                argument = int(value).to_bytes(32, "big")
            data = self._selectors[signature] + argument
            return {"binding":deepcopy(binding), "request":{"method":"eth_call", "params":[
                {"to":self.contract, "data":"0x"+data.hex()},
                {"blockHash":block["hash"], "requireCanonical":self.require_canonical}]}}
        except Exception:
            raise RemintReadCallRefused("Original pinned remint call unavailable") from None
