# Exchange domain

This package implements the staged scope of the private requirements document.

**Stage 1**: warehouse-receipt domain state, the owner/holder dual track, the
serial registration contract with three simulated registrar adapters,
explicitly paired limit intents, wallet-authorization checks, and a basic
operable status console.

**Stage 2**: one escrow position per leg funded by that leg's own buyer, release
per segment on the positional condition with bound authority evidence, an
optional separate payment adapter, unknown-outcome recovery by enquiry, and
per-segment reconciliation.

**Stage 3**: suffix rollback that protects the finalized prefix, refunds each
segment to its own original buyer, returns the asset to the boundary in one
control operation, and records each leg's buyer's own gas.

Execute according to the private requirements document. That document, the full
task text and any internal path, endpoint or credential stay out of this
repository.

## What this is not

- It is not a trading front end, an order book or a matching engine.
- It performs no network call, no chain transaction, no payment and no deployment.
- The three registration paths are **simulated business roles**. None of them is
  a real registration institution, and no real institutional cooperation,
  API access or business licence is implied.
- Deadline handling and redemption are later stages. Where an implemented stage
  touches them it says they are not implemented rather than showing a zero or an
  empty success.
- A rollback never takes the asset into temporary custody, never imposes a
  time-limited redemption or an overdue sale, and never liquidates a position to
  cover a shortfall. A shortfall is a blocked, resumable state.
- Payment is an optional, separate adapter. An escrow record, an amount or a
  released payment is never authority for completion, acceptance or return.
- A rendered page from `exchange.views` is development evidence. It is not UI
  acceptance evidence, which needs a real browser journey against a deployed
  build.

## Design rules this code holds to

1. **One NFT is one whole receipt.** The goods quantity inside a receipt and the
   tradeable quantity are separate fields; the tradeable quantity is always 1.
   A fractional, zero, multi-unit or duplicate asset mapping is refused.
2. **Owner and holder never merge.** `owner` is the position the trade chain has
   reached on chain; `holder` is the position the registrar has confirmed. A
   position is an occurrence index in one receipt's accepted chain, never the
   numeric order of an address.
3. **Registration is serial.** A result for a leg beyond the next expected one is
   *deferred*, not applied and not a refusal. Filling the gap drains the buffer
   in order.
4. **Idempotency is explicit.** An exact repeat returns the first result; the same
   identifier with different content is a conflict, never a silent overwrite.
5. **Evidence must bind.** A result advances nothing unless it names the right
   asset, network, receipt, transfer, leg, adapter and trusted source.
6. **No status is collapsed.** Execution, registration and funding states are
   recorded separately. There is no single `success` field.
7. **The wallet grant is the authority.** This layer checks a grant and refuses;
   it cannot widen one, it holds no key, and it adds no step-by-step approval of
   its own on top of what the wallet already authorized.
8. **Amounts are integers** in the smallest unit. A float cannot reach a
   canonical record.
9. **Each leg funds itself.** A position carries its own payer, payee, asset and
   principal; a later leg's unreleased money can never support an earlier one,
   and a release pays exactly one position to exactly its own payee.
10. **Release and refund are mutually exclusive**, and neither happens twice. A
    segment that already qualifies is not swept into a refund just because its
    payment is late.
11. **Release needs bound authority.** A plain signature, the text `VALID`,
    public JSON or a bare settlement identifier is refused. The evidence must
    bind source, asset, network, receipt, transfer, leg and a journal reference.
12. **An unknown payment is never repaired by a second payment.** The adapter is
    asked what happened first, a restart does not read unknown as failed, and an
    enquiry applies the outcome the payment was actually for.
13. **A finalized prefix is immutable.** A released segment is detached for
    good: it is not reopened, reversed or re-collected, and a return stops at
    the boundary that prefix established.
14. **A return is one control operation** to the boundary account. It does not
    walk back through the intermediate wallets and does not depend on their gas.
15. **A rollback is only complete when every step has its own evidence**, and
    each step is keyed so a resumed rollback repeats no refund and no return.

## Layout

| Module | Role |
| --- | --- |
| `errors.py` | refusal codes; every rejection names one |
| `ids.py` | canonical JSON, digests, identifier/address/instant/amount checks |
| `model.py` | `WarehouseReceipt`, `AuthorizationReference`, `TradeIntent`, `Asset` |
| `registration.py` | request/evidence contract and the three simulated adapters |
| `settlement.py` | escrow positions, release authority, optional payment adapter |
| `rollback.py` | rollback authority, recoverable steps, simulated asset-return control |
| `ledger.py` | the state machine: chain, dual track, registration, reporting |
| `views.py` | the six status pages and their wording rules |
| `webui.py` | read-only console over `http.server` |
| `cli.py` | diagnostic output, supplementary to the UI |
| `fixtures.py` | deterministic synthetic fixtures, clearly marked |

## Commands

Linux, Python 3.10+, standard library only, no third-party dependency.

```sh
# Stage 1 domain tests
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s exchange/tests -t . -v

# diagnostic state dump
python3 -B -m exchange.cli view
python3 -B -m exchange.cli timeline
python3 -B -m exchange.cli queue --canonical

# local status console, loopback only
python3 -B -m exchange.webui --host 127.0.0.1 --port 8415
```

A served origin is scheme, host **and** port. Which address an environment
serves on belongs in that environment's deployment document, not here.

## Requirement and test traceability

Requirement identifiers follow the private document. This table records which
tests cover each Stage 1 case; it names no requirement text.

| Case | Covered by | Notes |
| --- | --- | --- |
| T-01 | `test_receipt_state.WholeReceiptScope` | whole receipt; fractional, multi-unit and duplicate mapping refused |
| T-02 | `test_receipt_state.DualTrack` | origin is owner and holder; divergence stays readable |
| T-03 | `test_trade_chain.ContinuousChain` | A→B→C→D recorded in full, each hop files its own request |
| T-04 | `test_registration.SerialOrdering` | later results deferred, then drained in order |
| T-05 | `test_registration.Idempotency` | exact repeat is a no-op; same id, other content conflicts |
| T-06 | `test_authorization.AuthorizationChecks` | unauthorized, expired, revoked, altered amount/asset/chain/action/counterparty |
| T-07 | `test_trade_chain.OneValidHead` | nonce replay refused; two sales from one head advance once |
| T-08 | `test_authorization.SessionAndAccountChanges` | switch, disconnect and session loss |
| T-09 | `test_matching.ExplicitPairing` | independent orders; the pairing fixture rewrites no signed term |
| T-10 | `test_registration.ThreeAdapters` | three paths, one contract, each marked simulated |
| T-26 | `test_receipt_state.NoCollapsedStatus`, `test_views` | simulated vs real, pending vs complete, owner vs holder |
| T-27 | `test_reproducibility` | identical results from a fixed clock and fixture; traceable records |
| T-34 | `test_authorization.NoSecondApprovalLayer` | consecutive in-scope actions need no extra approval; out of scope still refused |
| T-11 | `test_settlement.SegmentFunding` | each leg funded by its own buyer; a failed lock forms no trade and no request |
| T-12 | `test_settlement.IndependentRelease` | AB releases without waiting for C or D; a released segment detaches |
| T-13 | `test_settlement.NoCrossSubsidy` | the three principals stay distinct; no later leg funds an earlier one |
| T-14 | `test_settlement.ReleaseAuthorityBinding` | wrong asset, network, segment, transfer, journal or source refused |
| T-15 | `test_settlement.HistoricalAndCurrentEvidence` | an earlier confirmation and a later holder observation both hold |
| T-16 | `test_settlement.PaymentFailureAndRecovery` | confirmed registration with a late payment is tracked, not refunded |
| T-28 | `test_settlement.PaymentFailureAndRecovery` | enquiry before retry; restart and repeat move nothing twice |
| T-31 | `test_settlement.Reconciliation` | release and refund exclusive; principal, gas and net per segment |
| T-17 | `test_rollback.FullSuffixRollback` | a refusal at the first leg unwinds the whole suffix back to the origin |
| T-18 | `test_rollback.FinalizedPrefixSurvives` | a settled prefix survives; only the later segments unwind, back to its buyer |
| T-19 | `test_rollback.RefundsAndGas` | each original buyer's own principal, with actual gas and net |
| T-20 | `test_rollback.ReturnDoesNotWalkIntermediates` | one control operation; a zero-balance intermediate changes no obligation |
| T-21 | `test_rollback.RefundsAndGas` | a shared operation is recorded once, never charged in full twice |
| T-22 | `test_rollback.ShortfallStaysBlocked` | a shortfall blocks and resumes; no custody, sale or liquidation |
| T-23 | `test_rollback.InterruptionAndLateResults` | resume without repeating; a late success revives nothing |
| T-29 | `test_rollback.RollbackPermission` | unverified authority refused; no confiscation, no prefix rewrite |
| T-30 | `test_rollback.DuplicateAndReorderedEvents` | duplicate and re-ordered observations move nothing twice |

Later-stage cases (T-24, T-25, T-32, T-33 and the Stage 5 set) are out of the
implemented scope and are not claimed here.

## Dependency gaps that do not block Stage 1

The gas apportionment rule for a shared on-chain operation, the actual fee
deduction mechanism, the recovery detail for a confirmed registration whose
payment failed, the real asset-return control and the exit ordering are all
still open in the requirements document. Re-trading a receipt after a rollback
returned it is also not a defined order, so it is refused with
`EX_TRADE_RETURNED_CHAIN_CLOSED` rather than guessed. The code records the facts and refuses
where an order is undefined; it does not assume an answer. A shared operation is
recorded once and is never charged in full to every leg.

Private artifact storage, the external document sync target and the designated
test-network token address are later-stage inputs. They are not configured in
this repository and are not guessed or substituted here. Stage 1 runs entirely
on local fixtures.
