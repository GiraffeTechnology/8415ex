"""Prepare complete verified replacement terms and detached change history.

No holder writer, mint/burn, signature, cleanup or approval is performed here.
"""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import re

from .mint_specification import MintSpecification, MintSpecificationRefused


class RemintTermsRefused(ValueError):
    pass


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _hash(value):
    return hashlib.sha256(_encoded(value).encode("utf-8")).hexdigest()


def _pointer(name):
    return name.replace("~", "~0").replace("/", "~1")


def _changes(old, new, path=""):
    if type(old) is dict and type(new) is dict:
        result = []
        for key in sorted(set(old) | set(new)):
            child = path + "/" + _pointer(key)
            if key not in old:
                result.append({"path": child, "kind": "added", "new": deepcopy(new[key])})
            elif key not in new:
                result.append({"path": child, "kind": "removed", "old": deepcopy(old[key])})
            else:
                result.extend(_changes(old[key], new[key], child))
        return result
    if type(old) is type(new) and old == new:
        return []
    return [{"path": path, "kind": "changed", "old": deepcopy(old), "new": deepcopy(new)}]


def prepare_remint_terms(old, replacement, verify_declaration, resolve_original_bill_link):
    """Use existing mint validation and the original bill-identity data resolver.

    The resolver is a trusted application binding, not a new human approval or
    clearing check. It must authenticate the ORIGINAL stable bill mapping and
    return its exact asset/declaration binding. Shape alone is not proof.
    """
    if type(old) is not MintSpecification or type(replacement) is not MintSpecification:
        raise RemintTermsRefused("Original and replacement complete mint specifications required")
    if not callable(verify_declaration) or not callable(resolve_original_bill_link):
        raise RemintTermsRefused("Original declaration verifier and bill mapping required")
    if (old.receipt.asset.chain_id != 11155111
            or replacement.receipt.asset.chain_id != old.receipt.asset.chain_id
            or replacement.receipt.asset == old.receipt.asset):
        raise RemintTermsRefused("Replacement must identify a distinct EX Sepolia NFT")
    # This invokes the same currency/schema/controlled encrypted mapping/privacy
    # validation as ordinary mint. It does not impose cleanup or holder gates.
    try:
        before = json.loads(_encoded(old.metadata(verify_declaration)))
        after = json.loads(_encoded(replacement.metadata(verify_declaration)))
    except (MintSpecificationRefused, ValueError, TypeError):
        raise RemintTermsRefused("Complete non-secret mint declaration refused") from None
    request = {"oldAsset": asdict(old.receipt.asset),
               "newAsset": asdict(replacement.receipt.asset),
               "oldReceiptId": old.receipt.receipt_id,
               "newReceiptId": replacement.receipt.receipt_id,
               "oldDeclarationDigest": _hash(before), "newDeclarationDigest": _hash(after)}
    try:
        linked = resolve_original_bill_link(deepcopy(request))
        # Python equality equates integer IDs with floats (and 1 with True).
        # Bind the original declaration's exact JSON types, not that coercion.
        exact_binding = (type(linked) is dict and type(linked.get("binding")) is dict
                         and _encoded(linked["binding"]) == _encoded(request))
    except Exception:
        raise RemintTermsRefused("Original bill identity mapping unavailable") from None
    if (type(linked) is not dict or set(linked) != {"billKey", "sourceReference", "binding"}
            or not exact_binding
            or type(linked["billKey"]) is not str
            or not re.fullmatch(r"0x[0-9a-f]{64}", linked["billKey"])
            or linked["billKey"] == "0x" + "0" * 64
            or type(linked["sourceReference"]) is not str
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", linked["sourceReference"])):
        raise RemintTermsRefused("Original stable bill/asset/declaration binding refused")
    history = {"schema": "8415ex-remint-terms/1", "billKey": linked["billKey"],
               "billSourceReference": linked["sourceReference"], "binding": request,
               "oldDeclaration": before, "newDeclaration": after,
               "changes": _changes(before, after)}
    # New identities are expected. Report them distinctly from editable terms.
    identity_prefixes = ("/receipt/asset/", "/receipt/receipt_id", "/receipt/minted_at")
    for change in history["changes"]:
        change["category"] = ("nft-identity" if any(change["path"].startswith(prefix)
                              for prefix in identity_prefixes) else "terms")
    return {"history": history, "historyDigest": _hash(history),
            "authorization": "NOT_PERFORMED", "oldBurn": "NOT_RUN", "newMint": "NOT_RUN",
            "originalBillResolverBinding": "Requires installed original-source evidence",
            "atomicExecutionRequired": True}
