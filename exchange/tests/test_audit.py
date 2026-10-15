"""The logical event contract: vocabulary, correlation, coverage and replay.

PRD 10.2 asks for three checkable things, and each one is checked against the
events the domain really writes rather than against a hand-written sample.
"""
import unittest
from dataclasses import replace

from exchange import audit, fixtures as F
from exchange.errors import DomainError

CHAIN = {"chainId": 11155111, "txHash": "0x" + "ab" * 32,
         "blockHash": "0x" + "cd" * 32, "logIndex": 3}


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

    def test_every_recorded_kind_is_declared(self):
        exchange, _ = _settled_chain()
        timeline = exchange.receipt_timeline("rcpt-8415-0001")
        self.assertTrue(timeline)
        for event in timeline:
            with self.subTest(kind=event["kind"]):
                self.assertIn(event["kind"], audit.EVENT_KINDS)

    def test_an_undeclared_kind_is_refused_rather_than_silently_recorded(self):
        exchange, _ = F.minted()
        with self.assertRaises(DomainError) as refused:
            exchange._record("rcpt-8415-0001", "transfer-excuted", {})
        self.assertEqual(refused.exception.code, "EX_EVENT_KIND_REFUSED")

    def test_an_ancillary_kind_is_recordable_but_counts_as_no_coverage(self):
        ancillary = {entry["kind"] for entry in audit.ANCILLARY_KINDS}
        grouped = {kind for group in audit.AUDIT_GROUPS for kind in group["kinds"]}
        self.assertTrue(ancillary)
        self.assertEqual(ancillary & grouped, set())
        self.assertTrue(ancillary <= set(audit.EVENT_KINDS))

    def test_the_declared_contract_is_readable_without_a_run(self):
        contract = audit.contract()
        self.assertEqual(contract["declaredKindCount"], len(audit.EVENT_KINDS))
        self.assertEqual(len(contract["groups"]), 8)
        self.assertTrue(contract["contractDigest"].startswith("0x"))
        self.assertIn("not an ABI", " ".join(contract["isNot"]))


class Correlation(unittest.TestCase):

    def test_every_event_carries_every_correlation_key(self):
        exchange, _ = _settled_chain()
        for event in exchange.receipt_timeline("rcpt-8415-0001"):
            with self.subTest(kind=event["kind"], sequence=event["sequence"]):
                for key in audit.CORRELATION_KEYS + audit.CHAIN_KEYS:
                    self.assertIn(key, event["correlation"],
                                  "an absent key and an unknown value must not "
                                  "read the same")

    def test_an_unknown_value_is_null_not_omitted_and_not_a_placeholder(self):
        exchange, _ = F.minted()
        event = exchange.receipt_timeline("rcpt-8415-0001")[0]
        self.assertIsNone(event["correlation"]["runId"],
                          "no run id was supplied, so none is invented")
        self.assertIsNone(event["correlation"]["txHash"])
        self.assertFalse(event["correlation"]["observedOnChain"])
        self.assertIsNone(event["correlation"]["chainPosition"])

    def test_a_supplied_run_id_correlates_every_event_of_that_run(self):
        run = F.Exchange(F.ManualClock(), run_id="local-run-1")
        run.mint(F.receipt())
        for event in run.receipt_timeline("rcpt-8415-0001"):
            self.assertEqual(event["correlation"]["runId"], "local-run-1")

    def test_the_asset_the_event_belongs_to_is_on_the_event(self):
        exchange, _ = F.minted()
        event = exchange.receipt_timeline("rcpt-8415-0001")[0]
        receipt = exchange.receipt("rcpt-8415-0001")
        self.assertEqual(event["correlation"]["assetKey"], list(receipt.asset.key))

    def test_the_transfer_and_request_are_lifted_out_of_the_detail(self):
        exchange, _ = _settled_chain()
        timeline = exchange.receipt_timeline("rcpt-8415-0001")
        transfers = {event["correlation"]["transferId"] for event in timeline}
        requests = {event["correlation"]["requestId"] for event in timeline}
        self.assertIn("transfer-ab", transfers)
        self.assertIn("req-leg-0", requests)

    def test_a_malformed_chain_position_is_refused_field_by_field(self):
        for key, bad, code in (
                ("chainId", -1, "EX_EVENT_CHAIN_ID_REFUSED"),
                ("chainId", True, "EX_EVENT_CHAIN_ID_REFUSED"),
                ("txHash", "0xAB", "EX_EVENT_TX_HASH_REFUSED"),
                ("blockHash", "cd" * 32, "EX_EVENT_BLOCK_HASH_REFUSED"),
                ("logIndex", True, "EX_EVENT_LOG_INDEX_REFUSED"),
                ("logIndex", "3", "EX_EVENT_LOG_INDEX_REFUSED")):
            with self.subTest(key=key, value=bad):
                with self.assertRaises(DomainError) as refused:
                    audit.correlation(chain=dict(CHAIN, **{key: bad}))
                self.assertEqual(refused.exception.code, code)

    def test_an_unknown_chain_key_is_refused_not_ignored(self):
        with self.assertRaises(DomainError) as refused:
            audit.correlation(chain={"txIndex": 1})
        self.assertEqual(refused.exception.code, "EX_EVENT_CHAIN_KEY_REFUSED")

    def test_a_complete_position_reports_itself_as_observed(self):
        block = audit.correlation(chain=CHAIN)
        self.assertTrue(block["observedOnChain"])
        self.assertEqual(block["chainPosition"],
                         "%s/%s/%d" % (CHAIN["blockHash"], CHAIN["txHash"], 3))


class ChainObservations(unittest.TestCase):
    """The two groups that cannot be evidenced locally, and must not be faked."""

    def test_an_incomplete_position_cannot_be_recorded_as_an_observation(self):
        exchange, _ = F.minted()
        for missing in sorted(CHAIN):
            partial = {key: value for key, value in CHAIN.items() if key != missing}
            with self.subTest(missing=missing):
                with self.assertRaises(DomainError) as refused:
                    exchange.record_chain_observation(
                        "rcpt-8415-0001", "transfer-observed", partial)
                self.assertEqual(refused.exception.code,
                                 "EX_CHAIN_OBSERVATION_INCOMPLETE")

    def test_only_the_two_observation_kinds_go_through_this_path(self):
        exchange, _ = F.minted()
        with self.assertRaises(DomainError) as refused:
            exchange.record_chain_observation("rcpt-8415-0001", "transfer-executed", CHAIN)
        self.assertEqual(refused.exception.code, "EX_EVENT_KIND_REFUSED")

    def test_a_complete_position_is_recorded_with_its_chain_fields(self):
        exchange, _ = F.minted()
        exchange.record_chain_observation("rcpt-8415-0001", "transfer-observed", CHAIN,
                                          {"transferId": "transfer-ab"})
        event = exchange.receipt_timeline("rcpt-8415-0001")[-1]
        self.assertEqual(event["kind"], "transfer-observed")
        self.assertTrue(event["correlation"]["observedOnChain"])
        self.assertEqual(event["correlation"]["txHash"], CHAIN["txHash"])
        self.assertEqual(event["correlation"]["transferId"], "transfer-ab")


class Coverage(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.exchange, _ = _settled_chain()
        cls.coverage = cls.exchange.audit_coverage("rcpt-8415-0001")

    def test_it_reports_all_eight_groups_and_invents_none(self):
        self.assertEqual(self.coverage["groupCount"], 8)
        self.assertEqual([entry["group"] for entry in self.coverage["groups"]],
                         [group["group"] for group in audit.AUDIT_GROUPS])

    def test_no_undeclared_kind_was_observed(self):
        self.assertEqual(self.coverage["undeclaredKindsObserved"], [])

    def test_the_locally_evidenced_groups_are_evidenced_by_this_run(self):
        for entry in self.coverage["groups"]:
            if entry["group"] in ("registration", "final-prefix", "funding"):
                with self.subTest(group=entry["group"]):
                    self.assertTrue(entry["anyObserved"])

    def test_a_group_needing_a_chain_is_named_with_its_reason_not_counted(self):
        needing = {entry["group"]: entry for entry in self.coverage["groups"]
                   if not entry["locallyEvidenced"]}
        self.assertEqual(sorted(needing), ["reorg-recovery", "transfer"])
        for group, entry in sorted(needing.items()):
            with self.subTest(group=group):
                self.assertFalse(entry["allObserved"],
                                 "a locally produced record is not an observation")
                self.assertTrue(entry["whyNotLocal"])
        self.assertEqual(self.coverage["notLocallyEvidenceable"],
                         ["reorg-recovery", "transfer"])

    def test_partly_observed_is_kept_apart_from_fully_observed(self):
        self.assertIn("transfer", self.coverage["partlyObserved"],
                      "the submitted half is local; the observed half is not")
        self.assertNotIn("transfer", self.coverage["fullyObserved"])

    def test_it_claims_neither_a_chain_observation_nor_an_acceptance_result(self):
        said = " ".join(self.coverage["isNot"])
        self.assertIn("not a chain observation", said)
        self.assertIn("not an acceptance result", said)

    def test_the_intent_group_is_evidenced_once_a_decision_is_recorded(self):
        exchange, _ = F.minted()
        before = exchange.audit_coverage("rcpt-8415-0001")
        groups = {entry["group"]: entry for entry in before["groups"]}
        self.assertFalse(groups["intent-decision"]["anyObserved"])
        F.hop(exchange, F.A, F.B, 1, "transfer-ab", "session-a", "session-b")
        decided = exchange.decide_intent("sell-ab")
        self.assertTrue(decided["recorded"])
        after = exchange.audit_coverage("rcpt-8415-0001")
        groups = {entry["group"]: entry for entry in after["groups"]}
        self.assertTrue(groups["intent-decision"]["anyObserved"])


class IntentDecisions(unittest.TestCase):

    def test_validating_an_intent_records_nothing(self):
        exchange, _ = F.minted()
        F.hop(exchange, F.A, F.B, 1, "transfer-ab", "session-a", "session-b")
        before = len(exchange.receipt_timeline("rcpt-8415-0001"))
        exchange.validate_intent("sell-ab")
        exchange.validate_intent("sell-ab")
        self.assertEqual(len(exchange.receipt_timeline("rcpt-8415-0001")), before,
                         "a read must not append to the audit trail")

    def test_a_refusal_is_recorded_with_its_reasons_not_as_an_acceptance(self):
        exchange, clock = F.minted()
        F.hop(exchange, F.A, F.B, 1, "transfer-ab", "session-a", "session-b")
        # Past the intent's own expiry, so the decision is a refusal.
        decision = exchange.decide_intent("sell-ab", now=2_000_000_000)
        self.assertFalse(decision["executable"])
        self.assertTrue(decision["reasons"])
        event = exchange.receipt_timeline("rcpt-8415-0001")[-1]
        self.assertEqual(event["kind"], "intent-refused")
        self.assertEqual(event["detail"]["reasons"], list(decision["reasons"]))

    def test_an_intent_for_an_unheld_asset_is_unrecorded_with_the_reason(self):
        exchange, _ = F.minted()
        elsewhere = replace(F.asset(), token_id=F.TOKEN_ID + 1)
        intent = replace(F.intent("sell-x", "sell", F.A, "auth-x", F.B, 1),
                         asset=elsewhere)
        exchange.submit_intent(intent)
        decision = exchange.decide_intent("sell-x")
        self.assertFalse(decision["recorded"])
        self.assertIn("EX_ASSET_UNKNOWN", decision["notRecordedBecause"])


class Replay(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.exchange, _ = _settled_chain()
        cls.timeline = cls.exchange.receipt_timeline("rcpt-8415-0001")

    def test_a_replay_consumes_every_event_in_order(self):
        state = audit.replay(self.timeline)
        self.assertEqual(state["consumed"], len(self.timeline))
        self.assertEqual(state["duplicatesIgnored"], 0)
        self.assertTrue(state["sequential"])

    def test_rebuilding_from_the_same_events_twice_gives_the_same_view(self):
        rebuild = self.exchange.audit_replay("rcpt-8415-0001")
        self.assertTrue(rebuild["identical"])
        self.assertEqual(rebuild["digest"], rebuild["repeatedDigest"])

    def test_repeated_consumption_moves_no_asset_and_no_money_twice(self):
        rebuild = self.exchange.audit_replay("rcpt-8415-0001")
        self.assertGreater(rebuild["assetMovementsOnce"], 0)
        self.assertGreater(rebuild["fundMovementsOnce"], 0)
        self.assertEqual(rebuild["assetMovementsOnRepeat"],
                         rebuild["assetMovementsOnce"])
        self.assertEqual(rebuild["fundMovementsOnRepeat"],
                         rebuild["fundMovementsOnce"])
        self.assertEqual(rebuild["duplicatesIgnoredOnRepeat"], len(self.timeline))

    def test_two_events_differing_only_in_detail_are_the_same_event(self):
        first = dict(self.timeline[0])
        second = dict(first, detail=dict(first["detail"], note="re-delivered"))
        state = audit.replay([first, second])
        self.assertEqual(state["consumed"], 1)
        self.assertEqual(state["duplicatesIgnored"], 1)

    def test_two_genuinely_different_events_are_not_collapsed(self):
        state = audit.replay(self.timeline)
        self.assertEqual(state["consumed"], len(self.timeline))
        self.assertEqual(sum(state["kindCounts"].values()), len(self.timeline))

    def test_the_rebuilt_final_prefix_matches_the_live_one(self):
        state = audit.replay(self.timeline)
        self.assertEqual(state["finalPrefix"],
                         self.exchange.holder_index("rcpt-8415-0001"))

    def test_the_rebuilt_index_groups_events_by_transfer_and_request(self):
        state = audit.replay(self.timeline)
        self.assertIn("transfer-ab", state["byTransfer"])
        self.assertIn("req-leg-0", state["byRequest"])

    def test_an_out_of_order_delivery_is_reported_not_silently_reordered(self):
        shuffled = [self.timeline[2], self.timeline[1]]
        state = audit.replay(shuffled)
        self.assertFalse(state["sequential"])
        self.assertEqual(state["outOfOrder"], [self.timeline[1]["sequence"]])

    def test_an_undeclared_kind_in_a_replayed_stream_is_refused(self):
        with self.assertRaises(DomainError) as refused:
            audit.replay([dict(self.timeline[0], kind="made-up")])
        self.assertEqual(refused.exception.code, "EX_EVENT_KIND_REFUSED")

    def test_a_successful_release_is_a_fund_movement(self):
        state = audit.replay(self.timeline)
        released = [entry for entry in state["fundMovements"]
                    if entry["kind"] == "segment-release-attempt"]
        self.assertEqual(len(released), 1,
                         "the released segment moved money once")
        self.assertEqual(state["attemptsThatMovedNothing"], [])

    def test_a_failed_release_attempt_is_not_counted_as_money_moved(self):
        exchange, _ = F.funded_chain_to_d(outcomes={"release:escrow-ab": "failed"})
        requests = F.submit_all(exchange)
        F.confirm(exchange, requests[0], "res-0")
        outcome = exchange.release_segment(
            "rcpt-8415-0001", 0, F.release_authority(exchange, 0, "rel-0"))
        self.assertFalse(outcome["released"])
        state = audit.replay(exchange.receipt_timeline("rcpt-8415-0001"))
        self.assertEqual([entry["kind"] for entry in state["fundMovements"]],
                         ["escrow-locked"] * len(state["fundMovements"]))
        self.assertEqual(state["attemptsThatMovedNothingCount"], 1)
        self.assertEqual(state["attemptsThatMovedNothing"][0]["kind"],
                         "segment-release-attempt")

    def test_an_attempt_with_a_completed_counterpart_is_not_double_counted(self):
        # A refund records its completion separately, so counting the attempt
        # as well would report the same money moving twice.
        self.assertIn("segment-refunded", audit.MOVEMENT_KINDS)
        self.assertNotIn("segment-refund-attempt", audit.MOVEMENT_KINDS)
        self.assertNotIn("segment-refund-attempt", audit.CONDITIONAL_MOVEMENT_KINDS)
        self.assertNotIn("asset-return-attempt", audit.MOVEMENT_KINDS)

    def test_a_correlation_gap_is_counted_rather_than_hidden(self):
        state = audit.replay(self.timeline)
        # No run id was supplied to the fixture, so every event reports the gap.
        self.assertEqual(state["correlationGaps"].get("runId"), len(self.timeline))
        self.assertIsNone(state["correlationGaps"].get("receiptId"))


if __name__ == "__main__":
    unittest.main()
