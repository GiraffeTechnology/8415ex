"""Remote-only ABI observation fixtures; no RPC, native funds or chain acceptance."""
from copy import deepcopy
import json
import unittest
from exchange.register_projection import register_projection
from exchange.register_projection_page import render_register, LABELS
from exchange.workbench import RuntimeBinding
from integration.test_nft_detail import OriginalReadOnlyDomain


def word(value):
    return "0x" + format(value, "064x")


def entry(version, effective, superseded, holder=1, position=7):
    return {"version": version, "effectiveAt": effective, "supersededAt": superseded,
            "recordCommitment": word(version), "previousCommitment": word(version - 1),
            "registryReference": word(100 + version), "holder": "0x" + format(holder, "040x"),
            "holderPosition": position}


def observation():
    first, latest = entry(1, 100, 200), entry(2, 200, 0, holder=2, position=19)
    return {"projectionInterface": "0x6309e170", "projectionSupported": True, "readStatus": "succeeded",
            "observedBlock": {"number": 999, "hash": word(999), "timestamp": 150},
            "queryTime": 150, "firstEntry": first, "currentEntry": latest,
            "entryAsOf": deepcopy(first), "holderAsOf": first["holder"],
            "queryStatus": "succeeded", "isFinalAsOf": True}


class RegisterQueryTime(unittest.TestCase):
    def test_future_latest_entry_is_separate_from_effective_holder_at_query(self):
        result = register_projection({"registerObservation": observation()})
        self.assertEqual(result["latestTiming"], "future-effective")
        self.assertEqual(result["latestAdmitted"]["holderPosition"], 19)
        self.assertEqual(result["holderAtQuery"]["holderPosition"], 7)
        self.assertEqual(result["holderAtQuery"]["version"], 1)
        self.assertTrue(result["queryIsObservedBlockTime"])

    def test_latest_effective_time_is_provisional_not_final_even_without_a_gap(self):
        value = observation()
        value.update(queryTime=200, entryAsOf=deepcopy(value["currentEntry"]),
                     holderAsOf=value["currentEntry"]["holder"], isFinalAsOf=False)
        result = register_projection({"registerObservation": value, "gap": "closed"})
        self.assertEqual(result["historicalFinality"], "provisional")
        self.assertFalse(result["isFinalAsOf"])
        self.assertFalse(result["queryIsObservedBlockTime"])

    def test_pre_first_query_must_revert_without_a_fabricated_holder(self):
        value = observation()
        value.update(queryTime=99, entryAsOf=None, holderAsOf=None, queryStatus="reverted", isFinalAsOf=False)
        result = register_projection({"registerObservation": value})
        self.assertEqual(result["queryStatus"], "reverted")
        self.assertIsNone(result["holderAtQuery"])
        self.assertFalse(result["isFinalAsOf"])
        self.assertEqual(result["historicalFinality"], "unresolved-before-first")
        value["holderAsOf"] = value["firstEntry"]["holder"]
        self.assertEqual(register_projection({"registerObservation": value}), {"status": "unavailable"})

    def test_same_holder_confirmation_keeps_position_and_can_advance_historical_finality(self):
        value = observation()
        value["currentEntry"].update(holder=value["firstEntry"]["holder"], holderPosition=7)
        result = register_projection({"registerObservation": value})
        self.assertEqual(result["latestAdmitted"]["version"], 2)
        self.assertEqual(result["latestAdmitted"]["holderPosition"], 7)
        self.assertTrue(result["isFinalAsOf"])

    def test_mismatched_holder_finality_or_adjacent_linkage_is_unavailable(self):
        for field in ("holder", "finality", "link", "time"):
            value = observation()
            if field == "holder":
                value["holderAsOf"] = value["currentEntry"]["holder"]
            elif field == "finality":
                value["isFinalAsOf"] = False
            elif field == "link":
                value["currentEntry"]["previousCommitment"] = word(77)
            else:
                value["currentEntry"]["effectiveAt"] = 100
            self.assertEqual(register_projection({"registerObservation": value}), {"status": "unavailable"})

    def test_missing_unsupported_and_failed_observations_are_not_zero_records(self):
        self.assertEqual(register_projection({}), {"status": "not-provided"})
        value = observation()
        value["projectionSupported"] = False
        self.assertEqual(register_projection({"registerObservation": value}), {"status": "unsupported"})
        value["projectionSupported"], value["readStatus"] = True, "failed"
        self.assertEqual(register_projection({"registerObservation": value}), {"status": "unavailable"})

    def test_original_detail_verification_precedes_register_projection_and_financial_state_is_untouched(self):
        row = {"receiptId": "private-r", "currentPosition": 20, "registerObservation": observation()}
        binding = RuntimeBinding(OriginalReadOnlyDomain(), "private-r", read_details=lambda rid: row,
                                 verify_details=lambda *args: False)
        self.assertEqual(binding.public_detail()["registerProjection"], {"status": "unavailable"})
        binding.verify_details = lambda *args: True
        detail = binding.public_detail()
        self.assertEqual(detail["positions"], {"current": 20, "owner": 7, "holder": 1})
        self.assertFalse(detail["ordinaryTransfer"]["gapEqualityFinalityGateApplied"])
        self.assertEqual(detail["ordinaryTransfer"]["executionEligibility"], "not-evaluated")

    def test_six_locale_renderer_exposes_times_and_positions_without_holder_addresses(self):
        projection = register_projection({"registerObservation": observation()})
        before = deepcopy(projection)
        for locale, labels in LABELS.items():
            page = render_register({"registerProjection": projection}, locale)
            self.assertIn(labels[13], page)
            self.assertIn(labels[3], page)
            self.assertIn(labels[17], page)
            self.assertNotIn("0x" + format(1, "040x"), page)
            self.assertNotIn("0x" + format(2, "040x"), page)
        self.assertEqual(projection, before)
        self.assertNotIn('"holder":', json.dumps(projection))
