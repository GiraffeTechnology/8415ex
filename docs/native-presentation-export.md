# Native browser presentation export

This initial exporter consumes the existing `exchange.browser_materials.capture`
result after an independent authorized browser journey. It prepares one editable
15-slide deck with Artifact Tool. It creates no second exchange runtime, starts
no browser, installs no packages, opens no provider and performs no filesystem I/O.

The order is one scope slide, six native page captures, six original scenarios,
remaining acceptance, then the exact runtime/capture identity. Text and speaker
notes remain editable. Screenshots preserve their full aspect ratio and visible
source content. There are no invented plots or decorative drawings.

## Original input and use

The host passes `{files, manifest}`. Files are an object of Uint8Array values,
using the exact paths from the original capture manifest. A Python host may
transport these bytes through its approved existing in-memory transport. The
exporter does not read JSON files, extract ZIPs, or choose staging directories.

The host supplies its verified available font family and uses its existing
`@oai/artifact-tool` module. No dependency installation is authorized by this
module. Dependency absence blocks only actual rendering/export, not source
preparation. Only the independent QA host executes the following:

```js
import {buildPresentation, renderSlides} from '../materials/native-presentation.mjs';
const prepared = await buildPresentation(captured, {fontFamily: verifiedAvailableFont});
const previews = await renderSlides(prepared);
const draft = await prepared.exportPptx();
// Use the host's existing approved non-system output sink for preview blobs
// and draft.save. No host path or credential belongs in public source.
```

Before actual deck generation, the QA host follows the installed presentation
skill's artifact-operation marker and finalization process. Use the existing
Linux runtime, font discovery and module binding. Save a separate draft and final
file in approved storage, validate/import with the finalizer and inspect every
slide at full size. No marker or export has been run by this development writer.
No final PPTX is supplied or claimed by this source batch.

## Binding and honest results

The input check requires all twelve screenshot observations and all six distinct
scenario run IDs, complete member size/hash accounting, same full commit/tree
in the first/last native snapshots and all original scenario records, original
route names and four outcome count names. It retains failures, blocked counts
and not-run obligations. It refuses absent screenshots, mixed versions, altered
summaries or local evidence relabelled as real execution.

Manifest hashes prove byte consistency only. They do not authenticate a caller,
prove that a PNG shows a genuine browser, or grant execution authority. The
original capture logs and independent UI observations remain necessary.

The visible slides retain LOCAL SIMULATION and synthetic-registration disclosure.
Source and evidence/run IDs accompany their actual screenshot in speaker notes.
No private PRD, private host paths, credentials or signed payloads are embedded.
A finalized video handle is separate from playback acceptance. Provider signing,
Sepolia, deployment, rendering/visual QA and final acceptance remain NOT_RUN in
this exporter output. Do not promote them based on PPTX creation alone.

## Authored QA cases

`materials/test_native-presentation.mjs` contains six authored Node test cases.
Independent Linux QA can execute `node --test materials/test_native-presentation.mjs`
on the exact candidate. Its mock presentation API verifies preparation only and
cannot establish Artifact Tool compatibility, image rendering or final PPTX
acceptance. The development writer did not import, parse, compile or execute
these modules or tests. Ordinary QA, submitted fixes, CI, integration, final deck
rendering and merge belong to the independent QA owner.
