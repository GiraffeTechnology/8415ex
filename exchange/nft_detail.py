"""Read-only identity-free detail projection; no invented gap or signatures.

Signed business clauses are supplied only by the original private document
projection reader. Their original bytes are never exposed through this module.
"""
from copy import deepcopy
import re
from .gap_projection import display_gap, settlement_record
from .signature_projection import signature_status
from .register_projection import register_projection

TERM_SECTION_KEYS = ("commodity", "quantity", "storage-delivery", "currencies",
                     "deadlines", "additional", "signed-business-terms", "revision-history")


def _market_card(row, view):
    card = row.get("marketCard")
    if card is None:
        return None
    if not isinstance(card, dict) or card.get("identityExcluded") is not True:
        raise ValueError("identity-excluding market projection required")
    output = {}
    for key in ("name", "spec", "quantity", "unit"):
        value = card.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > 512 or re.search(r"0x[0-9a-fA-F]{40}", value):
            raise ValueError("bounded original business field required")
        output[key] = value
    code = card.get("commodityCode")
    if code not in ("soy", "iron-ore", "copper", "other"):
        raise ValueError("explicit commodity classification required")
    output["commodityCode"] = code
    quote = card.get("quote")
    output["quote"] = None
    if quote is not None:
        value = quote.get("amountBaseUnits") if isinstance(quote, dict) else None
        if (not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,77}", value)
                or int(value) >= 2**256 or quote.get("currency") not in view.get("allowedPriceCurrencies", ())
                or quote.get("unit") != "base-units-per-whole-nft"
                or quote.get("source") not in ("simulated", "original-order")):
            raise ValueError("original whole-NFT single-currency quote required")
        output["quote"] = {key: quote[key] for key in ("amountBaseUnits", "currency", "unit", "source")}
    return output


def _position(value):
    return value if type(value) is int and value >= 0 else None


def receipt_detail(exchange, receipt_id, *, read_details=None, verify_details=None, verify_signature=None, now=None):
    # Preserve the explicit domain observation clock for legacy read callers.
    # This is not an original chain queryTime, effectiveAt or block timestamp.
    # The original resolver/verifier still owns those independent source facts.
    view = exchange.receipt_view(receipt_id) if now is None else exchange.receipt_view(receipt_id, now)
    # Owner position is an existing domain field. It is not an independent
    # current-position record, a GapOf result or a signature attestation.
    result = {
        "schema": "8415ex-public-nft-detail/1", "receiptId": receipt_id,
        "positions": {"current": None, "owner": _position(view["owner"]["position"]),
                      "holder": _position(view["holder"]["position"])},
        "gap": "unknown", "displayGap": {"state": "unknown"}, "signatureStatusByPosition": [],
        "signatureObservations": [],
        "registerProjection": {"status": "not-provided"},
        "settlementRecord": {"status": "not-provided"},
        "terms": {"status": "not-provided", "clauses": [],
                  "meaning": "Identity-excluding business projection, not byte-identical signed original"},
        "ordinaryTransfer": {"gapEqualityFinalityGateApplied": False,
                             "executionEligibility": "not-evaluated"},
        "sourceStatus": "original-detail-reader-not-configured",
    }
    if read_details is None or verify_details is None:
        return result
    try:
        row = deepcopy(read_details(receipt_id))
        # The original resolver binds every position, gap and clause to this
        # receipt and untouched private original. Hash-shaped strings alone
        # must never turn an unverified projection into signed evidence.
        if not isinstance(row, dict) or row.get("receiptId") != receipt_id:
            raise ValueError("detail receipt mismatch")
        if verify_details(receipt_id, deepcopy(row)) is not True:
            raise ValueError("detail source not verified")
        result["positions"]["current"] = _position(row.get("currentPosition"))
        result["gap"] = row.get("gap") if row.get("gap") in ("open", "closed") else "unknown"
        # Existing EX application gap remains separate from supported ABI reads.
        result["displayGap"] = display_gap(row)
        result["settlementRecord"] = settlement_record(row)
        result["registerProjection"] = register_projection(row)
        signatures = {}
        observations = []
        original_bindings = set()
        for item in row.get("signatures", []):
            position = _position(item.get("position"))
            status = item.get("status")
            if position is None or status not in ("signed", "unsigned", "pending", "unknown"):
                raise ValueError("invalid per-position signature state")
            if status == "signed" and item.get("verified") is not True:
                raise ValueError("signed status without verified original evidence")
            keys = ("role", "transferRef", "payloadRef", "schemeRef")
            if all(type(item.get(key)) is str and item[key].strip() for key in keys):
                identity = (position,) + tuple(item[key] for key in keys)
                if identity in original_bindings:
                    raise ValueError("duplicate original signature binding")
                original_bindings.add(identity)
            # Each original record reaches the original verifier with its OWN
            # role/transfer/payload/scheme. Never collapse by position before
            # verification or move a historical result to a current role.
            projected = signature_status(receipt_id, item, row, verify_signature)
            group = signatures.setdefault(position, [])
            group.append(projected)
            observations.append({"position": position, "observation": len(group),
                                 "status": projected})
        # Backward-compatible one-record summaries. A multi-record position
        # stays unknown here; no aggregate asserts all required roles signed.
        result["signatureStatusByPosition"] = [
            {"position": position, "status": values[0] if len(values) == 1 else "unknown"}
            for position, values in sorted(signatures.items())]
        result["signatureObservations"] = sorted(observations,
            key=lambda item: (item["position"], item["observation"]))
        terms = row.get("businessTerms")
        if terms is not None:
            if not isinstance(terms, dict) or terms.get("coverageVerified") is not True or terms.get("identityExcluded") is not True:
                raise ValueError("business projection coverage not verified")
            clauses = terms.get("clauses")
            if not isinstance(clauses, list) or not clauses:
                raise ValueError("empty business projection")
            output = []
            for clause in clauses:
                if (not isinstance(clause, dict)
                        or set(clause) not in ({"label", "text"}, {"label", "text", "section"})):
                    raise ValueError("business clause schema mismatch")
                if any(not isinstance(clause[key], str) or not clause[key].strip() for key in ("label", "text")):
                    raise ValueError("missing business clause")
                # Refuse rather than silently modifying a signed obligation.
                if re.search(r"0x[0-9a-fA-F]{40}", clause["label"] + clause["text"]):
                    raise ValueError("identity-bearing projection")
                projected = {"label": clause["label"], "text": clause["text"]}
                if "section" in clause:
                    if type(clause["section"]) is not str or clause["section"] not in TERM_SECTION_KEYS:
                        raise ValueError("unknown business section")
                    projected["section"] = clause["section"]
                output.append(projected)
            result["terms"].update(status="provided-verified-projection", clauses=output)
        result["sourceStatus"] = "verified-original-reader"
        result["marketCard"] = _market_card(row, view)
        return result
    except Exception:
        # Never leak resolver errors, private paths, raw JSON, names or addresses.
        return {"schema": result["schema"], "receiptId": receipt_id,
                "positions": {"current": None, "owner": None, "holder": None},
                "gap": "unknown", "displayGap": {"state": "unknown"}, "signatureStatusByPosition": [],
                "signatureObservations": [],
                "registerProjection": {"status": "unavailable"},
                "settlementRecord": {"status": "unavailable"},
                "terms": {"status": "unavailable", "clauses": []},
                "ordinaryTransfer": {"gapEqualityFinalityGateApplied": False,
                                     "executionEligibility": "not-evaluated"},
                "sourceStatus": "detail-source-unavailable"}
