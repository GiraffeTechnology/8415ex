"""Separate protocol state; never an overall business completion indicator."""
from html import escape

TEXT = {
    "en": ("Protocol gap record", "Not provided", "Unsupported", "Unavailable", "openedAt / deadline (Unix seconds)", "Protocol state does not establish Oracle outcome, funds movement, EX rollback, historical finality or business completion."),
    "zh-Hans": ("协议 gap 记录", "未提供", "不支持", "不可用", "openedAt / deadline（Unix 秒）", "协议状态不证明 Oracle 结果、资金移动、EX 回滚、历史 finality 或业务完成。"),
    "zh-Hant": ("協議 gap 記錄", "未提供", "不支援", "不可用", "openedAt / deadline（Unix 秒）", "協議狀態不證明 Oracle 結果、資金移動、EX 回滾、歷史 finality 或業務完成。"),
    "fr": ("État du gap du protocole", "Non fourni", "Non pris en charge", "Indisponible", "openedAt / deadline (secondes Unix)", "Cet état ne prouve ni le résultat Oracle, ni les fonds, ni le rollback EX, la finalité historique ou l’achèvement métier."),
    "es": ("Registro del gap del protocolo", "No proporcionado", "No compatible", "No disponible", "openedAt / deadline (segundos Unix)", "El estado no demuestra el resultado Oracle, movimientos de fondos, rollback EX, finalidad histórica ni finalización del negocio."),
    "ja": ("プロトコル gap の記録", "未提供", "未対応", "利用不可", "openedAt / deadline（Unix 秒）", "この状態は Oracle の結果、資金移動、EX rollback、過去の finality、業務完了を証明しません。"),
}


def render_settlement(detail, locale):
    text = TEXT[locale]
    e = lambda value: escape(str(value), quote=True)
    row = detail.get("settlementRecord") or {"status": "not-provided"}
    if row["status"] == "verified-original-observation":
        body = '<p>' + e(row["protocolGapStatus"]) + '</p><p>' + e(text[4]) + ': ' + e(row["openedAt"]) + ' / ' + e(row["deadline"]) + '</p>'
    else:
        body = '<p class="missing">' + e(text[{"not-provided": 1, "unsupported": 2}.get(row["status"], 3)]) + '</p>'
    return '<section><h2>' + e(text[0]) + '</h2>' + body + '<p class="muted">' + e(text[5]) + '</p></section>'
