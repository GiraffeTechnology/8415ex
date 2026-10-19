"""Edit unsigned replacement business terms using the original typed contracts."""
from copy import deepcopy
from dataclasses import asdict, replace
import hashlib

from .mint_specification import MintSpecification
from .mint_specification_codec import encode_mint_facts
from .remint_terms import _changes


SPECIFICATION_FIELDS = frozenset(("template", "bill_of_lading_number", "issuer",
    "registrar", "storage_location", "public_attributes", "bill_terms",
    "original_document_mapping", "controlled_access_mapping",
    "registration_deadline", "registration_comparison", "voucher_format"))
RECEIPT_FIELDS = frozenset(("commodity_name", "commodity_quantity", "commodity_unit",
    "receipt_number", "registration_path", "trade_stop_at",
    "allowed_price_currencies", "nft0_currency_reference"))


class RemintDraftEditRefused(ValueError):
    pass


def edit_remint_draft(old, replacement_seed, updates):
    """Return an unsigned complete replacement and original-to-proposed changes.

    The installed host supplies the original typed declarations and replacement
    identity. This function does not allocate or predict a minted token ID,
    select an account, establish ownership, verify a signature or execute mint.
    It is an optional editor, not an approval step for an authorized operation.
    """
    if type(old) is not MintSpecification or type(replacement_seed) is not MintSpecification:
        raise RemintDraftEditRefused("original typed specifications required")
    if type(updates) is not dict or set(updates) - {"specification", "receipt"}:
        raise RemintDraftEditRefused("business term update groups required")
    specification_updates = updates.get("specification", {})
    receipt_updates = updates.get("receipt", {})
    if (type(specification_updates) is not dict or type(receipt_updates) is not dict
            or set(specification_updates) - SPECIFICATION_FIELDS
            or set(receipt_updates) - RECEIPT_FIELDS):
        raise RemintDraftEditRefused("identity, custody and execution fields are not business term edits")
    # Original constructors retain complete whole-receipt, template, currency
    # and cutoff contracts. No metadata verifier or admission book is invoked.
    receipt = replace(replacement_seed.receipt, **deepcopy(receipt_updates))
    proposed = replace(replacement_seed, receipt=receipt,
                       **deepcopy(specification_updates))
    original_bytes = encode_mint_facts(old)
    proposed_bytes = encode_mint_facts(proposed)
    return {"specification": proposed,
            "changes": _changes(asdict(old), asdict(proposed)),
            "originalFactSHA256": hashlib.sha256(original_bytes).hexdigest(),
            "proposedFactSHA256": hashlib.sha256(proposed_bytes).hexdigest(),
            "digestMeaning": "local encoded facts only, not a wallet signing ABI or verified document digest",
            "signature": "NOT_REQUESTED", "metadataVerification": "NOT_PERFORMED",
            "execution": "NOT_RUN", "executionAuthorized": False}
