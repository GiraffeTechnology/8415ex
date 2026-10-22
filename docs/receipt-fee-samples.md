# Original receipt fees as applicable median samples

`receipt_fee_samples` bridges the existing `ReceiptGasObservation` output to
the existing `FeeSample` / `GasQuote` contract. Each sample preserves the exact
transaction gas used multiplied by effective gas price, original block number
and raw receipt hash. It does not use gas limits, cumulative gas, a prediction,
an average cap or a fabricated zero.

The installed original source supplies the complete chosen population, original
nonsecret sample/source labels, operation scope and actual observation times.
It must authenticate the complete detached population through the original
applicability callback, including the exact original attempts, transaction/block
identities, raw evidence, outcome, profile and window. This is a source trust
boundary, not a new human approval. Shape and fixture callbacks are not proof.
Do not derive observation times from block numbers, choose a profile or declare
an incomplete population representative. Two to 512 samples are supported;
larger original populations need an explicit compatible adapter rather than
silent truncation.

Each transaction and sample label may appear only once in one population.
Failed executions retain their real consumed gas if the original applicable
profile includes them; this adapter neither excludes them as free nor assumes
they apply to every operation. Unknown/pending observations provide no sample.
OriginalGasReceiptReader remains responsible for authenticated RPC, canonical
and finalized receipt consistency and original attempt binding. This adapter
does not re-query a provider or establish current finality.

GasQuote still owns exact P50 arithmetic, same-instant FX, cap, validity and
action coverage. This stage selects no cap, quote, FX rate, endpoint, wallet,
account, sample policy or operation. It neither freezes/debits/unfreezes gas,
changes reservations nor signs/sends/retries. Returned FeeSamples contain the
existing evidence fields, not private proof or transaction payloads; original
nonsecret label provenance remains the source owner's responsibility.

Nine authored synthetic definitions cover exact even-population fees/P50,
complete applicability binding, missing/duplicate/corrupt observations, time and
label constraints, unavailable/private errors, detached callback data and the
existing original-reader output. They have not been run by the author. No live
samples, deployed quote source, wallet or financial/chain acceptance is claimed.
