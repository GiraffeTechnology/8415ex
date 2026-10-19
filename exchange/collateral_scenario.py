"""Two explicit collateral categories for a non-executing product scenario."""
from html import escape
from urllib.parse import urlencode

from .nft_directory import NftDirectory


WORDS = {
    "en": ("Two-way collateral", "Collateral category", "Crypto asset", "Commodity receipt NFT",
        "Collateral asset", "Target receipt", "Choose", "Review selection", "No selection",
        "Mechanism parameters have not been provided. This is a simulation selection only.",
        "No financing, valuation, interest, liquidation or return is calculated.",
        "Selection does not prove ownership, collateral eligibility or a connected asset mapping.",
        "Market", "Selection unavailable", "No receipt is connected"),
    "zh-Hans": ("双向质押", "质押物类别", "加密资产", "商品仓单 NFT", "质押资产", "标的仓单",
        "请选择", "查看选择", "尚未选择", "机制参数尚未提供；此处仅为模拟场景选择。",
        "不计算融资、估值、利息、清算或收益。", "选择不代表已核验持有、质押资格或资产映射已接入。",
        "市场", "选择不可用", "尚未接入仓单"),
    "zh-Hant": ("雙向質押", "質押物類別", "加密資產", "商品倉單 NFT", "質押資產", "標的倉單",
        "請選擇", "查看選擇", "尚未選擇", "機制參數尚未提供；此處僅為模擬場景選擇。",
        "不計算融資、估值、利息、清算或收益。", "選擇不代表已核驗持有、質押資格或資產映射已接入。",
        "市場", "選擇不可用", "尚未接入倉單"),
    "fr": ("Collatéral dans les deux sens", "Catégorie de collatéral", "Cryptoactif", "NFT de récépissé de marchandise",
        "Actif en collatéral", "Récépissé cible", "Choisir", "Voir la sélection", "Aucune sélection",
        "Les paramètres du mécanisme ne sont pas fournis. Sélection de simulation uniquement.",
        "Aucun financement, valorisation, intérêt, liquidation ou rendement n’est calculé.",
        "La sélection ne prouve ni propriété, ni admissibilité, ni correspondance d’actif connectée.",
        "Marché", "Sélection indisponible", "Aucun récépissé connecté"),
    "es": ("Garantía en ambos sentidos", "Tipo de garantía", "Criptoactivo", "NFT de recibo de mercancía",
        "Activo en garantía", "Recibo de destino", "Elegir", "Ver selección", "Sin selección",
        "No se han proporcionado los parámetros del mecanismo. Solo es una selección de simulación.",
        "No se calcula financiación, valoración, interés, liquidación ni rendimiento.",
        "La selección no prueba propiedad, elegibilidad ni una vinculación de activo conectada.",
        "Mercado", "Selección no disponible", "No hay recibos conectados"),
    "ja": ("双方向の担保", "担保の種類", "暗号資産", "商品倉荷証券 NFT", "担保資産", "対象の倉荷証券",
        "選択してください", "選択内容を見る", "未選択", "仕組みの条件は未提供です。シミュレーション用の選択のみです。",
        "融資、評価額、利息、清算、収益は計算しません。", "選択は保有、担保適格性、資産連携の確認を意味しません。",
        "市場", "選択を利用できません", "接続された倉荷証券はありません"),
}


def collateral_selection(directory, *, kind="", asset="", target=""):
    if type(directory) is not NftDirectory:
        raise ValueError("original NFT directory required")
    if any(type(value) is not str for value in (kind, asset, target)):
        raise ValueError("explicit selection strings required")
    keys = tuple(directory._bindings)
    if target and target not in keys:
        raise ValueError("target receipt is not in the original directory")
    if not kind and not asset:
        selected = None
    elif kind == "crypto" and asset in ("BTC", "ETH"):
        selected = {"kind": kind, "asset": asset}
    elif kind == "warehouse-nft" and asset in keys:
        selected = {"kind": kind, "asset": asset}
    else:
        raise ValueError("explicit supported collateral category and asset required")
    return {"schema": "8415ex-collateral-scenario-selection/1", "selected": selected,
        "targetNftKey": target or None, "simulation": True,
        "mechanismParameters": None, "assetMappingVerified": False,
        "executionInvoked": False, "ordinarySpotEligibilityEvaluated": False}


def render_collateral(directory, locale="en", *, kind="", asset="", target=""):
    if locale not in WORDS:
        raise ValueError("supported locale required")
    selection = collateral_selection(directory, kind=kind, asset=asset, target=target)
    w = WORDS[locale]
    keys = tuple(directory._bindings)
    labels = {key: "NFT " + str(index + 1) for index, key in enumerate(keys)}

    def option(value, text, chosen):
        return '<option value="' + escape(value, quote=True) + '"' + (
            ' selected' if value == chosen else '') + '>' + escape(text) + '</option>'

    types = ''.join(option(value, label, kind) for value, label in
                    (("", w[6]), ("crypto", w[2]), ("warehouse-nft", w[3])))
    assets = option("", w[6], asset) + ''.join(option(value, value, asset) for value in ("BTC", "ETH"))
    assets += ''.join(option(key, labels[key], asset) for key in keys)
    targets = option("", w[6], target) + ''.join(option(key, labels[key], target) for key in keys)
    query = {"kind": kind, "asset": asset, "target": target}
    languages = ''.join('<a lang="' + code + '" href="/collateral?' + escape(
        urlencode({"lang": code, **query}), quote=True) + '">' + code + '</a>' for code in WORDS)
    selected = selection["selected"]
    summary = w[8] if selected is None else (w[2] if selected["kind"] == "crypto" else w[3]) + ': ' + labels.get(asset, asset)
    return ('<!doctype html><html lang="' + locale + '"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1"><title>' + escape(w[0])
        + '</title><body><main><nav><a href="/market?lang=' + locale + '">' + escape(w[12])
        + '</a> ' + languages + '</nav><h1>' + escape(w[0]) + '</h1><p>DEMO</p>'
        + '<form method="get" action="/collateral"><input type="hidden" name="lang" value="'
        + locale + '"><p><label>' + escape(w[1]) + ' <select name="kind">' + types + '</select></label></p>'
        + '<p><label>' + escape(w[4]) + ' <select name="asset">' + assets + '</select></label></p>'
        + '<p><label>' + escape(w[5]) + ' <select name="target">' + targets + '</select></label></p>'
        + '<button type="submit">' + escape(w[7]) + '</button></form><section data-collateral-selection="1"><h2>'
        + escape(summary) + '</h2><p>' + escape(w[9]) + '</p><p>' + escape(w[10]) + '</p><p>'
        + escape(w[11]) + '</p>' + ('<p>' + escape(w[14]) + '</p>' if not keys else '')
        + '</section></main></body></html>')
