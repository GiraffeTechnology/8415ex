"""Read-only original remint receipt result page on the existing workbench."""
from copy import deepcopy
from html import escape
import re
from urllib.parse import urlsplit
from .ids import identifier
from .remint_receipt_observation import RemintReceiptObserver
from .remint_review_workbench import RemintReviewWorkbenchServer, RemintReviewWorkbenchHandler

WORDS = {
 "en": ("Remint receipt", "Not mined at this read", "Failed transaction", "No matching event in this receipt", "Original remint events correlated", "Receipt unavailable", "Original NFT", "Replacement NFT", "Transaction", "Original operation", "Observed block", "Consumed transaction gas (ETH)", "Not available", "Read-only observation. This page does not establish settlement or finality, reconcile UNKNOWN, permit replay or release funds."),
 "zh-Hans": ("换铸交易回执", "本次读取尚未挖出", "交易失败", "本回执无匹配事件", "原换铸事件已关联", "回执暂不可用", "原 NFT", "替换 NFT", "交易", "原操作", "观测区块", "交易实际消耗 gas（ETH）", "暂不可用", "仅供读取。本页不确认结算或最终性，不处理 UNKNOWN，不允许重发或释放资金。"),
 "zh-Hant": ("換鑄交易回執", "本次讀取尚未挖出", "交易失敗", "本回執無相符事件", "原換鑄事件已關聯", "回執暫不可用", "原 NFT", "替換 NFT", "交易", "原操作", "觀測區塊", "交易實際消耗 gas（ETH）", "暫不可用", "僅供讀取。本頁不確認結算或最終性，不處理 UNKNOWN，不允許重發或釋放資金。"),
 "fr": ("Reçu du remplacement", "Non miné lors de cette lecture", "Transaction échouée", "Aucun événement correspondant dans ce reçu", "Événements originaux de remplacement corrélés", "Reçu indisponible", "NFT original", "NFT de remplacement", "Transaction", "Opération originale", "Bloc observé", "Gas consommé par la transaction (ETH)", "Indisponible", "Observation seule. Cette page ne prouve ni règlement ni finalité, ne réconcilie pas UNKNOWN, ne permet ni répétition ni libération de fonds."),
 "es": ("Recibo del reemplazo", "Sin minar en esta lectura", "Transacción fallida", "Sin evento coincidente en este recibo", "Eventos originales de reemplazo correlacionados", "Recibo no disponible", "NFT original", "NFT de reemplazo", "Transacción", "Operación original", "Bloque observado", "Gas consumido por la transacción (ETH)", "No disponible", "Solo observación. Esta página no establece liquidación ni finalidad, no concilia UNKNOWN ni permite reenvíos o liberación de fondos."),
 "ja": ("再発行の取引レシート", "この読取りでは未採掘", "取引失敗", "このレシートに一致するイベントなし", "元の再発行イベントを関連付け済み", "レシートを取得できません", "元の NFT", "置換 NFT", "取引", "元の操作", "観測ブロック", "取引で消費した gas（ETH）", "取得不可", "閲覧専用です。このページは決済や確定性を証明せず、UNKNOWN の照合、再送、資金解放を行いません。"),
}
STATUS = {"NOT_MINED_AT_READ": 1, "FAILED_RECEIPT": 2,
          "NO_MATCHING_EVENT_AT_READ": 3, "CORRELATED_ORIGINAL_RECEIPT": 4}


class RemintReceiptViewUnavailable(ValueError):
    pass


def _eth(value):
    if (type(value) is not str or re.fullmatch(r"0|[1-9][0-9]{0,154}", value) is None
            or int(value) >= 2**512):
        raise RemintReceiptViewUnavailable("Original consumed wei required")
    whole, part = divmod(int(value), 10**18)
    return str(whole) + "." + str(part).zfill(18)


class RemintReceiptViewBinding:
    """Only original application wiring supplies the receipt reader and context."""
    def __init__(self, receipt_id, observer, read_original_receipt, original_context):
        identifier(receipt_id)
        required = {"attempt_id", "transaction_hash", "proof_reference", "contract",
                    "operation_id", "old_token_id", "actor", "replacement"}
        if (type(observer) is not RemintReceiptObserver or not callable(read_original_receipt)
                or type(original_context) is not dict or set(original_context) != required):
            raise ValueError("Original receipt observer, reader and exact context required")
        self.receipt_id = receipt_id
        self.observer, self.read_original_receipt = observer, read_original_receipt
        self._original_context = deepcopy(original_context)

    def render(self, locale):
        if locale not in WORDS:
            raise ValueError("Supported locale required")
        words = WORDS[locale]
        try:
            value = self.observer.observe(self.read_original_receipt(),
                                         **deepcopy(self._original_context))
            if (type(value) is not dict
                    or value.get("schema") != "8415ex-remint-receipt-observation/1"
                    or value.get("status") not in STATUS
                    or value.get("replayAllowed") is not False
                    or value.get("financialMutation") is not False
                    or value.get("businessAcceptance") != "NOT_ESTABLISHED"):
                raise ValueError("Original read-only observation required")
            def token(raw, *, optional=False):
                if raw is None and optional:
                    return words[12]
                if (type(raw) is not str or re.fullmatch(r"[1-9][0-9]{0,77}", raw) is None
                        or int(raw) >= 2**256):
                    raise ValueError("Original observed token required")
                return raw
            old = token(value.get("oldTokenId"))
            new = token(value.get("newTokenId"), optional=True)
            for key in ("transactionHash", "operationId"):
                if (type(value.get(key)) is not str
                        or re.fullmatch(r"0x[0-9a-f]{64}", value[key]) is None):
                    raise ValueError("Original protocol identity required")
            block = value.get("blockNumber")
            if block is not None and (type(block) is not int or not 0 <= block < 2**256):
                raise ValueError("Original block required")
            gas = value.get("actualGasWei")
            gas_text = words[12] if gas is None else _eth(gas) + " ETH"
            fields = ((words[6],old), (words[7],new),
                      (words[8],value["transactionHash"]), (words[9],value["operationId"]),
                      (words[10],words[12] if block is None else str(block)), (words[11],gas_text))
            return ('<p role="status">' + escape(words[STATUS[value["status"]]]) + '</p><dl>'
                    + "".join('<dt>' + escape(label) + '</dt><dd><code>' + escape(text)
                              + '</code></dd>' for label,text in fields)
                    + '</dl><p>' + escape(words[13]) + '</p>')
        except Exception:
            raise RemintReceiptViewUnavailable("Original remint receipt unavailable") from None


class RemintReceiptWorkbenchServer(RemintReviewWorkbenchServer):
    def __init__(self, binding, *, remint_receipt=None, **original_options):
        if remint_receipt is not None and (
                type(remint_receipt) is not RemintReceiptViewBinding
                or remint_receipt.receipt_id != binding.receipt_id):
            raise ValueError("Original same-receipt result view required")
        self.remint_receipt = remint_receipt
        super().__init__(binding, **original_options)
        self.RequestHandlerClass = RemintReceiptWorkbenchHandler


class RemintReceiptWorkbenchHandler(RemintReviewWorkbenchHandler):
    @staticmethod
    def native_navigation(locale):
        if locale not in WORDS:
            raise ValueError("Supported locale required")
        return (RemintReviewWorkbenchHandler.native_navigation(locale)
                + '<nav><a href="/remint-result?lang=' + locale + '">'
                + escape(WORDS[locale][0]) + '</a></nav>')

    def do_GET(self):
        request = urlsplit(self.path)
        if request.path != "/remint-result":
            return super().do_GET()
        if not self.host_ok():
            self.send_body(421, "host refused")
            return
        try:
            locale = self._gas_locale(request)
        except ValueError:
            self.send_body(400, "input refused")
            return
        words = WORDS[locale]
        try:
            if self.server.remint_receipt is None:
                raise RemintReceiptViewUnavailable("Not configured")
            content = self.server.remint_receipt.render(locale)
            status = 200
        except RemintReceiptViewUnavailable:
            content, status = '<p role="alert">' + escape(words[5]) + '</p>', 503
        self.send_body(status, self._page(words[0], content, locale,
                                        language_path="/remint-result"))

    def do_POST(self):
        if urlsplit(self.path).path != "/remint-result":
            return super().do_POST()
        self.close_connection = True
        self.send_body(405, "read-only entry", Allow="GET", Connection="close")
