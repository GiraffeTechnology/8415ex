"""Read the original remint operation result through one authenticated block call."""
from copy import deepcopy
import json
import uuid

from .remint_read_calls import _word
from .remint_pinned_call_port import _unique, _no_number
from .remint_operation_result import decode_remint_operation_result


SIGNATURE = "operationResult(bytes32)"


class RemintOperationReadRefused(ValueError):
    pass


class RemintOperationResultReadPort:
    """Original installed read route and exact-response verifier, without effects.

    The host supplies its actual contract, Keccak implementation and canonical
    read policy. The original transport retains endpoint, credentials, timeout
    and no-retry handling. The verifier authenticates exact raw bytes, request,
    block, chain/code and original expected digest; echoed shapes are not proof.
    No input can select another function, destination, account or signer.
    """
    MAX_RESPONSE_BYTES = 4096

    def __init__(self, contract, keccak256, original_transport,
                 verify_original_response, *, require_canonical):
        try:
            if (type(contract) is not str or len(contract) != 42
                    or contract[:2] != "0x" or contract != contract.lower()
                    or int(contract[2:], 16) == 0
                    or any(char not in "0123456789abcdef" for char in contract[2:])
                    or not callable(keccak256) or not callable(original_transport)
                    or not callable(verify_original_response)
                    or type(require_canonical) is not bool):
                raise ValueError("Original read ports required")
            digest = keccak256(SIGNATURE.encode("ascii"))
            if type(digest) is not bytes or len(digest) != 32:
                raise ValueError("Original Keccak word required")
        except Exception:
            raise RemintOperationReadRefused("Original operation-result ports required") from None
        self.contract, self.selector = contract, digest[:4]
        self.original_transport = original_transport
        self.verify_original_response = verify_original_response
        self.require_canonical = require_canonical

    def __call__(self, binding, *, expected_digest):
        try:
            bound = deepcopy(binding)
            _word(expected_digest, nonzero=True)
            if (type(bound) is not dict
                    or set(bound) != {"chainId", "contract", "block", "function", "arguments"}
                    or type(bound["chainId"]) is not int or bound["chainId"] != 11155111
                    or bound["contract"] != self.contract
                    or bound["function"] != SIGNATURE
                    or type(bound["arguments"]) is not list or len(bound["arguments"]) != 1):
                raise ValueError("Exact original result binding required")
            operation = _word(bound["arguments"][0], nonzero=True)
            block = bound["block"]
            if type(block) is not dict or set(block) != {"number", "hash", "timestamp"}:
                raise ValueError("Complete original block required")
            for key in ("number", "timestamp"):
                if type(block[key]) is not int or not 0 <= block[key] < 2**256:
                    raise ValueError("Original block integer required")
            _word(block["hash"], nonzero=True)
            request = {"jsonrpc":"2.0", "id":uuid.uuid4().hex, "method":"eth_call",
                "params":[{"to":self.contract, "data":"0x"+(self.selector+operation).hex()},
                    {"blockHash":block["hash"], "requireCanonical":self.require_canonical}]}
            raw = self.original_transport(deepcopy(request))
            if type(raw) is not bytes or not 1 <= len(raw) <= self.MAX_RESPONSE_BYTES:
                raise ValueError("Bounded complete original response required")
            evidence = {"binding":deepcopy(bound), "expectedContractDigest":expected_digest,
                        "request":deepcopy(request), "rawResponse":raw}
            if self.verify_original_response(evidence) is not True:
                raise ValueError("Original exact-response authentication unavailable")
            response = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                parse_float=_no_number, parse_constant=_no_number)
            if (type(response) is not dict or set(response) != {"jsonrpc", "id", "result"}
                    or response["jsonrpc"] != "2.0" or type(response["id"]) is not str
                    or response["id"] != request["id"]):
                raise ValueError("Original successful JSON-RPC response required")
            observation = decode_remint_operation_result(response["result"],
                                                        expected_digest=expected_digest)
            return {"binding":deepcopy(bound), "observation":observation}
        except Exception:
            # Preserve raw provider evidence with the original private ports.
            # No second request, fallback, invented absence or permission follows.
            raise RemintOperationReadRefused("Original remint result read unavailable") from None
