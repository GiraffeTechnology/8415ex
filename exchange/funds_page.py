"""Identity-excluding principal and consumed-gas observations for the queue."""
from html import escape

from .public_workbench import amount, currency, integer


KEYS = ('heading', 'leg', 'principal', 'escrow', 'payment', 'sellerNet', 'buyerNet',
        'gas', 'units', 'unknown', 'empty', 'unavailable', 'boundary', 'locked',
        'released', 'refunded', 'unfunded', 'settled', 'failed', 'releaseFailed',
        'releaseUnknown', 'notModelled')
TEXT = {
    'en': ('Segment funds', 'Global leg', 'Original principal', 'Escrow state',
           'Payment outcome', 'Principal reported to seller', 'Principal reported to original buyer',
           'Consumed gas', 'base units', 'Unknown', 'No recorded segment funds.',
           'Original segment-funds observation unavailable.',
           'Principal remains in its original selected currency; consumed ETH gas is separate. '
           'No conversion or principal-minus-gas total is calculated. These are domain reports, '
           'not proof of native funds movement. Shared-operation allocation remains undecided; '
           'unknown outcomes require original-operation enquiry before retry.',
           'Locked', 'Released', 'Refunded', 'Not funded', 'Settled', 'Failed',
           'Release failed; funds still held', 'Release outcome unknown', 'Not modelled'),
    'zh-Hans': ('分段资金', '全局交易段', '原始本金', '冻结资金状态', '资金执行结果',
                '报告给卖方的本金', '报告退回原买方的本金', '已消耗 gas', '最小单位', '未知',
                '尚无分段资金记录。', '原始分段资金观察不可用。',
                '本金保持原选定币种，已消耗 ETH gas 单列。不兑换，也不计算本金减 gas 的合计。'
                '此为领域报告，不证明原生资金移动。共享操作分摊仍未确定；未知结果须先查询原始操作再重试。',
                '已冻结', '已释放', '已退款', '未出资', '已结算', '失败',
                '释放失败，资金仍被持有', '释放结果未知', '未建模'),
    'zh-Hant': ('分段資金', '全域交易段', '原始本金', '凍結資金狀態', '資金執行結果',
                '報告給賣方的本金', '報告退回原買方的本金', '已消耗 gas', '最小單位', '未知',
                '尚無分段資金記錄。', '原始分段資金觀測無法使用。',
                '本金保持原選定幣種，已消耗 ETH gas 單列。不兌換，也不計算本金減 gas 的合計。'
                '此為領域報告，不證明原生資金移動。共享操作分攤仍未確定；未知結果須先查詢原始操作再重試。',
                '已凍結', '已釋放', '已退款', '未出資', '已結算', '失敗',
                '釋放失敗，資金仍被持有', '釋放結果未知', '未建模'),
    'fr': ('Fonds par segment', 'Segment global', 'Principal d’origine', 'État du séquestre',
           'Résultat financier', 'Principal déclaré au vendeur', 'Principal déclaré à l’acheteur d’origine',
           'Gas consommé', 'unités minimales', 'Inconnu', 'Aucun fonds de segment consigné.',
           'Observation des fonds d’origine indisponible.',
           'Le principal conserve sa devise sélectionnée ; le gas ETH consommé reste distinct. '
           'Aucune conversion ni soustraction principal-gas. Ces rapports du domaine ne prouvent '
           'pas un mouvement de fonds natif. La répartition des opérations partagées reste indécise ; '
           'rechercher l’opération d’origine avant toute reprise de résultat inconnu.',
           'Bloqués', 'Libérés', 'Remboursés', 'Non financé', 'Réglé', 'Échec',
           'Libération échouée ; fonds retenus', 'Résultat de libération inconnu', 'Non modélisé'),
    'es': ('Fondos por tramo', 'Tramo global', 'Principal original', 'Estado del depósito',
           'Resultado financiero', 'Principal informado al vendedor', 'Principal informado al comprador original',
           'Gas consumido', 'unidades mínimas', 'Desconocido', 'No hay fondos de tramo registrados.',
           'Observación de fondos originales no disponible.',
           'El principal conserva su moneda seleccionada; el gas ETH consumido se muestra aparte. '
           'No se convierte ni se resta gas del principal. Estos informes del dominio no prueban '
           'movimientos nativos de fondos. El reparto de operaciones compartidas sigue pendiente; '
           'consulte la operación original antes de reintentar un resultado desconocido.',
           'Bloqueados', 'Liberados', 'Reembolsados', 'Sin financiar', 'Liquidado', 'Fallido',
           'Liberación fallida; fondos retenidos', 'Resultado de liberación desconocido', 'Sin modelar'),
    'ja': ('区間ごとの資金', '全体取引区間', '元の元本', 'エスクロー状態', '資金実行結果',
           '売り手への元本報告', '元の買い手への元本報告', '消費済み gas', '最小単位', '不明',
           '区間資金の記録はありません。', '元の区間資金を観測できません。',
           '元本は選択した元の通貨を維持し、消費済み ETH gas は別に表示します。'
           '交換や元本から gas を差し引いた合計は計算しません。ドメイン報告は原生資金移動の証明ではありません。'
           '共有操作の配分は未確定です。不明な結果は再試行前に元の操作を照会してください。',
           '凍結済み', '解放済み', '返金済み', '未入金', '決済済み', '失敗',
           '解放失敗・資金は保留中', '解放結果不明', 'モデル化なし'),
}
WORDS = {locale: dict(zip(KEYS, values)) for locale, values in TEXT.items()}
STATUS = {'locked': 'locked', 'released': 'released', 'refunded': 'refunded',
          'not-funded': 'unfunded', 'settled': 'settled', 'failed': 'failed',
          'release-failed': 'releaseFailed', 'release-outcome-unknown': 'releaseUnknown',
          'not-modelled': 'notModelled'}


def render_segment_funds(exchange, receipt_id, observed_at, expected_legs, *, locale='en'):
    """Reuse queue time and exact global leg identities; never publish positions.

    Only the original reconciliation reader is called. A missing or inconsistent
    report leaves this component unavailable without changing the queue or funds.
    No reported amount is converted, aggregated or inferred from a status.
    """
    if locale not in WORDS:
        raise ValueError('supported funds locale required')
    w = WORDS[locale]
    start = '<section lang="' + locale + '" data-segment-funds="1"><h2>' + escape(w['heading']) + '</h2>'
    boundary = '<p>' + escape(w['boundary']) + '</p>'
    try:
        if (integer(observed_at) is None or type(expected_legs) not in (tuple, list)
                or any(integer(index) is None for index in expected_legs)
                or len(set(expected_legs)) != len(expected_legs)):
            raise ValueError('original queue identity required')
        report = exchange.reconciliation(receipt_id, now=observed_at)
        if (type(report) is not dict or report.get('receiptId') != receipt_id
                or type(report.get('observedAt')) is not int or report['observedAt'] != observed_at
                or type(report.get('segments')) not in (tuple, list)):
            raise ValueError('original funds receipt/time binding required')
        segments = report['segments']
        if (any(type(row) is not dict or integer(row.get('legIndex')) is None for row in segments)
                or [row['legIndex'] for row in segments] != list(expected_legs)):
            raise ValueError('complete original ordered leg observations required')
        rows = []
        for row in segments:
            asset = currency(row.get('principalAsset'))
            def principal(key):
                value = amount(row.get(key))
                return (value + ' ' + asset + ' (' + w['units'] + ')'
                        if value is not None and asset is not None
                        and row.get('principalUnit') == 'base-units' else w['unknown'])
            gas = amount(row.get('gasTotal'))
            gas_text = (gas + ' ETH wei' if gas is not None and row.get('gasAsset') == 'ETH'
                        and row.get('gasUnit') == 'wei' else w['unknown'])
            def status(key):
                value = row.get(key)
                return w[STATUS.get(value, 'unknown')] if type(value) is str else w['unknown']
            cells = (str(row['legIndex']), principal('principal'), status('escrowStatus'),
                     status('paymentStatus'), principal('netToPayee'), principal('netToPayer'), gas_text)
            rows.append('<tr>' + ''.join('<td>' + escape(value) + '</td>' for value in cells) + '</tr>')
    except Exception:
        return start + '<p class="missing">' + escape(w['unavailable']) + '</p>' + boundary + '</section>'
    headers = ''.join('<th scope="col">' + escape(w[key]) + '</th>'
                      for key in ('leg', 'principal', 'escrow', 'payment', 'sellerNet', 'buyerNet', 'gas'))
    if not rows:
        rows = ['<tr><td colspan="7">' + escape(w['empty']) + '</td></tr>']
    return (start + boundary + '<div style="overflow-x:auto"><table><thead><tr>' + headers
            + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div></section>')
