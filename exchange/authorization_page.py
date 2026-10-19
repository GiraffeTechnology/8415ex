"""Read-only authorization display: original state, no wallet identities or grants."""
from html import escape
from .public_workbench import currency as public_currency, integer as public_integer


KEYS = ('heading', 'scope', 'applies', 'actions', 'counterparty', 'restricted',
        'unrestricted', 'amount', 'currency', 'chain', 'token', 'start', 'end',
        'revoked', 'yes', 'no', 'unknown', 'sell', 'buy', 'otherAction', 'reason',
        'observed', 'none', 'boundary', 'expired', 'future', 'sessionLost', 'sessionChanged')
TEXT = {
    'en': ('Authorization and trade', 'Scope', 'Original session/time state applies', 'Allowed actions',
           'Counterparty scope', 'Restricted by original grant', 'Unrestricted by this grant',
           'Maximum amount in smallest currency units', 'Currency', 'Chain ID', 'Token ID',
           'Valid from (Unix seconds)', 'Expires at (Unix seconds)', 'Revoked', 'Yes', 'No',
           'Unknown', 'Sell', 'Buy', 'Unrecognized action', 'Original status reason',
           'Observed at (Unix seconds)', 'No authorization references supplied',
           'Connecting a wallet grants nothing. This read-only domain report does not establish '
           'signature verification, installed Wallet enforcement, chain execution or acceptance. '
           'Execution must still follow the original authenticated and authorized path.',
           'Expired', 'Not yet valid', 'Original session absent', 'Original session changed'),
    'zh-Hans': ('授权与交易', '范围', '原会话与时间状态是否适用', '允许操作', '对手范围', '原授权有限制',
                '此授权未限制对手', '最小币种单位的金额上限', '币种', '链 ID', 'Token ID',
                '生效时间（Unix 秒）', '到期时间（Unix 秒）', '已撤销', '是', '否', '未知',
                '卖出', '买入', '未识别操作', '原始状态原因', '观察时间（Unix 秒）', '未提供授权引用',
                '连接钱包不产生授权。此页仅为只读领域报告，不能证明签名核验、已安装钱包的执行约束、'
                '链上执行或验收；执行仍须经过原有认证与授权路径。',
                '已过期', '尚未生效', '原会话不存在', '原会话已改变'),
    'zh-Hant': ('授權與交易', '範圍', '原工作階段與時間狀態是否適用', '允許操作', '對手範圍', '原授權有限制',
                '此授權未限制對手', '最小幣種單位的金額上限', '幣種', '鏈 ID', 'Token ID',
                '生效時間（Unix 秒）', '到期時間（Unix 秒）', '已撤銷', '是', '否', '未知',
                '賣出', '買入', '未識別操作', '原始狀態原因', '觀察時間（Unix 秒）', '未提供授權引用',
                '連線錢包不產生授權。此頁僅為唯讀領域報告，不能證明簽章核驗、已安裝錢包的執行約束、'
                '鏈上執行或驗收；執行仍須經過原有認證與授權路徑。',
                '已過期', '尚未生效', '原工作階段不存在', '原工作階段已改變'),
    'fr': ('Autorisation et échange', 'Périmètre', 'État de session et de temps applicable', 'Actions permises',
           'Contreparties', 'Limitées par l’autorisation d’origine', 'Non limitées par cette autorisation',
           'Montant maximal en unités monétaires minimales', 'Devise', 'ID de chaîne', 'ID de jeton',
           'Valide dès (secondes Unix)', 'Expiration (secondes Unix)', 'Révoquée', 'Oui', 'Non',
           'Inconnu', 'Vendre', 'Acheter', 'Action non reconnue', 'Motif de l’état d’origine',
           'Instant observé (secondes Unix)', 'Aucune référence d’autorisation fournie',
           'Connecter un portefeuille n’accorde rien. Ce rapport du domaine en lecture seule '
           'ne prouve ni vérification de signature, ni contrôle du Wallet installé, ni exécution '
           'sur chaîne, ni validation. L’exécution reste soumise au parcours authentifié et autorisé d’origine.',
           'Expirée', 'Pas encore valide', 'Session d’origine absente', 'Session d’origine modifiée'),
    'es': ('Autorización y operación', 'Ámbito', 'Estado de sesión y tiempo aplicable', 'Acciones permitidas',
           'Contrapartes', 'Restringidas por la autorización original', 'Sin restricción en esta autorización',
           'Importe máximo en unidades monetarias mínimas', 'Moneda', 'ID de cadena', 'ID de token',
           'Válida desde (segundos Unix)', 'Caducidad (segundos Unix)', 'Revocada', 'Sí', 'No',
           'Desconocido', 'Vender', 'Comprar', 'Acción no reconocida', 'Motivo del estado original',
           'Instante observado (segundos Unix)', 'No se proporcionaron referencias de autorización',
           'Conectar una cartera no concede autorización. Este informe del dominio de solo lectura '
           'no demuestra verificación de firmas, controles del Wallet instalado, ejecución en cadena '
           'ni aceptación. La ejecución debe seguir la ruta original autenticada y autorizada.',
           'Caducada', 'Aún no válida', 'Sesión original ausente', 'Sesión original modificada'),
    'ja': ('承認と取引', '範囲', '元のセッション・時刻状態の適用', '許可された操作', '取引相手の範囲',
           '元の承認による制限あり', 'この承認による相手の制限なし', '通貨の最小単位での上限額',
           '通貨', 'チェーン ID', 'トークン ID', '有効開始（Unix 秒）', '有効期限（Unix 秒）',
           '取消済み', 'はい', 'いいえ', '不明', '売却', '購入', '未認識の操作', '元の状態の理由',
           '観測時点（Unix 秒）', '承認参照は未提供です',
           'ウォレットへの接続は承認を意味しません。この読み取り専用ドメイン報告は、署名検証、'
           'インストール済み Wallet の実行制御、チェーン上の実行、受入完了の証明ではありません。'
           '実行には元の認証および承認経路が必要です。',
           '期限切れ', '有効開始前', '元のセッションなし', '元のセッション変更済み'),
}
WORDS = {locale: dict(zip(KEYS, values)) for locale, values in TEXT.items()}
REASONS = {'EX_AUTH_REVOKED': 'revoked', 'EX_AUTH_NOT_YET_VALID': 'future',
           'EX_AUTH_EXPIRED': 'expired', 'EX_AUTH_SESSION_LOST': 'sessionLost',
           'EX_AUTH_SESSION_REFUSED': 'sessionChanged'}


def render_authorizations(exchange, receipt_id, authorization_ids, *, locale='en', now=None):
    """Read existing grants without exposing reference IDs, account or session values."""
    if locale not in WORDS or type(authorization_ids) not in (tuple, list):
        raise ValueError('supported authorization locale and original references required')
    w = WORDS[locale]
    view = exchange.receipt_view(receipt_id, now)
    observed = view.get('observedAt')
    if view.get('receiptId') != receipt_id or type(observed) is not int or observed < 0:
        raise ValueError('original observation time required')
    receipt = exchange.receipt(receipt_id)
    if receipt.receipt_id != receipt_id:
        raise ValueError('original immutable receipt required')

    def number(value):
        return str(value) if public_integer(value) is not None else w['unknown']

    def yes_no(value):
        return w['yes'] if value is True else w['no'] if value is False else w['unknown']

    def row(key, value):
        return '<tr><th>' + escape(w[key]) + '</th><td>' + escape(value) + '</td></tr>'

    blocks = []
    for ordinal, authorization_id in enumerate(authorization_ids, 1):
        state = exchange.authorization_state(authorization_id, observed)
        grant = exchange.authorization(authorization_id)
        if (type(state) is not dict or state.get('authorizationId') != authorization_id
                or type(state.get('observedAt')) is not int
                or state.get('observedAt') != observed
                or grant.authorization_id != authorization_id
                or state.get('account') != grant.account
                or grant.asset.key != receipt.asset.key
                or grant.chain_id != receipt.asset.chain_id):
            raise ValueError('original receipt, grant and observation binding required')
        # Stable action meanings only: arbitrary action text could contain a
        # party label. Unknown values are never echoed into this public view.
        actions = ', '.join(w[action] if action in ('buy', 'sell') else w['otherAction']
                            for action in grant.allowed_actions)
        currency = public_currency(grant.quote_asset) or w['unknown']
        reasons = state.get('reasons', ())
        if type(reasons) not in (tuple, list):
            reasons = (None,)
        reason = ', '.join(w[REASONS[code]] if type(code) is str and code in REASONS
                           else w['unknown'] for code in reasons)
        rows = [row('scope', str(ordinal)), row('applies', yes_no(state.get('applies'))),
                row('actions', actions), row('counterparty', w['restricted']
                    if grant.counterparties else w['unrestricted']),
                row('amount', number(grant.max_amount)), row('currency', currency),
                row('chain', number(grant.chain_id)), row('token', number(grant.asset.token_id)),
                row('start', number(grant.not_before)), row('end', number(grant.expires_at)),
                row('revoked', yes_no(grant.revoked)), row('observed', str(observed))]
        if reasons:
            rows.append(row('reason', reason))
        blocks.append('<table>' + ''.join(rows) + '</table>')
    if not blocks:
        blocks.append('<p>' + escape(w['none']) + '</p>')
    return ('<section lang="' + locale + '"><h2>' + escape(w['heading']) + '</h2><p>'
            + escape(w['boundary']) + '</p>' + ''.join(blocks) + '</section>')
