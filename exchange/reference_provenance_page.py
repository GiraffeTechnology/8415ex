"""Localized reference provenance over an existing observation, without reads."""
from html import escape


FIELDS = ("provider", "sourceURL", "series", "commodity", "spec", "market",
          "priceType", "currency", "unit", "sourceAsOf", "sourcePrecision",
          "sourceTimezone", "fetchedAt", "sourceDelay", "lastSuccessful")
LABELS = {
    "en": ("Data provider", "Source page", "Price series", "Commodity", "Specification", "Market",
           "Price type", "Currency", "Unit", "Source observation", "Source time precision",
           "Source time zone", "Fetched at", "Source age range", "Last successful fetch"),
    "zh-Hans": ("数据提供方", "来源页面", "价格序列", "商品", "规格", "市场",
                "价格类型", "币种", "单位", "来源观测时点", "来源时间精度",
                "来源时区", "读取时点", "来源延迟范围", "最近成功读取"),
    "zh-Hant": ("資料提供方", "來源頁面", "價格序列", "商品", "規格", "市場",
                "價格類型", "幣種", "單位", "來源觀測時點", "來源時間精度",
                "來源時區", "讀取時點", "來源延遲範圍", "最近成功讀取"),
    "fr": ("Fournisseur de données", "Page source", "Série de prix", "Matière première", "Spécification", "Marché",
           "Type de prix", "Devise", "Unité", "Observation à la source", "Précision temporelle de la source",
           "Fuseau horaire de la source", "Date de lecture", "Plage d’âge de la source", "Dernière lecture réussie"),
    "es": ("Proveedor de datos", "Página de origen", "Serie de precios", "Materia prima", "Especificación", "Mercado",
           "Tipo de precio", "Moneda", "Unidad", "Observación de origen", "Precisión temporal de origen",
           "Zona horaria de origen", "Momento de lectura", "Intervalo de antigüedad", "Última lectura correcta"),
    "ja": ("データ提供元", "出典ページ", "価格系列", "商品", "仕様", "市場",
           "価格の種類", "通貨", "単位", "出典の観測時点", "出典時刻の精度",
           "出典のタイムゾーン", "取得時点", "出典の経過時間範囲", "最終取得成功時点"),
}
VALUES = {
    "en": ("Not provided", "Date only", "Timestamp provided", "Spot reference", "seconds"),
    "zh-Hans": ("未提供", "仅日期", "已提供时间戳", "现货参考价", "秒"),
    "zh-Hant": ("未提供", "僅日期", "已提供時間戳", "現貨參考價", "秒"),
    "fr": ("Non fourni", "Date uniquement", "Horodatage fourni", "Référence au comptant", "secondes"),
    "es": ("No proporcionado", "Solo fecha", "Marca temporal proporcionada", "Referencia al contado", "segundos"),
    "ja": ("未提供", "日付のみ", "タイムスタンプあり", "現物参考価格", "秒"),
}


def render_reference_fields(observation, locale="en"):
    if type(observation) is not dict or locale not in LABELS:
        raise ValueError("existing reference observation and supported locale required")
    missing, date_only, instant, spot, seconds = VALUES[locale]

    def display(key):
        value = observation.get(key)
        if key == "sourceDelay":
            if type(value) is not dict:
                return missing
            lower, upper = value.get("minimumSeconds"), value.get("maximumSeconds")
            if (type(lower) is not int or type(upper) is not int
                    or not 0 <= lower <= upper < 2**256):
                return missing
            # Retain both bounds. Date precision must not become an invented
            # exact timestamp or a zero source delay.
            return str(lower) + " – " + str(upper) + " " + seconds
        if key == "sourcePrecision":
            return {"date": date_only, "instant": instant}.get(value, missing) if type(value) is str else missing
        if key == "priceType":
            return spot if value == "spot-reference" else missing
        # Values describe the original series. Never translate source records,
        # stringify unknown nested fields, or fetch replacement observations.
        return value if type(value) is str and value else missing

    return ''.join('<dt>' + escape(label) + '</dt><dd>'
                   + escape(display(key), quote=True) + '</dd>'
                   for key, label in zip(FIELDS, LABELS[locale]))
