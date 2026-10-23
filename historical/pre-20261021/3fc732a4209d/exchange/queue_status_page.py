"""Read-only localized queue component; original domain remains authoritative."""
from html import escape


KEYS = ('heading', 'leg', 'state', 'detail', 'none', 'deferred', 'deferredDetail',
        'rejected', 'rejectedDetail', 'overdue', 'overdueDetail', 'pending',
        'pendingDetail', 'confirmed', 'confirmedDetail', 'unfiled', 'unfiledDetail',
        'unknown', 'unknownDetail', 'boundary')
TEXT = {
    'en': ('Operations queue', 'Leg', 'State', 'Detail', 'No trade legs recorded',
           'Deferred', 'A later result is waiting for the preceding registration.',
           'Refused', 'The domain records a registrar refusal for this leg.',
           'Commitment window passed', 'The reported window has passed; this observation alone does not decide the outcome.',
           'Awaiting registrar', 'Submitted and awaiting the original registration result.',
           'Confirmed', 'The domain records registration confirmation for this leg.',
           'Not submitted', 'No registration request is recorded for this leg.',
           'Unknown', 'The original status cannot be interpreted by this view; inspect the private journal.',
           'Read-only domain observation. This page cannot mark success, change holder, authorize a retry or prove chain acceptance.'),
    'zh-Hans': ('操作队列', '交易段', '状态', '详情', '尚无交易段记录',
                '延后处理', '后续结果等待前序登记。', '已拒绝', '领域记录显示登记方拒绝了本段。',
                '承诺窗口已过', '报告的窗口已过；此观察本身不决定最终结果。',
                '等待登记方', '已提交，等待原始登记结果。', '已确认', '领域记录显示本段登记已确认。',
                '未提交', '本段尚无登记请求记录。', '未知', '本页面无法解释原始状态，请检查私有日志。',
                '此页仅为只读领域观察，不能手动标记成功、改变 holder、授权重试或证明链上验收。'),
    'zh-Hant': ('操作佇列', '交易段', '狀態', '詳情', '尚無交易段記錄',
                '延後處理', '後續結果等待前序登記。', '已拒絕', '領域記錄顯示登記方拒絕了本段。',
                '承諾視窗已過', '報告的視窗已過；此觀察本身不決定最終結果。',
                '等待登記方', '已提交，等待原始登記結果。', '已確認', '領域記錄顯示本段登記已確認。',
                '未提交', '本段尚無登記請求記錄。', '未知', '本頁面無法解釋原始狀態，請檢查私有日誌。',
                '此頁僅為唯讀領域觀察，不能手動標記成功、改變 holder、授權重試或證明鏈上驗收。'),
    'fr': ('File des opérations', 'Segment', 'État', 'Détail', 'Aucun segment enregistré',
           'Différé', 'Un résultat ultérieur attend l’enregistrement précédent.',
           'Refusé', 'Le domaine consigne un refus du registraire pour ce segment.',
           'Délai d’engagement dépassé', 'Le délai indiqué est dépassé ; cette observation seule ne décide pas du résultat.',
           'En attente du registraire', 'Soumis, en attente du résultat d’enregistrement d’origine.',
           'Confirmé', 'Le domaine consigne la confirmation d’enregistrement de ce segment.',
           'Non soumis', 'Aucune demande d’enregistrement consignée pour ce segment.',
           'Inconnu', 'Cette vue ne peut interpréter l’état d’origine ; consulter le journal privé.',
           'Observation du domaine en lecture seule. Cette page ne peut déclarer un succès, modifier holder, autoriser une reprise ou prouver une validation sur chaîne.'),
    'es': ('Cola de operaciones', 'Tramo', 'Estado', 'Detalle', 'No hay tramos registrados',
           'Aplazado', 'Un resultado posterior espera el registro anterior.',
           'Rechazado', 'El dominio registra un rechazo del registrador para este tramo.',
           'Ventana de compromiso vencida', 'La ventana indicada ha vencido; esta observación por sí sola no decide el resultado.',
           'Esperando al registrador', 'Enviado, a la espera del resultado de registro original.',
           'Confirmado', 'El dominio registra la confirmación de registro de este tramo.',
           'Sin enviar', 'No consta una solicitud de registro para este tramo.',
           'Desconocido', 'Esta vista no puede interpretar el estado original; consulte el registro privado.',
           'Observación del dominio de solo lectura. Esta página no puede marcar éxito, cambiar holder, autorizar reintentos ni demostrar aceptación en cadena.'),
    'ja': ('操作キュー', '取引区間', '状態', '詳細', '取引区間の記録はありません',
           '保留', '後続の結果は先行する登記を待っています。',
           '拒否', 'ドメインにはこの区間の登記機関による拒否が記録されています。',
           '確約期間経過', '報告された期間は経過していますが、この観測だけでは結果を確定しません。',
           '登記機関待ち', '提出済みで、元の登記結果を待っています。',
           '確認済み', 'ドメインにはこの区間の登記確認が記録されています。',
           '未提出', 'この区間の登記申請は記録されていません。',
           '不明', 'このビューでは元の状態を解釈できません。非公開ジャーナルを確認してください。',
           '読み取り専用のドメイン観測です。成功の手動設定、holder の変更、再試行の承認、チェーン上の受入証明はできません。'),
}
WORDS = {locale: dict(zip(KEYS, values)) for locale, values in TEXT.items()}

CONTROL_KEYS = ('heading', 'disabled', 'boundary', 'action', 'key', 'leg', 'submit',
                'receipt', 'market', 'evidence', 'language', 'inputRefused',
                'gatewayRefused', 'originRefused', 'csrfRefused', 'outcomeUnknown',
                'timeout', 'submit-registration', 'reconcile-payment',
                'resume-payment', 'advance-rollback', 'advance-exit')
CONTROL_TEXT = {
    'en': ('Checked operation requests',
           'Original wallet/task-journal gateway NOT_CONFIGURED. No action is enabled. Read-only pages remain available.',
           'These requests use the original wallet-authorized gateway. Connecting is not authorization. Unknown results are enquired and are never blindly resent. No success outcome can be supplied.',
           'Action', 'Original task journal key', 'Leg index (only for segment actions)',
           'Submit through checked gateway', 'Receipt', 'Market', 'Evidence', 'Language',
           'Request refused; inspect the original private journal',
           'Original checked gateway refused this operation', 'Same-origin request required',
           'Request token refused', 'Operation outcome unknown; enquire original journal before retry',
           'Operation timed out; enquire original journal before retry',
           'Submit registration', 'Enquire payment outcome', 'Resume an eligible payment',
           'Continue authorized suffix recovery', 'Continue authorized exit'),
    'zh-Hans': ('受控操作请求', '原有钱包／任务日志网关未配置，未启用任何操作，只读页面仍可访问。',
                '请求进入原有钱包授权网关。连接不等于授权；未知结果先查询，绝不盲目重发，不能手动提供成功结果。',
                '操作', '原始任务日志键', '交易段索引（仅分段操作填写）', '通过受控网关提交',
                '提单', '市场', '证据', '语言', '请求被拒绝，请检查原始私有日志。',
                '原有受控网关拒绝了此操作。', '必须从相同来源提交请求。', '请求令牌被拒绝。',
                '操作结果未知，重试前先查询原始日志。', '操作超时，重试前先查询原始日志。',
                '提交登记', '查询资金执行结果', '恢复符合条件的资金执行', '继续已授权的后缀恢复', '继续已授权的退出'),
    'zh-Hant': ('受控操作請求', '原有錢包／任務日誌閘道未設定，未啟用任何操作，唯讀頁面仍可存取。',
                '請求進入原有錢包授權閘道。連線不等於授權；未知結果先查詢，絕不盲目重送，不能手動提供成功結果。',
                '操作', '原始任務日誌鍵', '交易段索引（僅分段操作填寫）', '透過受控閘道提交',
                '提單', '市場', '證據', '語言', '請求遭拒，請檢查原始私有日誌。',
                '原有受控閘道拒絕了此操作。', '必須從相同來源提交請求。', '請求權杖遭拒。',
                '操作結果未知，重試前先查詢原始日誌。', '操作逾時，重試前先查詢原始日誌。',
                '提交登記', '查詢資金執行結果', '恢復符合條件的資金執行', '繼續已授權的後綴復原', '繼續已授權的退出'),
    'fr': ('Demandes d’opération contrôlées', 'Passerelle portefeuille/journal d’origine non configurée. Aucune action activée ; les vues restent accessibles en lecture seule.',
           'Les demandes passent par la passerelle autorisée d’origine. Une connexion ne vaut pas autorisation. Tout résultat inconnu est d’abord recherché, sans renvoi aveugle. Aucun succès ne peut être fourni manuellement.',
           'Action', 'Clé du journal de tâche d’origine', 'Indice du segment (opérations segmentaires uniquement)',
           'Soumettre à la passerelle contrôlée', 'Titre', 'Marché', 'Preuves', 'Langue',
           'Demande refusée ; consulter le journal privé d’origine.', 'La passerelle d’origine a refusé cette opération.',
           'Une demande de même origine est nécessaire.', 'Jeton de demande refusé.',
           'Résultat inconnu ; consulter le journal d’origine avant toute reprise.',
           'Délai dépassé ; consulter le journal d’origine avant toute reprise.',
           'Soumettre l’enregistrement', 'Rechercher le résultat financier', 'Reprendre une exécution financière admissible',
           'Continuer la reprise autorisée du suffixe', 'Continuer la sortie autorisée'),
    'es': ('Solicitudes de operación controladas', 'Pasarela original de cartera y registro sin configurar. Ninguna acción habilitada; las vistas de solo lectura siguen disponibles.',
           'Las solicitudes usan la pasarela autorizada original. Conectar no autoriza. Los resultados desconocidos se consultan antes de actuar y nunca se reenvían a ciegas. No se puede introducir un éxito manualmente.',
           'Acción', 'Clave del registro de tarea original', 'Índice de tramo (solo operaciones de tramo)',
           'Enviar por la pasarela controlada', 'Título', 'Mercado', 'Pruebas', 'Idioma',
           'Solicitud rechazada; consulte el registro privado original.', 'La pasarela original rechazó esta operación.',
           'Se requiere una solicitud del mismo origen.', 'Token de solicitud rechazado.',
           'Resultado desconocido; consulte el registro original antes de reintentar.',
           'Operación agotada; consulte el registro original antes de reintentar.',
           'Enviar registro', 'Consultar el resultado financiero', 'Reanudar una ejecución financiera admisible',
           'Continuar la recuperación autorizada del sufijo', 'Continuar la salida autorizada'),
    'ja': ('検証付き操作要求', '元のウォレット／タスクジャーナル用ゲートウェイは未設定です。操作は無効ですが、読み取り専用ページは利用できます。',
           '要求は元の承認済みウォレットゲートウェイを使用します。接続は承認ではありません。不明な結果は先に照会し、盲目的に再送しません。成功結果を手動入力することはできません。',
           '操作', '元のタスクジャーナルキー', '取引区間インデックス（区間操作のみ）', '検証付きゲートウェイから送信',
           '船荷証券', '市場', '証拠', '言語', '要求は拒否されました。元の非公開ジャーナルを確認してください。',
           '元の検証付きゲートウェイが操作を拒否しました。', '同一オリジンからの要求が必要です。', '要求トークンが拒否されました。',
           '操作結果は不明です。再試行前に元のジャーナルを照会してください。', '操作がタイムアウトしました。再試行前に元のジャーナルを照会してください。',
           '登記を提出', '資金実行結果を照会', '条件を満たす資金実行を再開', '承認済みの後続区間復旧を継続', '承認済みの退出を継続'),
}
CONTROLS = {locale: dict(zip(CONTROL_KEYS, values)) for locale, values in CONTROL_TEXT.items()}


def render_queue_status(exchange, receipt_id, *, locale='en', now=None):
    """Render only original leg indices and known status meanings, never parties."""
    if locale not in WORDS:
        raise ValueError('supported queue locale required')
    w = WORDS[locale]
    view = exchange.receipt_view(receipt_id, now)
    overdue = {entry['legIndex'] for entry in exchange.overdue_requests(receipt_id, now)}
    rows = []
    for leg in view['legs']:
        index = leg['legIndex']
        if type(index) is not int or index < 0:
            raise ValueError('original leg index required')
        status = leg['registrationStatus']
        if index in view['deferredLegs']:
            key = 'deferred'
        elif index in view['rejectedLegs']:
            key = 'rejected'
        elif status == 'pending':
            key = 'overdue' if index in overdue else 'pending'
        elif status == 'confirmed':
            key = 'confirmed'
        elif status == 'not-submitted':
            key = 'unfiled'
        else:
            key = 'unknown'
        rows.append('<tr><td>' + str(index) + '</td><td>' + escape(w[key])
                    + '</td><td>' + escape(w[key + 'Detail']) + '</td></tr>')
    if not rows:
        rows.append('<tr><td colspan="3">' + escape(w['none']) + '</td></tr>')
    header = '<tr>' + ''.join('<th>' + escape(w[key]) + '</th>'
                              for key in ('leg', 'state', 'detail')) + '</tr>'
    return ('<section lang="' + locale + '"><h2>' + escape(w['heading']) + '</h2><p>'
            + escape(w['boundary']) + '</p><table>' + header + ''.join(rows) + '</table></section>')
