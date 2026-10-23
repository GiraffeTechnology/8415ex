"""Explicit static DEMO presentation, separate from original NFT/financial state."""
from html import escape
from urllib.parse import parse_qs, urlencode

from .demo_commodities import COMMODITY_ORDER, COMMODITY_CODES, NAMES, DISPLAY_WORDS, commodity_name, matches_query
from .nft_detail_page import LOCALES, STYLE

# Exact illustrative values from the completed design. None stays an em dash;
# none of these rows enters NftDirectory, a reference feed or an order book.
DEMO = {
    "gold": ("GOLD", "kg", None, None, None, None, "WR-GOLD-0108", "gold.svg"),
    "silver": ("SILVER", "kg", None, None, None, None, "WR-SILVER-0108", "silver.svg"),
    "copper": ("CU", "t", "73,420.00", "+1.26%", "10,120.00", "100", "WR-CU-0031", "copper.png"),
    "iron-ore": ("IRON", "t", "786.50", "−0.42%", "108.00", "2,000", "WR-IRON-0026", "ore.png"),
    "crude-oil": ("OIL", "bbl", None, None, None, None, "WR-OIL-0108", "crude-oil.svg"),
    "coal": ("COAL", "t", None, None, None, None, "WR-COAL-0108", "coal.svg"),
    "soy": ("SOY", "t", "3,860.00", "+0.68%", "520.00", "500", "WR-SOY-0108", "soy.png"),
    "corn": ("CORN", "t", None, None, None, None, "WR-CORN-0108", "corn.svg"),
}
WORDS = {
    "en": ("SIMULATED · not a live feed", "Source: public quotation, not connected", "Quoted: — · Read: —", "Source delay: — · illustrative price",
        "Whole receipt quantity", "Simulated receipt", "Unverified example", "View details", "Original NFT observations", "Illustrative specification"),
    "zh-Hans": ("模拟数据 · 未连接真实行情", "来源：公开报价（待接入）", "报价：— · 读取：—", "源延迟：— · 价格为设计示例",
        "整单数量", "模拟仓单", "待核验示例", "查看详情", "原始 NFT 观察", "规格示例"),
    "zh-Hant": ("模擬資料 · 未連接真實行情", "來源：公開報價（待接入）", "報價：— · 讀取：—", "來源延遲：— · 價格為設計示例",
        "整單數量", "模擬倉單", "待核驗示例", "查看詳情", "原始 NFT 觀察", "規格示例"),
    "fr": ("Données simulées · aucun flux réel", "Source publique : non connectée", "Publié : — · lu : —", "Délai source : — · exemple",
        "Quantité totale", "Récépissé simulé", "Exemple à vérifier", "Voir les détails", "Observations NFT originales", "Spécifications illustratives"),
    "es": ("Datos simulados · sin fuente en directo", "Fuente pública: sin conectar", "Cotizado: — · leído: —", "Retraso: — · precio ilustrativo",
        "Cantidad total", "Recibo simulado", "Ejemplo sin verificar", "Ver detalles", "Observaciones NFT originales", "Especificación ilustrativa"),
    "ja": ("模擬データ・実際の相場に未接続", "出典：公開価格（未接続）", "価格時刻：—・取得：—", "遅延：—・価格は表示例",
        "倉荷証券全体の数量", "模擬倉荷証券", "未検証の表示例", "詳細を見る", "元の NFT の観測", "仕様の表示例"),
}
TERM_HEADINGS = {
    "en": ("Commodity and specification", "Whole quantity and indivisibility", "Storage and delivery", "Allowed settlement currencies (NFT0)",
        "Trading and registration cutoffs", "Additional terms", "Original signed business terms", "Revisions and change history"),
    "zh-Hans": ("商品与规格", "数量与不可拆分性", "仓储与交付条件", "允许结算币种（NFT0）", "交易及登记期限", "附加条款", "原始签署业务条款", "修订与变更记录"),
    "zh-Hant": ("商品與規格", "數量與不可拆分性", "倉儲與交付條件", "允許結算幣種（NFT0）", "交易及登記期限", "附加條款", "原始簽署業務條款", "修訂與變更記錄"),
    "fr": ("Matière et spécifications", "Quantité entière et indivisibilité", "Stockage et livraison", "Devises de règlement autorisées (NFT0)",
        "Échéances de négociation et d’enregistrement", "Conditions supplémentaires", "Conditions originales signées", "Révisions et historique"),
    "es": ("Producto y especificación", "Cantidad entera e indivisibilidad", "Almacenamiento y entrega", "Monedas de liquidación permitidas (NFT0)",
        "Plazos de negociación y registro", "Condiciones adicionales", "Condiciones originales firmadas", "Revisiones e historial"),
    "ja": ("商品と仕様", "全体数量と不可分性", "保管と配送条件", "使用可能な決済通貨（NFT0）", "取引・登録期限", "追加条件", "元の署名済み業務条件", "改訂と変更履歴"),
}
DEMO_STYLE = """
.demo-area{border:0;padding:0;background:transparent}.demo-quotes{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}.demo-quote{height:249px;padding:20px;border-radius:10px;display:flex;flex-direction:column;gap:10px}.demo-quotes>article+article,.demo-products>article+article{margin-top:0}.demo-row{display:flex;align-items:center;justify-content:space-between;gap:8px}.demo-mono{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted)}.demo-price{font-family:Manrope,system-ui,sans-serif;font-size:28px;font-weight:600;line-height:42px}.demo-quote p,.demo-product-card p{margin:0}.demo-quote img{display:block;width:auto;max-width:100%;height:auto}.demo-source{font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--muted);line-height:17px}.demo-products{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.demo-product-card{display:flex;flex-direction:column;gap:14px;padding:20px;border-radius:12px;min-width:0}.demo-product-card h3{font-size:20px}.demo-image{height:148px;display:flex;align-items:center;justify-content:center;overflow:hidden}.demo-image img.illustration{display:block;max-width:100%;height:auto}.demo-image img.photo{width:100%;height:148px;object-fit:cover;border-radius:8px}.demo-separator{height:1px;background:var(--line)}.demo-button{display:inline-flex;align-items:center;justify-content:center;min-height:44px;padding:10px 16px;background:var(--raised);border-radius:6px;text-decoration:none;color:var(--ink)}.demo-rule{font-size:11px;color:var(--muted)}.demo-terms{display:grid;gap:12px}.demo-terms article+article{margin-top:0}
@media(max-width:1100px){.demo-quotes{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:850px){.demo-products{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:550px){.demo-quotes,.demo-products{grid-template-columns:1fr}.demo-product-card{padding:20px}}
"""


def _value(value):
    return "—" if value is None else value


def _href(code, locale, query):
    return "/demo-commodity?" + urlencode({"lang": locale, "commodity": code, "q": query})


def render_demo_quotes(locale):
    words = WORDS[locale]
    cards = []
    for code in COMMODITY_ORDER:
        ticker, unit, price, change, _, _, _, _ = DEMO[code]
        chart = ""
        if price is not None:
            asset = "sparkline-stale.svg" if code == "iron-ore" else "sparkline.svg"
            chart = '<img width="288" height="32" src="/assets/' + asset + '" alt="' + escape(words[0]) + '">'
        cards.append('<article class="demo-quote" data-demo-quote="' + code + '"><div class="demo-row"><b>'
            + escape(commodity_name(code, locale)) + '</b><span class="demo-mono">' + ticker + ' / CNY</span></div>'
            + '<div class="demo-row"><span class="demo-price">' + _value(price) + '</span><span class="muted">CNY / ' + unit
            + '</span></div><div class="demo-row"><span>' + _value(change) + '</span><span class="muted">SIMULATED</span></div>'
            + chart + '<div class="demo-source">' + '<br>'.join(escape(s) for s in words[1:4]) + '</div></article>')
    return '<p class="muted">' + escape(words[0]) + '</p><div class="demo-quotes">' + ''.join(cards) + '</div>'


def render_demo_products(locale, query=""):
    words = WORDS[locale]
    cards = []
    for code in COMMODITY_ORDER:
        name = commodity_name(code, locale)
        if not matches_query(code, name + " " + NAMES["en"][COMMODITY_ORDER.index(code)], query, locale):
            continue
        ticker, unit, _, _, price, quantity, receipt, asset = DEMO[code]
        kind = 'illustration' if asset.endswith('.svg') else 'photo'
        dimensions = ' width="400" height="148"' if kind == 'illustration' else ''
        gap = "NO" if code == "iron-ore" else "YES"
        css = "no" if gap == "NO" else "yes"
        cards.append('<article class="demo-product-card" data-demo-product="' + code + '"><div class="demo-image"><img class="'
            + kind + '"' + dimensions + ' src="/assets/' + asset + '" alt="DEMO · ' + escape(name) + '"></div>'
            + '<div class="demo-row"><h3>' + escape(name) + '</h3><span class="demo-mono">' + ticker + '</span></div>'
            + '<p class="muted">' + escape(name + " · " + words[9]) + '</p><div class="demo-row"><span class="demo-price">'
            + _value(price) + '</span><span class="muted">USDT / ' + unit + '</span><span class="badge">DEMO</span></div>'
            + '<div class="demo-separator"></div><div class="demo-row"><span class="muted">' + escape(words[4]) + '</span><span>'
            + _value(quantity) + ' ' + unit + ' · 1 NFT</span></div><div class="demo-row"><span class="muted">' + escape(words[5])
            + '</span><span class="demo-mono">' + receipt + '</span></div><p><span class="badge ' + css + '">openGapOF=' + gap
            + '</span> <span class="muted">SIMULATED</span></p><p class="demo-rule">' + escape(LOCALES[locale][15])
            + '</p><div class="demo-row"><span class="muted">' + escape(words[6]) + '</span><a class="demo-button" href="'
            + escape(_href(code, locale, query), quote=True) + '">' + escape(words[7]) + ' →</a></div></article>')
    return '<p class="muted">' + escape(DISPLAY_WORDS[locale][1]) + '</p><div class="demo-products">' + ''.join(cards) + '</div>'


def render_demo_detail(code, locale="en", query=""):
    if code not in COMMODITY_CODES or locale not in LOCALES or len(query) > 64:
        raise ValueError("bounded DEMO category and locale required")
    e = lambda s: escape(str(s), quote=True)
    t, words = LOCALES[locale], WORDS[locale]
    _, unit, _, _, price, quantity, receipt, _ = DEMO[code]
    back = '/market?' + urlencode({"lang": locale, "q": query})
    nav = ''.join('<a href="' + e(_href(item, locale, query)) + '">' + e(commodity_name(item, locale)) + '</a>' for item in COMMODITY_ORDER)
    langs = ''.join('<a lang="' + key + '" href="' + e(_href(code, key, query)) + '">' + key + '</a>' for key in LOCALES)
    markers = ''.join('<div class="marker"><span>' + e(t[5 + i]) + '</span><span class="position">' + str(value)
                      + '</span></div>' for i, value in enumerate((8, 7, 1)))
    chain = ''.join('<li class="node"><b>' + str(i) + '</b><span>' + e('Holder' if i == 1 else 'Owner' if i == 7 else t[5] if i == 8 else '—')
                    + '</span><span class="muted">' + e(t[8]) + '</span></li>' for i in range(1, 9))
    bodies = [commodity_name(code, locale) + ' · ' + words[9], _value(quantity) + ' ' + unit + ' · 1 NFT',
              t[3], 'USDT · ETH (DEMO)', t[3], t[3], t[13], t[3]]
    terms = ''.join('<article><h3>' + str(i + 1).zfill(2) + ' ' + e(title) + '</h3><p class="muted">' + e(bodies[i])
                    + '</p></article>' for i, title in enumerate(TERM_HEADINGS[locale]))
    gap = "NO" if code == "iron-ore" else "YES"
    return ('<!doctype html><html lang="' + locale + '"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        + '<title>DEMO · ' + e(commodity_name(code, locale)) + '</title><style>' + STYLE + DEMO_STYLE + '</style><body><main>'
        + '<header><a href="' + e(back) + '">← ' + e(t[1]) + '</a><nav>' + langs + '</nav></header><h1>' + e(t[0]) + ' · DEMO</h1>'
        + '<p class="muted">' + e(DISPLAY_WORDS[locale][1]) + '</p><p>' + receipt + '</p><nav>' + nav + '</nav><section><h2>' + e(t[2])
        + '</h2><h3>' + e(commodity_name(code, locale)) + '</h3><p class="demo-price">' + _value(price) + ' USDT / ' + unit
        + '</p><p class="muted">SIMULATED</p></section><section><h2>' + e(t[4]) + ' · DEMO</h2><div class="markers">' + markers
        + '</div><ol class="timeline">' + chain + '</ol><p class="gap ' + ('no' if gap == 'NO' else 'yes') + '">openGapOF=' + gap
        + ' · SIMULATED</p><p class="rule">' + e(t[15]) + '</p></section><section><h2>' + e(t[12]) + '</h2><p class="missing">'
        + e(t[13]) + '</p><div class="demo-terms">' + terms + '</div></section><a href="' + e(back) + '">← ' + e(t[1]) + '</a></main></body></html>')


def demo_detail_request(request):
    if request.fragment or len(request.query) > 2048:
        raise ValueError("bounded DEMO detail query required")
    params = parse_qs(request.query, strict_parsing=True, keep_blank_values=True, max_num_fields=3)
    if (set(params) - {"lang", "commodity", "q"} or "commodity" not in params
            or any(len(values) != 1 for values in params.values())):
        raise ValueError("one DEMO category, locale and query only")
    locale = params.get("lang", ["en"])[0]
    query = params.get("q", [""])[0]
    if len(query) > 64 or any(ord(char) < 32 for char in query):
        raise ValueError("bounded return query required")
    return render_demo_detail(params["commodity"][0], locale, query)
