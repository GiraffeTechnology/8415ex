"""Six-locale timeline from original predecessor projection; no state writes."""
from html import escape

from .timeline_projection import timeline_projection
from .queue_status_page import WORDS as QUEUE_WORDS


KEYS = ('heading', 'leg', 'source', 'destination', 'price', 'registration', 'funding',
        'recovery', 'path', 'active', 'withdrawn', 'unknown', 'none', 'empty', 'units',
        'observed', 'basis', 'boundary', 'locked', 'released', 'refunded', 'failed',
        'outcomeUnknown', 'notModelled', 'available', 'detached', 'returned', 'inProgress',
        'owner', 'holder')
TEXT = {
    'en': ('Continuous trade timeline', 'Global leg', 'From position', 'To position', 'Price',
           'Registration', 'Funding', 'Recovery', 'Path', 'Active path', 'Withdrawn history',
           'Unknown', 'None', 'No recorded trade legs', 'smallest currency units', 'Observed at',
           'Positions follow original predecessor records, including branches after recovery.',
           'Domain observation only. Positions are not wallet addresses, registration versions or '
           'protocol finality. Historical legs remain visible; this page neither executes nor proves chain acceptance.',
           'Locked', 'Released', 'Refunded', 'Release failed; funds still held',
           'Release outcome unknown; enquire original operation', 'Not modelled',
           'Available', 'Detached', 'Returned', 'In progress', 'Owner position', 'Holder position'),
    'zh-Hans': ('连续交易时间线', '全局交易段', '起点位置', '终点位置', '价格', '登记', '资金',
                '恢复', '路径', '当前路径', '已撤回历史', '未知', '无', '尚无交易段记录', '币种最小单位',
                '观察时点', '位置来自原始前驱记录，包括恢复交易后的分支。',
                '此页仅为领域观察。位置不是钱包地址、登记版本或协议 finality。历史交易段保持可见；'
                '页面不执行交易，也不证明链上验收。', '已冻结', '已释放', '已退款', '释放失败，资金仍被持有',
                '释放结果未知，请查询原始操作', '未建模', '可用', '已解除关联', '已返还', '进行中',
                'owner 位置', 'holder 位置'),
    'zh-Hant': ('連續交易時間線', '全域交易段', '起點位置', '終點位置', '價格', '登記', '資金',
                '復原', '路徑', '目前路徑', '已撤回歷史', '未知', '無', '尚無交易段記錄', '幣種最小單位',
                '觀察時點', '位置來自原始前驅記錄，包括恢復交易後的分支。',
                '此頁僅為領域觀察。位置不是錢包地址、登記版本或協定 finality。歷史交易段保持可見；'
                '頁面不執行交易，也不證明鏈上驗收。', '已凍結', '已釋放', '已退款', '釋放失敗，資金仍被持有',
                '釋放結果未知，請查詢原始操作', '未建模', '可用', '已解除關聯', '已返還', '進行中',
                'owner 位置', 'holder 位置'),
    'fr': ('Chronologie des échanges', 'Segment global', 'Position de départ', 'Position d’arrivée',
           'Prix', 'Enregistrement', 'Fonds', 'Reprise', 'Parcours', 'Parcours actif',
           'Historique retiré', 'Inconnu', 'Aucun', 'Aucun segment consigné', 'unités monétaires minimales',
           'Instant observé', 'Les positions suivent les prédécesseurs d’origine, y compris les branches après reprise.',
           'Observation du domaine uniquement. Les positions ne sont ni adresses, ni versions '
           'd’enregistrement, ni finalité du protocole. L’historique reste visible ; cette page '
           'n’exécute rien et ne prouve aucune validation sur chaîne.',
           'Bloqués', 'Libérés', 'Remboursés', 'Libération échouée ; fonds toujours retenus',
           'Résultat de libération inconnu ; rechercher l’opération d’origine', 'Non modélisé',
           'Disponible', 'Détaché', 'Retourné', 'En cours', 'Position owner', 'Position holder'),
    'es': ('Cronología de operaciones', 'Tramo global', 'Posición de origen', 'Posición de destino',
           'Precio', 'Registro', 'Fondos', 'Recuperación', 'Ruta', 'Ruta activa', 'Historial retirado',
           'Desconocido', 'Ninguno', 'No hay tramos registrados', 'unidades monetarias mínimas',
           'Instante observado', 'Las posiciones siguen los predecesores originales, incluidas las ramas posteriores a la recuperación.',
           'Solo observación del dominio. Las posiciones no son direcciones, versiones de registro '
           'ni finalidad del protocolo. Se conserva el historial; esta página no ejecuta ni '
           'demuestra aceptación en cadena.', 'Bloqueados', 'Liberados', 'Reembolsados',
           'Liberación fallida; los fondos siguen retenidos', 'Resultado de liberación desconocido; consulte la operación original',
           'Sin modelar', 'Disponible', 'Desvinculado', 'Devuelto', 'En curso', 'Posición owner', 'Posición holder'),
    'ja': ('連続取引のタイムライン', '全体取引区間', '起点位置', '終点位置', '価格', '登記', '資金',
           '復旧', '経路', '現在の経路', '撤回済み履歴', '不明', 'なし', '取引区間の記録はありません',
           '通貨の最小単位', '観測時点', '位置は元の前駆記録に基づき、復旧後の分岐も含みます。',
           'ドメイン観測のみです。位置はウォレットアドレス、登記バージョン、プロトコルの finality '
           'ではありません。過去の取引区間は保持され、このページは実行やチェーン上の受入証明を行いません。',
           '凍結済み', '解放済み', '返金済み', '解放失敗・資金は保留中', '解放結果不明・元の操作を照会してください',
           'モデル化なし', '利用可能', '関連付け解除済み', '返還済み', '進行中', 'owner の位置', 'holder の位置'),
}
WORDS = {locale: dict(zip(KEYS, values)) for locale, values in TEXT.items()}
REGISTRATION = {'not-submitted': 'unfiled', 'pending': 'pending', 'confirmed': 'confirmed',
                'rejected': 'rejected'}
FUNDING = {'not-modelled': 'notModelled', 'locked': 'locked', 'released': 'released',
           'refunded': 'refunded', 'release-failed': 'failed', 'release-outcome-unknown': 'outcomeUnknown'}
RECOVERY = {'none': 'none', 'available': 'available', 'detached': 'detached',
            'returned': 'returned', 'in-progress': 'inProgress'}
SIMULATION = {'en': 'Registration in this domain report is simulated.',
              'zh-Hans': '本领域报告中的登记为模拟结果。',
              'zh-Hant': '本領域報告中的登記為模擬結果。',
              'fr': 'L’enregistrement dans ce rapport du domaine est simulé.',
              'es': 'El registro de este informe del dominio es simulado.',
              'ja': 'このドメイン報告の登記結果はシミュレーションです。'}


def render_timeline(exchange, receipt_id, *, locale='en', now=None):
    if locale not in WORDS:
        raise ValueError('supported timeline locale required')
    w, q = WORDS[locale], QUEUE_WORDS[locale]
    value = timeline_projection(exchange, receipt_id, now=now)
    registration_evidence = SIMULATION[locale] if value['simulatedRegistration'] else w['unknown']

    def number(number):
        return str(number) if number is not None else w['unknown']

    rows = []
    for leg in value['legs']:
        registration = q[REGISTRATION[leg['registrationStatus']]] if leg['registrationStatus'] in REGISTRATION else w['unknown']
        funding = w[FUNDING[leg['fundingStatus']]] if leg['fundingStatus'] in FUNDING else w['unknown']
        recovery = w[RECOVERY[leg['rollbackStatus']]] if leg['rollbackStatus'] in RECOVERY else w['unknown']
        price = (leg['price'] + ' ' + leg['currency'] + ' (' + w['units'] + ')'
                 if leg['price'] is not None and leg['currency'] is not None else w['unknown'])
        cells = (str(leg['legIndex']), number(leg['fromPosition']), number(leg['toPosition']),
                 price, registration, funding, recovery, w['active'] if leg['active'] else w['withdrawn'])
        rows.append('<tr>' + ''.join('<td>' + escape(cell) + '</td>' for cell in cells) + '</tr>')
    if not rows:
        rows.append('<tr><td colspan="8">' + escape(w['empty']) + '</td></tr>')
    header = '<tr>' + ''.join('<th>' + escape(w[key]) + '</th>' for key in
                              ('leg', 'source', 'destination', 'price', 'registration', 'funding', 'recovery', 'path')) + '</tr>'
    summary = '<dl>' + ''.join('<dt>' + escape(w[key]) + '</dt><dd>' + escape(number(value[field])) + '</dd>'
                               for key, field in (('owner', 'ownerPosition'), ('holder', 'holderPosition'),
                                                  ('observed', 'observedAt'))) + '</dl>'
    return ('<section lang="' + locale + '"><h2>' + escape(w['heading']) + '</h2><p>'
            + escape(w['boundary']) + '</p><p>' + escape(w['basis']) + '</p><p>'
            + escape(w['registration']) + ': ' + escape(registration_evidence) + '</p>' + summary
            + '<table>' + header + ''.join(rows) + '</table></section>')
