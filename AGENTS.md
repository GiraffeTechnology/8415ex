# EX execution instructions

Before starting, resuming, receiving a task or handing off, read PRD.md, README.md and config/prd-lock.json, then run:

```sh
python3 -B -m scenarios.current_prd plan
```

This is the repository recovery contract, not a schedule or an acceptance certificate. The loader verifies the full current version 1.3 PRD and execution plan by byte size and SHA-256, checks 21 sections, all requirement/case/decision/stage IDs and rejects a stale pin or reactivated retired requirement. Resolve a local pin error for that checklist without turning it into a global stop of unrelated authorized work.

Use config/execution-plan.json for current requirements, D-01..13 statuses, T-01..68 and Stage 0..5. Never derive live duties from old HANDOFF, guide prose or historical scenario output. Physical collection, transport, warehouse exit, collection-driven burn, EX raw-voucher intake, second registration receipt, late-receipt grace, second buyer payment, issuer reset, permanent post-rollback closure, paired-counterparty matching substitution and gas policy marked wholly undecided are superseded.

Do not count old expectations or CI as revised-case PASS. Existing legacy demo entrypoints refuse unported scenarios before their callbacks; only a reviewed actual migration with exact-source evidence can remove that refusal. The new loader/checklist can succeed while product delivery remains OPEN.

After a stage implementation PR immediately continue the next independent authorized stage; do not wait for CI/merge. Exact-head required checks and relevant acceptance still control merge. A local dependency blocks only the affected action. Do not repeat completed unchanged tests without a new relevant concern or invent synonym wrappers to report motion.

Retain the original single writer and existing QA, review, CI/merge and deployment owners. This repository document does not assign another project's identity, network, runtime or credentials to EX. Product/unit/integration/API/EVM/browser/syntax/type/build/package validation must run only on an existing approved remote Linux server with verified CTYun or Aliyun provider evidence and the existing per-action execution boundary check. This local machine, Windows, WSL, containers and VMs are not test fallbacks. Local instruction recovery and source/hash editing remain allowed. Existing valid authorizations persist until explicitly revoked, replaced, expired or exceeded; do not request the same permission solely because a session or version changed.

Before external actions verify actual approved RPC, chain 11155111, test asset, actor/control, original signer/grant, fee/nonce/balance and unknown-outcome lookup. No guessed parameters, new identity, resource, credential, security/payment setting, mainnet or real-value transaction. Do not disclose secrets or perform human-only authentication actions.

Oracle alone verifies off-chain vouchers and writes their authoritative chain record. Holder follows that same record; owner may advance earlier. Freeze principal before trade and release the original frozen amount; gas is separate, bounded by buyer confirmation and settled from actual consumption. Preserve registered/settled prefix on suffix rollback.

NFT0 fixes one or more allowed currencies at mint and has no setters afterward.
An order selects exactly one allowed member; no exchange, substitution or mixed
balances. Gas uses ETH only. Insufficient selected principal or ETH gas must warn
and refuse before signing/execution/broadcast. ETH-priced principal and ETH gas
must not count the same funds twice. Original approved gas prepayment recovery
does not require a second prepayment when its remaining bound amount suffices.

Holder possession plus holder=owner permits atomic old-NFT burn/new-NFT mint with
new terms and permanent history/identity links. Do not add cleanup, migration or
separate approval prerequisites. This is not physical collection destruction.
Do not apply holder equality, gap or current-finality gates to ordinary transfer.
Keep owner-stopped capabilities probes stopped across reconnects and new callers.

Keep exact source/config/run/log/artifact references and distinguish NOT_RUN, NOT_VERIFIED, failed and passed. Full delivery also needs actual runtime, chain/Oracle/funds, source-specific UI, demo/PPT/playable film and artifact readback. No local checklist, package, CI or HTTP status alone closes the product.

Protect dirty files, keys, databases, journals, locks, evidence, shared services, production and active inputs. Respect existing at-most-two usable rollback retention; do not blindly delete or move live state. Public GitHub text is English and sanitized; keep private PRD locators and operational parameters private. No cancelled Drive polling, workflow or old migration is restored.
