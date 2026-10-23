"""Ordered DEMO display categories; no inventory, asset or trading configuration."""

COMMODITY_ORDER = ("gold", "silver", "copper", "iron-ore", "crude-oil", "coal", "soy", "corn")
COMMODITY_CODES = frozenset(COMMODITY_ORDER)
NAMES = {
    "en": ("Gold", "Silver", "Copper", "Iron Ore", "Crude Oil", "Coal", "Soybeans", "Corn"),
    "zh-Hans": ("黄金", "白银", "铜", "铁矿石", "原油", "煤", "大豆", "玉米"),
    "zh-Hant": ("黃金", "白銀", "銅", "鐵礦石", "原油", "煤", "大豆", "玉米"),
    "fr": ("Or", "Argent", "Cuivre", "Minerai de fer", "Pétrole brut", "Charbon", "Soja", "Maïs"),
    "es": ("Oro", "Plata", "Cobre", "Mineral de hierro", "Petróleo crudo", "Carbón", "Soja", "Maíz"),
    "ja": ("金", "銀", "銅", "鉄鉱石", "原油", "石炭", "大豆", "トウモロコシ"),
}
DISPLAY_WORDS = {
    "en": ("DEMO commodity categories", "Display categories only. No real inventory, price or on-chain asset is implied."),
    "zh-Hans": ("DEMO 商品分类", "仅为展示分类，不代表真实库存、价格或链上资产。"),
    "zh-Hant": ("DEMO 商品分類", "僅為展示分類，不代表真實庫存、價格或鏈上資產。"),
    "fr": ("Catégories de matières premières DEMO", "Catégories de présentation uniquement, sans inventaire, prix ou actif réel sur la chaîne implicite."),
    "es": ("Categorías de materias primas DEMO", "Solo categorías de presentación; no implican existencias, precios ni activos reales en la cadena."),
    "ja": ("DEMO 商品カテゴリー", "表示用の分類です。実在する在庫、価格、オンチェーン資産を示すものではありません。"),
}


def commodity_name(code, locale="en"):
    if code not in COMMODITY_CODES:
        return None
    return NAMES[locale][COMMODITY_ORDER.index(code)]


def commodity_order(code):
    return COMMODITY_ORDER.index(code) if code in COMMODITY_CODES else len(COMMODITY_ORDER)


GROUPS = {"agriculture": frozenset(("soy", "corn")),
          "metals": frozenset(("gold", "silver", "copper", "iron-ore")),
          "energy": frozenset(("crude-oil", "coal"))}
GROUP_NAMES = {
    "en": ("All commodities", "Agriculture", "Metals and minerals", "Energy and chemicals"),
    "zh-Hans": ("全部商品", "农产品", "金属矿产", "能源化工"),
    "zh-Hant": ("全部商品", "農產品", "金屬礦產", "能源化工"),
    "fr": ("Toutes les matières", "Agriculture", "Métaux et minerais", "Énergie et chimie"),
    "es": ("Todos los productos", "Agricultura", "Metales y minerales", "Energía y productos químicos"),
    "ja": ("すべての商品", "農産物", "金属・鉱物", "エネルギー・化学品"),
}


def matches_query(code, text, query, locale):
    if query.startswith("group:") and query[6:] in GROUPS:
        return code in GROUPS[query[6:]]
    label = commodity_name(code, locale) or ""
    return not query or query.casefold() in (str(text) + " " + label + " " + str(code or "")).casefold()
