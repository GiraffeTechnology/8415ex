"""Native HTML over the existing identity-free detail read model."""
from html import escape
from urllib.parse import urlencode
from .gap_projection import gap_label
from .register_projection_page import render_register
from .settlement_record_page import render_settlement
from .demo_commodities import commodity_name

LOCALES = {
    "en": ("NFT transfer details", "Back", "This NFT’s individual quote", "Not provided",
           "Signing & transfer progress", "Current position", "On-chain Owner position",
           "Registered Holder position", "Unknown", "Signed", "Unsigned", "Pending",
           "NFT (bill of lading): full terms", "Original terms not provided; completeness cannot be verified.",
           "Identity-excluding business projection. The unchanged signed original is retained privately for verification. Translations are informational.",
           "openGapOF=YES does not block normal continuous trading.", "Unavailable", "Language"),
    "zh-Hans": ("NFT 转移详情", "返回", "本张 NFT 的独立报价", "未提供", "签署与转移进度",
                "当前位次", "链上 Owner 位次", "登记 Holder 位次", "未知", "已签署", "未签署", "待处理",
                "NFT（提单）完整业务条款", "原始条款未提供，无法核验完整性。",
                "此为排除身份的业务投影。未改动的完整签署原件私有保留用于核验。译文仅供参考。",
                "openGapOF=YES 不阻止正常连续交易。", "不可用", "语言"),
    "zh-Hant": ("NFT 轉移詳情", "返回", "本張 NFT 的獨立報價", "未提供", "簽署與轉移進度",
                "當前位次", "鏈上 Owner 位次", "登記 Holder 位次", "未知", "已簽署", "未簽署", "待處理",
                "NFT（提單）完整業務條款", "原始條款未提供，無法核驗完整性。",
                "此為排除身分的業務投影。未改動的完整簽署原件私有保留用於核驗。譯文僅供參考。",
                "openGapOF=YES 不阻止正常連續交易。", "不可用", "語言"),
    "fr": ("Détails du transfert NFT", "Retour", "Cotation individuelle de ce NFT", "Non fourni",
           "Signatures et transfert", "Position actuelle", "Position Owner sur la chaîne",
           "Position Holder enregistrée", "Inconnu", "Signé", "Non signé", "En attente",
           "NFT (connaissement) : conditions intégrales", "Conditions originales non fournies ; exhaustivité non vérifiée.",
           "Projection des conditions sans identité. L’original signé inchangé est conservé en privé pour vérification. Traductions informatives.",
           "openGapOF=YES ne bloque pas les transferts continus ordinaires.", "Indisponible", "Langue"),
    "es": ("Detalles de transferencia NFT", "Volver", "Cotización individual de este NFT", "No proporcionado",
           "Firmas y transferencia", "Posición actual", "Posición Owner en cadena",
           "Posición Holder registrada", "Desconocido", "Firmado", "Sin firmar", "Pendiente",
           "NFT (conocimiento de embarque): condiciones completas", "No se han proporcionado las condiciones originales; integridad sin verificar.",
           "Proyección de condiciones sin identidad. El original firmado sin cambios se conserva en privado para su verificación. Traducciones informativas.",
           "openGapOF=YES no bloquea las transferencias continuas ordinarias.", "No disponible", "Idioma"),
    "ja": ("NFT 移転の詳細", "戻る", "この NFT の個別見積り", "未提供", "署名と移転の進捗",
           "現在の位置", "オンチェーン Owner の位置", "登録済み Holder の位置", "不明", "署名済み", "未署名", "処理待ち",
           "NFT（船荷証券）の完全な業務条件", "元の条件が未提供のため、完全性は確認できません。",
           "本人情報を除いた業務条件の表示です。変更していない署名済み原本は検証用に非公開で保存されます。翻訳は参考情報です。",
           "openGapOF=YES は通常の連続取引を妨げません。", "利用不可", "言語"),
}
QUOTE_LABELS = {
    "en": ("base units / whole NFT", "Simulated quote", "Original order quote", "ETH gas is checked separately. EX provides no conversion."),
    "zh-Hans": ("最小单位 / 整张 NFT", "模拟报价", "原始订单报价", "ETH gas 单独校验。EX 不提供兑换。"),
    "zh-Hant": ("最小單位 / 整張 NFT", "模擬報價", "原始訂單報價", "ETH gas 單獨校驗。EX 不提供兌換。"),
    "fr": ("unités minimales / NFT entier", "Cotation simulée", "Cotation de l’ordre original", "Le gas ETH est vérifié séparément. EX ne convertit pas les devises."),
    "es": ("unidades mínimas / NFT completo", "Cotización simulada", "Cotización de la orden original", "El gas ETH se verifica por separado. EX no convierte divisas."),
    "ja": ("最小単位 / NFT 全体", "模擬見積り", "元の注文の見積り", "ETH gas は別途確認します。EX は通貨を交換しません。"),
}
STYLE = """
:root{color-scheme:dark;--bg:#0b1012;--surface:#121a1d;--raised:#1a2529;--line:#2a363a;--ink:#edf3ef;--muted:#91a3a3;--accent:#c4ee8b;--gold:#c4a574}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px Inter,system-ui,sans-serif;line-height:1.5}
main{max-width:1440px;margin:auto;padding:40px;display:grid;gap:24px}a{color:var(--muted)}a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:4px}
header{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}nav{display:flex;gap:12px;flex-wrap:wrap}h1{font-size:32px;margin:0}h2{font-size:16px;margin:0 0 10px}h3{font-size:14px;margin:0}p{margin:8px 0}
section,article,details{border:1px solid var(--line);border-radius:12px;padding:20px;background:var(--surface);min-width:0}
.markers{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.marker,.node{padding:12px;background:var(--raised);border:1px solid var(--line);border-radius:12px}.marker{display:flex;align-items:center;justify-content:space-between;gap:12px}
.position,.gap{color:var(--accent);font-family:'IBM Plex Mono',monospace}.position{font-size:28px}.muted{color:var(--muted);font-size:12px}.missing{color:var(--gold)}.timeline{display:flex;gap:12px;overflow:auto;padding:12px 0}.node{flex:0 0 155px}.terms{white-space:pre-wrap;overflow-wrap:anywhere}.gap{font-size:18px}.rule{color:var(--accent)}.gap.yes,.badge.yes{color:#ff7777;border-color:#ff7777;background:#351d21}.gap.no,.badge.no{color:#78d99b;border-color:#78d99b;background:#173026}.gap.unverified,.badge.unverified{color:var(--muted);border-color:var(--line);background:var(--raised)}summary{cursor:pointer}article+article{margin-top:12px}
@media(max-width:650px){main{padding:20px}h1{font-size:24px}.markers{grid-template-columns:1fr}.timeline{display:grid;overflow:visible}.node{display:flex;gap:16px}.position{font-size:24px}section{padding:20px}}
"""


def render_detail(detail, locale="en", *, nft_key=None, choices=(), market_query=""):
    if locale not in LOCALES:
        raise ValueError("unsupported locale")
    t = LOCALES[locale]
    e = lambda value: escape(str(value), quote=True)
    quote_labels = QUOTE_LABELS[locale]
    card = detail.get("marketCard") or {}
    category = commodity_name(card.get("commodityCode"), locale)
    category_html = ('<p class="muted">DEMO · ' + e(category) + '</p>') if category else ''
    quote = card.get("quote") if detail.get("sourceStatus") == "verified-original-reader" else None
    quote_html = ('<p class="position">' + e(quote["amountBaseUnits"]) + ' ' + e(quote["currency"])
                  + '</p><p class="muted">' + e(quote_labels[0]) + '</p><p>'
                  + e(quote_labels[1] if quote["source"] == "simulated" else quote_labels[2]) + '</p>') if quote else '<p class="missing">' + e(t[3]) + '</p>'
    positions = detail["positions"]
    markers = "".join('<div class="marker"><span>' + t[5 + i] + '</span><span class="position">'
                      + e(positions[key] if positions[key] is not None else t[8]) + '</span></div>'
                      for i, key in enumerate(("current", "owner", "holder")))
    signature = {item["position"]: item["status"] for item in detail["signatureStatusByPosition"]}
    known_positions = sorted(set(signature) | {value for value in positions.values() if value is not None})
    nodes = []
    for position in known_positions:
        roles = [t[5 + i] for i, key in enumerate(("current", "owner", "holder")) if positions[key] == position]
        state = {"signed": t[9], "unsigned": t[10], "pending": t[11], "unknown": t[8]}.get(signature.get(position), t[8])
        nodes.append('<li class="node"><span class="position">' + e(position) + '</span><div><p>'
                     + e(" / ".join(roles)) + '</p><p class="muted">' + e(state) + '</p></div></li>')
    clauses = detail["terms"].get("clauses", [])
    terms = ''.join('<article><h3>' + e(clause["label"]) + '</h3><p class="terms">'
                    + e(clause["text"]) + '</p></article>' for clause in clauses)
    if not clauses:
        terms = '<p class="missing">' + e(t[16] if detail["terms"]["status"] == "unavailable" else t[13]) + '</p>'
    gap, gap_class = gap_label(detail, locale)
    selection = {"nft": nft_key} if nft_key is not None else {}
    if market_query:
        selection["q"] = market_query
    market_back = '/market?' + urlencode({"lang": locale, "q": market_query}) + ('#nft-' + nft_key if nft_key is not None else '')
    langs = ''.join('<a lang="' + key + '" href="/nft?' + e(urlencode(dict(selection, lang=key))) + '"'
                    + (' aria-current="page"' if key == locale else '') + '>' + key + '</a>' for key in LOCALES)
    selectors = ''.join('<a href="/nft?' + e(urlencode(dict({"lang": locale, "nft": item["nftKey"]}, **({"q": market_query} if market_query else {}))))
                        + '"' + (' aria-current="page"' if item["nftKey"] == nft_key else '')
                        + '>' + e(commodity_name(item.get("commodityCode"), locale) or ('NFT ' + str(index + 1))) + ' · '
                        + e(gap_label(item, locale)[0]) + '</a>'
                        for index, item in enumerate(choices))
    return ('<!doctype html><html lang="' + locale + '"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>' + e(t[0])
            + '</title><style>' + STYLE + '</style><body><main><header><a href="' + e(market_back) + '">← ' + e(t[1])
            + '</a><nav aria-label="' + e(t[17]) + '">' + langs + '</nav></header><nav aria-label="NFT">' + selectors + '</nav><h1>' + e(t[0])
            + '</h1>' + category_html + '<p class="gap ' + gap_class + '">' + e(gap) + '</p><section><h2>' + e(t[2]) + '</h2>' + quote_html
            + '<p class="muted">' + e(quote_labels[3]) + '</p></section><section><h2>' + e(t[4]) + '</h2><div class="markers">' + markers
            + '</div><ol class="timeline">' + ''.join(nodes) + '</ol><p class="rule">' + e(t[15])
            + '</p></section>' + render_register(detail, locale) + render_settlement(detail, locale) + '<section><h2>' + e(t[12]) + '</h2>' + terms + '<p class="muted">' + e(t[14])
            + '</p></section><a href="' + e(market_back) + '">← ' + e(t[1]) + '</a></main></body></html>')
