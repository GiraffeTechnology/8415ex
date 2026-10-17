"""Current contract recovery regressions; not runtime or business acceptance."""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scenarios import current_prd


class CurrentPRDV13Contracts(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        original = Path(__file__).resolve().parents[2]
        (self.root / "config").mkdir()
        for path in ("PRD.md", "config/prd-lock.json", "config/execution-plan.json"):
            shutil.copyfile(original / path, self.root / path)

    def read(self, path):
        return json.loads((self.root / path).read_text(encoding="utf-8"))

    def write(self, path, value):
        (self.root / path).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def repin_plan(self, plan):
        self.write("config/execution-plan.json", plan)
        raw = (self.root / "config/execution-plan.json").read_bytes()
        identity = (len(raw), hashlib.sha256(raw).hexdigest())
        lock = self.read("config/prd-lock.json")
        lock["executionPlan"].update(bytes=identity[0], sha256=identity[1])
        self.write("config/prd-lock.json", lock)
        return identity

    @contextmanager
    def structural_fixture(self, mutate):
        # Isolate structural checks after the separately tested immutable pin.
        # This temporary fixture patch is not a production repinning mechanism.
        plan = self.read("config/execution-plan.json")
        mutate(plan)
        identity = self.repin_plan(plan)
        with patch.dict(current_prd.PINNED, {"executionPlan": identity}):
            yield

    def test_current_contract_has_all_cases_and_no_inherited_acceptance(self):
        plan = current_prd.load(self.root)
        self.assertEqual(plan["version"], "1.3")
        self.assertEqual(len(plan["requirements"]), 91)
        self.assertEqual({row["id"] for row in plan["cases"]},
                         {"T-%02d" % n for n in range(1, 69)})
        report = current_prd.report("matrix", self.root)
        self.assertEqual(report["productStatus"], "OPEN")
        self.assertEqual(report["acceptedCases"], [])
        self.assertFalse(report["historicalPassInherited"])

    def test_old_version_lock_is_refused(self):
        lock = self.read("config/prd-lock.json")
        lock["version"] = "1.2"
        self.write("config/prd-lock.json", lock)
        with self.assertRaisesRegex(ValueError, "version pin"):
            current_prd.load(self.root)

    def test_rehashed_changed_plan_cannot_replace_fixed_current_pin(self):
        plan = self.read("config/execution-plan.json")
        plan["cases"].pop()
        self.repin_plan(plan)
        with self.assertRaisesRegex(ValueError, "identity was replaced"):
            current_prd.load(self.root)

    def test_missing_retired_id_is_not_silently_accepted(self):
        with self.structural_fixture(lambda plan: plan["retiredRequirements"].pop()):
            with self.assertRaisesRegex(ValueError, "retired requirement IDs"):
                current_prd.load(self.root)

    def test_retired_duty_cannot_be_reactivated(self):
        def reactivate(plan):
            plan["retiredRequirements"][0]["executable"] = True
        with self.structural_fixture(reactivate):
            with self.assertRaisesRegex(ValueError, "reactivated"):
                current_prd.load(self.root)

    def test_duplicate_case_does_not_satisfy_complete_case_count(self):
        def duplicate(plan):
            plan["cases"][-1] = dict(plan["cases"][0])
        with self.structural_fixture(duplicate):
            with self.assertRaisesRegex(ValueError, "duplicated current contract: cases"):
                current_prd.load(self.root)

    def test_old_demo_revision_still_requires_actual_v13_migration(self):
        plan = current_prd.load(self.root)
        with patch.object(current_prd, "load", return_value=plan):
            with self.assertRaisesRegex(ValueError, "PRD_MIGRATION_REQUIRED"):
                current_prd.require_current_scenario("DEMO-01", revision="1.2")
        report = current_prd.blocked("legacy-demo", self.root)
        self.assertFalse(report["executed"])
        self.assertFalse(report["allPassed"])
