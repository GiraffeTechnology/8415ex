# Native browser material collection

This initial development module consumes the host's existing approved async
browser Page. It launches no browser, creates no context or credential, and
performs no wallet signing, provider operation or chain transaction. It uses
only the loopback workbench's fixed simulations. The development writer has
not executed this module or any browser/ordinary test.

The QA host supplies an already permitted Page with goto, locator, screenshot,
wait_for_url, request.get and optional video operations. Responses expose status
and async json(); locators expose select_option, click and wait_for. No new
browser library or runtime is installed by the module. The original QA host
owns timeout policy and existing browser/context lifecycle.

    captured = await capture(page, original_loopback_origin,
                             {"commit": full_head, "tree": full_tree})
    draft_zip_bytes = pack_capture(captured)

capture reads the runtime source before and after the journey. It captures six
native pages and executes the existing six fixed simulation forms through the
actual browser page, then binds each resulting run ID, scenario, source identity,
raw JSON and PNG digest. Mismatching source, navigation away from the loopback
origin, unexpected run or real-execution claim refuses the capture. Failed local
assertion counts remain in captured records rather than becoming an acceptance
pass. Images and packages have explicit byte limits and remain in memory.

An optional existing browser recording must originate from the same page's
video handle. After the host safely closes its own approved recording context:

    completed = await finish_video(captured, read_approved_bytes)
    completed_zip_bytes = pack_capture(completed)

read_approved_bytes(path, maximum_bytes) is an async host callback. It must check
the original authorized storage mapping before reading. The collector does not
open, relocate or create the recording file. An absent video handle remains
NOT_RUN and cannot be replaced by an old text replay or scenario animation.
The finalized container must be a bounded WebM. Its hash and bytes are preserved,
but playback and visual/content QA stay NOT_RUN for the independent reviewer.
A container signature alone does not prove a valid or truthful playable movie.

This is a product material-collection implementation, not evidence that a
browser ran. It does not modify the private PRD, old packages, submitted runtime,
producer harness, CI workflow or deployment configuration. Ordinary Linux tests,
actual browser execution, storage binding, movie playback/content review and
final PPT/video acceptance belong to the independent QA/release owner. No
actual screenshot, movie or final acceptance is claimed by this source batch.
