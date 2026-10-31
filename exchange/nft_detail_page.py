"""Native HTML over the existing identity-free detail read model."""
from html import escape
from urllib.parse import urlencode
from .gap_projection import gap_label
from .register_projection_page import render_register
from .settlement_record_page import render_settlement
from .nft_detail import TERM_SECTION_KEYS

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
SIGNATURE_OBSERVATION_LABELS = {
    "en": "Signature observation", "zh-Hans": "签署观察记录", "zh-Hant": "簽署觀察記錄",
    "fr": "Observation de signature", "es": "Observación de firma", "ja": "署名の観測記録",
}
TERM_SECTION_LABELS = {
    "en": ("Commodity specifications", "Whole quantity", "Storage and delivery",
           "Immutable NFT0 currencies", "Trade and registration deadlines", "Additional terms",
           "Complete signed-business-terms view", "Revision history", "Other supplied clauses"),
    "zh-Hans": ("商品规格", "整体数量", "仓储与交付", "不可变 NFT0 币种", "交易与登记截止时间",
                "附加条款", "完整签署业务条款视图", "修订历史", "其他已提供条款"),
    "zh-Hant": ("商品規格", "整體數量", "倉儲與交付", "不可變 NFT0 幣種", "交易與登記截止時間",
                "附加條款", "完整簽署業務條款檢視", "修訂歷史", "其他已提供條款"),
    "fr": ("Spécifications du produit", "Quantité totale", "Stockage et livraison",
           "Devises NFT0 immuables", "Échéances de négociation et d’enregistrement",
           "Conditions supplémentaires", "Vue intégrale des conditions commerciales signées",
           "Historique des révisions", "Autres clauses fournies"),
    "es": ("Especificaciones del producto", "Cantidad total", "Almacenamiento y entrega",
           "Divisas NFT0 inmutables", "Plazos de negociación y registro", "Condiciones adicionales",
           "Vista completa de las condiciones comerciales firmadas", "Historial de revisiones",
           "Otras cláusulas proporcionadas"),
    "ja": ("商品仕様", "全体数量", "保管と引渡し", "変更不可の NFT0 通貨", "取引と登記の期限",
           "追加条件", "署名済み業務条件の全文表示", "改訂履歴", "その他の提供済み条項"),
}


def _render_business_terms(clauses, locale):
    e = lambda value: escape(str(value), quote=True)
    # Legacy readers retain their original flat view. No category is inferred
    # from an obligation, language, template name or an identity-bearing source.
    if not any("section" in clause for clause in clauses):
        return ''.join('<article><h3>' + e(clause["label"]) + '</h3><p class="terms">'
                       + e(clause["text"]) + '</p></article>' for clause in clauses)
    words = TERM_SECTION_LABELS[locale]
    rendered, links = [], []
    previous = object()
    for index, clause in enumerate(clauses):
        section = clause.get("section")
        if section != previous:
            if index:
                rendered.append('</div>')
            label = words[TERM_SECTION_KEYS.index(section)] if section in TERM_SECTION_KEYS else words[-1]
            anchor = "business-terms-" + str(index + 1)
            links.append('<a href="#' + anchor + '">' + e(label) + '</a>')
            rendered.append('<div class="terms-section" id="' + anchor
                            + '"><h3>' + e(label) + '</h3>')
            previous = section
        rendered.append('<article><h4>' + e(clause["label"]) + '</h4><p class="terms">'
                        + e(clause["text"]) + '</p></article>')
    rendered.append('</div>')
    # Every clause occurs once, in the original sequence. Repeated categories
    # receive distinct anchors instead of regrouping or silently deduplicating.
    return '<nav class="terms-navigation" aria-label="' + e(LOCALES[locale][12]) + '">' + ''.join(links) + '</nav>' + ''.join(rendered)


STYLE = """
:root{color-scheme:dark;--bg:#0b1012;--surface:#121a1d;--raised:#1a2529;--line:#2a363a;--ink:#edf3ef;--muted:#91a3a3;--accent:#c4ee8b;--gold:#c4a574}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px Inter,system-ui,sans-serif;line-height:1.5}
main{max-width:1440px;margin:auto;padding:40px;display:grid;gap:24px}a{color:var(--muted)}a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:4px}
header{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}nav{display:flex;gap:12px;flex-wrap:wrap}h1{font-size:32px;margin:0}h2{font-size:16px;margin:0 0 10px}h3{font-size:14px;margin:0}p{margin:8px 0}
section,article,details{border:1px solid var(--line);border-radius:12px;padding:20px;background:var(--surface);min-width:0}
.markers{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.marker,.node{padding:12px;background:var(--raised);border:1px solid var(--line);border-radius:12px}.marker{display:flex;align-items:center;justify-content:space-between;gap:12px}
.position,.gap{color:var(--accent);font-family:'IBM Plex Mono',monospace}.position{font-size:28px}.muted{color:var(--muted);font-size:12px}.missing{color:var(--gold)}.timeline{display:flex;gap:12px;overflow:auto;padding:12px 0}.node{flex:0 0 155px}.terms{white-space:pre-wrap;overflow-wrap:anywhere}.gap{font-size:18px}.rule{color:var(--accent)}.gap.yes,.badge.yes{color:#ff7777;border-color:#ff7777;background:#351d21}.gap.no,.badge.no{color:#78d99b;border-color:#78d99b;background:#173026}.gap.unverified,.badge.unverified{color:var(--muted);border-color:var(--line);background:var(--raised)}summary{cursor:pointer}article+article{margin-top:12px}.terms-section{scroll-margin-top:20px;margin-top:20px}.terms-section h4{font-size:14px;margin:0}.terms-navigation a{overflow-wrap:anywhere}.terms-section>h3{margin-bottom:12px}
@media(max-width:650px){main{padding:20px}h1{font-size:24px}.markers{grid-template-columns:1fr}.timeline{display:grid;overflow:visible}.node{display:flex;gap:16px}.position{font-size:24px}section{padding:20px}}
"""


DETAIL_STYLE = """
.nft-detail h1{line-height:48px}.nft-detail .detail-back{font-size:13px;line-height:20px;text-decoration:none;display:inline-flex;align-items:center;min-height:44px}.nft-detail .detail-return{display:flex;align-items:center;min-height:54px;padding:16px;background:var(--raised);border:1px solid var(--line);border-radius:12px;color:var(--ink);text-decoration:none}.nft-detail .detail-quote>.position{font-size:32px;line-height:48px}.nft-detail .detail-name{font-size:20px;line-height:30px;font-weight:700}.nft-detail .marker>span:first-child{font-size:12px;color:var(--muted)}.nft-detail .position.unknown{color:var(--muted)}.nft-detail .missing-terms{display:grid;gap:12px;margin-top:20px}.nft-detail .missing-terms-slot{padding:20px;border:1px solid var(--line);border-radius:12px;background:var(--surface)}.nft-detail .missing-terms-slot h3{font-size:14px;margin:0}.nft-detail .detail-selectors{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.nft-detail .detail-selectors a{display:flex;align-items:center;min-height:44px;padding:12px;background:var(--surface);border:1px solid var(--line);border-radius:12px;text-decoration:none;font:12px 'IBM Plex Mono',monospace;overflow-wrap:anywhere}.nft-detail .detail-selectors a[aria-current=page]{border-color:var(--accent);color:var(--accent)}.nft-detail .timeline{margin:0;list-style:none;padding-left:0}.nft-detail .gap.yes{color:#ea927f;border-color:#ea927f}.nft-detail .gap.no{color:#c4ee8b;border-color:#c4ee8b}
@media(max-width:650px){.nft-detail h1{line-height:36px}.nft-detail .detail-quote>.position{font-size:24px;line-height:36px}.nft-detail .detail-selectors{grid-template-columns:1fr}.nft-detail .node{min-width:0;align-items:flex-start}.nft-detail .node>.position{min-width:24px}}
"""

def render_detail(detail, locale="en", *, nft_key=None, choices=(), market_query=""):
    if locale not in LOCALES:
        raise ValueError("unsupported locale")
    t = LOCALES[locale]
    e = lambda value: escape(str(value), quote=True)
    quote_labels = QUOTE_LABELS[locale]
    card = detail.get("marketCard") or {}
    quote = card.get("quote") if detail.get("sourceStatus") == "verified-original-reader" else None
    name_html = '<p class="detail-name">' + e(card["name"]) + '</p>' if card.get("name") else ''
    quote_html = ('<p class="position">' + e(quote["amountBaseUnits"]) + ' ' + e(quote["currency"])
                  + '</p><p class="muted">' + e(quote_labels[0]) + '</p><p>'
                  + e(quote_labels[1] if quote["source"] == "simulated" else quote_labels[2]) + '</p>') if quote else '<p class="missing">' + e(t[3]) + '</p>'
    positions = detail["positions"]
    markers = "".join('<div class="marker"><span>' + t[5 + i] + '</span><span class="position' + (' unknown' if positions[key] is None else '') + '">'
                      + e(positions[key] if positions[key] is not None else t[8]) + '</span></div>'
                      for i, key in enumerate(("current", "owner", "holder")))
    signature = {item["position"]: item["status"] for item in detail["signatureStatusByPosition"]}
    observations = {}
    for item in detail.get("signatureObservations", ()):
        observations.setdefault(item["position"], []).append(item)
    known_positions = sorted(set(signature) | set(observations)
                             | {value for value in positions.values() if value is not None})
    nodes = []
    for position in known_positions:
        roles = [t[5 + i] for i, key in enumerate(("current", "owner", "holder")) if positions[key] == position]
        state = {"signed": t[9], "unsigned": t[10], "pending": t[11], "unknown": t[8]}.get(signature.get(position), t[8])
        records = observations.get(position)
        if records:
            states = []
            for index, record in enumerate(records, 1):
                label = SIGNATURE_OBSERVATION_LABELS[locale] + " " + str(index)
                observed = {"signed": t[9], "unsigned": t[10], "pending": t[11], "unknown": t[8]}.get(
                    record.get("status"), t[8])
                states.append('<li><span>' + e(label) + '</span>: <span>'
                              + e(observed) + '</span></li>')
            status_html = '<ol class="signature-observations">' + ''.join(states) + '</ol>'
        else:
            status_html = '<p class="muted">' + e(state) + '</p>'
        nodes.append('<li class="node"><span class="position">' + e(position) + '</span><div><p>'
                     + e(" / ".join(roles)) + '</p>' + status_html + '</div></li>')
    clauses = detail["terms"].get("clauses", [])
    terms = _render_business_terms(clauses, locale) if clauses else ''
    if not clauses:
        terms = '<p class="missing">' + e(t[16] if detail["terms"]["status"] == "unavailable" else t[13]) + '</p>'
        # Design sections are visible missing-input slots, never inferred clauses.
        missing = t[16] if detail["terms"]["status"] == "unavailable" else t[3]
        terms += '<aside class="missing-terms" aria-label="' + e(t[13]) + '">' + ''.join('<div class="missing-terms-slot" role="note" data-terms-status="'
                         + ('unavailable' if detail["terms"]["status"] == "unavailable" else 'not-provided')
                         + '"><h3>' + e(str(index + 1).zfill(2) + ' ' + label)
                         + '</h3><p class="muted">' + e(missing) + '</p></div>'
                         for index, label in enumerate(TERM_SECTION_LABELS[locale][:-1])) + '</aside>'
    gap, gap_class = gap_label(detail, locale)
    selection = {"nft": nft_key} if nft_key is not None else {}
    if market_query:
        selection["q"] = market_query
    market_back = '/market?' + urlencode({"lang": locale, "q": market_query}) + ('#nft-' + nft_key if nft_key is not None else '')
    langs = ''.join('<a lang="' + key + '" href="/nft?' + e(urlencode(dict(selection, lang=key))) + '"'
                    + (' aria-current="page"' if key == locale else '') + '>' + key + '</a>' for key in LOCALES)
    selectors = ''.join('<a href="/nft?' + e(urlencode(dict({"lang": locale, "nft": item["nftKey"]}, **({"q": market_query} if market_query else {}))))
                        + '"' + (' aria-current="page"' if item["nftKey"] == nft_key else '')
                        + '>NFT ' + str(index + 1) + ' · '
                        + e(gap_label(item, locale)[0]) + '</a>'
                        for index, item in enumerate(choices))
    return ('<!doctype html><html lang="' + locale + '"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><title>' + e(t[0])
            + '</title><style>' + STYLE + DETAIL_STYLE + '</style><body class="nft-detail"><main><header><a class="detail-back" href="' + e(market_back) + '">← ' + e(t[1])
            + '</a><nav aria-label="' + e(t[17]) + '">' + langs + '</nav></header><h1>' + e(t[0])
            + '</h1><p class="gap ' + gap_class + '">' + e(gap) + '</p><section class="detail-quote"><h2>' + e(t[2]) + '</h2>' + name_html + quote_html
            + '<p class="muted">' + e(quote_labels[3]) + '</p></section><section><h2>' + e(t[4]) + '</h2><div class="markers">' + markers
            + '</div><ol class="timeline">' + ''.join(nodes) + '</ol><p class="rule">' + e(t[15])
            + '</p></section><nav class="detail-selectors" aria-label="NFT">' + selectors + '</nav>' + render_register(detail, locale) + render_settlement(detail, locale) + '<section><h2>' + e(t[12]) + '</h2>' + terms + '<p class="muted">' + e(t[14])
            + '</p></section><a class="detail-return" href="' + e(market_back) + '">← ' + e(t[1]) + '</a></main></body></html>')
