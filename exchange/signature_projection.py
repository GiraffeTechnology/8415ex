"""Historical verification-result projection, not a new signing scheme.

The original verifier checks its applicable version/domain/nonce or equivalent
fields against the unchanged original payload and historical actor. The fields
below identify that verification result; they do not replace cryptography.
"""
from copy import deepcopy


def signature_status(receipt_id, item, record, verify_signature):
    status = item["status"]
    if status != "signed":
        return status
    if not callable(verify_signature):
        return "unknown"
    keys = ("role", "transferRef", "payloadRef", "schemeRef")
    if any(not isinstance(item.get(key), str) or not item[key].strip() for key in keys):
        return "unknown"
    try:
        verdict = verify_signature(receipt_id, deepcopy(item), deepcopy(record))
        if (not isinstance(verdict, dict) or verdict.get("verified") is not True
                or type(verdict.get("position")) is not int
                or verdict["position"] != item["position"]
                or any(verdict.get(key) != item[key] for key in keys)):
            return "unknown"
    except Exception:
        return "unknown"
    return "signed"
