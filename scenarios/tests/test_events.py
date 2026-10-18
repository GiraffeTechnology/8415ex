"""The logical event contract, checked read-only over the domain's timeline.

This surface does not own the recorder, so these tests check what a reader can
genuinely establish: that the vocabulary accounts for what the domain records,
that correlation says which keys are really carried, that coverage never
presents a derivation or a local record as a chain observation, and that a
replay rebuilds the same view without moving anything twice.
"""
import unittest
from pathlib import Path

from exchange import fixtures as F
from scenarios import events

ROOT = str(Path(__file__).resolve().parents[2])

CURRENT_DOMAIN_KINDS = {
    "receipt-minted", "trading-resumed", "transfer-executed", "registration-submitted",
    "registration-result-idempotent", "registration-result", "registration-result-drained",
    "escrow-locked", "payment-attempt-started", "segment-release-attempt", "payment-enquiry",
    "gas-recorded", "rollback-opened", "rollback-advanced", "segment-refunded",
    "segment-refund-attempt", "asset-returned", "rollback-step-blocked",
    "asset-return-attempt", "late-result-conflict",
}
CURRENT_AUDIT_GROUPS = {
    "intent-decision", "transfer", "registration", "final-prefix", "funding", "rollback",
    "trading-recovery", "currency-admission", "eth-gas-admission", "remint", "reorg-recovery",
}


def _settled_chain():
    """A -> B -> C -> D, funded, two legs registered, one segment released."""
    exchange, clock = F.funded_chain_to_d()
    requests = F.submit_all(exchange)
    for position in (0, 1):
        F.confirm(exchange, requests[position], "res-%d" % position)
    exchange.release_segment("rcpt-8415-0001", 0,
                             F.release_authority(exchange, 0, "rel-0"))
    return exchange, clock


class Vocabulary(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.conformance = events.conformance(ROOT)

    def test_the_kinds_are_read_from_the_domain_source_not_from_a_list(self):
        found = events.domain_recorded_kinds(ROOT)
        self.assertTrue(found["readable"])
        self.assertIsNone(found["error"])
        self.assertIn("transfer-executed", found["kinds"])
        self.assertIn("registration-result-drained", found["kinds"])
        self.assertEqual(set(found["kinds"]), CURRENT_DOMAIN_KINDS)
        self.assertEqual(found["kindCount"], len(CURRENT_DOMAIN_KINDS))

    def test_every_kind_the_domain_records_is_accounted_for(self):
        self.assertEqual(self.conformance["undeclaredKindsRecorded"], [],
                         "the trail carries a kind this contract does not declare")
        self.assertTrue(self.conformance["accountedFor"])

    def test_a_kind_the_contract_needs_and_the_domain_lacks_is_named_not_hidden(self):
        self.assertEqual(self.conformance["declaredKindsNotRecorded"],
                         ["intent-accepted", "intent-refused"])

    def test_a_chain_only_kind_is_not_reported_as_an_unrecorded_defect(self):
        chain_only = {entry["kind"] for entry in events.CHAIN_ONLY_KINDS}
        self.assertEqual(chain_only, {"transfer-observed", "chain-reorg-observed"})
        for kind in sorted(chain_only):
            with self.subTest(kind=kind):
                self.assertNotIn(kind, self.conformance["declaredKindsNotRecorded"])

    def test_an_unreadable_domain_source_is_a_refusal_not_an_empty_answer(self):
        found = events.domain_recorded_kinds("/nonexistent-root-for-this-test")
        self.assertFalse(found["readable"])
        self.assertEqual(found["error"], "EX_LEDGER_SOURCE_UNREADABLE")
        broken = events.conformance("/nonexistent-root-for-this-test")
        self.assertFalse(broken["accountedFor"],
                         "nothing was read, so nothing is accounted for")

    def test_each_interface_gap_names_its_owner_and_the_next_step(self):
        self.assertEqual(self.conformance["interfaceGapCount"],
                         len(events.INTERFACE_GAPS))
        for gap in self.conformance["interfaceGaps"]:
            with self.subTest(gap=gap["gap"]):
                self.assertTrue(gap["neededFor"])
                self.assertTrue(gap["whyNotLocal"])
                self.assertTrue(gap["owner"])
                self.assertTrue(gap["nextStep"])

    def test_it_does_not_claim_to_enforce_the_vocabulary(self):
        self.assertIn("not an enforcement point",
                      " ".join(self.conformance["isNot"]))

    def test_the_contract_is_readable_without_a_run(self):
        contract = events.contract()
        self.assertEqual({group["group"] for group in contract["groups"]}, CURRENT_AUDIT_GROUPS)
        self.assertTrue(contract["readOnly"])
        self.assertTrue(contract["contractDigest"].startswith("0x"))
        report = events.build(root=ROOT)
        self.assertFalse(report["timelineRead"])
        self.assertIsNone(report["coverage"])
        self.assertIsNone(report["replay"])


class Correlation(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.exchange, _ = _settled_chain()
        cls.timeline = cls.exchange.receipt_timeline("rcpt-8415-0001")
        cls.asset_key = cls.exchange.receipt("rcpt-8415-0001").asset.key

    def test_every_key_is_present_on_every_event(self):
        for event in self.timeline:
            block = events.derive_correlation(event, "run-1", self.asset_key)
            with self.subTest(kind=event["kind"], sequence=event["sequence"]):
                for key in events.CORRELATION_KEYS + events.CHAIN_KEYS:
                    self.assertIn(key, block["correlation"],
                                  "an absent key and an unknown value must not "
                                  "read the same")

    def test_it_says_which_keys_the_domain_really_carries(self):
        block = events.derive_correlation(self.timeline[0], "run-1", self.asset_key)
        self.assertIn("receiptId", block["carriedByDomain"])
        self.assertEqual(block["resolvedHere"], ["assetKey", "runId"])
        self.assertTrue(block["derived"])

    def test_a_key_the_domain_does_not_carry_is_null_and_listed_as_missing(self):
        block = events.derive_correlation(self.timeline[0])
        self.assertIsNone(block["correlation"]["runId"])
        self.assertIsNone(block["correlation"]["txHash"])
        for key in events.CHAIN_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, block["missing"])

    def test_it_never_reports_a_local_event_as_observed_on_chain(self):
        for event in self.timeline:
            block = events.derive_correlation(event, "run-1", self.asset_key)
            with self.subTest(sequence=event["sequence"]):
                self.assertFalse(block["observedOnChain"])
                self.assertTrue(block["whyNotObserved"])

    def test_the_transfer_and_request_are_lifted_out_of_the_free_form_detail(self):
        transfers, requests = set(), set()
        for event in self.timeline:
            block = events.derive_correlation(event)["correlation"]
            transfers.add(block["transferId"])
            requests.add(block["requestId"])
        self.assertIn("transfer-ab", transfers)
        self.assertIn("req-leg-0", requests)

    def test_each_key_says_where_it_comes_from(self):
        block = events.derive_correlation(self.timeline[0])
        self.assertEqual(sorted(block["sources"]),
                         sorted(events.CORRELATION_KEYS + events.CHAIN_KEYS))
        self.assertIn("not carried by the domain", block["sources"]["runId"])


class Coverage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.exchange, _ = _settled_chain()
        cls.coverage = events.coverage(
            cls.exchange.receipt_timeline("rcpt-8415-0001"))

    def test_it_reports_all_current_groups_and_invents_none(self):
        self.assertEqual(self.coverage["groupCount"], len(CURRENT_AUDIT_GROUPS))
        self.assertEqual([entry["group"] for entry in self.coverage["groups"]],
                         [group["group"] for group in events.AUDIT_GROUPS])

    def test_unjoined_current_requirements_are_explicit_gaps_not_recorded_coverage(self):
        groups = {entry["group"]: entry for entry in self.coverage["groups"]}
        for name in ("currency-admission", "eth-gas-admission", "remint"):
            with self.subTest(group=name):
                self.assertEqual(groups[name]["status"], "not-recorded-interface-gap")
                self.assertTrue(groups[name]["whyNotLocal"])
                self.assertNotIn(name, self.coverage["recordedGroups"])

    def test_retired_physical_events_are_not_required_current_domain_events(self):
        self.assertTrue(set(events.RETIRED_PHYSICAL_KINDS).isdisjoint(events.DECLARED_KINDS))
        self.assertNotIn("redemption", CURRENT_AUDIT_GROUPS)
        self.assertEqual(events.conformance(ROOT)["retiredPhysicalKindsRecorded"], [])

    def test_every_group_has_exactly_one_status(self):
        placed = [group for groups in self.coverage["byStatus"].values()
                  for group in groups]
        self.assertEqual(sorted(placed),
                         sorted(entry["group"] for entry in self.coverage["groups"]))
        self.assertEqual(len(placed), len(set(placed)),
                         "the status buckets must not overlap")

    def test_a_group_whose_other_half_needs_a_chain_is_not_called_recorded(self):
        awaiting = self.coverage["groupsAwaitingChainObservation"]
        self.assertEqual(awaiting, ["reorg-recovery", "transfer"])
        for group in awaiting:
            with self.subTest(group=group):
                self.assertNotIn(group, self.coverage["recordedGroups"])
        transfer = {entry["group"]: entry
                    for entry in self.coverage["groups"]}["transfer"]
        self.assertTrue(transfer["localHalfObserved"],
                        "the submitted half really was recorded")
        self.assertTrue(transfer["whyNotLocal"])

    def test_a_derived_group_is_reported_as_derived_never_as_recorded(self):
        prefix = {entry["group"]: entry
                  for entry in self.coverage["groups"]}["final-prefix"]
        self.assertEqual(prefix["status"], "derived")
        self.assertEqual(prefix["declaredKinds"], [],
                         "the domain records no event for the prefix moving")
        self.assertEqual(prefix["derivedValue"],
                         self.exchange.holder_index("rcpt-8415-0001"))
        self.assertTrue(prefix["derivedBy"])
        self.assertNotIn("final-prefix", self.coverage["recordedGroups"])

    def test_a_group_that_simply_did_not_happen_is_kept_apart_from_one_needing_a_chain(self):
        self.assertIn("rollback", self.coverage["notObserved"])
        self.assertNotIn("rollback", self.coverage["groupsAwaitingChainObservation"])
        self.assertIn("reorg-recovery",
                      self.coverage["groupsAwaitingChainObservation"])
        self.assertNotIn("reorg-recovery", self.coverage["notObserved"])

    def test_no_undeclared_kind_was_observed(self):
        self.assertEqual(self.coverage["undeclaredKindsObserved"], [])

    def test_it_claims_neither_a_chain_observation_nor_an_acceptance_result(self):
        said = " ".join(self.coverage["isNot"])
        self.assertIn("not a chain observation", said)
        self.assertIn("not an acceptance result", said)
        self.assertIn("not a derivation presented as a record", said)

    def test_the_intent_group_cannot_be_evidenced_until_the_domain_records_it(self):
        intent = {entry["group"]: entry
                  for entry in self.coverage["groups"]}["intent-decision"]
        self.assertEqual(intent["status"], "not-observed")
        gaps = [gap["gap"] for gap in events.INTERFACE_GAPS]
        self.assertIn("no event is recorded when an intent is accepted or refused",
                      gaps)


class Replay(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.exchange, _ = _settled_chain()
        cls.timeline = cls.exchange.receipt_timeline("rcpt-8415-0001")
        cls.asset_key = cls.exchange.receipt("rcpt-8415-0001").asset.key

    def test_a_replay_consumes_every_event_in_order(self):
        state = events.replay(self.timeline, "run-1", self.asset_key)
        self.assertEqual(state["consumed"], len(self.timeline))
        self.assertEqual(state["duplicatesIgnored"], 0)
        self.assertTrue(state["sequential"])

    def test_retained_retired_history_is_labelled_and_replayed_without_reexecution(self):
        event = dict(self.timeline[0], kind="receipt-burned")
        state = events.replay([event, event])
        self.assertEqual(state["duplicatesIgnored"], 1)
        self.assertEqual(state["assetMovementCount"], 1)
        self.assertEqual(state["retiredPhysicalKinds"],
                         [{"kind": "receipt-burned", "sequence": event["sequence"], "executable": False}])
        self.assertEqual(state["undeclaredKinds"], [])
        coverage = events.coverage([event])
        self.assertEqual(coverage["retiredPhysicalKindsObserved"], ["receipt-burned"])
        self.assertNotIn("remint", coverage["recordedGroups"])

    def test_rebuilding_from_the_same_events_twice_gives_the_same_view(self):
        rebuild = events.rebuilt_identically(self.timeline, "run-1", self.asset_key)
        self.assertTrue(rebuild["identical"])
        self.assertEqual(rebuild["digest"], rebuild["repeatedDigest"])

    def test_repeated_consumption_moves_no_asset_and_no_money_twice(self):
        rebuild = events.rebuilt_identically(self.timeline, "run-1", self.asset_key)
        self.assertGreater(rebuild["assetMovementsOnce"], 0)
        self.assertGreater(rebuild["fundMovementsOnce"], 0)
        self.assertEqual(rebuild["assetMovementsOnRepeat"],
                         rebuild["assetMovementsOnce"])
        self.assertEqual(rebuild["fundMovementsOnRepeat"],
                         rebuild["fundMovementsOnce"])
        self.assertEqual(rebuild["duplicatesIgnoredOnRepeat"], len(self.timeline))

    def test_two_events_differing_only_in_a_free_form_detail_are_one_event(self):
        first = dict(self.timeline[0])
        again = dict(first, detail=dict(first["detail"], note="re-delivered"))
        state = events.replay([first, again])
        self.assertEqual(state["consumed"], 1)
        self.assertEqual(state["duplicatesIgnored"], 1)

    def test_a_successful_release_is_counted_as_money_moved_once(self):
        state = events.replay(self.timeline, "run-1", self.asset_key)
        released = [entry for entry in state["fundMovements"]
                    if entry["kind"] == "segment-release-attempt"]
        self.assertEqual(len(released), 1)
        self.assertEqual(state["attemptsThatMovedNothing"], [])

    def test_a_failed_release_attempt_is_not_counted_as_money_moved(self):
        exchange, _ = F.funded_chain_to_d(outcomes={"release:escrow-ab": "failed"})
        requests = F.submit_all(exchange)
        F.confirm(exchange, requests[0], "res-0")
        outcome = exchange.release_segment(
            "rcpt-8415-0001", 0, F.release_authority(exchange, 0, "rel-0"))
        self.assertFalse(outcome["released"])
        state = events.replay(exchange.receipt_timeline("rcpt-8415-0001"))
        self.assertEqual({entry["kind"] for entry in state["fundMovements"]},
                         {"escrow-locked"})
        self.assertEqual(state["attemptsThatMovedNothingCount"], 1)
        self.assertEqual(state["attemptsThatMovedNothing"][0]["kind"],
                         "segment-release-attempt")

    def test_an_attempt_with_a_completed_counterpart_is_not_double_counted(self):
        # A refund records its completion separately, so counting the attempt
        # as well would report the same money moving twice.
        self.assertIn("segment-refunded", events.MOVEMENT_KINDS)
        self.assertNotIn("segment-refund-attempt", events.MOVEMENT_KINDS)
        self.assertNotIn("segment-refund-attempt", events.CONDITIONAL_MOVEMENT_KINDS)
        self.assertNotIn("asset-return-attempt", events.MOVEMENT_KINDS)

    def test_the_rebuilt_final_prefix_matches_the_live_one(self):
        state = events.replay(self.timeline, "run-1", self.asset_key)
        self.assertEqual(state["finalPrefix"],
                         self.exchange.holder_index("rcpt-8415-0001"))

    def test_the_rebuilt_index_groups_events_by_transfer_and_request(self):
        state = events.replay(self.timeline, "run-1", self.asset_key)
        self.assertIn("transfer-ab", state["byTransfer"])
        self.assertIn("req-leg-0", state["byRequest"])

    def test_an_out_of_order_delivery_is_reported_not_silently_reordered(self):
        state = events.replay([self.timeline[2], self.timeline[1]])
        self.assertFalse(state["sequential"])
        self.assertEqual(state["outOfOrder"], [self.timeline[1]["sequence"]])

    def test_an_undeclared_kind_is_reported_rather_than_raised(self):
        # This layer reads a trail it does not write: refusing would make an
        # unaccounted kind look like a crash in the reader.
        state = events.replay([dict(self.timeline[0], kind="made-up")])
        self.assertEqual(state["undeclaredKindCount"], 1)
        self.assertEqual(state["undeclaredKinds"][0]["kind"], "made-up")
        self.assertEqual(state["consumed"], 1)

    def test_a_correlation_gap_is_counted_rather_than_hidden(self):
        state = events.replay(self.timeline)
        self.assertEqual(state["correlationGaps"].get("runId"), len(self.timeline))
        self.assertEqual(state["correlationGaps"].get("assetKey"),
                         len(self.timeline))
        self.assertIsNone(state["correlationGaps"].get("receiptId"))

    def test_the_whole_report_reads_a_real_timeline_when_given_one(self):
        report = events.build(self.exchange, "rcpt-8415-0001", ROOT, "run-1")
        self.assertTrue(report["timelineRead"])
        self.assertEqual(report["receiptId"], "rcpt-8415-0001")
        self.assertEqual(report["coverage"]["eventCount"], len(self.timeline))
        self.assertTrue(report["rebuild"]["identical"])


if __name__ == "__main__":
    unittest.main()

