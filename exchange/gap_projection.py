"""Display-only interpretation of an original, verified ABI-read projection.

Called only after the original detail verifier binds the whole record to the
correct NFT/source. These are application projection keys, not new ABI fields.
No RPC discovery, mutation, trading eligibility or finality is implemented here.
"""
import re

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
