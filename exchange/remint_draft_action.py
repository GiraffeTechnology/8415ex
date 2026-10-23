"""Optional HTTP control for one original, already bound remint proposal."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
from html import escape
import re
import secrets
from urllib.parse import parse_qs, urlsplit

from .checkpointed_operation import CheckpointedOperationBridge
from .durable_operation import DurableNativeOutcomeUnknown
from .mint_specification_codec import encode_mint_facts
from .remint_draft_execution import invoke_draft_remint
from .remint_draft_workbench import RemintDraftEditorBinding, RemintDraftUnavailable, WORDS as DRAFT_WORDS
from .remint_review_workbench import RemintReviewWorkbenchServer
from .remint_receipt_workbench import WORDS as RESULT_WORDS

PATH = "/remint-action"
LIMIT = 2048
# Heading, submit, boundary, unavailable, stale, refused, observation, unknown.
WORDS = {
    "en": ("Bound replacement proposal", "Execute original bound replacement",
        "The displayed proposal is read-only here. The original gateway checks this exact operation. A response is not proof of burn or mint.",
        "Original replacement inputs unavailable", "Proposal changed; reload the original proposal",
        "Original operation refused", "Original gateway returned an observation",
        "Outcome unknown. Use the original result enquiry; do not create a new operation to resend."),
    "zh-Hans": ("已绑定的换铸提案", "执行原已绑定换铸",
        "本页展示的提案为只读。原网关核验此准确操作。收到响应不证明销毁或铸造成功。",
        "原换铸输入暂不可用", "提案已变化，请重新读取原提案", "原操作已拒绝", "原网关已返回观察结果",
        "结果未知。请通过原结果入口查询，不要新建操作重发。"),
    "zh-Hant": ("已綁定的換鑄提案", "執行原已綁定換鑄",
        "本頁展示的提案為唯讀。原閘道核驗此準確操作。收到回應不證明銷毀或鑄造成功。",
        "原換鑄輸入暫不可用", "提案已變化，請重新讀取原提案", "原操作已拒絕", "原閘道已回傳觀測結果",
        "結果未知。請透過原結果入口查詢，不要新建操作重發。"),
    "fr": ("Proposition de remplacement liée", "Exécuter le remplacement déjà lié",
        "La proposition affichée est en lecture seule. La passerelle d’origine contrôle cette opération exacte. Une réponse ne prouve ni destruction ni création.",
        "Données du remplacement indisponibles", "Proposition modifiée ; rechargez la proposition d’origine",
        "Opération d’origine refusée", "La passerelle d’origine a renvoyé une observation",
        "Résultat inconnu. Consultez le résultat d’origine sans créer une nouvelle opération pour renvoyer."),
    "es": ("Propuesta de reemplazo vinculada", "Ejecutar el reemplazo ya vinculado",
        "La propuesta mostrada es de solo lectura. La pasarela original comprueba esta operación exacta. Una respuesta no prueba destrucción ni acuñación.",
        "Datos originales del reemplazo no disponibles", "La propuesta cambió; vuelva a cargar la propuesta original",
        "Operación original rechazada", "La pasarela original devolvió una observación",
        "Resultado desconocido. Consulte el resultado original sin crear otra operación para reenviar."),
    "ja": ("紐付け済みの再発行提案", "紐付け済みの元の再発行を実行",
        "表示中の提案は読み取り専用です。元のゲートウェイがこの操作を確認します。応答は焼却や発行の成功証明ではありません。",
        "元の再発行データを取得できません", "提案が変更されました。元の提案を再読み込みしてください",
        "元の操作が拒否されました", "元のゲートウェイから観測結果が返されました",
        "結果は不明です。新しい操作を作成して再送せず、元の結果を照会してください。"),
}


class StaleRemintProposal(ValueError):
    pass


def _proposal(old, replacement):
    before, after = encode_mint_facts(old), encode_mint_facts(replacement)
    # Local stale-form identity only; never a signing ABI or operation digest.
    return hashlib.sha256(len(before).to_bytes(8, "big") + before + after).hexdigest()



def _business_projection(specification):
    """Complete public business terms; exclude technical NFT and access identities."""
    receipt = specification.receipt
    return {
        "template": asdict(specification.template),
        "voucher format": asdict(specification.voucher_format),
        "receipt": {
            "commodity name": receipt.commodity_name,
            "commodity quantity": receipt.commodity_quantity,
            "commodity unit": receipt.commodity_unit,
            "receipt number": receipt.receipt_number,
            "registration path": receipt.registration_path,
            "trade stop at": receipt.trade_stop_at,
            "allowed price currencies": receipt.allowed_price_currencies,
            "currency reference": receipt.nft0_currency_reference,
        },
        "bill of lading number": specification.bill_of_lading_number,
        "issuer": specification.issuer,
        "registrar": specification.registrar,
        "storage location": specification.storage_location,
        "commodity attributes": dict(specification.public_attributes),
        "bill terms": specification.bill_terms,
        "registration deadline": specification.registration_deadline,
        "registration comparison": specification.registration_comparison,
    }


def _render_business(value):
    if isinstance(value, dict):
        return "<dl>" + "".join("<dt>" + escape(key.replace("_", " "))
            + "</dt><dd>" + _render_business(item) + "</dd>"
            for key, item in value.items()) + "</dl>"
    if isinstance(value, (tuple, list)):
        return "<ul>" + "".join("<li>" + _render_business(item) + "</li>"
            for item in value) + "</ul>"
    return "<pre>" + escape("" if value is None else str(value)) + "</pre>"


class RemintDraftActionBinding:
    """Original host supplies one existing operation and its reviewed options."""
    def __init__(self, bridge, editor, binding, expected_revision,
                 verify_declaration, resolve_original_bill_link,
                 enquire_original, execute_original, *, history_store, draft_options=None):
        if (type(bridge) is not CheckpointedOperationBridge
                or type(editor) is not RemintDraftEditorBinding
                or bridge.access is not editor.access
                or type(binding) is not dict or binding.get("action") != "remint"
                or binding.get("receiptId") != editor.receipt_id
                or type(expected_revision) is not int or not 0 <= expected_revision < 2**64
                or any(not callable(port) for port in (verify_declaration,
                    resolve_original_bill_link, enquire_original, execute_original))
                or (draft_options is not None and type(draft_options) is not dict)):
            raise ValueError("one original bound remint context required")
        self.bridge, self.editor = bridge, editor
        self._binding, self._revision = deepcopy(binding), expected_revision
        self._options = deepcopy(draft_options or {})
        self._ports = (verify_declaration, resolve_original_bill_link, enquire_original, execute_original)
        self._history = history_store

    def _read(self):
        old, replacement = self.editor.draft_specifications(**deepcopy(self._options))
        return old, replacement, _proposal(old, replacement)

    def render(self, csrf, locale):
        with self.bridge.access._lock:
            old, replacement, proposal = self._read()
            # Reuse the original complete editor projection over detached facts.
            # The source reader is not called a second time to render this page.
            frozen = RemintDraftEditorBinding(self.bridge.access, self.editor.receipt_id,
                lambda receipt_id: (old, replacement),
                read_currency_choices=lambda receipt_id: replacement.receipt.allowed_price_currencies)
            body = frozen.render(csrf, locale)
        words = WORDS[locale]
        labels = DRAFT_WORDS[locale]
        complete = ''.join('<section data-bound-business="' + side + '"><h2>'
            + escape(title) + '</h2>' + _render_business(_business_projection(specification))
            + '</section>' for side, title, specification in
            (("original", labels[1], old), ("replacement", labels[2], replacement)))
        return ('<p>' + escape(words[2]) + '</p>' + complete + '<fieldset disabled>' + body + '</fieldset>'
            + '<form method="post" action="' + PATH + '" autocomplete="off">'
            + '<input type="hidden" name="csrf" value="' + escape(csrf, quote=True) + '">'
            + '<input type="hidden" name="lang" value="' + locale + '">'
            + '<input type="hidden" name="proposal" value="' + proposal + '">'
            + '<input type="hidden" name="revision" value="' + str(self._revision) + '">'
            + '<button type="submit">' + escape(words[1]) + '</button></form>')

    def invoke(self, proposal, revision):
        if (type(proposal) is not str or re.fullmatch(r"[0-9a-f]{64}", proposal) is None
                or revision != str(self._revision)):
            raise StaleRemintProposal("stale original form")
        with self.bridge.access._lock:
            old, replacement, current = self._read()
            if not secrets.compare_digest(proposal, current):
                raise StaleRemintProposal("stale original proposal")
            frozen = RemintDraftEditorBinding(self.bridge.access, self.editor.receipt_id,
                                              lambda receipt_id: (old, replacement))
            return invoke_draft_remint(self.bridge, frozen, deepcopy(self._binding),
                self._revision, *self._ports, history_store=self._history)


def mount_remint_draft_action(server, action=None):
    """Mount before serving; all existing routes and their handler remain."""
    if not isinstance(server, RemintReviewWorkbenchServer):
        raise ValueError("original remint workbench required")
    if action is not None and (type(action) is not RemintDraftActionBinding
            or action.bridge.access is not server.binding.exchange
            or action.editor.receipt_id != server.binding.receipt_id):
        raise ValueError("same original workbench, access and receipt required")
    if getattr(server, "_remint_action_mounted", False):
        if server.remint_action is not action:
            raise ValueError("original remint action already mounted")
        return server
    parent = server.RequestHandlerClass

    class ActionHandler(parent):
        @staticmethod
        def native_navigation(locale):
            return (parent.native_navigation(locale) + '<nav><a href="' + PATH
                    + '?lang=' + locale + '">' + escape(WORDS[locale][0]) + '</a></nav>')

        def _response(self, status, locale, text):
            content = '<p role="status">' + escape(text) + '</p>'
            if hasattr(self.server, "remint_receipt"):
                content += '<a href="/remint-result?lang=' + locale + '">' + escape(RESULT_WORDS[locale][0]) + '</a>'
            self.send_body(status, self._page(WORDS[locale][0], content, locale, language_path=PATH))

        def do_GET(self):
            request = urlsplit(self.path)
            if request.path != PATH:
                return super().do_GET()
            if len(self.headers.get_all("Host", [])) != 1 or not self.host_ok():
                return self.send_body(421, "host refused")
            locale = "en"
            try:
                if request.fragment or len(request.query) > 64:
                    raise ValueError("bounded locale required")
                query = parse_qs(request.query, strict_parsing=True, keep_blank_values=True, max_num_fields=1)
                if set(query) - {"lang"} or any(len(v) != 1 for v in query.values()):
                    raise ValueError("one locale required")
                locale = query.get("lang", ["en"])[0]
                if locale not in WORDS:
                    raise ValueError("supported locale required")
            except ValueError:
                return self.send_body(400, "input refused")
            try:
                if self.server.remint_action is None:
                    return self._response(503, locale, WORDS[locale][3])
                body = self.server.remint_action.render(self.server.csrf, locale)
            except Exception:
                return self._response(503, locale, WORDS[locale][3])
            self.send_body(200, self._page(WORDS[locale][0], body, locale, language_path=PATH))

        def do_POST(self):
            request = urlsplit(self.path)
            if request.path != PATH:
                return super().do_POST()
            self.close_connection = True
            if len(self.headers.get_all("Host", [])) != 1 or not self.host_ok():
                return self.send_body(421, "host refused", Connection="close")
            locale = "en"
            if (len(self.headers.get_all("Origin", [])) != 1
                    or self.headers.get("Origin") != self.server.origin):
                return self._response(403, locale, WORDS[locale][5])
            try:
                lengths = self.headers.get_all("Content-Length", [])
                if (request.query or request.fragment or len(lengths) != 1
                        or self.headers.get_all("Transfer-Encoding", [])
                        or len(self.headers.get_all("Content-Type", [])) != 1
                        or self.headers.get("Content-Type") != "application/x-www-form-urlencoded"
                        or re.fullmatch(r"[0-9]{1,4}", lengths[0]) is None):
                    raise ValueError("plain bounded form required")
                length = int(lengths[0])
                if not 0 < length <= LIMIT:
                    raise ValueError("bounded form required")
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError("complete form required")
                form = parse_qs(raw.decode("utf-8"), strict_parsing=True, keep_blank_values=True,
                                max_num_fields=4, errors="strict")
                if set(form) != {"csrf", "lang", "proposal", "revision"} or any(len(v) != 1 for v in form.values()):
                    raise ValueError("exact form required")
                fields = {k: v[0] for k, v in form.items()}
                locale = fields["lang"]
                if locale not in WORDS:
                    raise ValueError("supported locale required")
            except (ValueError, UnicodeError):
                return self.send_body(400, "input refused")
            if not fields["csrf"].isascii() or not secrets.compare_digest(fields["csrf"], self.server.csrf):
                return self._response(403, locale, WORDS[locale][5])
            if self.server.remint_action is None:
                return self._response(503, locale, WORDS[locale][3])
            try:
                self.server.remint_action.invoke(fields["proposal"], fields["revision"])
            except RemintDraftUnavailable:
                return self._response(503, locale, WORDS[locale][3])
            except DurableNativeOutcomeUnknown:
                return self._response(503, locale, WORDS[locale][7])
            except PermissionError:
                return self._response(403, locale, WORDS[locale][5])
            except StaleRemintProposal:
                return self._response(409, locale, WORDS[locale][4])
            except ValueError:
                return self._response(409, locale, WORDS[locale][5])
            except Exception:
                return self._response(503, locale, WORDS[locale][3])
            self._response(202, locale, WORDS[locale][6])

    server.remint_action = action
    server._remint_action_mounted = True
    server.RequestHandlerClass = ActionHandler
    return server
