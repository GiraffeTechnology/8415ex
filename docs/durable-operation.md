# EX durable operation claims

This candidate adds a restart-persistent EX command identity/CAS component. It
stores only exact non-secret EX/native references and an intent digest on a
caller-owned dedicated file-backed SQLite connection. Initialization is explicit;
importing this module opens no DB and changes no production state. The existing
store must already use FULL or EXTRA synchronous mode. Existing schemas are not
overwritten or silently migrated.

Claim and receipt-revision advancement commit in one local transaction. A new
claim is UNKNOWN before any original native gate can be entered. Lost commit
results require reopening and lookup of the same native operation. A restarted
process sees that exact claim and never treats it as a new send. Reuse with a
different intent is rejected; different operations cannot claim the same observed
receipt revision through separate connections. Authoritative original-journal
proof is required to record a reconciled result. Even proven not-applied outcomes
do not grant a resend or automatically release quota, funds, gas or nonce.

The explicit `invoke_once` application path first enquires the original native
journal. Existing original or local operations are only enquired, never dispatched
again. For a new authenticated absence it commits the UNKNOWN claim before calling
the original checked execution gateway once. A lookup failure or uncertain local
commit cannot reach that call. A lost native reply leaves UNKNOWN across reopening;
even a successful gateway response is not converted into finality or reconciliation
proof. Both callbacks are trusted application bindings, not caller form fields.

V3 adds `observe(binding, enquire_original)` for recovery without admission or
old declaration dependencies. It validates the complete original identity,
rejects any conflict with an existing local claim before querying, and returns
the original read without creating a claim, advancing a revision or changing
UNKNOWN/reconciled state. An absent local claim also permits enquiry only.
The remint composition stage defines two additional read-only recovery cases;
they remain NOT_RUN alongside the fourteen existing journal definitions.

This is not a second financial journal, a wallet authorization layer or an Oracle
writer. It does not freeze/release/refund money, transfer/burn/mint NFTs, sign,
broadcast, apply registration or dispatch a queue. The existing source mapper must
authenticate receipt/asset/global-leg/native-operation membership before claiming;
the original native gate must still atomically check current authority, funds,
gas, nonce and cutoff. A local receipt revision is not a cross-service transaction.
Actual EX state reconstruction/outbox integration and native outcome verification
remain unfinished. Storage corruption, hardware durability and chain reorganization
also require original operational/authority handling; hashes are not signatures.

Status: SOURCE_ONLY / NOT_RUN / NOT_INSTALLED. Fourteen authored cases include closing
and reopening a real temporary file database and competing connections, including a committed claim whose acknowledgement is lost. Gate-call ordering, lost native replies, original lookup failure, original preexisting operations and commit uncertainty are also covered by definitions. They are
separate from real process/native/chain acceptance, and must run only on an
existing approved provider-verified CTYun/Aliyun Linux target after its boundary
check. No local import, syntax check, product test or DB initialization was run.
