"""Optional six-language observation of an original gas-budget snapshot.

No financial, journal, reservation, confirmation or transaction writes.
"""
from html import escape

KEYS = ("heading", "cap", "spent", "pending", "unused", "proposal", "closed",
        "yes", "no", "unknown", "unavailable", "policy")
TEXT = {
    "en": ("Recorded ETH gas budget", "Recorded confirmed maximum",
           "Recorded consumed gas", "Pending or UNKNOWN reserved upper bound",
           "Unused maximum, including pending reservations", "Proposed unused ETH release",
           "Budget projection closed", "Yes", "No", "Not proposed",
           "Original budget observation unavailable.",
           "Amounts are ETH wei, separate from principal. Pending or UNKNOWN reservations remain reserved. "
           "Unused maximum is not spendable ETH. A release proposal is not a Wallet unfreeze or a new authority."),
    "zh-Hans": ("已记录的 ETH gas 预算", "已记录的确认上限", "已记录的已消耗 gas",
                "待决或 UNKNOWN 预留上限", "未用上限（含待决预留）", "未用 ETH 释放提议",
                "预算投影已关闭", "是", "否", "未提出",
                "原预算观察不可用。",
                "金额单位为 ETH wei，与本金分开。待决或 UNKNOWN 预留保持冻结。未用上限不等于可支用 ETH，释放提议不代表钱包已解冻或新增授权。"),
    "zh-Hant": ("已記錄的 ETH gas 預算", "已記錄的確認上限", "已記錄的已消耗 gas",
                "待決或 UNKNOWN 預留上限", "未用上限（含待決預留）", "未用 ETH 釋放提議",
                "預算投影已關閉", "是", "否", "未提出",
                "原預算觀察不可用。",
                "金額單位為 ETH wei，與本金分開。待決或 UNKNOWN 預留保持凍結。未用上限不等於可支用 ETH，釋放提議不代表錢包已解凍或新增授權。"),
    "fr": ("Budget de gas ETH consigné", "Maximum confirmé consigné", "Gas consommé consigné",
           "Borne réservée en attente ou UNKNOWN", "Maximum inutilisé, réservations en attente incluses",
           "Proposition de libération d’ETH inutilisé", "Projection du budget fermée",
           "Oui", "Non", "Non proposé", "Observation du budget d’origine indisponible.",
           "Montants en ETH wei, séparés du principal. Les réservations en attente ou UNKNOWN restent bloquées. "
           "Le maximum inutilisé n’est pas de l’ETH disponible. Une proposition ne prouve aucun déblocage Wallet ni nouvelle autorisation."),
    "es": ("Presupuesto de gas ETH registrado", "Máximo confirmado registrado", "Gas consumido registrado",
           "Límite reservado pendiente o UNKNOWN", "Máximo sin usar, incluidas reservas pendientes",
           "Propuesta de liberar ETH sin usar", "Proyección del presupuesto cerrada",
           "Sí", "No", "Sin propuesta", "Observación del presupuesto original no disponible.",
           "Importes en ETH wei, separados del principal. Las reservas pendientes o UNKNOWN siguen retenidas. "
           "El máximo sin usar no es ETH disponible. Una propuesta no acredita desbloqueo Wallet ni nueva autorización."),
    "ja": ("記録された ETH gas 予算", "記録された確認済み上限", "記録された消費済み gas",
           "未確定または UNKNOWN の予約上限", "未確定予約を含む未使用上限", "未使用 ETH の解放提案",
           "予算投影の終了", "はい", "いいえ", "提案なし", "元の予算観測を利用できません。",
           "金額は元本とは別の ETH wei です。未確定または UNKNOWN の予約は維持されます。未使用上限は利用可能 ETH ではありません。解放提案は Wallet の凍結解除や新たな権限を証明しません。"),
}
WORDS = {locale: dict(zip(KEYS, values)) for locale, values in TEXT.items()}


def render_budget_observation(read_original_budget, quote, locale):
    """Read one installed snapshot port for the current original quote.

    The port returns GasBudgetBook.snapshot's dict, not a recovery-journal
    envelope, and remains responsible for original source/session binding.
    Optional observation failures cannot replace or block quote confirmation.
    Private identities, errors, source/journal details and extra fields are
    never rendered. This is not the standalone UNKNOWN recovery query.
    """
    w = WORDS[locale]
    heading = '<h3>' + escape(w["heading"]) + '</h3>'
    policy = '<p>' + escape(w["policy"]) + '</p>'
    def unavailable():
        return ('<section data-gas-budget-observation="unavailable">'
                + heading + '<p>' + escape(w["unavailable"]) + '</p>' + policy + '</section>')
    try:
        value = read_original_budget(quote.budget_id)
        if (type(value) is not dict or "unfreezeProposalWei" not in value
                or value.get("budgetId") != quote.budget_id
                or value.get("quoteDigest") != quote.digest
                or type(value.get("closed")) is not bool):
            return unavailable()
        names = ("capWei", "actualConsumedWei", "pendingBoundWei", "unusedWei")
        if any(type(value.get(key)) is not int or not 0 <= value[key] < 2**256
               for key in names):
            return unavailable()
        cap, spent, pending, unused = (value[key] for key in names)
        proposal, closed = value.get("unfreezeProposalWei"), value["closed"]
        if (cap != quote.cap_wei or spent + pending > cap or unused != cap - spent
                or (closed and (pending != 0 or type(proposal) is not int or proposal != unused))
                or (not closed and proposal is not None)):
            return unavailable()
    except Exception:
        return unavailable()
    rows = [
        (w["cap"], str(cap) + " ETH wei"), (w["spent"], str(spent) + " ETH wei"),
        (w["pending"], str(pending) + " ETH wei"), (w["unused"], str(unused) + " ETH wei"),
        (w["proposal"], w["unknown"] if proposal is None else str(proposal) + " ETH wei"),
        (w["closed"], w["yes"] if closed else w["no"]),
    ]
    return ('<section data-gas-budget-observation="recorded">' + heading + '<dl>'
            + ''.join('<dt>' + escape(key) + '</dt><dd>' + escape(text) + '</dd>'
                      for key, text in rows) + '</dl>' + policy + '</section>')
