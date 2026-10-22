"""Join original remint getter encoding, transport and authenticated raw replies."""
from copy import deepcopy
import json
import uuid
from .remint_read_calls import RemintReadCallEncoder
from .remint_read_results import decode_remint_declaration, decode_remint_link


class RemintPinnedReadRefused(ValueError):
    pass


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def _no_number(value):
    raise ValueError("Unexpected JSON number")


class RemintPinnedCallPort:
    """Callable for the existing history snapshot's call_original_at_block port.

    original_transport accepts one complete detached JSON-RPC read request and
    returns its exact raw response bytes. It retains the actual installed route,
    credentials, timeout and no-retry policy. verify_original_response must
    authenticate those bytes against the original provider, chain/code binding,
    exact request/block and original trust policy. Echoing shape is not proof.
    """
    MAX_RESPONSE_BYTES = 2*1024*1024+4096

    def __init__(self, encoder, original_transport, verify_original_response):
        if (type(encoder) is not RemintReadCallEncoder
                or not callable(original_transport) or not callable(verify_original_response)):
            raise RemintPinnedReadRefused("Original read encoder and installed ports required")
        self.encoder = encoder
        self.original_transport = original_transport
        self.verify_original_response = verify_original_response

    def __call__(self, binding):
        try:
            planned = self.encoder(deepcopy(binding))
            request = {"jsonrpc":"2.0", "id":uuid.uuid4().hex,
                       **deepcopy(planned["request"])}
            # One transport call only. The ID is RPC correlation, never an
            # operation identifier, task claim, nonce or transaction reservation.
            raw = self.original_transport(deepcopy(request))
            if type(raw) is not bytes or not 1 <= len(raw) <= self.MAX_RESPONSE_BYTES:
                raise ValueError("Bounded complete original response bytes required")
            evidence = {"binding":deepcopy(planned["binding"]),
                        "request":deepcopy(request), "rawResponse":raw}
            if self.verify_original_response(evidence) is not True:
                raise ValueError("Original exact-response authentication unavailable")
            response = json.loads(raw.decode("utf-8"),object_pairs_hook=_unique,
                parse_float=_no_number,parse_constant=_no_number)
            if (type(response) is not dict or set(response) != {"jsonrpc","id","result"}
                    or response["jsonrpc"] != "2.0" or type(response["id"]) is not str
                    or response["id"] != request["id"] or type(response["result"]) is not str):
                raise ValueError("Original successful JSON-RPC reply required")
            data = response["result"]
            signature = planned["binding"]["function"]
            if signature == "declarationOf(uint256)":
                decode_remint_declaration(data)
            else:
                decode_remint_link(data,signature.split("(",1)[0])
            return {"binding":deepcopy(planned["binding"]), "data":data}
        except Exception:
            # Preserve the original transport's private evidence externally;
            # no retry, fallback, partial history or error/body echo is returned.
            raise RemintPinnedReadRefused("Original pinned contract read unavailable") from None
