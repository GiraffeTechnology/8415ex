"""Six-language controls for the restricted original-host wiring page."""
WORDS = {
'en': ('Restricted linked operations','Not public native access. Original caller authorization is required. Observation is not confirmation; UNKNOWN must be reconciled, never replayed. Wallet owner review stays in Wallet V3.', 'Aggregate generation', 'Open Wallet owner review','Refresh original state','Dispatch this existing PREPARED operation once', ('Owner review','Read original observation','Dispatch once','Read Oracle admission','Apply original deadline')),
'zh-Hans': ('受限接线操作','并非公众原生交易入口。必须核验原调用者权限。观察不等于确认；UNKNOWN 必须对账，不得重发。钱包所有者审核仍在 Wallet V3。','聚合版本','打开钱包所有者审核','刷新原始状态','仅执行此已存在的 PREPARED 操作一次',('所有者审核','读取原观察','执行一次','读取 Oracle 准入','应用原截止条款')),
'zh-Hant': ('受限接線操作','並非公眾原生交易入口。必須核驗原呼叫者權限。觀察不等於確認；UNKNOWN 必須對帳，不得重發。錢包所有者審核仍在 Wallet V3。','聚合版本','開啟錢包所有者審核','重新整理原始狀態','僅執行此已存在的 PREPARED 操作一次',('所有者審核','讀取原觀察','執行一次','讀取 Oracle 准入','套用原截止條款')),
'fr': ('Opérations liées restreintes',"Pas d’accès natif public. L’autorisation de l’appelant initial est requise. Une observation ne confirme rien ; UNKNOWN doit être rapproché, jamais rejoué. La revue du propriétaire reste dans Wallet V3.",'Génération agrégée','Ouvrir la revue du propriétaire','Actualiser l’état initial','Exécuter une seule fois cette opération PREPARED existante',('Revue du propriétaire','Lire l’observation initiale','Exécuter une fois','Lire l’admission Oracle','Appliquer l’échéance initiale')),
'es': ('Operaciones enlazadas restringidas','No es acceso nativo público. Se requiere autorización del solicitante original. Observar no confirma; UNKNOWN se concilia, nunca se repite. La revisión del propietario permanece en Wallet V3.','Generación agregada','Abrir revisión del propietario','Actualizar estado original','Ejecutar una sola vez esta operación PREPARED existente',('Revisión del propietario','Leer observación original','Ejecutar una vez','Leer admisión Oracle','Aplicar plazo original')),
'ja': ('制限付き連携操作','一般公開のネイティブ取引入口ではありません。元の呼出者権限が必要です。観測は確認ではありません。UNKNOWN は照合し、再送しません。所有者の確認は Wallet V3 で行います。','集約世代','ウォレット所有者の確認を開く','元の状態を更新','既存の PREPARED 操作を一度だけ実行',('所有者の確認','元の観測を読む','一度だけ実行','Oracle 受入を読む','元の期限条件を適用')),
}
ORDER = ('review','observe','dispatch','oracle-observe','deadline')

# Restricted original-proposal actions; public simulation controls unchanged.
TASK_LABELS = {
'en': ('Prepare original task proposal','Reconcile original task','Review task in Wallet V3','Reserve authorized original child'),
'zh-Hans': ('准备原任务提案','核对原任务','在 Wallet V3 审阅任务','预留已授权原子操作'),
'zh-Hant': ('準備原任務提案','核對原任務','在 Wallet V3 審閱任務','預留已授權原子操作'),
'fr': ('Préparer la proposition originale','Rapprocher la tâche originale','Examiner dans Wallet V3','Réserver l’opération autorisée'),
'es': ('Preparar propuesta original','Conciliar tarea original','Revisar en Wallet V3','Reservar operación autorizada'),
'ja': ('元のタスク提案を準備','元のタスクを照合','Wallet V3 でタスクを確認','承認済み操作を予約'),
}

RECOVERY_LABELS = {
'en':'Read original recovery progress (production proof UNBOUND)',
'zh-Hans':'读取原恢复进度（生产证明未绑定）',
'zh-Hant':'讀取原恢復進度（生產證明未綁定）',
'fr':'Lire la reprise originale (preuve de production non liée)',
'es':'Leer recuperación original (prueba de producción sin vincular)',
'ja':'元の復旧状況を読む（本番証明は未接続）',
}

ECONOMIC_LABELS = {
'en':('Read original direct-transfer evidence','Verify original terminal payment'),
'zh-Hans':('读取原直接转账证据','核验原终态付款'),
'zh-Hant':('讀取原直接轉帳證據','核驗原終態付款'),
'fr':('Lire la preuve du transfert direct','Vérifier le paiement terminal original'),
'es':('Leer evidencia de transferencia directa','Verificar pago terminal original'),
'ja':('元の直接送金証拠を読む','元の最終支払いを検証'),
}

RECOVERY_CONFIRM_LABELS = {
 'en':'Verify the existing deferred refund',
 'zh-Hans':'核收已执行的延期退款',
 'zh-Hant':'核收已執行的延期退款',
 'ja':'実行済み繰延返金を検証',
 'fr':'Vérifier le remboursement différé existant',
 'es':'Verificar el reembolso diferido existente',
}

ASSET_RETURN_CONFIRM_LABELS = {
 'en':'Verify the existing original asset return',
 'zh-Hans':'核收已执行的原资产返回',
 'zh-Hant':'核收已執行的原資產返回',
 'ja':'実行済みの元の資産返却を検証',
 'fr':"Vérifier le retour existant de l’actif original",
 'es':'Verificar la devolución existente del activo original',
}
