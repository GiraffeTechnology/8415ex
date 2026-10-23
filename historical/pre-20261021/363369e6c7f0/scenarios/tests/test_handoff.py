"""The handoff must hand over empty slots, never plausible-looking ones."""
import unittest

from scenarios import current_prd, handoff, matrix, validation


class Handoff(unittest.TestCase):

    def setUp(self):
        self.built = handoff.build(matrix.build({"commit": "a" * 40}, {"runId": "r"}))

    def test_every_evidence_slot_starts_not_run(self):
        self.assertTrue(self.built["evidenceSlots"])
        for slot in self.built["evidenceSlots"]:
            self.assertEqual(slot["status"], "NOT_RUN", slot["slot"])
            self.assertTrue(slot["requires"])

    def test_the_required_slots_are_all_present(self):
        names = {slot["slot"] for slot in self.built["evidenceSlots"]}
        for required in ("deployedHead", "chainId", "verifiedAddresses", "transactionHashes",
                         "receipts", "blockIdentities", "confirmationPolicy", "events",
                         "perSegmentReconciliation", "uiAssertions"):
            self.assertIn(required, names)

    def test_every_scenario_has_its_own_empty_evidence(self):
        self.assertEqual(len(self.built["scenarios"]), 6)
        for scenario in self.built["scenarios"]:
            self.assertTrue(scenario["steps"])
            self.assertTrue(scenario["evidence"])
            for status in scenario["evidence"].values():
                self.assertEqual(status, "NOT_RUN")

    def test_the_report_does_not_invent_configured_execution_inputs(self):
        slots = {row["slot"]: row for row in self.built["evidenceSlots"]}
        for required in ("deployedHead", "deployedTree", "requiredCiRun",
                         "verifiedAddresses", "transactionHashes", "uiAssertions"):
            self.assertEqual(slots[required]["status"], handoff.NOT_RUN)
        self.assertEqual(self.built["evidenceStatus"], "NOT_VERIFIED")
        self.assertTrue(self.built["existingOwnerDependencies"])
        for dependency in self.built["existingOwnerDependencies"]:
            self.assertNotEqual(dependency["status"], "VERIFIED")
        self.assertNotIn("rpcEndpoint", self.built)
        self.assertNotIn("privateKey", self.built)

    def test_requirement_metadata_cannot_be_promoted_to_current_acceptance(self):
        self.assertEqual(self.built["evidenceKind"], "REQUIREMENTS_ONLY")
        self.assertEqual(self.built["productStatus"], "OPEN")
        self.assertEqual(self.built["acceptedCases"], [])
        self.assertFalse(self.built["historicalPassInherited"])
        self.assertFalse(self.built["baselinePassIsCurrentPass"])
        self.assertEqual(self.built["currentSemanticAcceptance"], "OPEN")
        self.assertFalse(self.built["completeCurrentContractLoaded"])
        self.assertEqual(self.built["coverage"], "HISTORICAL_PUBLISHED_BASELINE_ONLY")
        self.assertEqual(self.built["currentCompletePRDVersion"], "1.4")

    def test_remaining_obligations_preserve_every_case_in_the_actual_baseline(self):
        plan = current_prd.load()
        cases = [row["id"] for row in plan["cases"]]
        self.assertEqual(self.built["remainingObligations"], cases)
        self.assertEqual(len(cases), len(set(cases)))
        self.assertEqual(len(cases), 68)
        self.assertEqual(self.built["publishedBaselineVersion"], "1.3")
        self.assertFalse(self.built["completeCurrentContractLoaded"])

    def test_a_supplied_green_legacy_matrix_does_not_accept_current_cases(self):
        legacy = {"allCasesSound": True, "unsoundCases": [], "rows": []}
        report = handoff.build(legacy)
        self.assertEqual(report["acceptedCases"], [])
        self.assertEqual(report["productStatus"], "OPEN")
        self.assertFalse(report["historicalPassInherited"])
        self.assertTrue(report["remainingObligations"])

    def test_an_unfilled_handoff_would_be_refused_as_evidence(self):
        """A checklist is not a result: feeding it back as evidence must fail."""
        outcome = validation.validate_result(self.built)
        self.assertFalse(outcome["accepted"])


if __name__ == "__main__":
    unittest.main()
