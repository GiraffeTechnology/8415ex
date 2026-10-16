# Native workbench initial implementation

This entry joins the existing six native domain views, operations detail, fixed
scenario console and evidence navigation in one loopback HTTP process. It adds
no second domain state machine. Fixed scenario runs remain isolated synthetic
observations and never mutate the native receipt. Source identity labels remain
declared until independently bound to a checkout and execution receipt.

## Entry and scope

On the existing approved Linux runtime and storage mapping, the QA/release owner
can use the actual full commit and tree with:

    python3 -B -m exchange.workbench --commit "$SOURCE_HEAD" --tree "$SOURCE_TREE" --port "$APPROVED_PORT"

The built-in entry prepares the existing explicit local fixture and keeps the
command gateway NOT_CONFIGURED. It sends no wallet, provider or chain request.
It creates no persistent files, authentication scheme, signer or deployment.
The six pages are /receipt, /authorization, /timeline, /rollback, /queue and
/evidence. /demo uses the original six fixed scenarios. /api/snapshot returns
the same domain object's state and source labels. /api/operations returns only
bounded command status references, not a durable task journal.

## Existing authorized gateway integration point

The original runtime host may construct RuntimeBinding(exchange, receipt_id,
authorization_ids, run, gateway) and pass it to WorkbenchServer. The gateway must
reuse the original wallet/task-journal and checked domain entry points. No
request may supply a success outcome, wallet grant or arbitrary target endpoint.

Required gateway methods:

- enquire(journal_key, context): reconcile existing/unknown/pending results and
  bind the original task identity, action and payload digest. A content conflict
  must be refused, never returned as a different operation's result.
- dispatch(action, payload, context): validate the original human wallet grant,
  account, chain, asset, segment, amount constraints, nonce, expiry, revocation,
  current head and existing authorization immediately before the original domain
  action. Persist and reconcile through the original journal. An observation
  revision is an optimistic UI guard and does not replace atomic domain checks.

The action vocabulary is submit-registration, reconcile-payment, resume-payment,
advance-rollback and advance-exit. Segment actions accept only a bounded leg index.
Receipt actions take no leg. The host must map these names to actual supported
interfaces and refuse unsupported capability. This is an adapter contract, not
proof that a real provider, Oracle authority or journal binding is configured.
Payment unknown states are enquired and never blindly resent. A gateway timeout
or I/O failure returns an explicit unresolved response and leaves reconciliation
to the original journal. No platform approval layer or manual success setter is
introduced. Queries do not dispatch commands.

Same-origin form/Host checks, bounded complete bodies and CSRF guard commands.
The gateway remains absent in the shipped fixture entry, so command forms stay
disabled. Any real-provider deployment requires the original approved binding
and independent validation by the QA/release owner.

## Product coverage and ownership

This initial module extends the existing receipt, authorization, timeline,
rollback, queue and evidence surfaces. It preserves separate owner/holder,
registration/funding/recovery dimensions and simulated/real boundaries. It reuses
views.page and DemoServer rather than changing the producer harness, ledger,
registration, settlement or exit implementation. No Claude-owned source changes.

The accompanying six contract tests are authored source only. No tests, compiler,
UI run, CI dispatch, deployment or chain execution were performed by this writer.
The independent QA owner owns ordinary Linux tests, native browser journeys,
HTTP refusals, exact-source combination, submitted-code repairs and merge.
Actual provider/UI/signature/chain/persistent recovery and final acceptance stay
NOT_RUN. Existing older package, PPTX and recorded material identities remain
unchanged and must not be relabelled as evidence of this new candidate.
