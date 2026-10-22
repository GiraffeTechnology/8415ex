"""Read-only comparison of original identity-excluding business projections."""
from copy import deepcopy
from difflib import SequenceMatcher
from html import escape
import re

from .ids import identifier


class RemintReviewUnavailable(ValueError):
    pass


WORDS = {
    "en": ("Review replacement bill terms", "Current bill terms", "Proposed bill terms",
           "Business terms differ", "Business terms are unchanged", "Terms unavailable",
           "Review only. This page does not sign, burn or mint an NFT.",
           "The existing execution path checks Holder possession and Holder = Owner.", "Replacement terms"),
    "zh-Hans": ("查看换铸提单条款", "当前提单条款", "拟新提单条款", "业务条款有变化", "业务条款未变化",
                "条款暂不可用", "仅供查看。本页不签署、不销毁或铸造 NFT。",
                "既有执行流程核验 Holder 持有及 Holder = Owner。", "换铸条款"),
    "zh-Hant": ("查看換鑄提單條款", "目前提單條款", "擬新提單條款", "業務條款有變化", "業務條款未變化",
                "條款暫不可用", "僅供查看。本頁不簽署、不銷毀或鑄造 NFT。",
                "既有執行流程核驗 Holder 持有及 Holder = Owner。", "換鑄條款"),
    "fr": ("Examiner les conditions du connaissement de remplacement", "Conditions actuelles", "Conditions proposées",
           "Les conditions commerciales diffèrent", "Conditions commerciales inchangées", "Conditions indisponibles",
           "Consultation uniquement. Cette page ne signe, ne détruit et ne crée aucun NFT.",
           "Le parcours d’exécution existant vérifie la possession par Holder et Holder = Owner.", "Conditions de remplacement"),
    "es": ("Revisar las condiciones del conocimiento de reemplazo", "Condiciones actuales", "Condiciones propuestas",
           "Las condiciones comerciales difieren", "Condiciones comerciales sin cambios", "Condiciones no disponibles",
           "Solo consulta. Esta página no firma, destruye ni acuña un NFT.",
           "El proceso existente verifica la posesión de Holder y Holder = Owner.", "Condiciones de reemplazo"),
    "ja": ("再発行する船荷証券の条件を確認", "現在の条件", "提案された条件", "業務条件に変更があります", "業務条件に変更はありません",
           "条件を取得できません", "閲覧専用です。このページで NFT の署名、焼却、発行は行いません。",
           "既存の実行処理で Holder の保有および Holder = Owner を確認します。", "再発行の条件"),
}


def _clauses(detail, receipt_id):
    if (type(detail) is not dict or detail.get("schema") != "8415ex-public-nft-detail/1"
            or detail.get("receiptId") != receipt_id
            or detail.get("sourceStatus") != "verified-original-reader"):
        raise RemintReviewUnavailable("original public projection unavailable")
    terms = detail.get("terms")
    if type(terms) is not dict or terms.get("status") != "provided-verified-projection":
        raise RemintReviewUnavailable("complete business projection unavailable")
    clauses = terms.get("clauses")
    if type(clauses) is not list or not 1 <= len(clauses) <= 128:
        raise RemintReviewUnavailable("bounded complete clauses required")
    result, total = [], 0
    for clause in clauses:
        if type(clause) is not dict or set(clause) != {"label", "text"}:
            raise RemintReviewUnavailable("exact projected business clause required")
        for key in ("label", "text"):
            value = clause[key]
            if (type(value) is not str or not value.strip() or len(value) > 16384
                    or any(ord(char) < 32 and char not in "\n\r\t" for char in value)
                    or re.search(r"0x[0-9a-fA-F]{40}", value)):
                raise RemintReviewUnavailable("identity-excluding bounded clause required")
            total += len(value)
        if total > 131072:
            raise RemintReviewUnavailable("business projection limit exceeded")
        result.append(dict(clause))
    return result


def _render_changes(before, after, words):
    """Compare ordered public clauses exactly; no semantic or identity inference."""
    old = [(item["label"], item["text"]) for item in before]
    new = [(item["label"], item["text"]) for item in after]
    changes = []
    for kind, start, end, new_start, new_end in SequenceMatcher(
            a=old, b=new, autojunk=False).get_opcodes():
        if kind == "equal":
            continue
        def side(clauses, first, last, title, tag):
            if first == last:
                return ""
            articles = "".join(
                '<article data-clause-position="' + str(index + 1) + '"><h4>'
                + escape(clauses[index]["label"]) + '</h4><pre>'
                + escape(clauses[index]["text"]) + '</pre></article>'
                for index in range(first, last))
            return ('<section><h3>' + escape(title) + ' '
                    + str(first + 1) + '–' + str(last) + '</h3><' + tag + '>'
                    + articles + '</' + tag + '></section>')
        changes.append('<div data-clause-change="' + kind + '">'
                       + side(before, start, end, words[1], "del")
                       + side(after, new_start, new_end, words[2], "ins") + '</div>')
    if not changes:
        return ""
    return ('<section data-remint-clause-changes="1"><h2>' + escape(words[3])
            + '</h2>' + "".join(changes) + '</section>')


class RemintReviewBinding:
    """The host injects its original trusted projection reader, never request data.

    The reader resolves the current and proposed document versions from one
    original context and returns two existing public-detail read models. Status
    strings and hashes alone do not authenticate arbitrary request-body models.
    This class performs no new schema/document verification or eligibility check.
    """

    def __init__(self, receipt_id, replacement_receipt_id, read_original_pair):
        identifier(receipt_id)
        identifier(replacement_receipt_id)
        if not callable(read_original_pair):
            raise RemintReviewUnavailable("original current/proposed document binding required")
        self.receipt_id = receipt_id
        self.replacement_receipt_id = replacement_receipt_id
        self.read_original_pair = read_original_pair

    def render(self, locale="en"):
        if locale not in WORDS:
            raise ValueError("supported locale required")
        try:
            pair = deepcopy(self.read_original_pair(self.receipt_id, self.replacement_receipt_id))
            if type(pair) is not tuple or len(pair) != 2:
                raise RemintReviewUnavailable("original paired projections required")
            before = _clauses(pair[0], self.receipt_id)
            after = _clauses(pair[1], self.replacement_receipt_id)
        except Exception:
            raise RemintReviewUnavailable("original business terms unavailable") from None
        words = WORDS[locale]
        def section(title, clauses):
            return ('<section><h2>' + escape(title) + '</h2>' + ''.join(
                '<article><h3>' + escape(item["label"]) + '</h3><pre>' + escape(item["text"])
                + '</pre></article>' for item in clauses) + '</section>')
        return ('<p role="status">' + escape(words[3] if before != after else words[4]) + '</p>'
                + _render_changes(before, after, words)
                + section(words[1], before) + section(words[2], after)
                + '<p>' + escape(words[6]) + '</p><p>' + escape(words[7]) + '</p>')
