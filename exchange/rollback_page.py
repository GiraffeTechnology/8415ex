"""Six-locale rollback observation; no success, retry or funds-writing controls."""
from html import escape

from .authorization_page import WORDS as AUTH
from .timeline_page import WORDS as TIMELINE
from .queue_status_page import WORDS as QUEUE
from .rollback_projection import rollback_projection, rollback_history_projection


KEYS = ('heading', 'prefix', 'outstanding', 'trigger', 'boundary', 'returned', 'steps',
        'kind', 'refundStep', 'returnStep', 'completion', 'noRecovery', 'refusal', 'deadline',
        'pending', 'blocked', 'done', 'financial', 'principal', 'escrow', 'buyerNet', 'gas',
        'policy', 'nativeBoundary', 'scope', 'consistency', 'unfunded', 'payment', 'failed')
TEXT = {
    'en': ('Suffix recovery detail', 'Protected registered prefix', 'Outstanding legs',
           'Original trigger', 'Return boundary position', 'Asset return reported',
           'Outstanding original steps', 'Step kind', 'Refund original principal', 'Return asset',
           'Domain completion report', 'No recovery is open in this domain report.',
           'Recorded registrar refusal', 'Trading deadline passed', 'Pending', 'Blocked', 'Done',
           'Affected funds', 'Principal', 'Escrow', 'Net principal returned to original buyer',
           'Consumed buyer gas',
           'Principal returns in its original currency. Consumed ETH is charged separately and is not refunded. '
           'Unknown outcomes require original-operation enquiry before retry; no second buyer payment is introduced.',
           'Read-only domain observation, not native financial, Oracle, Wallet or chain acceptance. '
           'The protected prefix stays visible; no step can be marked complete here.',
           'Leg or boundary position', 'Domain report internally consistent', 'Not funded', 'Payment outcome', 'Failed'),
    'zh-Hans': ('后缀恢复详情', '受保护的已登记前缀', '未完成交易段', '原始触发原因', '返还边界位置',
                '报告的资产返还', '未完成的原始步骤', '步骤类型', '退回原冻结本金', '返还资产',
                '领域完成报告', '本领域报告中没有进行中的恢复。', '有记录的登记方拒绝', '交易截止时间已过',
                '待处理', '已阻塞', '完成', '受影响资金', '本金', '冻结资金', '退回原买方的本金净额',
                '买方已消耗 gas', '本金按原币种退回，已消耗 ETH 单独计费且不退还。未知结果须先查询原始操作再重试，不新增第二次买方付款。',
                '此页仅为只读领域观察，不代表原生资金、Oracle、钱包或链上验收。受保护前缀保持可见，不能在此手动标记步骤完成。',
                '交易段或边界位置', '领域报告内部一致', '未出资', '资金执行结果', '失败'),
    'zh-Hant': ('後綴復原詳情', '受保護的已登記前綴', '未完成交易段', '原始觸發原因', '返還邊界位置',
                '報告的資產返還', '未完成的原始步驟', '步驟類型', '退回原凍結本金', '返還資產',
                '領域完成報告', '本領域報告中沒有進行中的復原。', '有記錄的登記方拒絕', '交易截止時間已過',
                '待處理', '已阻塞', '完成', '受影響資金', '本金', '凍結資金', '退回原買方的本金淨額',
                '買方已消耗 gas', '本金按原幣種退回，已消耗 ETH 單獨計費且不退還。未知結果須先查詢原始操作再重試，不新增第二次買方付款。',
                '此頁僅為唯讀領域觀察，不代表原生資金、Oracle、錢包或鏈上驗收。受保護前綴保持可見，不能在此手動標記步驟完成。',
                '交易段或邊界位置', '領域報告內部一致', '未出資', '資金執行結果', '失敗'),
    'fr': ('Détail de reprise du suffixe', 'Préfixe enregistré protégé', 'Segments en attente',
           'Déclencheur d’origine', 'Position limite de retour', 'Retour d’actif déclaré',
           'Étapes d’origine en attente', 'Type d’étape', 'Rembourser le principal bloqué', 'Retourner l’actif',
           'Déclaration d’achèvement du domaine', 'Aucune reprise ouverte dans ce rapport du domaine.',
           'Refus consigné du registraire', 'Échéance de négociation dépassée', 'En attente', 'Bloqué', 'Terminé',
           'Fonds concernés', 'Principal', 'Séquestre', 'Principal net retourné à l’acheteur d’origine',
           'Gas consommé par l’acheteur',
           'Le principal revient dans sa devise d’origine. L’ETH consommé est facturé séparément et non remboursé. '
           'Tout résultat inconnu exige une recherche de l’opération d’origine avant reprise, sans second paiement de l’acheteur.',
           'Observation du domaine en lecture seule, pas une validation financière native, Oracle, Wallet ou sur chaîne. '
           'Le préfixe protégé reste visible ; aucune étape ne peut être déclarée terminée ici.',
           'Segment ou position limite', 'Rapport du domaine cohérent', 'Non financé', 'Résultat financier', 'Échec'),
    'es': ('Detalle de recuperación del sufijo', 'Prefijo registrado protegido', 'Tramos pendientes',
           'Motivo original', 'Posición límite de retorno', 'Retorno del activo informado',
           'Pasos originales pendientes', 'Tipo de paso', 'Reembolsar el principal bloqueado', 'Devolver el activo',
           'Informe de finalización del dominio', 'No hay recuperación abierta en este informe del dominio.',
           'Rechazo registrado del registrador', 'Plazo de negociación vencido', 'Pendiente', 'Bloqueado', 'Hecho',
           'Fondos afectados', 'Principal', 'Depósito', 'Principal neto devuelto al comprador original',
           'Gas consumido por el comprador',
           'El principal se devuelve en su moneda original. El ETH consumido se cobra por separado y no se reembolsa. '
           'Un resultado desconocido exige consultar la operación original antes de reintentar, sin un segundo pago del comprador.',
           'Observación del dominio de solo lectura, no aceptación financiera nativa, Oracle, Wallet ni en cadena. '
           'El prefijo protegido sigue visible; aquí no se puede marcar ningún paso como terminado.',
           'Tramo o posición límite', 'Informe del dominio coherente', 'Sin financiar', 'Resultado financiero', 'Fallido'),
    'ja': ('後続区間の復旧詳細', '保護された登記済みプレフィックス', '未完了区間', '元の開始理由', '返還境界位置',
           '報告された資産返還', '元の未完了手順', '手順の種類', '元の凍結元本を返金', '資産を返還',
           'ドメインの完了報告', 'このドメイン報告に進行中の復旧はありません。', '記録された登記機関の拒否', '取引期限経過',
           '待機中', '停止中', '完了', '対象資金', '元本', 'エスクロー', '元の買い手への元本返還純額',
           '買い手が消費した gas', '元本は元の通貨で返還されます。消費済み ETH は別途請求され、返金されません。'
           '結果不明の場合は再試行前に元の操作を照会し、買い手の二重払いを追加しません。',
           '読み取り専用のドメイン観測であり、原生資金、Oracle、Wallet、チェーン上の受入証明ではありません。'
           '保護されたプレフィックスは保持され、このページから手順を完了扱いにすることはできません。',
           '区間または境界位置', 'ドメイン報告の内部整合性', '未入金', '資金実行結果', '失敗'),
}
WORDS = {locale: dict(zip(KEYS, values)) for locale, values in TEXT.items()}

HOP_TEXT = {
    'en': ('Reverse-chain asset hops', 'Sequence', 'Confirmed hops', 'From position',
           'To position', 'Result reference recorded', 'Hop progress not recorded', 'Unknown'),
    'zh-Hans': ('沿原链反向逐跳回退', '回退序列', '已确认跳数', '起点位置',
                '目标位置', '已记录结果引用', '尚无逐跳进度记录', '未知'),
    'zh-Hant': ('沿原鏈反向逐跳回退', '回退序列', '已確認跳數', '起點位置',
                '目標位置', '已記錄結果引用', '尚無逐跳進度記錄', '未知'),
    'fr': ('Retours successifs sur le parcours inverse', 'Séquence', 'Étapes confirmées',
           'Position de départ', 'Position d’arrivée', 'Référence du résultat consignée',
           'Progression des étapes non consignée', 'Inconnu'),
    'es': ('Retornos sucesivos por la ruta inversa', 'Secuencia', 'Saltos confirmados',
           'Posición de origen', 'Posición de destino', 'Referencia del resultado registrada',
           'Progreso de los saltos no registrado', 'Desconocido'),
    'ja': ('元の経路を逆順にたどる返還', '返還シーケンス', '確認済みステップ数',
           '開始位置', '到達位置', '結果参照を記録済み', 'ステップの進捗記録なし', '不明'),
}


HISTORY = {
    'en': ('Archived suffix recoveries', 'No archived recovery reports.',
           'Archived report source unavailable. Current positions are not historical evidence.'),
    'zh-Hans': ('历史后缀恢复', '没有已归档的恢复报告。',
                '归档报告来源不可用，当前位置不作为历史证据。'),
    'zh-Hant': ('歷史後綴復原', '沒有已歸檔的復原報告。',
                '歸檔報告來源不可用，目前位置不作為歷史證據。'),
    'fr': ('Reprises du suffixe archivées', 'Aucun rapport de reprise archivé.',
           'Source des archives indisponible. Les positions actuelles ne prouvent pas les positions historiques.'),
    'es': ('Recuperaciones del sufijo archivadas', 'No hay informes de recuperación archivados.',
           'Fuente de archivos no disponible. Las posiciones actuales no prueban las históricas.'),
    'ja': ('過去の後続区間の復旧', '保存された復旧報告はありません。',
           '保存済み報告の参照元を利用できません。現在位置は過去の証拠として扱いません。'),
}


def render_rollback(exchange, receipt_id, *, locale='en', now=None):
    if locale not in WORDS:
        raise ValueError('supported rollback locale required')
    current = rollback_projection(exchange, receipt_id, now=now)
    history = rollback_history_projection(exchange, receipt_id, observed_at=current['observedAt'])
    title, empty, unavailable = HISTORY[locale]
    body = _render_report(current, locale)
    body += '<section data-rollback-history="1"><h2>' + escape(title) + '</h2>'
    if not history['available']:
        body += '<p>' + escape(unavailable) + '</p>'
    elif not history['reports']:
        body += '<p>' + escape(empty) + '</p>'
    else:
        for number, report in enumerate(history['reports'], 1):
            body += '<article data-history-sequence="' + str(number) + '">'
            body += _render_report(report, locale) + '</article>'
    return body + '</section>'


def _render_report(value, locale):
    w, a, t, q = WORDS[locale], AUTH[locale], TIMELINE[locale], QUEUE[locale]

    def number(value):
        return str(value) if value is not None else t['unknown']

    def yes(value):
        return a['yes'] if value is True else a['no']

    def status(value):
        local = {'pending': w['pending'], 'blocked': w['blocked'], 'done': w['done'],
                 'settled': w['done'], 'failed': w['failed'], 'refused': q['rejected'],
                 'not-funded': w['unfunded'], 'locked': t['locked'], 'released': t['released'],
                 'refunded': t['refunded'], 'not-modelled': t['notModelled']}
        return local.get(value, t['unknown'])

    def table(headers, rows):
        return ('<table><tr>' + ''.join('<th>' + escape(label) + '</th>' for label in headers)
                + '</tr>' + ''.join('<tr>' + ''.join('<td>' + escape(cell) + '</td>' for cell in row)
                                   + '</tr>' for row in rows) + '</table>')

    summary = [(w['prefix'], number(value['registeredPrefixLegs'])),
               (w['outstanding'], number(value['outstandingLegs'])),
               (t['owner'], number(value['ownerPosition'])), (t['holder'], number(value['holderPosition'])),
               (t['observed'], number(value['observedAt']))]
    body = '<p>' + escape(w['nativeBoundary']) + '</p><p>' + escape(w['policy']) + '</p>'
    body += table(('', ''), summary)
    if not value['open']:
        body += '<p>' + escape(w['noRecovery']) + '</p>'
    else:
        trigger = {'registrar-refusal': w['refusal'], 'deadline': w['deadline']}.get(value['trigger'], t['unknown'])
        completion = (yes(value['domainReportedComplete']) if value['domainReportConsistent'] else t['unknown'])
        body += table(('', ''), [(w['trigger'], trigger),
            (w['boundary'], number(value['returnBoundaryPosition'])), (w['returned'], yes(value['assetReturned'])),
            (w['completion'], completion), (w['consistency'], yes(value['domainReportConsistent']))])
        h = HOP_TEXT[locale]
        progress = value['hopProgress']
        body += '<section data-hop-progress="1"><h3>' + escape(h[0]) + '</h3>'
        if not progress['available']:
            body += '<p>' + escape(h[6]) + '</p>'
        else:
            body += table(('', ''), [(h[1], progress['sequence']),
                (h[2], str(progress['cursor']) + ' / ' + str(progress['count']))])
            rows = [(str(hop['fromPosition']), str(hop['toPosition']),
                     h[7] if hop['status'] == 'unknown' else status(hop['status']),
                     yes(hop['hasResultReference'])) for hop in progress['hops']]
            body += table((h[3], h[4], q['state'], h[5]), rows)
        body += '</section>'
        steps = []
        for step in value['outstandingSteps']:
            kind = {'refund': w['refundStep'], 'asset-return': w['returnStep']}.get(step['kind'], t['unknown'])
            scope = (w['boundary'] if step['kind'] == 'asset-return' else t['leg']) + ' ' + number(step['legIndex'])
            steps.append((kind, scope, status(step['status'])))
        body += '<h3>' + escape(w['steps']) + '</h3>' + table((w['kind'], w['scope'], q['state']), steps)
        funds = []
        for row in value['funds']:
            asset = row['principalAsset']
            principal = (row['principal'] + ' ' + asset + ' (' + t['units'] + ')'
                         if row['principal'] is not None and asset is not None and row['principalUnit'] == 'base-units' else t['unknown'])
            net = (row['netToOriginalBuyer'] + ' ' + asset + ' (' + t['units'] + ')'
                   if row['netToOriginalBuyer'] is not None and asset is not None and row['principalUnit'] == 'base-units' else t['unknown'])
            gas = (row['gasTotal'] + ' ETH wei' if row['gasTotal'] is not None
                   and row['gasAsset'] == 'ETH' and row['gasUnit'] == 'wei' else t['unknown'])
            funds.append((number(row['legIndex']), principal, status(row['escrowStatus']),
                          status(row['paymentStatus']), net, gas))
        body += '<h3>' + escape(w['financial']) + '</h3>' + table(
            (t['leg'], w['principal'], w['escrow'], w['payment'], w['buyerNet'], w['gas']), funds)
    return '<section lang="' + locale + '"><h2>' + escape(w['heading']) + '</h2>' + body + '</section>'
