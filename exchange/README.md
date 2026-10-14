# Stage 1 exchange domain

This package implements the Stage 1 scope of the private staged requirements
document: warehouse-receipt domain state, the owner/holder dual track, the
serial registration contract with three simulated registrar adapters,
explicitly paired limit intents, wallet-authorization checks, and a basic
operable status console.

Execute according to the private requirements document. That document, the full
task text and any internal path, endpoint or credential stay out of this
repository.

## What this is not

- It is not a trading front end, an order book or a matching engine.
- It performs no network call, no chain transaction, no payment and no deployment.
- The three registration paths are **simulated business roles**. None of them is
  a real registration institution, and no real institutional cooperation,
  API access or business licence is implied.
- Segmented escrow, suffix rollback, deadline handling and redemption are later
  stages. Where Stage 1 touches them it says they are not implemented rather
  than showing a zero or an empty success.
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

## Layout

| Module | Role |
| --- | --- |
| `errors.py` | refusal codes; every rejection names one |
| `ids.py` | canonical JSON, digests, identifier/address/instant/amount checks |
| `model.py` | `WarehouseReceipt`, `AuthorizationReference`, `TradeIntent`, `Asset` |
| `registration.py` | request/evidence contract and the three simulated adapters |
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

Later-stage cases (T-11 onward) are out of Stage 1 scope and are not claimed
here.

## Dependency gaps that do not block Stage 1

Private artifact storage, the external document sync target and the designated
test-network token address are later-stage inputs. They are not configured in
this repository and are not guessed or substituted here. Stage 1 runs entirely
on local fixtures.
