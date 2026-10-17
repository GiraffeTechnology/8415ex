# EX principal journal integration contract

This increment translates existing EX `EscrowPosition`, `Asset` and `ReleaseAuthority` facts into detached requests for the original native principal writer. It does not implement a Wallet API, initialize a financial store, construct calldata, sign, dispatch, change EX ledger state, or write Oracle ownership. A request is PREPARED_NOT_DISPATCHED. An authenticated journal snapshot alone is not complete trade admission.

## Existing source and integration limits

The EX base is PR53 `a7a9a53abed007a255873fce25fe9d378bc7352f`, including stable global leg IDs. Local `lock_escrow` creates a model position, not proof of externally locked funds. The simulated payment adapter is separate and is not invoked here.

The audited Wallet source `f57e298b8680588cc9458c43b69eb9d58e9d5567` has receipt task/encoder/provider/runtime components. Its declared phases are funded, registered and paid, with fund, confirmRegistration and paySeller wire functions. Standard main does not compose that receipt runtime. The audited encoder has no refund/rejection ABI. Journal capability and grant reservation do not establish payment-token principal inventory. This module does not relabel those components as a complete EX financial service or call their ArtFi-specific wire contract.

## Exact EX binding

`PrincipalBinding` consumes the original segment position and whole NFT identity. The immutable terms include Sepolia chainId 11155111, NFT contract and tokenId, receiptId, stable globalLegId, transferId, escrowId, buyer, seller, exact configured payment-token address, verified tokenDecimals, integer principalBaseUnits, nativeOperationId and journalReference. The position's quote_asset must equal that configured token. No token address, RPC, signing actor, runtime origin or native operation is guessed.

The principal amount is encoded as an exact decimal integer string in requests. Decimals document the verified token unit; they never multiply, round or convert the principal. The configured designated PYUSD binding must be independently verified at deployment. ETH gas is separate. A principal freeze does not assert gas freeze or buyer confirmation.

The EX binding digest and stable per-action operationKey are EX identities, not Wallet taskDigest/executorDigest, EIP-712 signatures, calldata hashes or Oracle commitments. The original adapter must preserve both sets of identities and their authenticated mapping.

## Native read and state rules

The injected verify_native callback must authenticate the original financial source/store and exact operation, revision, freshness and canonical financial evidence. A local JSON body, signature-shaped value, grant, receipt phase, transaction hash or local escrow is insufficient. Only an exact True accepts. No permissive default exists.

A native snapshot has exactly binding, sourceReference, revision, state, freezeReference, lockedBaseUnits, releasedBaseUnits, refundedBaseUnits and pendingAction. Amounts in this internal Python DTO are exact uint256 integers. Known states must conserve this segment's principal:

| State | Locked | Released to seller | Refunded to buyer |
| --- | ---: | ---: | ---: |
| absent | 0 | 0 | 0 |
| frozen | full principal | 0 | 0 |
| released | 0 | full principal | 0 |
| refunded | 0 | 0 | full principal |

An authenticated absent read is required before preparing freeze. Frozen and terminal states require the original freeze reference. UNKNOWN records require a pending action and cannot assert any of those balances. Release/refund UNKNOWN also retains the original freeze reference. All action requests on UNKNOWN become RECONCILE_ONLY, without authority evaluation or an executable request. Reconciliation must query the original operation; a missing lookup after an earlier attempt is not evidence of no effect.

Preparing an already recorded action is idempotent and returns no request. Release/refund are exclusive. A released or refunded segment cannot be frozen afresh by this bridge. Retries use the same operationKey even when the native revision changes.

## Action authority and atomic writer responsibilities

verify_authority is an internal installation port, not a claim that a Wallet function of that name exists. It must check current original authority against the exact binding and native snapshot.

Release reuses `ReleaseAuthority` and recomputes the existing `segment_binding` over source journal reference and exact parties/amount/asset/segment. The original verifier must still authenticate the authoritative Oracle record, registry/version/commitment, registered prefix and atomic cutoff/finality condition. observed_at is not effectiveAt. EX does not accept raw registrar vouchers or write a second holder receipt.

Freeze/refund use an exact original authority reference with bindingDigest, action and journalReference. The reference must resolve through the original authenticated native verifier. A freeze verifier checks current buyer intent/grant, available principal after other reservations, and separately confirmed ETH cap freeze. A refund verifier checks canonical rejection or overdue unregistered suffix, preserved prefix, original freeze availability and required NFT return ordering. A label such as VALID is refused.

The native writer must atomically compare expectedNativeRevision, immutable terms and originalFreezeReference; recheck current authority, nonce and available balances; and persist the original operation's UNKNOWN attempt before the external effect. It must enforce globally exclusive release/refund and stable idempotency across restarts. A stale request cannot be dispatched after re-reading a newer revision without preparation again. Verifier callbacks must be read-only; preparation performs no durable reservation.

Freeze requests debit the buyer principal once and leave the actual escrow target to the verified original native implementation. Release and refund both carry debitBuyerBaseUnits=0 and consumeOriginalFreeze=true: release routes held principal to the original seller; refund returns held principal to the original buyer. There is no second buyer payment after registration.

The gas account remains the original confirmed ETH budget, with its own budget ID, quote/version/digest, confirmation, freeze/adjustment references, attempts, maximum reservations and actual receipt cost. Success and reverted transactions consume actual gas; retries/splits do not reset the cap. UNKNOWN retains reservations. Returning unused gas is a separate proven native unfreeze; principal refund never restores consumed gas.

## Wallet adaptation handoff

The controller must join these EX facts to the original Wallet/native implementation:

| EX requirement | Existing Wallet source field or seam | Required adaptation/evidence |
| --- | --- | --- |
| original operation identity | taskId, taskDigest, executorDigest, grantReference, grantPolicyVersion, operationId | Authenticated mapping to exact EX binding and stable global leg, preserving native digests |
| principal freeze | funded phase / fund encoder | Actual configured Sepolia ERC20 principal inventory, durable freeze reference and full balance; not a grant fee reservation |
| registration authority | registered phase / confirmRegistration | Actual authoritative Oracle source + NFT + transfer/global leg + registry version/commitment and atomic effective-time condition |
| release held funds | paid phase / paySeller | Consume original freeze via native revision/CAS, fixed seller and amount, buyer debit zero |
| refund/rejection | no audited receipt refund ABI | Original implementation must add/identify the actual scoped refund path and preserve asset-return/final prefix semantics; no guessed selector |
| outcome reconciliation | receipt nonce/plan/journal hashes and native operation journal | Canonical source/transaction result and revision, UNKNOWN before effect, no automatic resend |
| ETH gas | phase gasLimit/maxFee/priority fields and attempt accounting | Actual separate confirmed cap freeze, aggregate remaining reservations, failed actual cost and unused-balance unfreeze |
| runtime composition | explicit receipt runtime exists; absent from audited standard main | Original owner supplies reviewed installed source/store/peer/provider bindings and served identity |

This table requests implementation and exact source evidence; it does not wait for a nonexistent ready-made API. Other independent EX stages continue.

## Validation and remaining acceptance

Twelve synthetic contract regressions are authored, NOT_RUN. The independent QA command after exact source preparation is `python -m unittest integration.test_principal_journal_contract -v`. No compilation/import, unit suite, hosted CI, actual native store, browser, signature, transaction or deployment was executed by this source stage. Callback fixtures cannot establish live acceptance.

The next integration must connect authenticated verifiers and the original native writer, then consume actual results in the EX runtime without treating prepared requests as locked funds. Real principal/gas segregation, authoritative registration/cutoff, return/refund, UNKNOWN recovery, restart/CAS, source/artifact/served identity and complete UI/chain evidence remain OPEN.
