"""Localized, identity-excluding observation page; no acceptance attestation."""
from html import escape
import re


_KEYS = ('heading', 'language', 'receipt', 'market', 'scenario', 'run', 'commit',
         'tree', 'chain', 'transactions', 'registration', 'owner', 'holder',
         'prefix', 'observed', 'gateway', 'missing', 'local', 'simulated',
         'configured', 'unconfigured', 'boundary')
_TEXT = {
    'en': ('Observation and evidence', 'Language', 'Receipt', 'Market', 'Scenario',
           'Run reference', 'Source commit', 'Source tree', 'Test chain ID',
           'Transaction hashes', 'Registration evidence', 'Owner position',
           'Holder position', 'Registered prefix', 'Observed at', 'Original checked gateway',
           'Not supplied', 'Native domain observation', 'Simulated adapter results only',
           'Configured; execution not verified', 'Not configured',
           'These are current domain observations. A transaction hash or configured gateway '
           'does not prove chain confirmation, deployment, durable recovery or acceptance. '
           'Original journals and independently verified evidence remain required.'),
    'zh-Hans': ('观察与证据', '语言', '提单', '市场', '场景', '运行引用', '源码提交',
                '源码树', '测试链 ID', '交易哈希', '登记证据', 'owner 位置', 'holder 位置',
                '已登记前缀', '观察时点', '原有受控网关', '未提供', '原生领域观察',
                '仅模拟适配器结果', '已配置；执行尚未核验', '未配置',
                '此页仅展示当前领域观察。交易哈希或已配置网关不能证明链上确认、部署、'
                '持久化恢复或验收通过，仍须核对原始日志和独立核验的证据。'),
    'zh-Hant': ('觀察與證據', '語言', '提單', '市場', '場景', '執行引用', '原始碼提交',
                '原始碼樹', '測試鏈 ID', '交易雜湊', '登記證據', 'owner 位置', 'holder 位置',
                '已登記前綴', '觀察時點', '原有受控閘道', '未提供', '原生領域觀察',
                '僅模擬介面結果', '已設定；執行尚未核驗', '未設定',
                '此頁僅顯示目前領域觀察。交易雜湊或已設定閘道不能證明鏈上確認、部署、'
                '持久化復原或驗收通過，仍須核對原始日誌和獨立核驗的證據。'),
    'fr': ('Observation et preuves', 'Langue', 'Titre', 'Marché', 'Scénario',
           'Référence d’exécution', 'Commit source', 'Arbre source', 'ID de chaîne de test',
           'Empreintes des transactions', 'Preuve d’enregistrement', 'Position owner',
           'Position holder', 'Préfixe enregistré', 'Instant observé', 'Passerelle contrôlée d’origine',
           'Non fourni', 'Observation du domaine natif', 'Résultats d’adaptateurs simulés uniquement',
           'Configurée ; exécution non vérifiée', 'Non configurée',
           'Cette page présente les observations actuelles du domaine. Une empreinte de '
           'transaction ou une passerelle configurée ne prouve ni confirmation sur chaîne, '
           'ni déploiement, ni reprise persistante, ni validation. Les journaux d’origine '
           'et des preuves vérifiées indépendamment restent nécessaires.'),
    'es': ('Observación y pruebas', 'Idioma', 'Título', 'Mercado', 'Escenario',
           'Referencia de ejecución', 'Commit de origen', 'Árbol de origen', 'ID de cadena de prueba',
           'Hashes de transacciones', 'Prueba de registro', 'Posición owner',
           'Posición holder', 'Prefijo registrado', 'Instante observado', 'Pasarela controlada original',
           'No proporcionado', 'Observación del dominio nativo', 'Solo resultados de adaptadores simulados',
           'Configurada; ejecución sin verificar', 'Sin configurar',
           'Esta página muestra observaciones actuales del dominio. Un hash de transacción '
           'o una pasarela configurada no prueba confirmación en cadena, despliegue, '
           'recuperación persistente ni aceptación. Siguen siendo necesarios los registros '
           'originales y las pruebas verificadas de forma independiente.'),
    'ja': ('観測と証拠', '言語', '船荷証券', '市場', 'シナリオ', '実行参照', 'ソースコミット',
           'ソースツリー', 'テストチェーン ID', '取引ハッシュ', '登記証拠', 'owner の位置',
           'holder の位置', '登記済みプレフィックス', '観測時点', '元の検証付きゲートウェイ',
           '未提供', 'ネイティブドメインの観測', 'シミュレーション用アダプターの結果のみ',
           '設定済み・実行未検証', '未設定',
           'このページは現在のドメイン観測を表示します。取引ハッシュや設定済みゲートウェイだけでは、'
           'チェーン上の確認、配備、永続化復旧、受入完了を証明できません。元のジャーナルと独立して'
           '検証された証拠が必要です。'),
}
WORDS = {locale: dict(zip(_KEYS, values)) for locale, values in _TEXT.items()}
LANGUAGES = (('en', 'English'), ('zh-Hans', '简体中文'), ('zh-Hant', '繁體中文'),
             ('fr', 'Français'), ('es', 'Español'), ('ja', '日本語'))


def render_evidence(exchange, receipt_id, run, *, locale='en', gateway_configured=False):
    """Read the original model once; display only typed public evidence fields."""
    if locale not in WORDS or type(run) is not dict or type(gateway_configured) is not bool:
        raise ValueError('supported evidence locale and original binding required')
    w = WORDS[locale]
    view = exchange.receipt_view(receipt_id)

    def identity(key, pattern, fallback=None):
        value = run.get(key)
        return value if type(value) is str and re.fullmatch(pattern, value) else fallback or w['missing']

    def number(value):
        return str(value) if type(value) is int and value >= 0 else w['missing']

    hashes = run.get('transactionHashes', ())
    hashes = [hashes] if type(hashes) is str else hashes
    hashes = (hashes if type(hashes) in (list, tuple) and len(hashes) <= 64 else ())
    hashes = [value for value in hashes if type(value) is str
              and re.fullmatch(r'0x[0-9a-fA-F]{64}', value)]
    rows = [
        ('scenario', identity('scenario', r'DEMO-0[1-6]', w['local'])),
        ('run', identity('runId', r'demo-[0-9a-f]{32}')),
        ('commit', identity('commit', r'[0-9a-f]{40}')),
        ('tree', identity('tree', r'[0-9a-f]{40}')),
        ('chain', number(view.get('asset', {}).get('chainId'))),
        ('transactions', ', '.join(hashes) or w['missing']),
        ('registration', w['simulated']),
        ('owner', number(view.get('owner', {}).get('position'))),
        ('holder', number(view.get('holder', {}).get('position'))),
        ('prefix', number(view.get('registeredPrefixLegs'))),
        ('observed', number(view.get('observedAt'))),
        ('gateway', w['configured'] if gateway_configured else w['unconfigured']),
    ]
    table = '<table>' + ''.join('<tr><th>' + escape(w[key]) + '</th><td>'
                               + escape(value) + '</td></tr>' for key, value in rows) + '</table>'
    suffix = '' if locale == 'en' else '?lang=' + locale
    nav = ('<nav><a href="/receipt' + suffix + '">' + escape(w['receipt'])
           + '</a> <a href="/market' + suffix + '">' + escape(w['market']) + '</a></nav>')
    languages = '<nav aria-label="' + escape(w['language']) + '">' + ' '.join(
        '<a lang="' + key + '" href="/evidence?lang=' + key + '">' + label + '</a>'
        for key, label in LANGUAGES) + '</nav>'
    return ('<!doctype html><html lang="' + locale + '"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>8415ex - ' + escape(w['heading']) + '</title></head><body><main>'
            + nav + languages + '<h2>' + escape(w['heading']) + '</h2><p role="note">'
            + escape(w['boundary']) + '</p>' + table + '</main></body></html>')
