"""Read one installed original operation without current draft availability."""
from copy import deepcopy
from html import escape
from urllib.parse import parse_qs, urlsplit

from .checkpointed_operation import CheckpointedOperationBridge
from .checkpointed_operation_observation import observe_checkpointed_operation
from .command_observation_page import STATUSES
from .durable_operation import _scope as original_scope
from .integrated_workbench import IntegratedWorkbenchServer

PATH = "/operation-observation"
KEYS = ("heading", "local", "native", "history", "checkpoint", "absent",
        "unknown", "reconciled", "notConfigured", "found", "unavailable",
        "noRecord", "boundary")
TEXT = {
    "en": ("Original operation enquiry", "Local EX claim", "Original gateway report",
        "Retained replacement history", "Pre-effect checkpoint", "No local record",
        "Unknown", "Locally reconciled", "Not configured", "Record found", "Unavailable",
        "No record returned by this enquiry",
        "Read-only enquiry of the already bound original operation. Local absence, a gateway report and a retained preimage are separate observations. None proves signing, burn/mint, settlement or finality, permits replay, reconciles UNKNOWN or releases funds."),
    "zh-Hans": ("原操作查询", "本地 EX 操作记录", "原网关报告", "保留的换铸历史",
        "执行前检查点", "无本地记录", "未知", "本地已对账", "未配置", "找到记录", "暂不可用",
        "本次查询未返回记录",
        "只读查询原已绑定操作。本地无记录、网关报告和保留的执行前状态是不同观察，均不证明签名、销毁或铸造、结算或最终性，不允许重发、不处理 UNKNOWN 或释放资金。"),
    "zh-Hant": ("原操作查詢", "本地 EX 操作記錄", "原閘道報告", "保留的換鑄歷史",
        "執行前檢查點", "無本地記錄", "未知", "本地已對帳", "未配置", "找到記錄", "暫不可用",
        "本次查詢未返回記錄",
        "唯讀查詢原已綁定操作。本地無記錄、閘道報告和保留的執行前狀態是不同觀測，均不證明簽名、銷毀或鑄造、結算或最終性，不允許重發、不處理 UNKNOWN 或釋放資金。"),
    "fr": ("Recherche de l’opération d’origine", "Enregistrement EX local", "Rapport de la passerelle d’origine",
        "Historique de remplacement conservé", "Point de contrôle avant effet", "Aucun enregistrement local",
        "Inconnu", "Réconcilié localement", "Non configuré", "Enregistrement trouvé", "Indisponible",
        "Aucun enregistrement renvoyé par cette recherche",
        "Recherche seule de l’opération déjà liée. Absence locale, rapport de passerelle et état conservé sont distincts. Rien ici ne prouve signature, destruction, création, règlement ou finalité, ni ne permet répétition, réconciliation de UNKNOWN ou libération de fonds."),
    "es": ("Consulta de la operación original", "Registro EX local", "Informe de la pasarela original",
        "Historial de reemplazo conservado", "Punto de control previo al efecto", "Sin registro local",
        "Desconocido", "Conciliado localmente", "Sin configurar", "Registro encontrado", "No disponible",
        "Esta consulta no devolvió un registro",
        "Solo consulta de la operación ya vinculada. Ausencia local, informe de pasarela y estado conservado son distintos. Nada aquí prueba firma, destrucción, acuñación, liquidación o finalidad, ni permite reenvío, conciliación de UNKNOWN o liberación de fondos."),
    "ja": ("元の操作を照会", "ローカル EX 記録", "元のゲートウェイ報告", "保持した再発行履歴",
        "実行前チェックポイント", "ローカル記録なし", "不明", "ローカル照合済み", "未設定",
        "記録あり", "取得不可", "この照会では記録が返されませんでした",
        "紐付け済みの元の操作を読み取り専用で照会します。ローカル記録の不在、ゲートウェイ報告、保持した実行前状態は別の観測です。署名、焼却、発行、決済、確定性を証明せず、再送、UNKNOWN の照合、資金解放を許可しません。"),
}
WORDS = {locale: dict(zip(KEYS, values)) for locale, values in TEXT.items()}


class OperationObservationUnavailable(ValueError):
    pass


class CheckpointedOperationObservationBinding:
    """Original host-selected scope and read-only port, never HTTP-selected IDs."""
    def __init__(self, bridge, binding, enquire_original, *, remint_history=None):
        if type(bridge) is not CheckpointedOperationBridge or not callable(enquire_original):
            raise ValueError("original checkpoint bridge and enquiry required")
        self.bridge = bridge
        self._binding = original_scope(binding)
        if remint_history is not None and self._binding["action"] != "remint":
            raise ValueError("remint history is specific to remint observations")
        self.receipt_id = self._binding["receiptId"]
        self.enquire_original, self.remint_history = enquire_original, remint_history

    def render(self, locale):
        if locale not in WORDS:
            raise ValueError("supported locale required")
        words = WORDS[locale]
        try:
            with self.bridge.access._lock:
                result = observe_checkpointed_operation(self.bridge, deepcopy(self._binding),
                    self.enquire_original, remint_history=self.remint_history)
            if (type(result) is not dict or result.get("nativeGateInvoked") is not False
                    or result.get("replayAllowed") is not False
                    or result.get("executionAuthorized") is not False):
                raise ValueError("original read-only observation required")
            operation = result["operation"]
            if (type(operation) is not dict or operation.get("nativeGateInvoked") is not False
                    or operation.get("replayAllowed") is not False):
                raise ValueError("original read-only enquiry required")
            claim = operation["localClaim"]
            if claim is None:
                local = words["absent"]
            elif type(claim) is dict and claim.get("status") in ("UNKNOWN", "RECONCILED"):
                local = words["unknown" if claim["status"] == "UNKNOWN" else "reconciled"]
            else:
                raise ValueError("original local claim observation required")
            native = operation["nativeObservation"]
            status = native.get("status") if type(native) is dict else None
            reported = (words["noRecord"] if native is None else
                        STATUSES[locale].get(status, words["unknown"])
                        if type(status) is str else words["unknown"])
            labels = {"NOT_CONFIGURED": "notConfigured", "FOUND": "found",
                      "ABSENT": "absent", "UNAVAILABLE": "unavailable"}
            history = operation.get("historyView", {"status": "NOT_CONFIGURED"})
            checkpoint = result["preEffectCheckpointView"]
            if (type(history) is not dict or history.get("status") not in labels
                    or type(checkpoint) is not dict or checkpoint.get("status") not in labels):
                raise ValueError("finite retained-state observations required")
            fields = ((words["local"], local), (words["native"], reported),
                (words["history"], words[labels[history["status"]]]),
                (words["checkpoint"], words[labels[checkpoint["status"]]]))
            # Deliberately never render scope, native IDs, proof references,
            # raw observations/errors, snapshots, history or declaration terms.
            return ('<dl>' + ''.join('<dt>' + escape(key) + '</dt><dd>'
                    + escape(value) + '</dd>' for key, value in fields)
                    + '</dl><p>' + escape(words["boundary"]) + '</p>')
        except Exception:
            raise OperationObservationUnavailable("original operation enquiry unavailable") from None


def mount_checkpointed_operation_observation(server, observation=None):
    """Mount before serving; no background loop or automatic reconciliation."""
    if not isinstance(server, IntegratedWorkbenchServer):
        raise ValueError("original workbench required")
    if observation is not None and (
            type(observation) is not CheckpointedOperationObservationBinding
            or observation.bridge.access is not server.binding.exchange
            or observation.receipt_id != server.binding.receipt_id):
        raise ValueError("same original workbench access and receipt required")
    if getattr(server, "_checkpointed_observation_mounted", False):
        if server.checkpointed_observation is not observation:
            raise ValueError("original observation already mounted")
        return server
    parent = server.RequestHandlerClass

    class ObservationHandler(parent):
        @staticmethod
        def native_navigation(locale):
            return (parent.native_navigation(locale) + '<nav><a href="' + PATH
                    + '?lang=' + locale + '">' + escape(WORDS[locale]["heading"]) + '</a></nav>')

        def do_GET(self):
            request = urlsplit(self.path)
            if request.path != PATH:
                return super().do_GET()
            if len(self.headers.get_all("Host", [])) != 1 or not self.host_ok():
                return self.send_body(421, "host refused")
            try:
                if request.fragment or len(request.query) > 64:
                    raise ValueError("bounded locale required")
                query = parse_qs(request.query, strict_parsing=True,
                                 keep_blank_values=True, max_num_fields=1)
                if set(query) - {"lang"} or any(len(v) != 1 for v in query.values()):
                    raise ValueError("one locale only")
                locale = query.get("lang", ["en"])[0]
                if locale not in WORDS:
                    raise ValueError("supported locale required")
            except ValueError:
                return self.send_body(400, "input refused")
            words = WORDS[locale]
            try:
                if self.server.checkpointed_observation is None:
                    raise OperationObservationUnavailable("not configured")
                content = self.server.checkpointed_observation.render(locale)
                status = 200
            except OperationObservationUnavailable:
                content, status = '<p role="alert">' + escape(words["unavailable"]) + '</p>', 503
            self.send_body(status, self._page(words["heading"], content, locale, language_path=PATH))

        def do_POST(self):
            if urlsplit(self.path).path != PATH:
                return super().do_POST()
            self.close_connection = True
            self.send_body(405, "read-only entry", Allow="GET", Connection="close")

    server.checkpointed_observation = observation
    server._checkpointed_observation_mounted = True
    server.RequestHandlerClass = ObservationHandler
    return server
