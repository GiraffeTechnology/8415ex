"""Evidence export contracts; no deployment, rendered film or PPTX acceptance."""
import copy
import hashlib
import io
import json
import unittest
import zipfile
from exchange import demo_materials, demo_public
from exchange.demo_ui import DemoServer
from scenarios.demos import DEMOS

class DemoMaterialContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server = DemoServer(commit="a" * 40, tree="b" * 40)
        try:
            cls.records = [server.simulate(item.scenario_id) for item in DEMOS]
        finally:
            server.server_close()

    def test_all_six_original_records_and_member_hashes_are_preserved(self):
        data, manifest = demo_materials.build(self.records)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(set(archive.namelist()), set(manifest["files"]) | {"manifest.json"})
            for path, binding in manifest["files"].items():
                payload = archive.read(path)
                self.assertEqual(len(payload), binding["bytes"])
                self.assertEqual(hashlib.sha256(payload).hexdigest(), binding["sha256"])
            for record in self.records:
                name = record["report"]["scenarios"][0]["scenarioId"]
                self.assertEqual(json.loads(archive.read("evidence/" + name + ".json")), record)
            scenes = json.loads(archive.read("scenes.json"))["scenes"]
            self.assertEqual(len(scenes), 8)
            self.assertEqual({scene["runId"] for scene in scenes if "runId" in scene},
                             {record["runId"] for record in self.records})
            self.assertIn("NOT_RUN", archive.read("replay.html").decode())
            self.assertTrue(archive.read("captions.vtt").startswith(b"WEBVTT\n"))
            self.assertIn("not a rendered film", archive.read("README.md").decode())
            self.assertIn("Rendered PPTX", manifest["notRun"])

    def test_typed_public_projection_exports_without_reintroducing_original_setup(self):
        records = [demo_public.run_record(record) for record in self.records]
        data, _ = demo_materials.build(records)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for record in records:
                name = record["report"]["scenarios"][0]["scenarioId"]
                captured = json.loads(archive.read("evidence/" + name + ".json"))
                self.assertEqual(captured, record)
                self.assertNotIn("accounts", captured["report"]["scenarios"][0]["setup"])
        broken = copy.deepcopy(records)
        broken[0]["schema"] = "untyped-projection"
        with self.assertRaises(ValueError):
            demo_materials.build(broken)
        broken = copy.deepcopy(records)
        broken[0]["report"]["scenarios"][0]["counts"]["passed"] += 1
        with self.assertRaises(ValueError):
            demo_materials.build(broken)

    def test_same_captured_records_produce_identical_archive_bytes(self):
        self.assertEqual(demo_materials.build(self.records)[0], demo_materials.build(copy.deepcopy(self.records))[0])

    def test_missing_duplicate_mixed_source_and_real_evidence_refused(self):
        samples = [self.records[:-1]]
        duplicate = copy.deepcopy(self.records)
        duplicate[-1] = duplicate[0]
        samples.append(duplicate)
        mixed = copy.deepcopy(self.records)
        mixed[0]["source"]["tree"] = "c" * 40
        samples.append(mixed)
        real = copy.deepcopy(self.records)
        real[0]["realEvidence"]["chain"] = "passed"
        samples.append(real)
        for sample in samples:
            with self.subTest(kind=str(sample[0].get("source"))), self.assertRaises(ValueError):
                demo_materials.build(sample)

    def test_false_pass_label_is_refused_and_actual_failure_remains_visible(self):
        conflict = copy.deepcopy(self.records)
        conflict[0]["report"]["scenarios"][0]["error"] = "captured fault"
        with self.assertRaises(ValueError):
            demo_materials.build(conflict)
        conflict[0]["report"]["scenarios"][0]["passed"] = False
        conflict[0]["report"]["allPassed"] = False
        data, _ = demo_materials.build(conflict)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertIn("local failure retained", archive.read("slides.md").decode())
            self.assertIn("captured fault", archive.read("evidence/DEMO-01.json").decode())

    def test_untrusted_title_is_escaped_in_html(self):
        records = copy.deepcopy(self.records)
        records[0]["report"]["scenarios"][0]["title"] = "<script>bad</script>"
        data, _ = demo_materials.build(records)
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            page = archive.read("replay.html").decode()
            self.assertNotIn("<script>", page)
            self.assertIn("&lt;script&gt;", page)

    def test_stdin_stdout_entry_accepts_records_and_refuses_incomplete_input(self):
        output, errors = io.BytesIO(), io.StringIO()
        code = demo_materials.main(io.BytesIO(json.dumps(self.records).encode()), output, errors)
        self.assertEqual(code, 0)
        self.assertEqual(output.getvalue(), demo_materials.build(self.records)[0])
        self.assertEqual(errors.getvalue(), "")
        output = io.BytesIO()
        self.assertEqual(demo_materials.main(io.BytesIO(b"[]"), output, errors), 1)
        self.assertEqual(output.getvalue(), b"")
        self.assertIn("EX_DEMO_MATERIALS_REFUSED", errors.getvalue())

    def assert_cli_refuses(self, records):
        output, errors = io.BytesIO(), io.StringIO()
        with self.assertRaises(ValueError):
            demo_materials.build(records)
        self.assertEqual(demo_materials.main(
            io.BytesIO(json.dumps(records).encode()), output, errors), 1)
        self.assertEqual(output.getvalue(), b"")
        self.assertIn("EX_DEMO_MATERIALS_REFUSED:", errors.getvalue())
        self.assertNotIn("Traceback", errors.getvalue())

    def test_unknown_assertion_outcome_cannot_preserve_pass_label(self):
        records = copy.deepcopy(self.records)
        result = records[0]["report"]["scenarios"][0]
        # Previously this extra outcome contributed to no count and left the
        # passing labels intact, allowing an unrecognized result to disappear.
        result["expectations"].append({"outcome": "unknown"})
        self.assertTrue(result["passed"])
        self.assert_cli_refuses(records)

    def test_malformed_nested_shapes_are_refused_without_cli_traceback(self):
        paths = [(), ("source",), ("source", "commit"), ("source", "tree"),
                 ("runId",), ("realEvidence",), ("report",),
                 ("report", "scenarios"), ("report", "scenarios", 0),
                 ("report", "scenarios", 0, "title"),
                 ("report", "scenarios", 0, "expectations"),
                 ("report", "scenarios", 0, "expectations", 0),
                 ("report", "scenarios", 0, "expectations", 0, "outcome"),
                 ("report", "scenarios", 0, "steps"),
                 ("report", "scenarios", 0, "steps", 0),
                 ("report", "scenarios", 0, "setup"),
                 ("report", "scenarios", 0, "counts")]
        for path in paths:
            for value in (None, 1, [], "invalid"):
                with self.subTest(path=path, value=value):
                    # A string title is valid and escaped; only wrong types
                    # belong in this malformed-shape regression.
                    if path[-1:] == ("title",) and isinstance(value, str):
                        continue
                    records = copy.deepcopy(self.records)
                    if not path:
                        records[0] = value
                    else:
                        target = records[0]
                        for key in path[:-1]:
                            target = target[key]
                        target[path[-1]] = value
                    self.assert_cli_refuses(records)
