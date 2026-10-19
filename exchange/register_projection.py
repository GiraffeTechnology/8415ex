"""Private original ABI observations -> identity-free, time-specific read model.

The enclosing original detail verifier must bind the NFT, query and block. This
module checks their internal semantics; it does not perform RPC, establish proof
authority or change EX trading/settlement eligibility. holderPosition is an EX
source mapping, never a register version or an ABI array index.
"""
import re


def _uint(value):
    if type(value) is not int or not 0 <= value < 2**64:
        raise ValueError("uint64 required")
    return value


def _word(value, *, zero=False):
    if not isinstance(value, str) or re.fullmatch(r"0x[0-9a-fA-F]{64}", value) is None or (not zero and int(value[2:], 16) == 0):
        raise ValueError("bytes32 required")
    return value.lower()


def _entry(value):
    if not isinstance(value, dict):
        raise ValueError("original register entry required")
    entry = {key: _uint(value[key]) for key in ("version", "effectiveAt", "supersededAt")}
    if entry["version"] == 0 or (entry["supersededAt"] and entry["supersededAt"] <= entry["effectiveAt"]):
        raise ValueError("invalid register interval")
    holder = value["holder"]
    if not isinstance(holder, str) or re.fullmatch(r"0x[0-9a-fA-F]{40}", holder) is None:
        raise ValueError("original holder address required")
    entry.update(holder=holder.lower(), recordCommitment=_word(value["recordCommitment"]),
                 previousCommitment=_word(value["previousCommitment"], zero=True),
                 registryReference=_word(value["registryReference"], zero=True))
    position = value.get("holderPosition")
    if position is not None and (type(position) is not int or position < 0):
        raise ValueError("EX timeline mapping required")
    entry["holderPosition"] = position
    if (entry["version"] == 1) != (int(entry["previousCommitment"][2:], 16) == 0):
        raise ValueError("initial commitment linkage mismatch")
    return entry


def _public(entry):
    return {key: entry[key] for key in ("version", "effectiveAt", "supersededAt", "holderPosition")}


def register_projection(row):
    value = row.get("registerObservation")
    if value is None:
        return {"status": "not-provided"}
    if not isinstance(value, dict) or value.get("projectionInterface") != "0x6309e170":
        return {"status": "unavailable"}
    if value.get("projectionSupported") is False:
        return {"status": "unsupported"}
    if value.get("projectionSupported") is not True or value.get("readStatus") != "succeeded":
        return {"status": "unavailable"}
    try:
        block = value["observedBlock"]
        observed = {"number": _uint(block["number"]), "hash": _word(block["hash"]), "timestamp": _uint(block["timestamp"])}
        query = _uint(value["queryTime"])
        first, latest = _entry(value["firstEntry"]), _entry(value["currentEntry"])
        if first["version"] != 1 or latest["supersededAt"] != 0:
            raise ValueError("first/current entry mismatch")
        if latest["version"] == 1:
            if latest != first:
                raise ValueError("one-entry history mismatch")
        elif latest["effectiveAt"] <= first["effectiveAt"] or latest["recordCommitment"] == first["recordCommitment"]:
            raise ValueError("strict effective time and commitment required")
        elif not first["supersededAt"] or first["supersededAt"] > latest["effectiveAt"]:
            raise ValueError("first historical interval must be closed")
        if latest["version"] == 2 and (latest["previousCommitment"] != first["recordCommitment"] or first["supersededAt"] != latest["effectiveAt"]):
            raise ValueError("adjacent entry linkage mismatch")
        expected_final = first["effectiveAt"] <= query < latest["effectiveAt"]
        if type(value.get("isFinalAsOf")) is not bool or value["isFinalAsOf"] != expected_final:
            raise ValueError("historical finality mismatch")
        result = {"status": "verified-original-observation", "observedBlock": observed,
                  "queryTime": query, "queryIsObservedBlockTime": query == observed["timestamp"],
                  "latestAdmitted": _public(latest),
                  "latestTiming": "future-effective" if latest["effectiveAt"] > observed["timestamp"] else "effective-at-observed-block",
                  "isFinalAsOf": expected_final,
                  "historicalFinality": "unresolved-before-first" if query < first["effectiveAt"] else ("final" if expected_final else "provisional")}
        if query < first["effectiveAt"]:
            if value.get("queryStatus") != "reverted" or value.get("holderAsOf") is not None or value.get("entryAsOf") is not None:
                raise ValueError("pre-first holder query must revert")
            result.update(queryStatus="reverted", holderAtQuery=None)
        else:
            entry = _entry(value["entryAsOf"])
            if value.get("queryStatus") != "succeeded" or not isinstance(value.get("holderAsOf"), str) or value["holderAsOf"].lower() != entry["holder"]:
                raise ValueError("holder and entry query mismatch")
            if not first["effectiveAt"] <= entry["effectiveAt"] <= query or entry["version"] > latest["version"]:
                raise ValueError("entry does not cover query")
            if expected_final:
                if not entry["supersededAt"] or not query < entry["supersededAt"] <= latest["effectiveAt"]:
                    raise ValueError("closed historical interval required")
            elif entry != latest:
                raise ValueError("latest provisional interval mismatch")
            result.update(queryStatus="succeeded", holderAtQuery=_public(entry))
        return result
    except Exception:
        return {"status": "unavailable"}
