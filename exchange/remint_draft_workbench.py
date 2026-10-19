"""Unsigned bill-term editing on the original serialized native workbench."""
from copy import deepcopy
from html import escape
import re
import secrets
from urllib.parse import parse_qs, urlsplit

from .demo_ui import MAX_BODY
from .mint_specification import MintSpecification
from .remint_draft_edit import edit_remint_draft
from .remint_review_workbench import RemintReviewWorkbenchServer, RemintReviewWorkbenchHandler
from .serialized_exchange_access import SerializedExchangeAccess


WORDS = {
    "en": ("Edit replacement bill terms", "Original bill terms", "Proposed complete terms",
        "Preview unsigned draft", "Unsigned draft preview", "The original terms remain unchanged. This editor does not sign, submit, burn or mint.",
        "Terms unavailable", "Draft request refused"),
    "zh-Hans": ("编辑换铸提单条款", "原提单条款", "拟新完整条款", "预览未签署草稿", "未签署草稿预览",
        "原条款保持不变。本编辑器不签署、不提交、不销毁或铸造。", "条款暂不可用", "草稿请求被拒绝"),
    "zh-Hant": ("編輯換鑄提單條款", "原提單條款", "擬新完整條款", "預覽未簽署草稿", "未簽署草稿預覽",
        "原條款保持不變。本編輯器不簽署、不提交、不銷毀或鑄造。", "條款暫不可用", "草稿請求被拒絕"),
    "fr": ("Modifier les conditions du connaissement de remplacement", "Conditions originales", "Conditions intégrales proposées",
        "Aperçu du brouillon non signé", "Brouillon non signé", "Les conditions originales restent inchangées. Cet éditeur ne signe, ne soumet, ne détruit et ne crée aucun NFT.",
        "Conditions indisponibles", "Demande de brouillon refusée"),
    "es": ("Editar las condiciones del conocimiento de reemplazo", "Condiciones originales", "Condiciones completas propuestas",
        "Vista previa del borrador sin firmar", "Borrador sin firmar", "Las condiciones originales no cambian. Este editor no firma, envía, destruye ni acuña.",
        "Condiciones no disponibles", "Solicitud de borrador rechazada"),
    "ja": ("再発行する船荷証券の条件を編集", "元の条件", "提案する条件の全文", "未署名の下書きを確認", "未署名の下書き",
        "元の条件は変更されません。この編集画面では署名、送信、焼却、発行を行いません。", "条件を取得できません", "下書きのリクエストを拒否しました"),
}


class RemintDraftUnavailable(ValueError):
    pass


def _business_text(value):
    if (type(value) is not str or not value.strip() or len(value) > 16384
            or re.search(r"0x[0-9a-fA-F]{40}", value)
            or any(ord(char) < 32 and char not in "\n\r\t" for char in value)):
        raise ValueError("bounded identity-excluding business text required")
    return value


class RemintDraftEditorBinding:
    """Trusted host supplies original typed declarations and nonsecret bill terms.

    No request selects a receipt, source reader, replacement asset or account.
    This is an unsigned editing aid, not an authorization or qualification gate.
    """
    def __init__(self, access, receipt_id, read_original_specifications):
        if type(access) is not SerializedExchangeAccess or not callable(read_original_specifications):
            raise ValueError("original serialized access and declaration reader required")
        self.access = access
        self.receipt_id = receipt_id
        self.read_original_specifications = read_original_specifications

    def draft(self, bill_terms=None):
        with self.access._lock:
            try:
                pair = deepcopy(self.read_original_specifications(self.receipt_id))
                if (type(pair) is not tuple or len(pair) != 2
                        or any(type(item) is not MintSpecification for item in pair)
                        or pair[0].receipt.receipt_id != self.receipt_id):
                    raise RemintDraftUnavailable("original bound declaration pair required")
                old, seed = pair
                old_text = _business_text(old.bill_terms)
                seed_text = _business_text(seed.bill_terms)
            except Exception:
                raise RemintDraftUnavailable("original business terms unavailable") from None
            text = seed_text if bill_terms is None else _business_text(bill_terms)
            result = edit_remint_draft(old, seed, {"specification": {"bill_terms": text}})
        return old_text, result

    def render(self, csrf, locale="en", bill_terms=None):
        words = WORDS[locale]
        original, result = self.draft(bill_terms)
        proposed = result["specification"].bill_terms
        preview = ("" if bill_terms is None else '<section><h2>' + escape(words[4])
            + '</h2><pre>' + escape(proposed) + '</pre></section>')
        # Only the selected complete business text is rendered. No raw model,
        # account, asset address, mapping, fact hash or local diagnostic is served.
        return ('<p>' + escape(words[5]) + '</p><section><h2>' + escape(words[1])
            + '</h2><pre>' + escape(original) + '</pre></section>'
            + '<form method="post" action="/remint-draft" autocomplete="off">'
            + '<input type="hidden" name="csrf" value="' + escape(csrf, quote=True) + '">'
            + '<input type="hidden" name="lang" value="' + locale + '">'
            + '<label>' + escape(words[2]) + '<textarea name="billTerms" rows="16" '
            + 'maxlength="16384" required>' + escape(proposed) + '</textarea></label>'
            + '<button type="submit">' + escape(words[3]) + '</button></form>' + preview)


def mount_remint_draft(server, editor):
    """Wire a constructed original server before its host starts serving."""
    if (type(server) is not RemintReviewWorkbenchServer
            or type(editor) is not RemintDraftEditorBinding
            or server.binding.exchange is not editor.access
            or server.binding.receipt_id != editor.receipt_id):
        raise ValueError("same original server, receipt and serialized access required")
    server.draft_editor = editor
    server.RequestHandlerClass = RemintDraftWorkbenchHandler
    return server


class RemintDraftWorkbenchHandler(RemintReviewWorkbenchHandler):
    @staticmethod
    def native_navigation(locale):
        return (RemintReviewWorkbenchHandler.native_navigation(locale)
            + '<nav><a href="/remint-draft?lang=' + locale + '">'
            + escape(WORDS[locale][0]) + '</a></nav>')

    def _draft_page(self, locale, text=None):
        return self._page(WORDS[locale][0],
            self.server.draft_editor.render(self.server.csrf, locale, text), locale,
            language_path="/remint-draft")

    def _refuse(self, status, locale="en"):
        self.close_connection = True
        self.send_body(status, WORDS[locale][7], Connection="close")

    def do_GET(self):
        request = urlsplit(self.path)
        if request.path != "/remint-draft":
            return super().do_GET()
        if not self.host_ok():
            return self._refuse(421)
        locale = "en"
        try:
            if request.fragment or len(request.query) > 64:
                raise ValueError("bounded locale required")
            query = parse_qs(request.query, strict_parsing=True,
                             keep_blank_values=True, max_num_fields=1)
            if set(query) - {"lang"} or any(len(value) != 1 for value in query.values()):
                raise ValueError("one locale only")
            locale = query.get("lang", ["en"])[0]
            if locale not in WORDS:
                raise ValueError("supported locale required")
        except ValueError:
            return self._refuse(400)
        try:
            self.send_body(200, self._draft_page(locale))
        except RemintDraftUnavailable:
            self.send_body(503, self._page(WORDS[locale][0],
                '<p role="alert">' + escape(WORDS[locale][6]) + '</p>', locale,
                language_path="/remint-draft"))

    def do_POST(self):
        request = urlsplit(self.path)
        if request.path != "/remint-draft":
            return super().do_POST()
        if not self.host_ok() or self.headers.get("Origin") != self.server.origin:
            return self._refuse(403)
        locale = "en"
        try:
            if (request.query or request.fragment or self.headers.get("Transfer-Encoding") is not None
                    or self.headers.get("Content-Type") != "application/x-www-form-urlencoded"):
                raise ValueError("plain bounded form required")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                raise ValueError("bounded body required")
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("incomplete body")
            fields = parse_qs(raw.decode("utf-8"), strict_parsing=True,
                keep_blank_values=True, max_num_fields=3, errors="strict")
            if set(fields) != {"csrf", "lang", "billTerms"} or any(len(v) != 1 for v in fields.values()):
                raise ValueError("exact draft fields required")
            locale = fields["lang"][0]
            if locale not in WORDS:
                locale = "en"
                raise ValueError("supported locale required")
            token = fields["csrf"][0]
            if not token.isascii() or not secrets.compare_digest(token, self.server.csrf):
                return self._refuse(403, locale)
            text = _business_text(fields["billTerms"][0])
            self.send_body(200, self._draft_page(locale, text))
        except RemintDraftUnavailable:
            self.close_connection = True
            self.send_body(503, WORDS[locale][6], Connection="close")
        except TimeoutError:
            return self._refuse(408, locale)
        except (ValueError, UnicodeError):
            return self._refuse(400, locale)
