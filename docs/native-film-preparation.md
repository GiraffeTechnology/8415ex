# Original browser film preparation

This initial module consumes the original completed browser-material capture and
its finalized browser WebM. It preserves that recording byte for byte and adds
an HTML viewing entry, six source-bound chapter records, WebVTT captions and a
source/hash manifest. It never replaces browser footage with text frames or
animation. It creates no product runtime, browser, provider, account or credential.

The original recording context must provide its actual recording start and end
UTC, measured media duration in integer milliseconds, and a non-secret reference
to its original clock evidence. There is no default timestamp, synthetic timing
or guessed subtitle alignment. Chapter times locate the actual screenshot
observation, not the start of a business operation. The six observations must
fit the measured recording and retain chronological order. The host keeps its
original clock evidence for independent review. Plausible timestamps alone are
not timing authenticity or playback acceptance.

Independent Linux QA uses the original captured object, then calls:

```js
import {buildFilm} from '../materials/native-film.mjs';
const output = buildFilm(captured, {
  recordingStartedUTC, recordingFinishedUTC, mediaDurationMs, clockEvidenceRef
});
// Persist output.files only with the original approved non-system sink.
// The module itself does not open paths, launch processes or write files.
```

Serve index.html with its relative files from an approved existing evidence
viewer. It references browser-capture.webm and chapters.vtt on the same origin.
No external network content or third-party script is included. The original
recording is a WebM file, not a promised MP4 transcode. Playback support must be
checked in the actual target viewer. No codec probe, duration measurement,
transcode, browser playback or content review is executed by this module.

The module reuses validateCapture from the existing presentation exporter to
bind twelve screenshots, six distinct run IDs, member hashes, full runtime
commit/tree, original scenario/route/counts and LOCAL_SIMULATION evidence.
The recording's byte count/hash must also match its finalized-handle manifest.
The local source manifest remains NOT_RUN for playback, content review, provider
signing, Sepolia, deployment and final acceptance. Do not promote these results
because a file or viewing entry was generated.

Six authored tests in materials/test_native-film.mjs use synthetic container
headers solely for contract assertions. Independent QA can run
`node --test materials/test_native-film.mjs` on Linux at the exact candidate.
Those cases cannot establish valid codecs, real browser provenance, duration,
caption synchronization or playback. Actual finalized browser media and clock
records are separate required inputs for final film preparation and review.

The developer did not import, parse, compile or execute the module/tests, create
a movie, probe a codec or run playback. Ordinary tests, submitted corrections,
CI, integration, actual movie/content QA and merge belong to independent QA.
No earlier submitted or producer-owned files are modified by this initial batch.
