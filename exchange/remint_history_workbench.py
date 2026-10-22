"""Same-block, read-only remint history navigation over an installed reader."""
from copy import deepcopy
from html import escape
import re
from urllib.parse import parse_qs, urlencode, urlsplit
from .ids import identifier
from .nft_detail_page import STYLE
from .remint_read_results import decode_remint_declaration, decode_remint_link
from .remint_review_workbench import RemintReviewWorkbenchServer, RemintReviewWorkbenchHandler

WORDS = {
 "en": ("Remint history", "NFT token", "Predecessor NFT", "Successor NFT", "Active NFT for this bill", "Zero at this read", "History unavailable", "Observed block", "Read-only original snapshot. Retained declarations do not prove that a token remains active.", "Language"),
 "zh-Hans": ("换铸历史", "NFT 编号", "前身 NFT", "后继 NFT", "本提单当前有效 NFT", "本次读取为零", "历史暂不可用", "观测区块", "仅展示原始快照。保留的声明不代表该 NFT 仍然有效。", "语言"),
 "zh-Hant": ("換鑄歷史", "NFT 編號", "前身 NFT", "後繼 NFT", "本提單目前有效 NFT", "本次讀取為零", "歷史暫不可用", "觀測區塊", "僅展示原始快照。保留的聲明不代表該 NFT 仍然有效。", "語言"),
 "fr": ("Historique du remplacement", "Identifiant NFT", "NFT précédent", "NFT suivant", "NFT actif de ce connaissement", "Zéro lors de cette lecture", "Historique indisponible", "Bloc observé", "Instantané original en lecture seule. Une déclaration conservée ne prouve pas que le NFT est encore actif.", "Langue"),
 "es": ("Historial de reemplazo", "Identificador NFT", "NFT anterior", "NFT siguiente", "NFT activo de este conocimiento", "Cero en esta lectura", "Historial no disponible", "Bloque observado", "Instantánea original de solo lectura. Una declaración conservada no demuestra que el NFT siga activo.", "Idioma"),
 "ja": ("再発行の履歴", "NFT 番号", "前身 NFT", "後継 NFT", "この船荷証券の有効な NFT", "この読取りではゼロ", "履歴を取得できません", "観測ブロック", "元のスナップショットの閲覧専用です。保持された宣言は NFT が現在も有効であることを証明しません。", "言語"),
}


def _token(value):
    if (type(value) is not str or re.fullmatch(r"[1-9][0-9]{0,77}", value) is None
            or int(value) >= 2**256):
        raise ValueError("Canonical positive token ID required")
    return value


def _hash(value):
    if (type(value) is not str or re.fullmatch(r"0x[0-9a-f]{64}", value) is None
            or int(value[2:], 16) == 0):
        raise ValueError("Original nonzero word required")
    return value


class RemintHistoryUnavailable(ValueError):
    pass


class RemintChainHistoryBinding:
    """The installed reader authenticates one original contract/block snapshot.

    No request can select a chain, contract, bill or callback. A reader must
    return all original getter responses from the same exact observed block,
    including reciprocal links. Shape validation is not provider authentication.
    This read binding is never called as an execution eligibility prerequisite.
    """
    def __init__(self, receipt_id, contract, bill_key, token_id, read_original_snapshot):
        identifier(receipt_id)
        if (type(contract) is not str or re.fullmatch(r"0x[0-9a-f]{40}", contract) is None
                or int(contract[2:], 16) == 0 or not callable(read_original_snapshot)):
            raise ValueError("Installed original remint reader required")
        self.receipt_id, self.contract = receipt_id, contract
        self.bill_key, self.token_id = _hash(bill_key), _token(token_id)
        self.read_original_snapshot = read_original_snapshot

    def read(self, token_id):
        token_id = _token(token_id)
        requested = {"chainId": 11155111, "contract": self.contract,
                     "billKey": self.bill_key, "tokenId": token_id}
        try:
            row = deepcopy(self.read_original_snapshot(deepcopy(requested)))
            keys = {"scope", "observedBlock", "declaration", "predecessor", "successor",
                    "active", "predecessorReverse", "successorReverse"}
            if (type(row) is not dict or set(row) != keys or type(row["scope"]) is not dict
                    or row["scope"] != requested
                    or any(type(row["scope"].get(k)) is not type(v) for k, v in requested.items())):
                raise ValueError("Original same-asset response required")
            block = row["observedBlock"]
            if type(block) is not dict or set(block) != {"number", "hash", "timestamp"}:
                raise ValueError("Original block binding required")
            for key in ("number", "timestamp"):
                if type(block[key]) is not int or not 0 <= block[key] < 2**256:
                    raise ValueError("Original block integer required")
            _hash(block["hash"])
            declaration = decode_remint_declaration(row["declaration"])
            if declaration["billKey"] != self.bill_key:
                raise ValueError("Original retained declaration belongs to another bill")
            values = {key: decode_remint_link(row[key], getter)["tokenId"]
                      for key, getter in (("predecessor", "predecessorOf"),
                                          ("successor", "successorOf"),
                                          ("active", "activeTokenForBill"))}
            previous, following, active = (values[k] for k in ("predecessor", "successor", "active"))
            if (active == "0" or token_id in (previous, following)
                    or previous != "0" and previous == following
                    or following == "0" and active != token_id
                    or following != "0" and active == token_id):
                raise ValueError("Original remint mapping conflict")
            for key, getter in (("predecessor", "successorOf"), ("successor", "predecessorOf")):
                response = row[key + "Reverse"]
                if values[key] == "0":
                    if response is not None:
                        raise ValueError("No invented reciprocal read for zero link")
                elif decode_remint_link(response, getter)["tokenId"] != token_id:
                    raise ValueError("Reciprocal original link differs")
            return {"tokenId": token_id, **values, "observedBlock": deepcopy(block),
                    "meaning": "Original same-block reader observation, not execution authority"}
        except Exception:
            raise RemintHistoryUnavailable("Original remint history unavailable") from None


class RemintHistoryWorkbenchServer(RemintReviewWorkbenchServer):
    def __init__(self, binding, *, remint_history=None, **original_options):
        if remint_history is not None and (
                type(remint_history) is not RemintChainHistoryBinding
                or remint_history.receipt_id != binding.receipt_id):
            raise ValueError("Original same-receipt history binding required")
        self.remint_history = remint_history
        super().__init__(binding, **original_options)
        self.RequestHandlerClass = RemintHistoryWorkbenchHandler


class RemintHistoryWorkbenchHandler(RemintReviewWorkbenchHandler):
    @staticmethod
    def native_navigation(locale):
        if locale not in WORDS:
            raise ValueError("Supported locale required")
        return (RemintReviewWorkbenchHandler.native_navigation(locale)
                + '<nav><a href="/remint-history?lang=' + locale + '">'
                + escape(WORDS[locale][0]) + '</a></nav>')

    def do_GET(self):
        request = urlsplit(self.path)
        if request.path != "/remint-history":
            return super().do_GET()
        if not self.host_ok():
            self.send_body(421, "host refused")
            return
        try:
            if request.fragment or len(request.query) > 160:
                raise ValueError("Bounded history selection required")
            query = parse_qs(request.query, strict_parsing=True,
                             keep_blank_values=True, max_num_fields=2)
            if set(query) - {"lang", "token"} or any(len(v) != 1 for v in query.values()):
                raise ValueError("One original selection required")
            locale = query.get("lang", ["en"])[0]
            if locale not in WORDS:
                raise ValueError("Supported locale required")
            selected = query.get("token", [None])[0]
            if selected is not None:
                _token(selected)
        except ValueError:
            self.send_body(400, "input refused")
            return
        words = WORDS[locale]
        selected = selected or (self.server.remint_history.token_id
                                if self.server.remint_history is not None else None)
        languages = "".join('<a lang="' + lang + '" href="/remint-history?'
            + escape(urlencode(dict({"lang": lang}, **({"token": selected} if selected else {}))), quote=True)
            + '">' + lang + '</a> ' for lang in WORDS)
        try:
            if self.server.remint_history is None:
                raise RemintHistoryUnavailable("Not configured")
            view = self.server.remint_history.read(selected)
            def link(token):
                if token == "0":
                    return escape(words[5])
                return '<a href="/remint-history?' + escape(urlencode(
                    {"lang": locale, "token": token}), quote=True) + '">' + token + '</a>'
            content = '<dl>' + "".join('<dt>' + escape(words[index]) + '</dt><dd>'
                + link(view[key]) + '</dd>' for index, key in (
                    (1, "tokenId"), (2, "predecessor"), (3, "successor"), (4, "active"))) + '</dl>'
            block = view["observedBlock"]
            content += '<section><h2>' + escape(words[7]) + '</h2><p>' + str(block["number"]) + '</p><code>' + block["hash"] + '</code><p>' + str(block["timestamp"]) + '</p></section>'
            status = 200
        except RemintHistoryUnavailable:
            content, status = '<p role="alert">' + escape(words[6]) + '</p>', 503
        body = ('<!doctype html><html lang="' + locale + '"><meta charset="utf-8">'
                + '<meta name="viewport" content="width=device-width,initial-scale=1">'
                + '<title>' + escape(words[0]) + '</title><style>' + STYLE + '</style><body><main>'
                + self.native_navigation(locale) + '<nav aria-label="' + escape(words[9]) + '">'
                + languages + '</nav><h1>' + escape(words[0]) + '</h1>' + content
                + '<p>' + escape(words[8]) + '</p></main></body></html>')
        self.send_body(status, body)

    def do_POST(self):
        if urlsplit(self.path).path != "/remint-history":
            return super().do_POST()
        self.close_connection = True
        self.send_body(405, "read-only entry", Allow="GET", Connection="close")
