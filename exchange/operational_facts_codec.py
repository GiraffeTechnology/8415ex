"""Private operational facts codec; no restore into an Exchange or dispatch."""
from dataclasses import dataclass, fields
import json

from .errors import DomainError
from .ledger import Transfer
from .model import Asset
from .registration import RegistrationEvidence, RegistrationRequest
from .rollback import RollbackStep
from .settlement import EscrowPosition


class OperationalFactsRefused(ValueError):
    pass


SCHEMA = "8415ex-operational-facts/1"
MAX_BYTES = 2 * 1024 * 1024
MAX_DEPTH = 32
MAX_NODES = 100000
# Fixed class and field contracts: no input-controlled imports or class lookup.
CONTRACTS = {
    "asset": (Asset, ("chain_id", "contract", "token_id")),
    "transfer": (Transfer, (
        "transfer_id", "receipt_id", "leg_index", "seller", "buyer",
        "predecessor_transfer_id", "price", "quote_asset", "sell_intent_digest",
        "buy_intent_digest", "sell_authorization_id", "buy_authorization_id",
        "executed_at", "execution_status", "registration_status", "funding_status",
        "rollback_status")),
    "registration-request": (RegistrationRequest, (
        "request_id", "receipt_id", "transfer_id", "leg_index", "predecessor_transfer_id",
        "adapter", "asset", "submitted_at", "commitment_deadline_at", "attempt")),
    "registration-evidence": (RegistrationEvidence, (
        "result_id", "request_id", "receipt_id", "transfer_id", "leg_index", "adapter",
        "source", "outcome", "asset", "observed_at", "result_version",
        "record_commitment", "simulated")),
    "escrow": (EscrowPosition, (
        "escrow_id", "receipt_id", "leg_index", "payer", "payee", "quote_asset",
        "principal", "status", "locked_at", "settled_at", "refunded_at", "payment_key",
        "payment_status", "payment_reference", "payment_intent", "gas_record")),
    "rollback-step": (RollbackStep, (
        "step_id", "kind", "receipt_id", "leg_index", "key", "status", "detail")),
}


@dataclass(frozen=True)
class DecodedOperationalFacts:
    value: object
    execution_authorized: bool = False


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _exact(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise OperationalFactsRefused("exact tagged field membership required")


def _contract():
    for cls, names in CONTRACTS.values():
        if tuple(f.name for f in fields(cls)) != names:
            raise OperationalFactsRefused("domain field drift requires an explicit codec revision")


def _budget(depth, count):
    count[0] += 1
    if depth > MAX_DEPTH or count[0] > MAX_NODES:
        raise OperationalFactsRefused("component structure limit exceeded")


def _key(value):
    if type(value) in (str, int):
        return True
    return type(value) is tuple and all(_key(item) for item in value)


def _encode(value, depth, count):
    _budget(depth, count)
    if value is None or type(value) in (bool, str, int):
        return value
    if type(value) in (list, tuple, set, frozenset):
        kind = {list: "list", tuple: "tuple", set: "set", frozenset: "frozenset"}[type(value)]
        items = [_encode(item, depth + 1, count) for item in value]
        if kind in ("set", "frozenset"):
            items.sort(key=_canonical)
        return {"kind": kind, "items": items}
    if type(value) is dict:
        items = []
        for key, item in value.items():
            if not _key(key):
                raise OperationalFactsRefused("only exact string/integer/tuple map keys allowed")
            items.append([_encode(key, depth + 1, count), _encode(item, depth + 1, count)])
        items.sort(key=lambda pair: _canonical(pair[0]))
        return {"kind": "map", "items": items}
    for name, (cls, names) in CONTRACTS.items():
        if type(value) is cls:
            return {"kind": name, "fields": {
                key: _encode(getattr(value, key), depth + 1, count) for key in names}}
    raise OperationalFactsRefused("unsupported operational value type")


def _decode(value, depth, count):
    _budget(depth, count)
    if value is None or type(value) in (bool, str, int):
        return value
    if type(value) is not dict or type(value.get("kind")) is not str:
        raise OperationalFactsRefused("explicit supported value tag required")
    kind = value["kind"]
    if kind in ("list", "tuple", "set", "frozenset", "map"):
        _exact(value, ("kind", "items"))
        if type(value["items"]) is not list:
            raise OperationalFactsRefused("tagged item list required")
        if kind == "map":
            result = {}
            for pair in value["items"]:
                if type(pair) is not list or len(pair) != 2:
                    raise OperationalFactsRefused("exact map entry pair required")
                key = _decode(pair[0], depth + 1, count)
                if not _key(key) or key in result:
                    raise OperationalFactsRefused("invalid or duplicate map key")
                result[key] = _decode(pair[1], depth + 1, count)
            return result
        items = [_decode(item, depth + 1, count) for item in value["items"]]
        if kind == "list":
            return items
        if kind == "tuple":
            return tuple(items)
        result = set(items)
        if len(result) != len(items):
            raise OperationalFactsRefused("duplicate set entry")
        return result if kind == "set" else frozenset(result)
    if kind not in CONTRACTS:
        raise OperationalFactsRefused("unsupported record tag")
    _exact(value, ("kind", "fields"))
    cls, names = CONTRACTS[kind]
    _exact(value["fields"], names)
    kwargs = {key: _decode(value["fields"][key], depth + 1, count) for key in names}
    return cls(**kwargs)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise OperationalFactsRefused("duplicate JSON field")
        result[key] = value
    return result


def _number(value):
    raise OperationalFactsRefused("floating or nonfinite numbers refused")


def encode_operational_facts(value):
    _contract()
    try:
        raw = _canonical({"schema": SCHEMA, "value": _encode(value, 0, [0])})
        if len(raw) > MAX_BYTES:
            raise OperationalFactsRefused("component byte limit exceeded")
        # Validate original record constructors as well as container encoding.
        _decode(json.loads(raw)["value"], 0, [0])
        return raw
    except (DomainError, TypeError, ValueError, OverflowError, RecursionError) as error:
        if isinstance(error, OperationalFactsRefused):
            raise
        raise OperationalFactsRefused("invalid operational facts") from error


def decode_operational_facts(raw):
    _contract()
    if type(raw) is not bytes or not raw or len(raw) > MAX_BYTES:
        raise OperationalFactsRefused("bounded immutable component bytes required")
    try:
        envelope = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs,
                              parse_float=_number, parse_constant=_number)
        _exact(envelope, ("schema", "value"))
        if envelope["schema"] != SCHEMA or _canonical(envelope) != raw:
            raise OperationalFactsRefused("exact canonical codec version required")
        value = _decode(envelope["value"], 0, [0])
        if encode_operational_facts(value) != raw:
            raise OperationalFactsRefused("noncanonical container order or altered type")
        return DecodedOperationalFacts(value)
    except (DomainError, UnicodeError, TypeError, ValueError, OverflowError, RecursionError) as error:
        if isinstance(error, OperationalFactsRefused):
            raise
        raise OperationalFactsRefused("invalid operational encoding") from error
