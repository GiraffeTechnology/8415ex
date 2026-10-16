# Evidence-derived demonstration materials

The local console runs the existing six scenario definitions. This exporter
consumes their captured records; it does not execute domain actions or invent a
second scenario runtime.

Collect the six JSON evidence records from the same reviewed console source into
one JSON array. Preserve each unique run ID and every expected/observed assertion,
step, price, gas condition, failure and NOT_RUN field.

On approved Linux, use the existing approved storage/output destination:

```sh
python3 -B -m exchange.demo_materials < captured-records.json > demo-materials.zip
```

The input is bounded to4MiB. All six scenarios, their original main paths, distinct
run IDs and identical full source labels are required. Mixed source labels,
duplicate/missing scenarios, false pass labels and promoted real evidence are
refused. Declared labels and manifests are not independent execution proof.

The archive contains six unmodified records, editable slides.md, captions.vtt,
scenes.json, replay.html, README and a manifest binding every member's bytes and
SHA-256. ZIP ordering/timestamps are deterministic for identical captured inputs.
replay.html is a read-only text replay, not a trading UI. Captions and scene times
are presentation timing choices, not measured transaction durations.

Run the affected contracts on approved Linux:

```sh
python3 -B -m unittest integration.test_demo_materials -v
```

PPTX rendering, final film rendering/visual inspection and real browser/provider,
signing, deployment and Sepolia acceptance remain separate NOT_RUN duties.
Only existing approved Linux render tools and storage may be used. No new runtime,
credentials or public listener is provisioned by this exporter.

To roll back, stop the local console and use the separately reviewed source
candidate. This exporter installs no service, changes no shared setting and
writes only the selected stdout stream. Do not reset dirty work or overwrite
another task's evidence. Upload/readback and final rendering must each have their
own actual receipt.
