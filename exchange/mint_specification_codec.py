"""Preserve complete mint terms without calling a verifier or admitting a mint."""
from dataclasses import dataclass, fields

from .mint_specification import CommodityTemplate, RegistrationFormat, MintSpecification
from .operational_facts_codec import encode_operational_facts, decode_operational_facts
from .receipt_checkpoint_codec import encode_receipt_facts, decode_receipt_facts


class MintFactsRefused(ValueError):
    pass


SCHEMA = "8415ex-mint-specification-facts/1"
TEMPLATE_FIELDS = ("template_id", "version", "commodity_scope", "standard_reference",
                   "applicable_fields", "required_fields")
FORMAT_FIELDS = ("format_id", "version", "required_fields", "path")
SPEC_FIELDS = ("receipt", "template", "bill_of_lading_number", "issuer", "registrar",
               "storage_location", "public_attributes", "bill_terms",
               "original_document_mapping", "controlled_access_mapping",
               "registration_deadline", "registration_comparison", "voucher_format")


@dataclass(frozen=True)
class DecodedMintFacts:
    specification: MintSpecification
    provenance_verified: bool = False
    execution_authorized: bool = False


def _contract():
    for cls, names in ((CommodityTemplate, TEMPLATE_FIELDS), (RegistrationFormat, FORMAT_FIELDS),
                       (MintSpecification, SPEC_FIELDS)):
        if tuple(f.name for f in fields(cls)) != names:
            raise MintFactsRefused("mint field drift requires an explicit codec revision")


def _keys(value, names):
    if type(value) is not dict or set(value) != set(names):
        raise MintFactsRefused("exact mint fields required")


def _pack(specification):
    if (type(specification) is not MintSpecification
            or type(specification.template) is not CommodityTemplate
            or type(specification.voucher_format) is not RegistrationFormat):
        raise MintFactsRefused("original exact mint types required")
    value = {name: getattr(specification, name) for name in SPEC_FIELDS}
    value["receipt"] = encode_receipt_facts(specification.receipt).decode("ascii")
    value["template"] = {name: getattr(specification.template, name) for name in TEMPLATE_FIELDS}
    value["voucher_format"] = {name: getattr(specification.voucher_format, name) for name in FORMAT_FIELDS}
    return {"schema": SCHEMA, "specification": value}


def _unpack(value):
    _keys(value, ("schema", "specification"))
    if value["schema"] != SCHEMA:
        raise MintFactsRefused("exact mint facts version required")
    item = value["specification"]
    _keys(item, SPEC_FIELDS)
    _keys(item["template"], TEMPLATE_FIELDS)
    _keys(item["voucher_format"], FORMAT_FIELDS)
    if type(item["receipt"]) is not str:
        raise MintFactsRefused("canonical receipt text required")
    kwargs = dict(item)
    kwargs["receipt"] = decode_receipt_facts(item["receipt"].encode("ascii")).receipt
    kwargs["template"] = CommodityTemplate(**item["template"])
    kwargs["voucher_format"] = RegistrationFormat(**item["voucher_format"])
    # Original constructors recheck field membership, template requirements,
    # registration path and deadline comparison. No metadata/verifier call occurs.
    return MintSpecification(**kwargs)


def encode_mint_facts(specification):
    _contract()
    try:
        raw = encode_operational_facts(_pack(specification))
        _unpack(decode_operational_facts(raw).value)
        return raw
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        raise MintFactsRefused("mint specification facts refused") from None


def decode_mint_facts(raw):
    _contract()
    try:
        specification = _unpack(decode_operational_facts(raw).value)
        if encode_operational_facts(_pack(specification)) != raw:
            raise MintFactsRefused("mint facts are not canonical")
        return DecodedMintFacts(specification)
    except (ValueError, TypeError, KeyError, AttributeError, UnicodeError):
        raise MintFactsRefused("stored mint specification facts refused") from None
