"""Localized source-time explanation without exposing holder identity."""
from html import escape

BLOCK_TIME = {"en": "Observed block time (Unix seconds)", "zh-Hans": "观察区块时间（Unix 秒）",
              "zh-Hant": "觀察區塊時間（Unix 秒）", "fr": "Instant du bloc observé (secondes Unix)",
              "es": "Instante del bloque observado (segundos Unix)", "ja": "観測ブロック時刻（Unix 秒）"}

LABELS = {
    "en": ("Register observation", "Latest admitted entry", "Holder at query time", "Query time (Unix seconds)", "Observed block", "EX timeline position", "Register version", "effectiveAt (Unix seconds)", "Historical finality", "Not provided", "Unsupported", "Unavailable", "Query reverted before first entry", "Future-effective", "Effective at observed block", "Final", "Provisional", "Latest admission, effective holder, EX position and business completion are separate facts."),
    "zh-Hans": ("登记观察", "最新准入项", "查询时点的 holder", "查询时间（Unix 秒）", "观察区块", "EX 时间线位置", "登记版本", "effectiveAt（Unix 秒）", "历史时点 finality", "未提供", "不支持", "不可用", "早于首条登记，查询已回退", "尚未到生效时间", "在观察区块时已生效", "历史已确定", "暂定", "最新准入、时点 holder、EX 位置与业务完成是不同事实。"),
    "zh-Hant": ("登記觀察", "最新准入項", "查詢時點的 holder", "查詢時間（Unix 秒）", "觀察區塊", "EX 時間線位置", "登記版本", "effectiveAt（Unix 秒）", "歷史時點 finality", "未提供", "不支援", "不可用", "早於首條登記，查詢已回退", "尚未到生效時間", "在觀察區塊時已生效", "歷史已確定", "暫定", "最新准入、時點 holder、EX 位置與業務完成是不同事實。"),
    "fr": ("Observation du registre", "Dernière entrée admise", "Holder à l’instant demandé", "Instant demandé (secondes Unix)", "Bloc observé", "Position EX", "Version du registre", "effectiveAt (secondes Unix)", "Finalité historique", "Non fourni", "Non pris en charge", "Indisponible", "Requête annulée avant la première entrée", "Effet futur", "Effective au bloc observé", "Finale", "Provisoire", "Admission, holder à un instant, position EX et achèvement métier sont distincts."),
    "es": ("Observación del registro", "Última entrada admitida", "Holder en el instante consultado", "Instante consultado (segundos Unix)", "Bloque observado", "Posición EX", "Versión del registro", "effectiveAt (segundos Unix)", "Finalidad histórica", "No proporcionado", "No compatible", "No disponible", "Consulta revertida antes de la primera entrada", "Efectiva en el futuro", "Efectiva en el bloque observado", "Final", "Provisional", "Admisión, holder por instante, posición EX y finalización del negocio son hechos distintos."),
    "ja": ("登録の観測", "最新の受理済み項目", "照会時点の holder", "照会時刻（Unix 秒）", "観測ブロック", "EX タイムライン位置", "登録バージョン", "effectiveAt（Unix 秒）", "過去時点の finality", "未提供", "未対応", "利用不可", "最初の登録より前のため照会が revert", "将来に発効", "観測ブロック時点で発効済み", "確定", "暫定", "最新の受理、時点の holder、EX の位置、業務完了は別の事実です。"),
}


def render_register(detail, locale):
    labels = LABELS[locale]
    value = detail.get("registerProjection") or {"status": "not-provided"}
    e = lambda text: escape(str(text), quote=True)
    if value["status"] != "verified-original-observation":
        status = {"not-provided": 9, "unsupported": 10}.get(value["status"], 11)
        return '<section><h2>' + e(labels[0]) + '</h2><p class="missing">' + e(labels[status]) + '</p></section>'
    def entry(title, row):
        if row is None:
            return '<h3>' + e(title) + '</h3><p class="missing">' + e(labels[12]) + '</p>'
        fields = ((5, row["holderPosition"] if row["holderPosition"] is not None else labels[9]),
                  (6, row["version"]), (7, row["effectiveAt"]))
        return '<h3>' + e(title) + '</h3><dl>' + ''.join('<dt>' + e(labels[key]) + '</dt><dd>' + e(item) + '</dd>' for key, item in fields) + '</dl>'
    final = labels[12] if value["historicalFinality"] == "unresolved-before-first" else labels[15 if value["isFinalAsOf"] else 16]
    return ('<section><h2>' + e(labels[0]) + '</h2><p class="muted">' + e(labels[17]) + '</p>'
            + entry(labels[1], value["latestAdmitted"]) + '<p>' + e(labels[13 if value["latestTiming"] == "future-effective" else 14]) + '</p>'
            + entry(labels[2], value["holderAtQuery"]) + '<dl><dt>' + e(labels[3]) + '</dt><dd>' + e(value["queryTime"])
            + '</dd><dt>' + e(labels[4]) + '</dt><dd>' + e(value["observedBlock"]["number"]) + ' · ' + e(value["observedBlock"]["hash"])
            + '</dd><dt>' + e(BLOCK_TIME[locale]) + '</dt><dd>' + e(value["observedBlock"]["timestamp"])
            + '</dd><dt>' + e(labels[8]) + '</dt><dd>' + e(final) + '</dd></dl></section>')
