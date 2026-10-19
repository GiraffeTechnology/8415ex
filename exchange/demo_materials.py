"""Evidence-derived presentation and film inputs; no final PPT/video claim.
Consumes six records captured by the local simulation console. It never runs a
scenario, signs, sends, changes a result or writes a file.
"""
import hashlib
from html import escape
import io
import json
import re
import zipfile

from scenarios.demos import DEMOS

def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()

def validate(records):
    if not isinstance(records, list) or len(records) != len(DEMOS):
        raise ValueError("all six captured scenario records required")
    by_id = {}
    run_ids = set()
    source = None
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("captured record mapping required")
        kind = record.get("evidenceKind")
        if kind != "LOCAL_SIMULATION" and not (
                kind == "SIMULATION_PUBLIC_PROJECTION"
                and record.get("schema") == "8415ex-public-demo/2"):
            raise ValueError("only labelled local or typed public simulation records accepted")
        current = record.get("source", {})
        if not isinstance(current, dict):
            raise ValueError("captured source mapping required")
        if any(not isinstance(current.get(key), str) or
               re.fullmatch(r"[0-9a-f]{40}", current[key]) is None
               for key in ("commit", "tree")):
            raise ValueError("full captured source identity required")
        if source is None:
            source = current
        if current != source:
            raise ValueError("mixed source identities refused")
        run_id = record.get("runId", "")
        if (not isinstance(run_id, str) or
                re.fullmatch(r"demo-[0-9a-f]{32}", run_id) is None or run_id in run_ids):
            raise ValueError("distinct captured run ids required")
        run_ids.add(run_id)
        real = record.get("realEvidence")
        if not isinstance(real, dict) or not real or any(value != "NOT_RUN" for value in real.values()):
            raise ValueError("this local material cannot promote real evidence")
        report = record.get("report", {})
        if not isinstance(report, dict):
            raise ValueError("captured report mapping required")
        scenarios = report.get("scenarios", [])
        if not isinstance(scenarios, list) or len(scenarios) != 1:
            raise ValueError("one captured scenario per run required")
        result = scenarios[0]
        if not isinstance(result, dict):
            raise ValueError("captured scenario mapping required")
        if not isinstance(result.get("title"), str):
            raise ValueError("captured scenario title required")
        name = result.get("scenarioId")
        definition = next((d for d in DEMOS if d.scenario_id == name), None)
        if definition is None or name in by_id or result.get("mainPath") != definition.main_path:
            raise ValueError("scenario or main path mismatch")
        expectations = result.get("expectations", [])
        if (not isinstance(expectations, list) or not expectations
                or not isinstance(result.get("steps"), list) or not result["steps"]
                or any(not isinstance(step, dict) for step in result["steps"])
                or not isinstance(result.get("setup"), dict) or not result["setup"]):
            raise ValueError("captured setup, steps and expectations required")
        outcomes = ("passed", "failed", "blocked", "not-run")
        if any(not isinstance(e, dict) or e.get("outcome") not in outcomes
               for e in expectations):
            raise ValueError("captured assertion mapping and known outcome required")
        counts = {key: sum(e.get("outcome") == key for e in expectations)
                  for key in ("passed", "failed", "blocked", "not-run")}
        if counts != result.get("counts"):
            raise ValueError("assertion counts conflict")
        passed = (not result.get("error") and counts["failed"] == counts["blocked"] == 0
                  and counts["passed"] > 0)
        if result.get("passed") is not passed or report.get("allPassed") is not passed:
            raise ValueError("pass label conflicts with observed failures")
        by_id[name] = record
    return source, by_id

def build(records):
    """Return deterministic ZIP bytes plus a hash manifest over actual inputs."""
    source, by_id = validate(records)
    files = {}
    scenes = [{"title": "8415ex local scenario demonstration",
               "text": "Synthetic model evidence only. No deployment, wallet signing or chain transaction.",
               "kind": "scope"}]
    for definition in DEMOS:
        record = by_id[definition.scenario_id]
        result = record["report"]["scenarios"][0]
        files["evidence/" + definition.scenario_id + ".json"] = canonical(record)
        counts = result["counts"]
        outcome = "local checks passed" if result["passed"] else "local failure retained"
        scenes.append({"title": definition.scenario_id + ": " + result["title"],
                       "text": f"{definition.main_path}; {outcome}. "
                               f"{counts['passed']} passed, {counts['failed']} failed, "
                               f"{counts['blocked']} blocked, {counts['not-run']} not run. "
                               "Recorded observations are evidence replay, not live transactions.",
                       "kind": "recorded-simulation", "runId": record["runId"],
                       "evidence": "evidence/" + definition.scenario_id + ".json",
                       "cases": list(definition.cases), "steps": result["steps"]})
    scenes.append({"title": "Remaining acceptance",
                   "text": "Real browser/provider/signatures, approved deployment, Sepolia and designated "
                           "test token execution, durable process recovery and final presentation/video "
                           "acceptance remain NOT_RUN.",
                   "kind": "limits"})
    slide_lines = ["# 8415ex local demonstration", "",
                   "Presentation content draft derived from captured simulation records.",
                   "Not a rendered PPTX, final film or real-chain acceptance.", "",
                   "Declared source: " + source["commit"] + " / " + source["tree"], ""]
    caption_lines = ["WEBVTT", ""]
    html_sections = []
    for index, scene in enumerate(scenes):
        slide_lines += [f"## {index + 1}. {scene['title']}", "", scene["text"], ""]
        if scene.get("evidence"):
            slide_lines += ["Evidence: " + scene["evidence"], "Run: " + scene["runId"],
                            "Cases: " + ", ".join(scene["cases"]), ""]
        def stamp(seconds):
            return f"{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}.000"
        caption_lines += [str(index + 1), stamp(index * 8) + " --> " + stamp((index + 1) * 8),
                          scene["title"], scene["text"], ""]
        html_sections.append('<section id="scene-' + str(index + 1) + '"><h2>'
                             + escape(scene["title"]) + '</h2><p>' + escape(scene["text"])
                             + '</p>' + ('<p>Run ' + escape(scene["runId"]) + '</p>'
                                         if scene.get("runId") else '') + '</section>')
    files["slides.md"] = "\n".join(slide_lines).encode()
    files["captions.vtt"] = "\n".join(caption_lines).encode()
    files["scenes.json"] = canonical({"kind": "DRAFT_EVIDENCE_REPLAY", "source": source,
                                      "sceneSeconds": 8, "scenes": scenes})
    files["replay.html"] = ('<!doctype html><html lang="en"><meta charset="utf-8">'
                            '<meta name="viewport" content="width=device-width,initial-scale=1">'
                            '<title>8415ex simulation evidence replay</title><body>'
                            '<h1>LOCAL SIMULATION — presentation content draft</h1>'
                            '<p>No real provider, signing, deployment or chain execution. '
                            'No institutional cooperation implied. This file does not execute actions.</p>'
                            + ''.join(html_sections) + '</body></html>').encode()
    files["README.md"] = (
        "# Captured local demonstration inputs\n"
        "\n"
        "Use replay.html to read the draft scenes; slides.md supplies editable presentation text.\n"
        "captions.vtt and scenes.json are film inputs, not a rendered film.\n"
        "Each evidence JSON preserves setup, prices, gas conditions, steps, expectations and failures.\n"
        "The manifest hashes actual member bytes; it does not independently certify execution.\n"
        "No credentials are included.\n"
        "A reviewed rendering on the supported Linux configuration is still required for final PPT/video.\n"
    ).encode()
    manifest = {"schema": "8415ex-demo-materials/1", "source": source,
                "kind": "LOCAL_SIMULATION_CONTENT_DRAFT",
                "notRun": ["Rendered PPTX", "Rendered video", "Real browser/provider/signing",
                           "Deployment and chain", "Durable process recovery"],
                "files": {path: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                          for path, data in sorted(files.items())}}
    files["manifest.json"] = canonical(manifest)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path, data in sorted(files.items()):
            info = zipfile.ZipInfo(path, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    return stream.getvalue(), manifest

def main(input_stream=None, output_stream=None, error_stream=None):
    """Read bounded captured JSON from stdin and write ZIP bytes to stdout."""
    import sys
    input_stream = sys.stdin.buffer if input_stream is None else input_stream
    output_stream = sys.stdout.buffer if output_stream is None else output_stream
    error_stream = sys.stderr if error_stream is None else error_stream
    try:
        raw = input_stream.read(4 * 1024 * 1024 + 1)
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError("captured input exceeds 4 MiB bound")
        records = json.loads(raw)
        payload, _ = build(records)
        output_stream.write(payload)
    except (ValueError, TypeError, KeyError) as error:
        print("EX_DEMO_MATERIALS_REFUSED: " + str(error), file=error_stream)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
