"""Canonical private receipt facts; no grants, live state restoration or effects."""
from dataclasses import dataclass, fields
import json

from .errors import DomainError
from .model import Asset, WarehouseReceipt


class ReceiptCheckpointRefused(ValueError):
    pass


SCHEMA = "8415ex-receipt-facts/1"
MAX_BYTES = 1024 * 1024
ASSET_FIELDS = ("chain_id", "contract", "token_id")
RECEIPT_FIELDS = (
    "receipt_id", "asset", "commodity_name", "commodity_quantity", "commodity_unit",
    "receipt_number", "registration_path", "trade_stop_at", "origin_account",
    "minted_at", "allowed_price_currencies", "nft0_currency_reference",
)


@dataclass(frozen=True)
class DecodedReceiptFacts:
    receipt: WarehouseReceipt
    # A declaration is not a current holder/owner observation or authorization.
    execution_authorized: bool = False


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ReceiptCheckpointRefused("exact versioned fields required")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ReceiptCheckpointRefused("duplicate JSON field")
        result[key] = value
    return result


def _reject_number(value):
    raise ReceiptCheckpointRefused("only exact integer numbers are allowed")


def _schema_contract():
    # A changed domain type must receive an explicit codec revision, even when
    # its new dataclass field has a default. Never silently drop new facts.
    if (tuple(f.name for f in fields(Asset)) != ASSET_FIELDS or
            tuple(f.name for f in fields(WarehouseReceipt)) != RECEIPT_FIELDS):
        raise ReceiptCheckpointRefused("domain fields changed; explicit codec revision required")


def _receipt(value):
    _keys(value, RECEIPT_FIELDS)
    _keys(value["asset"], ASSET_FIELDS)
    for name in ("chain_id", "token_id"):
        if type(value["asset"][name]) is not int:
            raise ReceiptCheckpointRefused("exact asset integer required")
    for name in ("commodity_quantity", "trade_stop_at", "minted_at"):
        if type(value[name]) is not int:
            raise ReceiptCheckpointRefused("exact receipt integer required")
    currencies = value["allowed_price_currencies"]
    if type(currencies) is not list or any(type(c) is not str for c in currencies):
        raise ReceiptCheckpointRefused("original ordered currency list required")
    try:
        asset = Asset(**value["asset"])
        kwargs = dict(value, asset=asset, allowed_price_currencies=tuple(currencies))
        return WarehouseReceipt(**kwargs)
    except (DomainError, TypeError, ValueError) as error:
        raise ReceiptCheckpointRefused("stored receipt violates domain contract") from error


def encode_receipt_facts(receipt):
    """Return immutable bytes for one original declaration, without I/O."""
    _schema_contract()
    if type(receipt) is not WarehouseReceipt or type(receipt.asset) is not Asset:
        raise ReceiptCheckpointRefused("exact original receipt and asset types required")
    value = {name: getattr(receipt, name) for name in RECEIPT_FIELDS}
    value["asset"] = {name: getattr(receipt.asset, name) for name in ASSET_FIELDS}
    value["allowed_price_currencies"] = list(receipt.allowed_price_currencies)
    # Revalidate the supplied instance; do not rely only on its class identity.
    _receipt(value)
    try:
        raw = _canonical({"schema": SCHEMA, "receipt": value})
    except (ValueError, TypeError, OverflowError) as error:
        raise ReceiptCheckpointRefused("receipt cannot be encoded canonically") from error
    if len(raw) > MAX_BYTES:
        raise ReceiptCheckpointRefused("receipt byte limit exceeded")
    return raw


def decode_receipt_facts(raw):
    """Reconstruct a declaration only; caller still verifies its provenance."""
    _schema_contract()
    if type(raw) is not bytes or not raw or len(raw) > MAX_BYTES:
        raise ReceiptCheckpointRefused("bounded immutable receipt bytes required")
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs,
                           parse_float=_reject_number, parse_constant=_reject_number)
        _keys(value, ("schema", "receipt"))
        if value["schema"] != SCHEMA or _canonical(value) != raw:
            raise ReceiptCheckpointRefused("exact schema and canonical bytes required")
        receipt = _receipt(value["receipt"])
    except (UnicodeError, ValueError, TypeError, RecursionError, OverflowError) as error:
        if isinstance(error, ReceiptCheckpointRefused):
            raise
        raise ReceiptCheckpointRefused("invalid receipt encoding") from error
    return DecodedReceiptFacts(receipt)
