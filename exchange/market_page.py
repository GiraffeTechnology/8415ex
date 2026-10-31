"""Commodity market surface over original NFT and reference observations."""
from html import escape
from urllib.parse import urlencode
from .nft_detail_page import LOCALES, STYLE, language_menu
from .gap_projection import gap_label
from .reference_provenance_page import render_reference_fields, LABELS
from .market_reference_refresh import REFERENCE_SCRIPT

ASSETS = {name: ("image/png" if name.endswith(".png") else "image/svg+xml") for name in
          ("soy.png", "ore.png", "copper.png", "cube.svg", "search.svg", "sparkline.svg", "sparkline-stale.svg", "collateral-swap-crypto.svg", "collateral-swap-receipt.svg", "collateral-arrow.svg")}
PHOTOS = {"soy": "soy.png", "iron-ore": "ore.png", "copper": "copper.png"}
BASE_UNITS = {"en": "base units / NFT", "zh-Hans": "最小单位 / NFT", "zh-Hant": "最小單位 / NFT",
              "fr": "unités minimales / NFT", "es": "unidades mínimas / NFT", "ja": "最小単位 / NFT"}
WORDS = {
    "en": ("Market", "Spot trading", "Two-way collateral", "Receipt registration", "Commodity references",
           "Documented goods. Orderly trading.", "Whole receipts, source-bound observations and separate settlement currencies.",
           "Reference prices and NFT orders are separate. EX provides no conversion.", "Original details not provided", "Illustration only",
           "View NFT details", "Execution route not connected", "Search", "No matching NFT records", "All NFTs", "Not connected",
           "Order book", "Settlement currency", "Whole receipt", "Price / whole NFT (base units)", "Priority", "No currently eligible orders", "Order book unavailable", "Original price history not provided", "Receipt details", "Refresh observation", "Buy receipt", "Sell receipt", "Limit price", "Source observation, not an execution result", "Choose receipt", "Whole-receipt order", "Immutable currencies not provided", "Only original settlement currencies are shown. No conversion."),
    "zh-Hans": ("市场", "现货交易", "双向质押", "仓单登记", "商品参考行情", "有据商品，有序交易。",
                "整张仓单、绑定来源的观察与独立结算币种。", "参考价与 NFT 订单分开。EX 不提供兑换。", "原始资料未提供", "仅为示意图",
                "查看 NFT 详情", "执行路由未接通", "搜索", "没有匹配的 NFT 记录", "全部 NFT", "未连接",
           "订单簿", "结算币种", "整张仓单", "每张 NFT 价格（最小单位）", "优先序", "当前无符合条件的订单", "订单簿不可用", "原始价格历史未提供", "仓单详情", "刷新观察", "买入仓单", "卖出仓单", "限价", "来源观察，不是执行结果", "选择仓单", "整张仓单订单", "不可变币种集合未提供", "只展示原始结算币种，不提供兑换。"),
    "zh-Hant": ("市場", "現貨交易", "雙向質押", "倉單登記", "商品參考行情", "有據商品，有序交易。",
                "整張倉單、綁定來源的觀察與獨立結算幣種。", "參考價與 NFT 訂單分開。EX 不提供兌換。", "原始資料未提供", "僅為示意圖",
                "查看 NFT 詳情", "執行路由未接通", "搜尋", "沒有匹配的 NFT 記錄", "全部 NFT", "未連接",
           "訂單簿", "結算幣種", "整張倉單", "每張 NFT 價格（最小單位）", "優先序", "目前無符合條件的訂單", "訂單簿不可用", "原始價格歷史未提供", "倉單詳情", "重新整理觀察", "買入倉單", "賣出倉單", "限價", "來源觀察，不是執行結果", "選擇倉單", "整張倉單訂單", "不可變幣種集合未提供", "只顯示原始結算幣種，不提供兌換。"),
    "fr": ("Marché", "Négoce au comptant", "Garanties bidirectionnelles", "Enregistrement", "Références de matières premières",
           "Des biens documentés. Des échanges ordonnés.", "Récépissés entiers, observations liées à leur source et devises de règlement distinctes.",
           "Les références et les ordres NFT sont distincts. EX ne convertit pas les devises.", "Données originales non fournies", "Illustration uniquement",
           "Voir les détails NFT", "Circuit d’exécution non connecté", "Rechercher", "Aucun NFT correspondant", "Tous les NFT", "Non connecté",
           "Carnet d’ordres", "Devise de règlement", "Récépissé entier", "Prix / NFT entier (unités minimales)", "Priorité", "Aucun ordre actuellement admissible", "Carnet d’ordres indisponible", "Historique de prix original non fourni", "Détails du récépissé", "Actualiser l’observation", "Acheter le récépissé", "Vendre le récépissé", "Prix limite", "Observation de source, pas un résultat d’exécution", "Choisir un récépissé", "Ordre sur récépissé entier", "Devises immuables non fournies", "Seules les devises de règlement originales sont affichées. Aucune conversion."),
    "es": ("Mercado", "Negociación al contado", "Garantías bidireccionales", "Registro", "Referencias de materias primas",
           "Bienes documentados. Negociación ordenada.", "Recibos completos, observaciones vinculadas a su fuente y monedas de liquidación separadas.",
           "Las referencias y las órdenes NFT son independientes. EX no convierte monedas.", "Datos originales no proporcionados", "Solo ilustración",
           "Ver detalles NFT", "Ruta de ejecución sin conectar", "Buscar", "No hay NFT coincidentes", "Todos los NFT", "Sin conectar",
           "Libro de órdenes", "Moneda de liquidación", "Recibo completo", "Precio / NFT completo (unidades mínimas)", "Prioridad", "No hay órdenes actualmente admisibles", "Libro de órdenes no disponible", "Historial de precios original no proporcionado", "Detalles del recibo", "Actualizar observación", "Comprar recibo", "Vender recibo", "Precio límite", "Observación de origen, no resultado de ejecución", "Elegir recibo", "Orden de recibo completo", "Monedas inmutables no proporcionadas", "Solo se muestran las monedas de liquidación originales. Sin conversión."),
    "ja": ("市場", "現物取引", "双方向担保", "倉荷証券登録", "商品参考相場", "記録された商品。秩序ある取引。",
           "倉荷証券全体、出典に紐づく観測と個別の決済通貨。", "参考価格と NFT 注文は別です。EX は通貨を交換しません。", "元の情報は未提供", "説明用の画像です",
           "NFT の詳細を見る", "実行経路は未接続", "検索", "一致する NFT 記録はありません", "すべての NFT", "未接続",
           "注文板", "決済通貨", "倉荷証券全体", "NFT 全体の価格（最小単位）", "優先順位", "現在、適格な注文はありません", "注文板は利用できません", "元の価格履歴は未提供", "倉荷証券の詳細", "観測を更新", "倉荷証券を購入", "倉荷証券を売却", "指値", "出典の観測であり実行結果ではありません", "倉荷証券を選択", "倉荷証券全体の注文", "不変の通貨集合は未提供", "元の決済通貨のみ表示します。両替は行いません。"),
}
STATES = {
    "en": ("Fresh", "Stale", "Unavailable", "Unknown", "SIMULATED", "Original order"),
    "zh-Hans": ("有效时点内", "已陈旧", "不可用", "未知", "模拟", "原始订单"),
    "zh-Hant": ("有效時點內", "已陳舊", "不可用", "未知", "模擬", "原始訂單"),
    "fr": ("À jour", "Périmé", "Indisponible", "Inconnu", "SIMULÉ", "Ordre original"),
    "es": ("Actualizado", "Obsoleto", "No disponible", "Desconocido", "SIMULADO", "Orden original"),
    "ja": ("鮮度範囲内", "古いデータ", "利用不可", "不明", "シミュレーション", "元の注文"),
}
MARKET_STYLE = """
#commodity-reference{max-width:360px;display:grid;gap:10px;padding:20px;border-radius:10px;margin:24px 0}
#commodity-reference h2{font-size:16px;line-height:24px;margin:0}
#commodity-reference p{margin:0;overflow-wrap:anywhere}
#commodity-reference .quote{font-size:28px;line-height:42px}
.reference-instrument,.reference-source{font-size:11px;color:var(--muted);line-height:17px}
.reference-provenance{min-width:0}.reference-provenance summary{min-height:44px;display:list-item;align-content:center;cursor:pointer;color:var(--muted);font-size:12px}
.reference-provenance summary:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.reference-provenance .source-fields{display:block}.reference-provenance dt{margin-top:10px;color:var(--muted)}.reference-provenance dd{margin:3px 0 0;overflow-wrap:anywhere}
.market-top{display:flex;align-items:center;gap:36px;flex-wrap:wrap;padding:20px 0}.market-top>a{min-height:44px;display:inline-flex;align-items:center;text-decoration:none}.market-top>a[aria-current=page]{color:var(--accent)}.market-top nav{margin-left:auto}.market-top .locale-menu{margin-left:auto}.wallet-entry{background:var(--raised);border-radius:6px;padding:0 16px}.market-top a:focus-visible,.hero a:focus-visible{outline:2px solid var(--accent);outline-offset:4px}.hero-start{display:inline-flex;align-items:center;min-height:44px;padding:0 24px;border-radius:6px;background:var(--accent);color:var(--bg);text-decoration:none}.market-top b{font-size:25px}.notice{padding:12px 20px;background:#20312a;color:var(--muted)}
.hero{display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:center}.hero h1{font-size:42px;line-height:1.3}.hero-photo{width:370px;max-width:100%;height:192px;object-fit:cover;border-radius:8px}
.nft-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.nft-card{display:grid;gap:12px;text-decoration:none;color:var(--ink);padding:20px;border:1px solid var(--line);border-radius:12px;background:var(--surface);min-width:0;overflow-wrap:anywhere}
.product-photo{width:100%;height:148px;object-fit:cover;border-radius:8px}.nft-card:hover{border-color:var(--accent)}.badge{padding:5px 10px;border:1px solid var(--line);border-radius:5px;display:inline-block}.badge.open{color:var(--accent);border-color:var(--accent);background:#20312a}.quote{font:28px 'IBM Plex Mono',monospace}.search{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.search input{background:var(--raised);color:var(--ink);border:1px solid var(--line);padding:12px;max-width:100%}button{background:var(--raised);color:var(--ink);padding:12px;border:1px solid var(--line);border-radius:6px}button:disabled{opacity:.55}dl{display:grid;grid-template-columns:max-content 1fr;gap:8px;overflow-wrap:anywhere}dd{margin:0;min-width:0}.source-fields{font-size:12px}.market-tools{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}
@media(max-width:850px){.nft-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.hero{grid-template-columns:1fr}.hero h1{font-size:32px}}@media(max-width:550px){.nft-grid{grid-template-columns:1fr}.market-top{gap:16px}.hero h1{font-size:28px}dl{grid-template-columns:1fr}.search input{width:100%}}
"""


EMPTY_MODE = {"en": "Read-only catalogue", "zh-Hans": "只读目录", "zh-Hant": "唯讀目錄",
              "fr": "Catalogue en lecture seule", "es": "Catálogo de solo lectura", "ja": "読み取り専用一覧"}


PROVENANCE_SUMMARY = {
    "en": "Source details", "zh-Hans": "来源详情", "zh-Hant": "來源詳情",
    "fr": "Détails de la source", "es": "Detalles de origen", "ja": "出典の詳細",
}


REFRESH_FAILURE = {
    "en": "Page refresh unavailable; the previous observation is retained.",
    "zh-Hans": "\u9875\u9762\u5237\u65b0\u4e0d\u53ef\u7528\uff1b\u4fdd\u7559\u4e0a\u6b21\u89c2\u5bdf\u503c\u3002",
    "zh-Hant": "\u9801\u9762\u66f4\u65b0\u4e0d\u53ef\u7528\uff1b\u4fdd\u7559\u4e0a\u6b21\u89c0\u5bdf\u503c\u3002",
    "fr": "Actualisation de la page indisponible ; observation pr\u00e9c\u00e9dente conserv\u00e9e.",
    "es": "Actualizaci\u00f3n de p\u00e1gina no disponible; se conserva la observaci\u00f3n anterior.",
    "ja": "\u30da\u30fc\u30b8\u3092\u66f4\u65b0\u3067\u304d\u307e\u305b\u3093\u3002\u524d\u56de\u306e\u89b3\u6e2c\u5024\u3092\u4fdd\u6301\u3057\u3066\u3044\u307e\u3059\u3002",
}


def render_reference_panel(reference, locale="en"):
    if locale not in LOCALES or type(reference) is not dict:
        raise ValueError("original reference observation and locale required")
    t, common, states = WORDS[locale], LOCALES[locale], STATES[locale]
    e = lambda value: escape(str(value), quote=True)
    status = reference.get("status", "not-connected")
    label = {"fresh": states[0], "stale": states[1], "unavailable": states[2],
             "unknown": states[3], "not-connected": t[15]}.get(status, states[3])
    def text(key):
        value = reference.get(key)
        return value if type(value) is str and value else common[3]
    labels = LABELS[locale]
    return ('<section id="commodity-reference" aria-live="polite"><h2>' + e(t[4])
            + '</h2><p class="reference-instrument">' + e(text("spec"))
            + ' · ' + e(text("currency")) + ' / ' + e(text("unit"))
            + '</p><p class="missing" data-reference-status>' + e(label)
            + '</p><p class="quote">' + e(reference.get("price") if reference.get("price") is not None else common[3])
            + '</p><p class="reference-source">' + e(labels[0]) + ': ' + e(text("provider"))
            + '</p><p class="reference-source">' + e(labels[9]) + ': ' + e(text("sourceAsOf"))
            + '</p><p class="reference-source">' + e(labels[12]) + ': ' + e(text("fetchedAt"))
            + '</p><details class="reference-provenance"><summary>' + e(PROVENANCE_SUMMARY[locale])
            + '</summary><dl class="source-fields">' + render_reference_fields(reference, locale)
            + '</dl></details><p class="missing" data-browser-error hidden>'
            + e(REFRESH_FAILURE[locale]) + '</p></section>')


def render_market(entries, reference, locale="en", query="", *, empty_catalogue=False, evidence_kind=None, collateral_available=False):
    if evidence_kind not in (None, "LOCAL_SIMULATION"):
        raise ValueError("explicit supported evidence kind required")
    if type(empty_catalogue) is not bool or type(collateral_available) is not bool:
        raise ValueError("explicit catalogue and route modes required")
    if empty_catalogue and entries:
        raise ValueError("empty catalogue cannot contain receipt records")
    if locale not in LOCALES or len(query) > 64:
        raise ValueError("market locale or search refused")
    t, common, states = WORDS[locale], LOCALES[locale], STATES[locale]
    e = lambda value: escape(str(value), quote=True)
    cards = []
    for index, entry in enumerate(entries):
        card = entry.get("marketCard") or {}
        name = card.get("name") or "NFT " + str(index + 1)
        if query and query.casefold() not in (name + " " + card.get("spec", "")).casefold():
            continue
        key = entry["nftKey"]
        href = '/nft?' + urlencode({"lang": locale, "nft": key, "q": query})
        photo = PHOTOS.get(card.get("commodityCode"))
        image = ('<img class="product-photo" src="/assets/' + photo + '" alt="' + e(t[9]) + '">') if photo else ''
        gap, gap_class = gap_label(entry, locale)
        quote = card.get("quote")
        price = (e(quote["amountBaseUnits"]) + ' ' + e(quote["currency"]) + '<small> ' + e(BASE_UNITS[locale]) + '</small><p class="muted">'
                 + e(states[4] if quote["source"] == "simulated" else states[5]) + '</p>') if quote else e(common[3])
        quantity = e(card["quantity"] + ' ' + card["unit"]) if card else e(t[8])
        cards.append('<a class="nft-card" id="nft-' + key + '" href="' + e(href) + '">' + image
                     + '<h2>' + e(name) + '</h2><p class="muted">' + e(card.get("spec", t[8])) + '</p><div class="quote">'
                     + price + '</div><p>' + quantity + ' · 1 NFT</p><p><span class="badge ' + gap_class
                     + '">' + e(gap) + '</span></p><span>' + e(t[10]) + ' →</span></a>')
    terminal_href = "#nfts" if empty_catalogue else "/terminal?" + urlencode({"lang": locale, "q": query})
    collateral_link = ('<a class="collateral-entry" href="/collateral?' + e(urlencode({"lang": locale})) +
                       '">' + e(t[2]) + '</a>') if collateral_available else '<span>' + e(t[2]) + '</span>'
    reference_panel = render_reference_panel(reference, locale)
    languages = ''.join('<a href="/market?' + e(urlencode({"lang": key, "q": query})) + '" lang="' + key + '">' + key + '</a>' for key in LOCALES)
    return ('<!doctype html><html lang="' + locale + '"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>8415EX · ' + e(t[0]) + '</title><style>' + STYLE + MARKET_STYLE + '</style><body><main><header class="market-top">'
            '<img src="/assets/cube.svg" width="20" height="20" alt=""><b>8415EX</b><span class="badge">' + e(EMPTY_MODE[locale] if empty_catalogue else evidence_kind or "DEMO") + '</span><a href="#nfts" aria-current="page">' + e(t[0])
            + '</a><a href="' + e(terminal_href) + '">' + e(t[1]) + '</a>' + collateral_link + '<span>' + e(t[3]) + '</span>' + language_menu(languages, locale, common[17]) + '<a class="wallet-entry" href="https://8415wallet.com" rel="noopener noreferrer">8415Wallet &#8599;</a></header>'
            '<p class="notice">' + e(t[7]) + '</p>' + reference_panel + '<section class="hero"><div><h1>' + e(t[5])
            + '</h1><p class="muted">' + e(t[6]) + '</p><a class="hero-start" href="' + e(terminal_href) + '">' + e(t[1]) + '</a></div><figure><img class="hero-photo" src="/assets/soy.png" alt="'
            + e(t[9]) + '"><figcaption class="muted">' + e(t[9]) + '</figcaption></figure></section><div class="market-tools"><h2 id="nfts">' + e(t[1])
            + '</h2><a href="/market?' + e(urlencode({"lang": locale})) + '">' + e(t[14]) + '</a><form class="search" method="get" action="/market">'
            '<input type="hidden" name="lang" value="' + locale + '"><img src="/assets/search.svg" width="18" height="18" alt=""><input name="q" maxlength="64" value="'
            + e(query) + '" aria-label="' + e(t[12]) + '"><button>' + e(t[12]) + '</button></form></div><div class="nft-grid">'
            + (''.join(cards) or '<p>' + e(t[13]) + '</p>') + '</div><footer class="muted">' + e(t[7]) + '</footer></main><script>' + REFERENCE_SCRIPT + '</script></body></html>')

TERMINAL_STYLE = """
.terminal-layout{display:grid;grid-template-columns:minmax(0,964px) minmax(300px,372px);gap:24px;align-items:start}
.terminal-main{min-width:0}.terminal-upper{display:grid;grid-template-columns:264px minmax(0,1fr);gap:16px}
.terminal-lower{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.16fr);gap:16px}
.terminal-layout .quote{overflow-wrap:anywhere}.terminal-layout select,.terminal-layout input{box-sizing:border-box}
.terminal-layout section{margin:0 0 16px;min-width:0}.terminal-ticket{position:sticky;top:16px}
.terminal-chart{min-height:312px;display:grid;align-content:center;text-align:center;color:var(--muted)}
.terminal-heading{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}
.terminal-layout h1{font-size:22px}.terminal-layout h2{font-size:16px;margin:0 0 16px}
.terminal-layout table{width:100%;table-layout:fixed;border-collapse:collapse;font-size:12px}
.terminal-layout th,.terminal-layout td{padding:10px 4px;text-align:left;overflow-wrap:anywhere}
.terminal-layout th{color:var(--muted);font-weight:400}.terminal-layout tr{border-bottom:1px solid var(--line)}
.terminal-layout .ask{color:#ea927f}.terminal-layout .bid{color:#a9d991}
.terminal-layout label{display:block;font-size:12px;color:var(--muted);margin:12px 0}
.terminal-layout select,.terminal-layout input{width:100%;max-width:100%;min-width:0;min-height:44px;background:var(--raised);color:var(--ink);border:1px solid var(--line);padding:10px;border-radius:6px;font:inherit}
.terminal-layout button,.terminal-layout a.action{min-height:44px;display:inline-flex;align-items:center;padding:10px 16px;border:1px solid var(--line);border-radius:6px}
.terminal-layout a{color:var(--muted);overflow-wrap:anywhere}.terminal-layout .active-side{background:var(--accent);color:var(--bg)}
.terminal-side{display:flex;gap:8px;flex-wrap:wrap}.terminal-side a{flex:1;justify-content:center;text-decoration:none}
.terminal-empty{padding:24px 0;color:var(--muted)}.terminal-scope{font-size:11px;color:var(--muted);line-height:1.6}
.terminal-layout :focus-visible{outline:2px solid var(--accent);outline-offset:3px}
@media(max-width:1100px){.terminal-layout{grid-template-columns:minmax(0,1fr) 320px}.terminal-upper,.terminal-lower{grid-template-columns:1fr}}
@media(max-width:850px){.terminal-layout{grid-template-columns:1fr}.terminal-ticket{position:static}.terminal-upper,.terminal-lower{grid-template-columns:1fr}}
"""


def render_terminal(detail, choices, currencies, book, locale="en", *, nft_key,
                    currency=None, market_query="", side="buy", evidence_kind=None, collateral_available=False):
    """Original selected observations only; this renderer never submits an order."""
    if (type(collateral_available) is not bool or locale not in LOCALES or side not in ("buy", "sell")
            or evidence_kind not in (None, "LOCAL_SIMULATION")
            or (currency is not None and (currencies is None or currency not in currencies))):
        raise ValueError("supported terminal observation required")
    t, common = WORDS[locale], LOCALES[locale]
    e = lambda value: escape(str(value), quote=True)
    def target(**changes):
        values = {"lang": locale, "nft": nft_key, "q": market_query, "side": side}
        if currency is not None:
            values["currency"] = currency
        values.update(changes)
        return "/terminal?" + urlencode(values)
    def hidden(name, value):
        return '<input type="hidden" name="' + name + '" value="' + e(value) + '">'
    context = hidden("lang", locale) + hidden("q", market_query) + hidden("side", side)
    languages = ''.join('<a href="' + e(target(lang=lang)) + '" lang="' + lang + '">' + lang + '</a>' for lang in LOCALES)
    back = "/market?" + urlencode({"lang": locale, "q": market_query}) + "#nft-" + nft_key
    detail_href = "/nft?" + urlencode({"lang": locale, "nft": nft_key, "q": market_query})
    collateral_href = "/collateral?" + urlencode({"lang": locale, "target": nft_key})
    collateral_link = ('<a class="collateral-entry" href="' + e(collateral_href) + '">' +
                       e(t[2]) + '</a>') if collateral_available else '<span>' + e(t[2]) + '</span>'
    card = detail.get("marketCard") or {}
    name = card.get("name") or "NFT"
    quote = card.get("quote")
    price = (quote["amountBaseUnits"] if quote and quote["currency"] == currency else common[3])
    options = ''.join('<option value="' + e(row["nftKey"]) + '"' +
        (' selected' if row["nftKey"] == nft_key else '') + '>NFT ' + str(index + 1) + '</option>'
        for index, row in enumerate(choices))
    receipt_form = '<form method="get" action="/terminal">' + context + '<label>' + e(t[30]) + '<select name="nft">' + options + '</select></label><button>' + e(t[30]) + '</button></form>'
    if currencies:
        currency_options = ''.join('<option value="' + e(value) + '"' + (' selected' if value == currency else '') + '>' + e(value) + '</option>' for value in currencies)
        currency_form = '<form method="get" action="/terminal">' + context + hidden("nft", nft_key) + '<label>' + e(t[17]) + '<select name="currency">' + currency_options + '</select></label><button>' + e(t[25]) + '</button></form>'
    else:
        currency_form = '<p class="missing">' + e(t[32]) + '</p>'
    def levels(name, css, label):
        if book is None:
            return '<p class="terminal-empty">' + e(t[22]) + '</p>'
        data = book[name]
        if not data["rows"]:
            return '<p class="terminal-empty">' + e(label) + ' · ' + e(t[21]) + '</p>'
        rows = ''.join('<tr class="' + css + '"><td>' + e(row["priceBaseUnits"]) + '</td><td>1 NFT</td><td>' + e(row["priority"]) + '</td></tr>' for row in data["rows"])
        return '<h3>' + e(label) + '</h3><table><thead><tr><th>' + e(t[19]) + '</th><th>' + e(t[18]) + '</th><th>' + e(t[20]) + '</th></tr></thead><tbody>' + rows + '</tbody></table>' + ('<p class="muted">' + str(len(data["rows"])) + ' / ' + str(data["total"]) + '</p>' if data["hasMore"] else '')
    gap, gap_class = gap_label(detail, locale)
    image = PHOTOS.get(card.get("commodityCode"))
    photo = '<img class="product-photo" src="/assets/' + image + '" alt="' + e(t[9]) + '">' if image else ''
    return ('<!doctype html><html lang="' + locale + '"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>8415EX · ' + e(t[1]) + '</title><style>' + STYLE + MARKET_STYLE + TERMINAL_STYLE + '</style><body><main>'
        '<header class="market-top"><img src="/assets/cube.svg" width="20" height="20" alt=""><b>8415EX</b><span class="badge">' + e(evidence_kind or EMPTY_MODE[locale]) + '</span><a href="' + e(back) + '">' + e(t[0]) + '</a><a href="' + e(target()) + '" aria-current="page">' + e(t[1]) + '</a>' + collateral_link + '<span>' + e(t[3]) + '</span>' + language_menu(languages, locale, common[17]) + '<a class="wallet-entry" href="https://8415wallet.com" rel="noopener noreferrer">8415Wallet &#8599;</a></header>'
        '<div class="terminal-heading"><h1>' + e(t[1]) + '</h1><a class="action" href="' + e(detail_href) + '">' + e(t[24]) + ' →</a></div><p class="notice">' + e(t[33]) + '</p>'
        '<div class="terminal-layout"><div class="terminal-main"><div class="terminal-upper"><section class="terminal-product">' + photo + '<h2>' + e(name) + '</h2><p class="quote">' + e(price) + '</p><p class="muted">' + e(currency or common[3]) + ' · ' + e(t[19]) + '</p><span class="badge ' + gap_class + '">' + e(gap) + '</span><p><a href="' + e(detail_href) + '">' + e(t[24]) + ' →</a></p></section><section class="terminal-chart"><h2>' + e(t[23]) + '</h2><p>' + e(t[29]) + '</p></section></div>'
        '<div class="terminal-lower"><section class="terminal-book"><div class="terminal-heading"><h2>' + e(t[16]) + '</h2><span class="badge">' + e(currency or common[3]) + '</span></div>' + levels("asks", "ask", t[27]) + levels("bids", "bid", t[26]) + '<p class="terminal-scope">' + e(t[29]) + '</p></section><section class="terminal-receipts"><h2>' + e(t[30]) + '</h2>' + receipt_form + '<a href="' + e(detail_href) + '">' + e(t[24]) + ' →</a></section></div></div>'
        '<section class="terminal-ticket"><h2>' + e(t[31]) + '</h2><nav class="terminal-side"><a class="action ' + ('active-side' if side == "buy" else '') + '" href="' + e(target(side="buy")) + '">' + e(t[26]) + '</a><a class="action ' + ('active-side' if side == "sell" else '') + '" href="' + e(target(side="sell")) + '">' + e(t[27]) + '</a></nav>' + currency_form + '<p>1 NFT</p><label>' + e(t[28]) + '<input readonly value="' + e(price) + '"></label><p class="muted">ETH gas · ' + e(common[3]) + '</p><button disabled>' + e(t[11]) + '</button><p class="terminal-scope">' + e(t[29]) + '</p></section></div></main></body></html>')
