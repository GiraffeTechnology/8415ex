"""Display-only interpretation of an original, verified ABI-read projection.

Called only after the original detail verifier binds the whole record to the
correct NFT/source. These are application projection keys, not new ABI fields.
No RPC discovery, mutation, trading eligibility or finality is implemented here.
"""
import re

PROTOCOL_GAP_STATES = {1: "OPEN", 2: "ADMITTED", 3: "CANCELLED", 4: "SUPERSEDED"}


def settlement_record(row):
    # A separate original settlement(bytes32) read, not the EX application gap,
    # Oracle outcome, current openGapOf pointer, funds or execution status.
    value = row.get("settlementRecord")
    if value is None:
        return {"status": "not-provided"}
    if not isinstance(value, dict) or value.get("projectionInterface") != "0x6309e170" or value.get("settlementInterface") != "0xf4a7d71b":
        return {"status": "unavailable"}
    if value.get("projectionSupported") is False or value.get("settlementSupported") is False:
        return {"status": "unsupported"}
    if value.get("projectionSupported") is not True or value.get("settlementSupported") is not True:
        return {"status": "unavailable"}
    try:
        if value.get("readStatus") != "succeeded" or value.get("method") != "settlement(bytes32)":
            raise ValueError("successful original getter required")
        identifier = value["settlementId"]
        if not isinstance(identifier, str) or re.fullmatch(r"0x[0-9a-fA-F]{64}", identifier) is None or int(identifier[2:], 16) == 0:
            raise ValueError("known settlement identifier required")
        record = value["record"]
        token = record["tokenId"]
        if type(token) is not int or not 0 <= token < 2**256 or type(row["tokenBinding"]["tokenId"]) is not int or row["tokenBinding"]["tokenId"] != token:
            raise ValueError("original NFT binding mismatch")
        state = record["status"]
        if type(state) is not int or state not in PROTOCOL_GAP_STATES:
            # NONE is internal; a successful query for an unknown ID must not
            # fabricate it. REJECTED is not an ABI enum member.
            raise ValueError("invalid successful protocol gap status")
        opened, deadline = record["openedAt"], record["deadline"]
        if any(type(item) is not int or not 0 <= item < 2**64 for item in (opened, deadline)) or deadline <= opened:
            raise ValueError("original settlement times required")
        return {"status": "verified-original-observation", "protocolGapStatus": PROTOCOL_GAP_STATES[state],
                "openedAt": opened, "deadline": deadline}
    except Exception:
        return {"status": "unavailable"}

GAP_LABELS = {
    "en": ("Unknown", "Unsupported", "Loading", "Read failed"),
    "zh-Hans": ("未知", "不支持", "加载中", "读取失败"),
    "zh-Hant": ("未知", "不支援", "載入中", "讀取失敗"),
    "fr": ("Inconnu", "Non pris en charge", "Chargement", "Échec de lecture"),
    "es": ("Desconocido", "No compatible", "Cargando", "Error de lectura"),
    "ja": ("不明", "未対応", "読み込み中", "読み取り失敗"),
}


def gap_label(detail, locale):
    state = detail.get("displayGap", {}).get("state", "unknown")
    if state in ("yes", "no"):
        return "openGapOF=" + state.upper(), state
    index = {"unknown": 0, "unsupported": 1, "loading": 2, "error": 3}.get(state, 0)
    return "openGapOF: " + GAP_LABELS[locale][index], "unverified"


def display_gap(row):
    value = row.get("settlementProjection")
    if not isinstance(value, dict):
        return {"state": "unknown"}
    if value.get("projectionInterface") != "0x6309e170" or value.get("settlementInterface") != "0xf4a7d71b":
        return {"state": "unknown"}
    if value.get("projectionSupported") is False or value.get("settlementSupported") is False:
        return {"state": "unsupported"}
    if value.get("projectionSupported") is not True or value.get("settlementSupported") is not True:
        return {"state": "unknown"}
    status = value.get("readStatus")
    if status in ("loading", "error"):
        return {"state": status}
    if status != "succeeded":
        return {"state": "unknown"}
    raw = value.get("settlementId")
    if (value.get("method") != "openGapOf(uint256)" or value.get("returnType") != "bytes32"
            or not isinstance(raw, str) or re.fullmatch(r"0x[0-9a-fA-F]{64}", raw) is None):
        return {"state": "error"}
    return {"state": "no" if int(raw[2:], 16) == 0 else "yes"}
