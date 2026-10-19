"""The handoff must hand over empty slots, never plausible-looking ones."""
import unittest

from scenarios import handoff, matrix, validation


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

    def test_requirement_metadata_is_not_current_runtime_acceptance(self):
        self.assertFalse(self.built["completeCurrentContractLoaded"])
        self.assertFalse(self.built["baselinePassIsCurrentPass"])
        self.assertEqual(self.built["acceptedCases"], [])

    def test_current_semantic_acceptance_and_real_evidence_stay_open(self):
        self.assertEqual(self.built["currentSemanticAcceptance"], "OPEN")
        self.assertEqual(self.built["productStatus"], "OPEN")
        for scenario in self.built["scenarios"]:
            self.assertTrue(all(value == "NOT_RUN" for value in scenario["evidence"].values()))

    def test_the_remaining_obligations_come_from_the_matrix(self):
        self.assertEqual(sorted(self.built["remainingObligations"]),
                         ["T-%02d" % n for n in range(1, 85)])

    def test_an_unfilled_handoff_would_be_refused_as_evidence(self):
        """A checklist is not a result: feeding it back as evidence must fail."""
        outcome = validation.validate_result(self.built)
        self.assertFalse(outcome["accepted"])


if __name__ == "__main__":
    unittest.main()
