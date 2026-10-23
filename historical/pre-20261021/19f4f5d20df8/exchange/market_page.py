"""Commodity market surface over original NFT and reference observations."""
from html import escape
from urllib.parse import urlencode
from .nft_detail_page import LOCALES, STYLE
from .gap_projection import gap_label
from .reference_provenance_page import render_reference_fields
from .demo_commodities import (COMMODITY_ORDER, COMMODITY_CODES, DISPLAY_WORDS,
                              GROUP_NAMES, GROUPS, commodity_name, commodity_order, matches_query)
from .demo_commodity_pages import DEMO_STYLE, WORDS as DEMO_WORDS, render_demo_quotes, render_demo_products

ASSETS = {name: ("image/png" if name.endswith(".png") else "image/svg+xml") for name in
          ("soy.png", "ore.png", "copper.png", "cube.svg", "search.svg", "sparkline.svg", "sparkline-stale.svg",
           "gold.svg", "silver.svg", "crude-oil.svg", "coal.svg", "corn.svg")}
PHOTOS = {"soy": "soy.png", "iron-ore": "ore.png", "copper": "copper.png",
          "gold": "gold.svg", "silver": "silver.svg", "crude-oil": "crude-oil.svg",
          "coal": "coal.svg", "corn": "corn.svg"}
BASE_UNITS = {"en": "base units / NFT", "zh-Hans": "最小单位 / NFT", "zh-Hant": "最小單位 / NFT",
              "fr": "unités minimales / NFT", "es": "unidades mínimas / NFT", "ja": "最小単位 / NFT"}
WORDS = {
    "en": ("Market", "Spot trading", "Two-way collateral", "Receipt registration", "Commodity references",
           "Documented goods. Orderly trading.", "Whole receipts, source-bound observations and separate settlement currencies.",
           "Reference prices and NFT orders are separate. EX provides no conversion.", "Original details not provided", "Illustration only",
           "View NFT details", "Execution route not connected", "Search", "No matching NFT records", "All NFTs", "Not connected"),
    "zh-Hans": ("市场", "现货交易", "双向质押", "仓单登记", "商品参考行情", "有据商品，有序交易。",
                "整张仓单、绑定来源的观察与独立结算币种。", "参考价与 NFT 订单分开。EX 不提供兑换。", "原始资料未提供", "仅为示意图",
                "查看 NFT 详情", "执行路由未接通", "搜索", "没有匹配的 NFT 记录", "全部 NFT", "未连接"),
    "zh-Hant": ("市場", "現貨交易", "雙向質押", "倉單登記", "商品參考行情", "有據商品，有序交易。",
                "整張倉單、綁定來源的觀察與獨立結算幣種。", "參考價與 NFT 訂單分開。EX 不提供兌換。", "原始資料未提供", "僅為示意圖",
                "查看 NFT 詳情", "執行路由未接通", "搜尋", "沒有匹配的 NFT 記錄", "全部 NFT", "未連接"),
    "fr": ("Marché", "Négoce au comptant", "Garanties bidirectionnelles", "Enregistrement", "Références de matières premières",
           "Des biens documentés. Des échanges ordonnés.", "Récépissés entiers, observations liées à leur source et devises de règlement distinctes.",
           "Les références et les ordres NFT sont distincts. EX ne convertit pas les devises.", "Données originales non fournies", "Illustration uniquement",
           "Voir les détails NFT", "Circuit d’exécution non connecté", "Rechercher", "Aucun NFT correspondant", "Tous les NFT", "Non connecté"),
    "es": ("Mercado", "Negociación al contado", "Garantías bidireccionales", "Registro", "Referencias de materias primas",
           "Bienes documentados. Negociación ordenada.", "Recibos completos, observaciones vinculadas a su fuente y monedas de liquidación separadas.",
           "Las referencias y las órdenes NFT son independientes. EX no convierte monedas.", "Datos originales no proporcionados", "Solo ilustración",
           "Ver detalles NFT", "Ruta de ejecución sin conectar", "Buscar", "No hay NFT coincidentes", "Todos los NFT", "Sin conectar"),
    "ja": ("市場", "現物取引", "双方向担保", "倉荷証券登録", "商品参考相場", "記録された商品。秩序ある取引。",
           "倉荷証券全体、出典に紐づく観測と個別の決済通貨。", "参考価格と NFT 注文は別です。EX は通貨を交換しません。", "元の情報は未提供", "説明用の画像です",
           "NFT の詳細を見る", "実行経路は未接続", "検索", "一致する NFT 記録はありません", "すべての NFT", "未接続"),
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
.market-top{display:flex;align-items:center;gap:24px;flex-wrap:wrap}.market-top b{font-size:25px}.notice{padding:12px 20px;background:#20312a;color:var(--muted)}
.commodity-grid{display:none;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.commodity-category{display:block;padding:12px;border:1px solid var(--line);border-radius:8px;text-decoration:none;color:var(--ink)}.commodity-category.active{border-color:var(--accent)}.commodity-category h3{margin:0}.commodity-label{color:var(--muted)}.commodity-filters{display:flex;gap:8px;flex-wrap:wrap}.commodity-filters a{padding:6px 10px;background:var(--raised);text-decoration:none;border-radius:5px}.commodity-filters a.active{background:var(--accent);color:var(--bg)}
.product-illustration{display:block;max-width:100%;height:auto;border-radius:8px}
.hero{display:grid;grid-template-columns:1fr 1fr;gap:24px;align-items:center}.hero h1{font-size:42px;line-height:1.3}.hero-photo{width:370px;max-width:100%;height:192px;object-fit:cover;border-radius:8px}
.nft-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.nft-card{display:grid;gap:12px;text-decoration:none;color:var(--ink);padding:20px;border:1px solid var(--line);border-radius:12px;background:var(--surface);min-width:0;overflow-wrap:anywhere}
.product-photo{width:100%;height:148px;object-fit:cover;border-radius:8px}.nft-card:hover{border-color:var(--accent)}.badge{padding:5px 10px;border:1px solid var(--line);border-radius:5px;display:inline-block}.badge.open{color:var(--accent);border-color:var(--accent);background:#20312a}.quote{font:28px 'IBM Plex Mono',monospace}.search{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.search input{background:var(--raised);color:var(--ink);border:1px solid var(--line);padding:12px;max-width:100%}button{background:var(--raised);color:var(--ink);padding:12px;border:1px solid var(--line);border-radius:6px}button:disabled{opacity:.55}dl{display:grid;grid-template-columns:max-content 1fr;gap:8px;overflow-wrap:anywhere}dd{margin:0;min-width:0}.source-fields{font-size:12px}.market-tools{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}
@media(max-width:850px){.nft-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.hero{grid-template-columns:1fr}.hero h1{font-size:32px}}@media(max-width:550px){.nft-grid{grid-template-columns:1fr}.commodity-grid{display:grid}.commodity-filters{display:none}.market-top{gap:16px}.hero h1{font-size:28px}dl{grid-template-columns:1fr}.search input{width:100%}}
"""


EMPTY_MODE = {"en": "Read-only catalogue", "zh-Hans": "只读目录", "zh-Hant": "唯讀目錄",
              "fr": "Catalogue en lecture seule", "es": "Catálogo de solo lectura", "ja": "読み取り専用一覧"}


def render_market(entries, reference, locale="en", query="", *, empty_catalogue=False):
    if type(empty_catalogue) is not bool:
        raise ValueError("explicit catalogue mode required")
    if empty_catalogue and entries:
        raise ValueError("empty catalogue cannot contain receipt records")
    if locale not in LOCALES or len(query) > 64:
        raise ValueError("market locale or search refused")
    t, common, states = WORDS[locale], LOCALES[locale], STATES[locale]
    e = lambda value: escape(str(value), quote=True)
    cards = []
    # Display ordering only; never reorder an order book or mutate source rows.
    ordered = sorted(entries, key=lambda row: commodity_order((row.get("marketCard") or {}).get("commodityCode")))
    for index, entry in enumerate(ordered):
        card = entry.get("marketCard") or {}
        code = card.get("commodityCode")
        if card and code not in COMMODITY_CODES:
            continue
        source_name = card.get("name") or "NFT " + str(index + 1)
        name = commodity_name(code, locale) or source_name
        if not matches_query(code, source_name + " " + name + " " + card.get("spec", ""), query, locale):
            continue
        key = entry["nftKey"]
        href = '/nft?' + urlencode({"lang": locale, "nft": key, "q": query})
        photo = PHOTOS.get(card.get("commodityCode"))
        image = (('<img class="product-illustration" width="400" height="148" src="/assets/' + photo
                  + '" alt="' + e(t[9]) + '">') if photo.endswith('.svg') else
                 ('<img class="product-photo" src="/assets/' + photo + '" alt="' + e(t[9]) + '">')) if photo else ''
        gap, gap_class = gap_label(entry, locale)
        quote = card.get("quote")
        price = (e(quote["amountBaseUnits"]) + ' ' + e(quote["currency"]) + '<small> ' + e(BASE_UNITS[locale]) + '</small><p class="muted">'
                 + e(states[4] if quote["source"] == "simulated" else states[5]) + '</p>') if quote else e(common[3])
        quantity = e(card["quantity"] + ' ' + card["unit"]) if card else e(t[8])
        cards.append('<a class="nft-card" id="nft-' + key + '" href="' + e(href) + '">' + image
                     + '<h2>' + e(name) + '</h2><p class="commodity-label">' + e(source_name) + '</p><p class="muted">' + e(card.get("spec", t[8])) + '</p><div class="quote">'
                     + price + '</div><p>' + quantity + ' · 1 NFT</p><p><span class="badge ' + gap_class
                     + '">' + e(gap) + '</span></p><span>' + e(t[10]) + ' →</span></a>')
    status = reference.get("status", "not-connected")
    status_label = {"fresh": states[0], "stale": states[1], "unavailable": states[2], "unknown": states[3], "not-connected": t[15]}.get(status, states[3])
    fields = render_reference_fields(reference, locale)
    languages = ''.join('<a href="/market?' + e(urlencode({"lang": key, "q": query})) + '" lang="' + key + '">' + key + '</a>' for key in LOCALES)
    category_words = DISPLAY_WORDS[locale]
    categories = ''.join('<a class="commodity-category' + (' active' if query.casefold() == code else '')
        + '" data-demo-commodity="' + code + '" href="/market?'
        + e(urlencode({"lang": locale, "q": code})) + '#nfts"><span class="badge">DEMO</span><h3>'
        + e(commodity_name(code, locale)) + '</h3></a>' for code in COMMODITY_ORDER)
    filters = ''.join('<a class="' + ('active' if query == value else '') + '" href="/market?'
        + e(urlencode({"lang": locale, "q": value})) + '#nfts">' + e(label) + '</a>'
        for value, label in zip(("",) + tuple("group:" + key for key in GROUPS), GROUP_NAMES[locale]))
    return ('<!doctype html><html lang="' + locale + '"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>8415EX · ' + e(t[0]) + '</title><style>' + STYLE + MARKET_STYLE + DEMO_STYLE + '</style><body><main><header class="market-top">'
            '<img src="/assets/cube.svg" width="20" height="20" alt=""><b>8415EX</b><span class="badge">' + e(EMPTY_MODE[locale] if empty_catalogue else "DEMO") + '</span><a href="#nfts">' + e(t[0])
            + '</a><span>' + e(t[1]) + '</span><span>' + e(t[2]) + '</span><span>' + e(t[3]) + '</span><nav>' + languages + '</nav></header>'
            '<p class="notice">' + e(t[7]) + '</p><section class="demo-area"><h2>' + e(t[4]) + '</h2>' + render_demo_quotes(locale)
            + '<details><summary>' + e(t[4]) + ' · ' + e(status_label) + '</summary><p class="missing">' + e(status_label)
            + '</p><p class="quote">' + e(reference.get("price") if reference.get("price") is not None else common[3])
            + '</p><dl class="source-fields">' + fields + '</dl></details></section><section class="hero"><div><h1>' + e(t[5])
            + '</h1><p class="muted">' + e(t[6]) + '</p><button disabled>' + e(t[11]) + '</button></div><figure><img class="hero-photo" src="/assets/soy.png" alt="'
            + e(t[9]) + '"><figcaption class="muted">' + e(t[9]) + '</figcaption></figure></section><section aria-label="'
            + e(category_words[0]) + '"><h2>' + e(category_words[0]) + '</h2><p class="muted">' + e(category_words[1])
            + '</p><nav class="commodity-grid">' + categories + '</nav><nav class="commodity-filters">' + filters + '</nav></section><div class="market-tools"><h2 id="nfts">' + e(t[1])
            + '</h2><a href="/market?' + e(urlencode({"lang": locale})) + '">' + e(t[14]) + '</a><form class="search" method="get" action="/market">'
            '<input type="hidden" name="lang" value="' + locale + '"><img src="/assets/search.svg" width="18" height="18" alt=""><input name="q" maxlength="64" value="'
            + e(query) + '" aria-label="' + e(t[12]) + '"><button>' + e(t[12]) + '</button></form></div>' + render_demo_products(locale, query)
            + '<h2>' + e(DEMO_WORDS[locale][8]) + '</h2><div class="nft-grid">'
            + (''.join(cards) or '<p>' + e(t[13]) + '</p>') + '</div><footer class="muted">' + e(t[7]) + '</footer></main></body></html>')
