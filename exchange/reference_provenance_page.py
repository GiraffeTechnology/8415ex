"""Localized reference provenance over an existing observation, without reads."""
from datetime import date, datetime
from html import escape
import re
from .eia_wti_bulk_series import BULK_URL


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



EVIDENCE_LABELS = {
    "en": ("Source publication date", "Source response SHA-256"),
    "zh-Hans": ("来源发布日期", "来源响应 SHA-256"),
    "zh-Hant": ("來源發布日期", "來源回應 SHA-256"),
    "fr": ("Date de publication de la source", "SHA-256 de la réponse source"),
    "es": ("Fecha de publicación de origen", "SHA-256 de la respuesta de origen"),
    "ja": ("出典の公開日", "出典レスポンスの SHA-256"),
}

BULK_WORDS = {
    "en": ("Upstream source attribution", "Source copyright statement",
           "Series updated at", "Distribution updated at", "Complete archive SHA-256",
           "Selected series line SHA-256", "Manifest SHA-256", "Meaning of source metadata",
           "Original source metadata is not a display permission, independent approval or executable NFT price. Update times are distinct from observation and fetch times."),
    "zh-Hans": ("上游来源归属", "来源版权声明", "序列更新时间", "分发更新时间",
                "完整归档 SHA-256", "选中序列行 SHA-256", "清单 SHA-256", "来源元数据含义",
                "原来源元数据不代表展示许可、独立批准或可执行的 NFT 价格。更新时间与观测和读取时间分别保留。"),
    "zh-Hant": ("上游來源歸屬", "來源版權聲明", "序列更新時間", "分發更新時間",
                "完整歸檔 SHA-256", "選中序列行 SHA-256", "清單 SHA-256", "來源中繼資料含義",
                "原來源中繼資料不代表展示許可、獨立批准或可執行的 NFT 價格。更新時間與觀測和讀取時間分別保留。"),
    "fr": ("Attribution de la source amont", "Mention de droit d’auteur de la source",
           "Mise à jour de la série", "Mise à jour de la distribution", "SHA-256 de l’archive complète",
           "SHA-256 de la ligne sélectionnée", "SHA-256 du manifeste", "Sens des métadonnées de source",
           "Les métadonnées d’origine ne prouvent ni droit d’affichage, ni approbation indépendante, ni prix NFT exécutable. Mise à jour, observation et lecture restent distinctes."),
    "es": ("Atribución de la fuente original", "Declaración de derechos de la fuente",
           "Actualización de la serie", "Actualización de la distribución", "SHA-256 del archivo completo",
           "SHA-256 de la línea seleccionada", "SHA-256 del manifiesto", "Significado de los metadatos",
           "Los metadatos originales no acreditan permiso de publicación, aprobación independiente ni precio NFT ejecutable. Actualización, observación y lectura son tiempos distintos."),
    "ja": ("上流の出典帰属", "出典の著作権表示", "系列の更新時刻", "配布の更新時刻",
           "完全アーカイブの SHA-256", "選択された系列行の SHA-256", "マニフェストの SHA-256", "出典メタデータの意味",
           "元の出典メタデータは表示許可、独立した承認、実行可能な NFT 価格を証明しません。更新、観測、取得の時刻は別々に保持されます。"),
}

FIELDS += ("publicationDate", "rawResponseSHA256")
LABELS = {locale: labels + EVIDENCE_LABELS[locale] for locale, labels in LABELS.items()}


def _source_evidence(observation, key):
    evidence = observation.get("sourceEvidence")
    if type(evidence) is not dict:
        return None
    value = evidence.get(key)
    if type(value) is not str:
        return None
    if key == "rawResponseSHA256":
        return value if re.fullmatch(r"[0-9a-f]{64}", value) else None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value) is None:
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        return None
    return value


def _render_bulk_source_fields(observation, locale):
    """Present a trusted original snapshot; hashes alone authenticate nothing."""
    if observation.get("sourceURL") != BULK_URL:
        return ""
    missing = VALUES[locale][0]
    words = BULK_WORDS[locale]
    evidence = observation.get("sourceEvidence")
    source = evidence.get("bulkSource") if type(evidence) is dict else None
    digest = evidence.get("rawResponseSHA256") if type(evidence) is dict else None
    bound = (type(source) is dict and type(digest) is str
             and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
             and source.get("sha256") == digest
             and evidence.get("responseDigestScope") == "complete-petroleum-archive"
             and observation.get("sourceAttributionStatus") == "recorded")
    fields = ("upstreamSource", "sourceCopyright", "sourceUpdatedAt", "datasetUpdatedAt",
              "sha256", "selectedLineSHA256", "manifestSHA256")
    def display(key):
        value = source.get(key) if bound else None
        if type(value) is not str:
            return missing
        if key in ("sha256", "selectedLineSHA256", "manifestSHA256"):
            return value if re.fullmatch(r"[0-9a-f]{64}", value) else missing
        if (not value.strip() or len(value) > 256 or any(ord(c) < 32 for c in value)
                or re.search(r"0x[0-9a-fA-F]{40}", value)):
            return missing
        if key in ("sourceUpdatedAt", "datasetUpdatedAt"):
            if len(value) > 64:
                return missing
            try:
                stamp = datetime.fromisoformat(value)
                if stamp.tzinfo is None or stamp.utcoffset() is None:
                    return missing
            except ValueError:
                return missing
        return value
    values = [display(key) for key in fields] + [words[8]]
    return "".join('<dt>' + escape(label) + '</dt><dd>' + escape(value, quote=True) + '</dd>'
                   for label, value in zip(words[:8], values))


def render_reference_fields(observation, locale="en"):
    if type(observation) is not dict or locale not in LABELS:
        raise ValueError("existing reference observation and supported locale required")
    missing, date_only, instant, spot, seconds = VALUES[locale]

    def display(key):
        value = (_source_evidence(observation, key) if key in ("publicationDate", "rawResponseSHA256")
                 else observation.get(key))
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

    original = ''.join('<dt>' + escape(label) + '</dt><dd>'
                   + escape(display(key), quote=True) + '</dd>'
                   for key, label in zip(FIELDS, LABELS[locale]))
    return original + _render_bulk_source_fields(observation, locale)
