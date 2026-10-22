"""Six-locale view of existing bounded process-local gateway observations."""
from html import escape

from .public_workbench import command_result
from .queue_status_page import CONTROLS

KEYS = ("heading", "ordinal", "action", "status", "source", "transaction",
        "enquired", "dispatched", "unknown", "empty", "boundary")
TEXT = {
    "en": ("Recent gateway observations in this process", "Observation", "Action", "Reported status",
           "Observation path", "Transaction reference", "Returned by original gateway enquiry",
           "Returned by original gateway dispatch", "Unknown",
           "No observations retained in this process. The original journal has not been queried by this view.",
           "At most 64 process-local observations; restart or eviction may remove rows. These are gateway reports, not a durable journal or proof of signing, broadcast, registration, payment or full completion. An empty list is not absence of an original operation; unknown outcomes require original enquiry, never blind resend."),
    "zh-Hans": ("本进程最近的网关观察", "观察记录", "操作", "报告状态", "观察路径", "交易引用",
                "原网关查询返回", "原网关分发返回", "未知",
                "本进程未保留观察记录。本页面没有查询原始日志。",
                "最多保留64条进程内观察；重启或淘汰可能移除记录。这些是网关报告，不是持久日志，也不证明签署、广播、登记、付款或全部完成。空列表不代表原始操作不存在；未知结果必须通过原路径查询，不可盲目重发。"),
    "zh-Hant": ("本進程最近的閘道觀測", "觀測記錄", "操作", "報告狀態", "觀測路徑", "交易引用",
                "原閘道查詢返回", "原閘道分發返回", "未知",
                "本進程未保留觀測記錄。本頁面沒有查詢原始日誌。",
                "最多保留64條進程內觀測；重啟或淘汰可能移除記錄。這些是閘道報告，不是持久日誌，也不證明簽署、廣播、登記、付款或全部完成。空列表不代表原始操作不存在；未知結果必須透過原路徑查詢，不可盲目重發。"),
    "fr": ("Observations récentes de la passerelle dans ce processus", "Observation", "Action", "État rapporté",
           "Chemin d’observation", "Référence de transaction", "Retour de la recherche par la passerelle d’origine",
           "Retour de l’envoi par la passerelle d’origine", "Inconnu",
           "Aucune observation conservée dans ce processus. Cette vue n’a pas interrogé le journal d’origine.",
           "Au plus 64 observations en mémoire ; redémarrage et éviction peuvent les supprimer. Ces rapports ne sont ni un journal durable ni une preuve de signature, diffusion, enregistrement, paiement ou achèvement global. Une liste vide ne prouve pas l’absence d’opération ; rechercher les résultats inconnus par la voie d’origine sans renvoi aveugle."),
    "es": ("Observaciones recientes de la pasarela en este proceso", "Observación", "Acción", "Estado informado",
           "Vía de observación", "Referencia de transacción", "Devuelto por consulta de la pasarela original",
           "Devuelto por envío de la pasarela original", "Desconocido",
           "No hay observaciones conservadas en este proceso. Esta vista no ha consultado el registro original.",
           "Máximo 64 observaciones en memoria; reinicios y expulsiones pueden eliminarlas. Estos informes no son un registro duradero ni prueban firma, difusión, registro, pago o finalización global. Una lista vacía no demuestra ausencia de operaciones; consulte los resultados desconocidos por la vía original sin reenvíos a ciegas."),
    "ja": ("このプロセスの最近のゲートウェイ観測", "観測記録", "操作", "報告された状態", "観測経路", "取引参照",
           "元のゲートウェイ照会からの応答", "元のゲートウェイ送信からの応答", "不明",
           "このプロセスには観測記録がありません。この表示は元のジャーナルを照会していません。",
           "最大64件のプロセス内観測で、再起動や削除により失われます。ゲートウェイの報告であり、永続ジャーナルや署名、ブロードキャスト、登記、支払い、全体完了の証明ではありません。空の一覧は元の操作の不存在を示しません。不明な結果は元の経路で照会し、盲目的に再送しないでください。"),
}
WORDS = {locale: dict(zip(KEYS, values)) for locale, values in TEXT.items()}
STATUS_KEYS = ("pending", "unknown", "settled", "failed", "refused", "blocked", "not-funded",
               "locked", "released", "refunded", "not-modelled", "release-failed",
               "release-outcome-unknown", "not-submitted", "confirmed", "rejected", "none",
               "available", "detached", "in-progress", "returned", "complete", "done")
STATUS_TEXT = {
    "en": ("Pending", "Unknown", "Settled", "Failed", "Refused", "Blocked", "Not funded",
           "Locked", "Released", "Refunded", "Not modelled", "Release failed",
           "Release outcome unknown", "Not submitted", "Confirmed", "Rejected", "None",
           "Available", "Detached", "In progress", "Returned", "Reported complete", "Reported done"),
    "zh-Hans": ("待处理", "未知", "已结算", "失败", "已拒绝", "受阻", "未入资", "已冻结", "已释放",
                "已退款", "未建模", "释放失败", "释放结果未知", "未提交", "已确认", "已拒绝", "无",
                "可用", "已解除关联", "进行中", "已返还", "报告已完成", "报告已处理"),
    "zh-Hant": ("待處理", "未知", "已結算", "失敗", "已拒絕", "受阻", "未入資", "已凍結", "已釋放",
                "已退款", "未建模", "釋放失敗", "釋放結果未知", "未提交", "已確認", "已拒絕", "無",
                "可用", "已解除關聯", "進行中", "已返還", "報告已完成", "報告已處理"),
    "fr": ("En attente", "Inconnu", "Réglé", "Échec", "Refusé", "Bloqué", "Non financé",
           "Bloqué en dépôt", "Libéré", "Remboursé", "Non modélisé", "Libération échouée",
           "Résultat de libération inconnu", "Non soumis", "Confirmé", "Rejeté", "Aucun",
           "Disponible", "Détaché", "En cours", "Retourné", "Rapporté complet", "Rapporté terminé"),
    "es": ("Pendiente", "Desconocido", "Liquidado", "Fallido", "Rechazado", "Bloqueado", "Sin fondos",
           "Fondos retenidos", "Liberado", "Reembolsado", "Sin modelar", "Liberación fallida",
           "Resultado de liberación desconocido", "Sin enviar", "Confirmado", "Rechazado", "Ninguno",
           "Disponible", "Desvinculado", "En curso", "Devuelto", "Informado como completo", "Informado como terminado"),
    "ja": ("処理待ち", "不明", "決済済み", "失敗", "拒否", "停止中", "未入金", "凍結済み", "解放済み",
           "返金済み", "モデル化なし", "解放失敗", "解放結果不明", "未提出", "確認済み", "拒否", "なし",
           "利用可能", "関連付け解除済み", "進行中", "返還済み", "完了との報告", "処理済みとの報告"),
}
STATUSES = {locale: dict(zip(STATUS_KEYS, values)) for locale, values in STATUS_TEXT.items()}
ACTIONS = frozenset(("submit-registration", "reconcile-payment", "resume-payment", "advance-rollback"))


def render_command_observations(observations, *, locale="en"):
    """Project only existing RAM values; never query, reconcile or dispatch."""
    if locale not in WORDS:
        raise ValueError("supported observation locale required")
    if type(observations) not in (tuple, list) or len(observations) > 64:
        raise ValueError("existing bounded observation snapshot required")
    w, statuses, controls = WORDS[locale], STATUSES[locale], CONTROLS[locale]
    rows = []
    for ordinal, raw in enumerate(observations, 1):
        item = raw if type(raw) is dict else {}
        action = item.get("action")
        action_label = controls[action] if type(action) is str and action in ACTIONS else w["unknown"]
        result = command_result(item.get("result"))
        status = statuses.get(result["status"], w["unknown"])
        enquired = item.get("enquired")
        path = w["enquired"] if enquired is True else w["dispatched"] if enquired is False else w["unknown"]
        cells = (str(ordinal), action_label, status, path, result.get("transactionHash", w["unknown"]))
        rows.append('<tr>' + ''.join('<td>' + escape(cell, quote=True) + '</td>' for cell in cells) + '</tr>')
    if not rows:
        rows.append('<tr><td colspan="5">' + escape(w["empty"]) + '</td></tr>')
    headings = ''.join('<th scope="col">' + escape(w[key]) + '</th>'
                       for key in ("ordinal", "action", "status", "source", "transaction"))
    return ('<section class="command-observations" lang="' + locale + '"><h3>' + escape(w["heading"])
            + '</h3><p>' + escape(w["boundary"]) + '</p><div style="overflow:auto;overflow-wrap:anywhere">'
            + '<table><thead><tr>' + headings + '</tr></thead><tbody>' + ''.join(rows)
            + '</tbody></table></div></section>')
