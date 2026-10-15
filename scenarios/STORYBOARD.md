# Demonstration storyboard and presentation outline

This outline is factual scaffolding for the six confirmed scenarios. Every claim
in it is tied to a recorded result or marked as still owed.

**What this outline may say today.** It may show the local model output produced
by `python3 -B -m scenarios.cli run-all`, clearly labelled as a local model run
against simulated registrar, payment and asset-control adapters.

**What it may not say.** It may not present a local run as a public test network
result, may not present a rendered status page as operable interface acceptance,
and may not imply cooperation with any real warehouse, registrar, exchange or
member firm. The three registration routes are simulated business roles. Final
acceptance of the demonstration, the deck and the video depends on verified
execution evidence that this package does not hold.

## Per-scenario storyboard

Each panel lists what is shown, where the figure comes from, and what is still
owed. "Local" means recorded by the scenario runner. "NOT_RUN" means the real
evidence does not exist yet and must come from the party that owns deployment
and authorized test-network execution.

| Panel | Scenario | Shown on screen | Source of the figures | Still owed |
| --- | --- | --- | --- | --- |
| 1 | DEMO-01, route REG_DIRECT | one whole receipt; owner and holder both at the origin; the buyer funding its own segment; the segment releasing; the four exit steps with four distinct instants; the retained history after the burn | Local | T-35, T-36: real transactions, receipts and a real interface journey |
| 2 | DEMO-02, route REG_ELECTRONIC | the owner at D while the holder is still at the origin; the later result waiting for the gap; the first segment releasing before the holder reaches D; each segment's own principal | Local | T-35, T-36 |
| 3 | DEMO-03, route REG_INTERMEDIARY | a first-hop refusal; the whole unfinished suffix returning to the origin; each buyer's whole principal refunded in the quote asset, with that leg's gas shown separately as an amount in gas units and the party bearing it | Local | T-35, T-36 |
| 4 | DEMO-04, route REG_DIRECT | a settled first segment surviving a later refusal; only the later segments unwinding; the receipt returning to the first buyer, not the origin | Local | T-35, T-36 |
| 5 | DEMO-05, route REG_ELECTRONIC | intermediate wallets without gas; one return operation that does not walk them; the blocked, resumable state; no custody, no forced sale, no liquidation | Local | T-35, T-36 |
| 6 | DEMO-06, route REG_INTERMEDIARY | the stop-trading instant; a new trade refused; in-flight registration and settlement continuing; the eligible exit checked | Local | T-35, T-36 |

## Deck outline

1. **What this is.** An application-layer infrastructure model for one whole
   warehouse receipt traded in a continuous chain, with registration lagging
   behind on purpose. One slide, no product claims.
2. **The two positions.** Owner is the on-chain trade position; holder is the
   registration-confirmed position. They are shown side by side and never
   merged. This is the idea the rest of the deck depends on.
3. **Serial registration.** Why a later result waits for the gap, and why a
   deferred result is not a refusal.
4. **Segment independence.** Each leg funds itself; a qualifying segment settles
   without waiting for the ones behind it; a settled segment is final.
5. **Bounded failure.** A refusal unwinds only the unfinished suffix. The
   finalized prefix is not reopened, and the asset returns to the boundary in
   one operation.
6. **Who pays.** Each leg's buyer bears that leg's gas. A shared operation is
   recorded once; the apportionment rule is still an open decision and the deck
   says so.
7. **Exit.** Owner equal to holder is necessary and not sufficient. The physical
   hand-over and the on-chain burn complete at different times.
8. **Evidence status.** One honest slide: what the local model shows, what the
   public test network has not yet shown, and which open decisions remain. The
   NOT_RUN list appears here verbatim.

## Video outline

| Segment | Length | Content | Labelling required on screen |
| --- | --- | --- | --- |
| Opening | 20 s | the receipt, the two positions | "local model" |
| Chain and registration | 60 s | DEMO-02 panels | "local model, simulated registrar" |
| Independent settlement | 40 s | DEMO-01 and DEMO-02 release panels | "local model, simulated payment" |
| Bounded rollback | 60 s | DEMO-03 and DEMO-04 panels | "local model, simulated asset control" |
| Gas and shortfall | 30 s | DEMO-05 panels | "fixture gas figures, not a fee mechanism" |
| Cutoff and exit | 40 s | DEMO-06 panels | "local model, simulated collection desk" |
| Status | 30 s | the NOT_RUN list and the open decisions | "no deployment or chain execution yet" |

Animation may illustrate a mechanism, and when it does the frame says
"animation". A frame that shows a figure states where the figure came from.
