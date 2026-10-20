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
    "zh-Hans": ("\u5e02\u573a\u573a\u666f", "\u5957\u4fdd", "\u62b5\u62bc", "\u5957\u5229", "\u573a\u666f", "\u52a0\u5bc6\u8d44\u4ea7\u80cc\u666f", "\u5546\u54c1\u80cc\u666f", "\u5927\u8c46", "\u94c1\u77ff\u77f3",
        "\u5df2\u63a5\u5165\u4ed3\u5355", "\u8bf7\u9009\u62e9", "\u67e5\u770b\u573a\u666f", "\u5e02\u573a", "\u5c1a\u672a\u63a5\u5165\u4ed3\u5355", "\u6253\u5f00\u539fNFT\u8be6\u60c5", "\u4ec5\u4e3a\u6a21\u62df\u573a\u666f",
        "\u6b64\u9009\u62e9\u4e0d\u63d0\u4ea4\u8ba2\u5355\u3001\u4e0d\u5efa\u7acb\u5957\u4fdd\uff0c\u4e5f\u4e0d\u8868\u793a\u5b58\u5728\u53ef\u6267\u884c\u5957\u5229\u673a\u4f1a\u3002",
        "\u4f30\u503c\u3001\u878d\u8d44\u3001\u6bd4\u4f8b\u3001\u6e05\u7b97\u548c\u6536\u76ca\u53c2\u6570\u5c1a\u672a\u63d0\u4f9b\uff1b\u4e0d\u8ba1\u7b97\u7ecf\u6d4e\u7ed3\u679c\u3002",
        "BTC/ETH\u548c\u5546\u54c1\u540d\u79f0\u662f\u573a\u666f\u6807\u7b7e\uff0c\u4e0d\u8bc1\u660e\u8d44\u4ea7\u6620\u5c04\u6216\u4ed3\u5355\u5185\u5bb9\u5df2\u6838\u9a8c\u3002",
        "\u4efb\u4f55\u72ec\u7acb\u4ea4\u6613\u4ecd\u9075\u5faa\u539f\u4ed3\u5355\u3001\u5e01\u79cd\u3001\u6388\u6743\u53caETH\u71c3\u6599\u89c4\u5219\u3002", "\u573a\u666f\u4e0d\u53ef\u7528"),
    "zh-Hant": ("\u5e02\u5834\u5834\u666f", "\u5957\u4fdd", "\u62b5\u62bc", "\u5957\u5229", "\u5834\u666f", "\u52a0\u5bc6\u8cc7\u7522\u80cc\u666f", "\u5546\u54c1\u80cc\u666f", "\u5927\u8c46", "\u9435\u7926\u77f3",
        "\u5df2\u63a5\u5165\u5009\u55ae", "\u8acb\u9078\u64c7", "\u67e5\u770b\u5834\u666f", "\u5e02\u5834", "\u5c1a\u672a\u63a5\u5165\u5009\u55ae", "\u958b\u555f\u539fNFT\u8a73\u60c5", "\u50c5\u70ba\u6a21\u64ec\u5834\u666f",
        "\u6b64\u9078\u64c7\u4e0d\u63d0\u4ea4\u8a02\u55ae\u3001\u4e0d\u5efa\u7acb\u5957\u4fdd\uff0c\u4e5f\u4e0d\u8868\u793a\u5b58\u5728\u53ef\u57f7\u884c\u5957\u5229\u6a5f\u6703\u3002",
        "\u4f30\u503c\u3001\u878d\u8cc7\u3001\u6bd4\u4f8b\u3001\u6e05\u7b97\u548c\u6536\u76ca\u53c3\u6578\u5c1a\u672a\u63d0\u4f9b\uff1b\u4e0d\u8a08\u7b97\u7d93\u6fdf\u7d50\u679c\u3002",
        "BTC/ETH\u548c\u5546\u54c1\u540d\u7a31\u662f\u5834\u666f\u6a19\u7c64\uff0c\u4e0d\u8b49\u660e\u8cc7\u7522\u6620\u5c04\u6216\u5009\u55ae\u5167\u5bb9\u5df2\u6838\u9a57\u3002",
        "\u4efb\u4f55\u7368\u7acb\u4ea4\u6613\u4ecd\u9075\u5faa\u539f\u5009\u55ae\u3001\u5e63\u7a2e\u3001\u6388\u6b0a\u53caETH\u71c3\u6599\u898f\u5247\u3002", "\u5834\u666f\u7121\u6cd5\u4f7f\u7528"),
    "fr": ("Sc\xe9narios de march\xe9", "Couverture", "Collat\xe9ral", "Arbitrage", "Sc\xe9nario", "Contexte crypto",
        "Contexte de marchandise", "Soja", "Minerai de fer", "R\xe9c\xe9piss\xe9 connect\xe9", "Choisir", "Voir le contexte",
        "March\xe9", "Aucun r\xe9c\xe9piss\xe9 connect\xe9", "Ouvrir le d\xe9tail NFT original", "Contexte de simulation uniquement",
        "Cette s\xe9lection ne place aucun ordre, ne cr\xe9e aucune couverture et ne d\xe9signe aucune opportunit\xe9 d\u2019arbitrage ex\xe9cutable.",
        "Valorisation, financement, ratios, liquidation et rendement ne sont pas fournis. Aucun r\xe9sultat \xe9conomique n\u2019est calcul\xe9.",
        "BTC/ETH et les marchandises sont des \xe9tiquettes de sc\xe9nario, sans v\xe9rification des actifs ou du r\xe9c\xe9piss\xe9.",
        "Toute transaction distincte conserve les r\xe8gles originales du r\xe9c\xe9piss\xe9, de devise, d\u2019autorit\xe9 et de gaz ETH.",
        "Contexte indisponible"),
    "es": ("Escenarios de mercado", "Cobertura", "Garant\xeda", "Arbitraje", "Escenario", "Contexto cripto",
        "Contexto de mercanc\xeda", "Soja", "Mineral de hierro", "Recibo conectado", "Elegir", "Ver contexto",
        "Mercado", "No hay recibos conectados", "Abrir detalle NFT original", "Solo contexto de simulaci\xf3n",
        "Esta selecci\xf3n no coloca \xf3rdenes, no crea coberturas ni identifica una oportunidad de arbitraje ejecutable.",
        "No se han definido valoraci\xf3n, financiaci\xf3n, ratios, liquidaci\xf3n ni rendimientos. No se calcula un resultado econ\xf3mico.",
        "BTC/ETH y las mercanc\xedas son etiquetas de escenario; no verifican activos ni contenido del recibo.",
        "Toda operaci\xf3n separada conserva las reglas originales del recibo, moneda, autoridad y gas ETH.",
        "Contexto no disponible"),
    "ja": ("\u5e02\u5834\u30b7\u30ca\u30ea\u30aa", "\u30d8\u30c3\u30b8", "\u62c5\u4fdd", "\u88c1\u5b9a", "\u30b7\u30ca\u30ea\u30aa", "\u6697\u53f7\u8cc7\u7523\u306e\u80cc\u666f", "\u5546\u54c1\u306e\u80cc\u666f", "\u5927\u8c46", "\u9244\u9271\u77f3",
        "\u63a5\u7d9a\u3055\u308c\u305f\u5009\u8377\u8a3c\u5238", "\u9078\u629e\u3057\u3066\u304f\u3060\u3055\u3044", "\u9078\u629e\u5185\u5bb9\u3092\u898b\u308b", "\u5e02\u5834", "\u63a5\u7d9a\u3055\u308c\u305f\u5009\u8377\u8a3c\u5238\u306f\u3042\u308a\u307e\u305b\u3093",
        "\u5143\u306eNFT\u8a73\u7d30\u3092\u958b\u304f", "\u30b7\u30df\u30e5\u30ec\u30fc\u30b7\u30e7\u30f3\u7528\u306e\u80cc\u666f\u306e\u307f",
        "\u3053\u306e\u9078\u629e\u306f\u6ce8\u6587\u3001\u30d8\u30c3\u30b8\u306e\u4f5c\u6210\u3001\u5b9f\u884c\u53ef\u80fd\u306a\u88c1\u5b9a\u6a5f\u4f1a\u306e\u7279\u5b9a\u3092\u884c\u3044\u307e\u305b\u3093\u3002",
        "\u8a55\u4fa1\u984d\u3001\u878d\u8cc7\u3001\u6bd4\u7387\u3001\u6e05\u7b97\u3001\u53ce\u76ca\u306e\u6761\u4ef6\u306f\u672a\u63d0\u4f9b\u3067\u3059\u3002\u7d4c\u6e08\u7684\u306a\u7d50\u679c\u306f\u8a08\u7b97\u3057\u307e\u305b\u3093\u3002",
        "BTC/ETH\u3068\u5546\u54c1\u540d\u306f\u30b7\u30ca\u30ea\u30aa\u306e\u30e9\u30d9\u30eb\u3067\u3042\u308a\u3001\u8cc7\u7523\u9023\u643a\u3084\u5009\u8377\u8a3c\u5238\u5185\u5bb9\u306e\u691c\u8a3c\u3067\u306f\u3042\u308a\u307e\u305b\u3093\u3002",
        "\u5225\u9014\u884c\u3046\u53d6\u5f15\u306b\u306f\u5143\u306e\u5009\u8377\u8a3c\u5238\u3001\u901a\u8ca8\u3001\u6a29\u9650\u3001ETH\u30ac\u30b9\u306e\u898f\u5247\u304c\u9069\u7528\u3055\u308c\u307e\u3059\u3002", "\u9078\u629e\u3092\u5229\u7528\u3067\u304d\u307e\u305b\u3093"),
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
