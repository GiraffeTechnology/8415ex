"""Read-only context for confirmed commodity/crypto demonstration scenes."""
from html import escape
from urllib.parse import urlencode

from .nft_directory import NftDirectory


SCENES = ("hedging", "collateral", "arbitrage")
CRYPTO = ("BTC", "ETH")
COMMODITIES = ("soybean", "iron-ore")
WORDS = {
    "en": ("Market scenarios", "Hedging", "Collateral", "Arbitrage", "Scenario", "Crypto context",
        "Commodity context", "Soybean", "Iron ore", "Connected receipt", "Choose", "Review context",
        "Market", "No receipt connected", "Open original NFT detail", "Simulation context only",
        "This selection does not place an order, create a hedge or identify an executable arbitrage opportunity.",
        "Valuation, financing, ratios, liquidation and returns have not been provided. No economic result is calculated.",
        "BTC/ETH and commodity names are scenario labels; they do not verify asset mappings or receipt contents.",
        "The original receipt, currency, authority and ETH gas rules still apply to any separate trade.",
        "Context unavailable"),
    "zh-Hans": ("市场场景", "套保", "抵押", "套利", "场景", "加密资产背景", "商品背景", "大豆", "铁矿石",
        "已接入仓单", "请选择", "查看场景", "市场", "尚未接入仓单", "打开原NFT详情", "仅为模拟场景",
        "此选择不提交订单、不建立套保，也不表示存在可执行套利机会。",
        "估值、融资、比例、清算和收益参数尚未提供；不计算经济结果。",
        "BTC/ETH和商品名称是场景标签，不证明资产映射或仓单内容已核验。",
        "任何独立交易仍遵循原仓单、币种、授权及ETH燃料规则。", "场景不可用"),
    "zh-Hant": ("市場場景", "套保", "抵押", "套利", "場景", "加密資產背景", "商品背景", "大豆", "鐵礦石",
        "已接入倉單", "請選擇", "查看場景", "市場", "尚未接入倉單", "開啟原NFT詳情", "僅為模擬場景",
        "此選擇不提交訂單、不建立套保，也不表示存在可執行套利機會。",
        "估值、融資、比例、清算和收益參數尚未提供；不計算經濟結果。",
        "BTC/ETH和商品名稱是場景標籤，不證明資產映射或倉單內容已核驗。",
        "任何獨立交易仍遵循原倉單、幣種、授權及ETH燃料規則。", "場景無法使用"),
    "fr": ("Scénarios de marché", "Couverture", "Collatéral", "Arbitrage", "Scénario", "Contexte crypto",
        "Contexte de marchandise", "Soja", "Minerai de fer", "Récépissé connecté", "Choisir", "Voir le contexte",
        "Marché", "Aucun récépissé connecté", "Ouvrir le détail NFT original", "Contexte de simulation uniquement",
        "Cette sélection ne place aucun ordre, ne crée aucune couverture et ne désigne aucune opportunité d’arbitrage exécutable.",
        "Valorisation, financement, ratios, liquidation et rendement ne sont pas fournis. Aucun résultat économique n’est calculé.",
        "BTC/ETH et les marchandises sont des étiquettes de scénario, sans vérification des actifs ou du récépissé.",
        "Toute transaction distincte conserve les règles originales du récépissé, de devise, d’autorité et de gaz ETH.",
        "Contexte indisponible"),
    "es": ("Escenarios de mercado", "Cobertura", "Garantía", "Arbitraje", "Escenario", "Contexto cripto",
        "Contexto de mercancía", "Soja", "Mineral de hierro", "Recibo conectado", "Elegir", "Ver contexto",
        "Mercado", "No hay recibos conectados", "Abrir detalle NFT original", "Solo contexto de simulación",
        "Esta selección no coloca órdenes, no crea coberturas ni identifica una oportunidad de arbitraje ejecutable.",
        "No se han definido valoración, financiación, ratios, liquidación ni rendimientos. No se calcula un resultado económico.",
        "BTC/ETH y las mercancías son etiquetas de escenario; no verifican activos ni contenido del recibo.",
        "Toda operación separada conserva las reglas originales del recibo, moneda, autoridad y gas ETH.",
        "Contexto no disponible"),
    "ja": ("市場シナリオ", "ヘッジ", "担保", "裁定", "シナリオ", "暗号資産の背景", "商品の背景", "大豆", "鉄鉱石",
        "接続された倉荷証券", "選択してください", "選択内容を見る", "市場", "接続された倉荷証券はありません",
        "元のNFT詳細を開く", "シミュレーション用の背景のみ",
        "この選択は注文、ヘッジの作成、実行可能な裁定機会の特定を行いません。",
        "評価額、融資、比率、清算、収益の条件は未提供です。経済的な結果は計算しません。",
        "BTC/ETHと商品名はシナリオのラベルであり、資産連携や倉荷証券内容の検証ではありません。",
        "別途行う取引には元の倉荷証券、通貨、権限、ETHガスの規則が適用されます。", "選択を利用できません"),
}


def scenario_selection(directory, *, scene="", crypto="", commodity="", target=""):
    if type(directory) is not NftDirectory:
        raise ValueError("original NFT directory required")
    for value, allowed in ((scene, SCENES), (crypto, CRYPTO), (commodity, COMMODITIES)):
        if type(value) is not str or (value and value not in allowed):
            raise ValueError("supported scenario context required")
    if type(target) is not str or (target and target not in directory._bindings):
        raise ValueError("original connected receipt required")
    return {"schema": "8415ex-market-scenario-selection/1", "scene": scene or None,
        "cryptoContext": crypto or None, "commodityContext": commodity or None,
        "targetNftKey": target or None, "simulation": True, "executionInvoked": False,
        "receiptCommodityVerified": False, "assetMappingVerified": False,
        "economicParameters": None, "economicResult": None, "tradeEligibilityEvaluated": False}


def render_scenarios(directory, locale="en", **context):
    if locale not in WORDS:
        raise ValueError("supported locale required")
    selection = scenario_selection(directory, **context)
    selected = {"scene": selection["scene"] or "", "crypto": selection["cryptoContext"] or "",
        "commodity": selection["commodityContext"] or "", "target": selection["targetNftKey"] or ""}
    w = WORDS[locale]
    def options(name, rows):
        return ''.join('<option value="' + escape(value, quote=True) + '"'
            + (' selected' if selected[name] == value else '') + '>' + escape(label) + '</option>'
            for value, label in (("", w[10]), *rows))
    fields = (("scene", w[4], tuple(zip(SCENES, w[1:4]))),
        ("crypto", w[5], tuple((value, value) for value in CRYPTO)),
        ("commodity", w[6], tuple(zip(COMMODITIES, w[7:9]))),
        ("target", w[9], tuple((key, "NFT " + str(index + 1))
                             for index, key in enumerate(directory._bindings))))
    controls = ''.join('<p><label>' + escape(label) + ' <select name="' + name + '">'
        + options(name, rows) + '</select></label></p>' for name, label, rows in fields)
    languages = ' '.join('<a lang="' + code + '" href="/scenarios?' + escape(
        urlencode({"lang": code, **selected}), quote=True) + '">' + code + '</a>' for code in WORDS)
    detail = ''
    if selected["target"]:
        detail = '<p><a href="/nft?' + escape(urlencode({"nft": selected["target"], "lang": locale}),
            quote=True) + '">' + escape(w[14]) + '</a></p>'
    return ('<!doctype html><html lang="' + locale + '"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>' + escape(w[0])
        + '</title><body><main><nav><a href="/market?lang=' + locale + '">' + escape(w[12])
        + '</a> ' + languages + '</nav><h1>' + escape(w[0]) + '</h1><p>DEMO</p><p>' + escape(w[15])
        + '</p><form method="get" action="/scenarios"><input type="hidden" name="lang" value="'
        + locale + '">' + controls + '<button type="submit">' + escape(w[11]) + '</button></form>'
        + detail + ('<p>' + escape(w[13]) + '</p>' if not directory._bindings else '')
        + ''.join('<p>' + escape(w[index]) + '</p>' for index in (16, 17, 18, 19))
        + '</main></body></html>')
