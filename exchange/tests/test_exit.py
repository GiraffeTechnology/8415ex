"""T-24, T-25, T-32, T-33: the trading deadline, exit eligibility and the burn."""
import unittest

from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.exit import EXIT_STEPS, REQUIRED_OTHER_CHECKS
from exchange.rollback import rollback_binding


class DeadlineBoundary(unittest.TestCase):
    """T-24: the boundary is exact, and in-flight work continues under its rules."""

    def setUp(self):
        self.exchange, self.clock = F.exit_exchange()
        self.stop = self.exchange.receipt("rcpt-8415-0001").trade_stop_at

    def test_the_mint_time_stop_instant_is_preserved_exactly(self):
        state = self.exchange.evaluate_deadline("rcpt-8415-0001")
        self.assertEqual(state["tradeStopAt"], self.stop)
        self.assertIsInstance(state["tradeStopAt"], int)

    def test_the_instant_before_the_stop_still_accepts_a_trade(self):
        self.clock.now = self.stop - 1
        state = self.exchange.evaluate_deadline("rcpt-8415-0001")
        self.assertFalse(state["pastDeadline"])
        self.assertTrue(state["newTradesAccepted"])
        escrow, leg = F.funded_hop(self.exchange, F.A, F.B, 1, "transfer-ab",
                                   "session-a", "session-b", price=F.PRICE_AB,
                                   now=self.stop - 1, expires_at=self.stop + 1)
        self.assertEqual(leg.leg_index, 0)

    def test_the_stop_instant_itself_refuses_a_new_trade(self):
        self.clock.now = self.stop
        state = self.exchange.evaluate_deadline("rcpt-8415-0001")
        self.assertTrue(state["pastDeadline"])
        self.assertFalse(state["newTradesAccepted"])
        with self.assertRaises(DomainError) as caught:
            F.funded_hop(self.exchange, F.A, F.B, 1, "transfer-late",
                         "session-a", "session-b", price=F.PRICE_AB, now=self.stop,
                         expires_at=self.stop + 1)
        self.assertIn(caught.exception.code, ("EX_MATCH_UNEXECUTABLE", "EX_TRADE_WINDOW_CLOSED"))
        self.assertEqual(self.exchange.owner_index("rcpt-8415-0001"), 0)

    def test_an_in_flight_registration_continues_after_the_deadline(self):
        F.funded_hop(self.exchange, F.A, F.B, 1, "transfer-ab", "session-a", "session-b",
                     price=F.PRICE_AB)
        request, _ = self.exchange.submit_registration("rcpt-8415-0001", 0, "req-leg-0", 86_400)
        self.clock.now = self.stop
        state = self.exchange.evaluate_deadline("rcpt-8415-0001")
        self.assertEqual(state["inFlightRegistrationLegs"], (0,))
        F.confirm(self.exchange, request, "res-ab")
        self.assertEqual(self.exchange.holder_index("rcpt-8415-0001"), 1)

    def test_an_unfinished_suffix_after_the_deadline_returns_to_the_confirmed_holder(self):
        exchange, clock = F.rollback_chain_to_d()
        requests = F.submit_all(exchange)
        F.confirm(exchange, requests[0], "res-ab")
        clock.now = exchange.receipt("rcpt-8415-0001").trade_stop_at
        state = exchange.evaluate_deadline("rcpt-8415-0001")
        self.assertEqual(state["unfinishedSuffixReturnsTo"], F.B)
        boundary = exchange.deadline_boundary("rcpt-8415-0001")
        self.assertEqual((boundary["boundaryIndex"], boundary["boundaryAccount"]), (1, F.B))
        authority = F.rollback_authority(
            exchange, 1, "rb-deadline", boundary_account=F.B,
            binding=rollback_binding(exchange.receipt("rcpt-8415-0001").asset,
                                     "rcpt-8415-0001", 1, F.B, (1, 2)))
        exchange.begin_rollback("rcpt-8415-0001", 1, authority, trigger="deadline")
        report = exchange.advance_rollback("rcpt-8415-0001")
        self.assertTrue(report["complete"])
        self.assertEqual(exchange.owner_of("rcpt-8415-0001"), F.B)
        self.assertEqual(report["affectedLegs"], (1, 2))

    def test_a_deadline_rollback_before_the_deadline_is_refused(self):
        exchange, _ = F.rollback_chain_to_d()
        requests = F.submit_all(exchange)
        F.confirm(exchange, requests[0], "res-ab")
        authority = F.rollback_authority(
            exchange, 1, "rb-early", boundary_account=F.B,
            binding=rollback_binding(exchange.receipt("rcpt-8415-0001").asset,
                                     "rcpt-8415-0001", 1, F.B, (1, 2)))
        with self.assertRaises(DomainError) as caught:
            exchange.begin_rollback("rcpt-8415-0001", 1, authority, trigger="deadline")
        self.assertEqual(caught.exception.code, "EX_ROLLBACK_TRIGGER_REFUSED")

    def test_a_live_timeout_and_deadline_conflict_is_reported_not_ranked(self):
        F.funded_hop(self.exchange, F.A, F.B, 1, "transfer-ab", "session-a", "session-b",
                     price=F.PRICE_AB)
        self.exchange.submit_registration("rcpt-8415-0001", 0, "req-leg-0", 3_600)
        self.clock.now = self.stop
        state = self.exchange.evaluate_deadline("rcpt-8415-0001")
        self.assertEqual(state["overdueRequests"], (0,))
        self.assertTrue(state["pastDeadline"])
        self.assertEqual(len(state["undefinedOrdering"]), 1)
        self.assertIn("D-03", state["undefinedOrdering"][0])
        self.assertIn("not defined", state["undefinedOrdering"][0])


class ExitEligibility(unittest.TestCase):
    """T-25: divergence refuses the exit, and agreement is not enough on its own."""

    def setUp(self):
        self.exchange, self.clock = F.settled_at_b()
        F.redeem_authorization(self.exchange)

    def test_owner_equals_holder_with_every_check_is_eligible(self):
        eligibility = self.exchange.exit_eligibility("rcpt-8415-0001", F.B, "auth-redeem",
                                                     F.ALL_CHECKS)
        self.assertTrue(eligibility["eligible"])
        self.assertTrue(eligibility["ownerEqualsHolderIsNotSufficient"])

    def test_divergence_refuses_the_exit(self):
        exchange, _ = F.rollback_chain_to_d()
        requests = F.submit_all(exchange)
        F.confirm(exchange, requests[0], "res-ab")
        exchange.connect_wallet(F.D, "session-d")
        exchange.register_authorization(F.authorization(F.D, "auth-d", "session-d",
                                                        actions=("redeem",)))
        eligibility = exchange.exit_eligibility("rcpt-8415-0001", F.D, "auth-d", F.ALL_CHECKS)
        self.assertFalse(eligibility["eligible"])
        self.assertIn("EX_OWNER_HOLDER_DIVERGED", eligibility["reasons"])

    def test_agreement_alone_is_not_sufficient_when_a_check_is_unverified(self):
        for missing in REQUIRED_OTHER_CHECKS:
            with self.subTest(missing=missing):
                supplied = tuple(c for c in F.ALL_CHECKS if c != missing)
                eligibility = self.exchange.exit_eligibility("rcpt-8415-0001", F.B, "auth-redeem",
                                                             supplied)
                self.assertTrue(eligibility["ownerEqualsHolder"])
                self.assertFalse(eligibility["eligible"])
                self.assertIn("EX_REDEMPTION_CHECKS_NOT_VERIFIED", eligibility["reasons"])
                self.assertEqual(eligibility["missingChecks"], (missing,))

    def test_no_supplied_check_means_nothing_is_assumed_passed(self):
        eligibility = self.exchange.exit_eligibility("rcpt-8415-0001", F.B, "auth-redeem")
        self.assertEqual(eligibility["missingChecks"], REQUIRED_OTHER_CHECKS)
        self.assertFalse(eligibility["eligible"])

    def test_another_account_cannot_request_the_exit(self):
        eligibility = self.exchange.exit_eligibility("rcpt-8415-0001", F.C, "auth-redeem",
                                                     F.ALL_CHECKS)
        self.assertFalse(eligibility["eligible"])
        self.assertIn("EX_REDEMPTION_REQUESTER_REFUSED", eligibility["reasons"])

    def test_an_authorization_that_does_not_cover_the_exit_is_refused(self):
        self.exchange.register_authorization(
            F.authorization(F.B, "auth-trade-only", "session-b", actions=("sell", "buy")))
        eligibility = self.exchange.exit_eligibility("rcpt-8415-0001", F.B, "auth-trade-only",
                                                     F.ALL_CHECKS)
        self.assertFalse(eligibility["eligible"])
        self.assertIn("EX_AUTH_ACTION_REFUSED", eligibility["reasons"])

    def test_a_revoked_authorization_refuses_the_exit(self):
        self.exchange.revoke_authorization("auth-redeem")
        eligibility = self.exchange.exit_eligibility("rcpt-8415-0001", F.B, "auth-redeem",
                                                     F.ALL_CHECKS)
        self.assertFalse(eligibility["eligible"])
        self.assertIn("EX_AUTH_REVOKED", eligibility["reasons"])

    def test_requesting_without_eligibility_is_refused_and_opens_nothing(self):
        with self.assertRaises(DomainError) as caught:
            self.exchange.request_redemption("rcpt-8415-0001", F.B, "auth-redeem", "rdm-1")
        self.assertEqual(caught.exception.code, "EX_REDEMPTION_REFUSED")
        self.assertFalse(self.exchange.exit_report("rcpt-8415-0001")["open"])


class VoucherAndBurn(unittest.TestCase):
    """T-32: stop-resale, voucher and burn are separate, recoverable records."""

    def setUp(self):
        self.exchange, self.clock = F.settled_at_b()
        F.redeem_authorization(self.exchange)
        self.exchange.request_redemption("rcpt-8415-0001", F.B, "auth-redeem", "rdm-1",
                                         F.ALL_CHECKS)

    def test_the_four_steps_are_recorded_separately(self):
        self.clock.advance(5)
        self.exchange.advance_exit("rcpt-8415-0001", through="stop-resale")
        self.clock.advance(5)
        self.exchange.advance_exit("rcpt-8415-0001", through="voucher-issued")
        self.clock.advance(5)
        self.exchange.advance_exit("rcpt-8415-0001", through="voucher-handover-confirmed")
        self.clock.advance(5)
        report = self.exchange.advance_exit("rcpt-8415-0001")
        self.assertEqual(tuple(entry["step"] for entry in report["steps"]), EXIT_STEPS)
        self.assertTrue(all(entry["status"] == "done" for entry in report["steps"]))
        self.assertEqual(len(report["distinctCompletionInstants"]), 4)

    def test_the_physical_handover_and_the_burn_are_not_atomic(self):
        self.clock.advance(5)
        self.exchange.advance_exit("rcpt-8415-0001", through="voucher-handover-confirmed")
        self.clock.advance(120)
        report = self.exchange.advance_exit("rcpt-8415-0001")
        self.assertFalse(report["physicalAndOnChainAreAtomic"])
        self.assertTrue(report["completionInstantsDiffer"])
        handover = next(e for e in report["steps"] if e["step"] == "voucher-handover-confirmed")
        burn = next(e for e in report["steps"] if e["step"] == "burn")
        self.assertNotEqual(handover["completedAt"], burn["completedAt"])

    def test_a_later_step_is_never_completed_from_an_earlier_one(self):
        report = self.exchange.advance_exit("rcpt-8415-0001", through="voucher-issued")
        statuses = {entry["step"]: entry["status"] for entry in report["steps"]}
        self.assertEqual(statuses["voucher-handover-confirmed"], "pending")
        self.assertEqual(statuses["burn"], "pending")
        self.assertFalse(report["burned"])

    def test_a_failed_step_blocks_and_then_recovers(self):
        exchange, clock = F.settled_at_b(voucher_outcomes={"burn:rdm-1": "failed"})
        F.redeem_authorization(exchange)
        exchange.request_redemption("rcpt-8415-0001", F.B, "auth-redeem", "rdm-1", F.ALL_CHECKS)
        report = exchange.advance_exit("rcpt-8415-0001")
        self.assertEqual(report["state"], "blocked")
        self.assertFalse(report["burned"])
        clock.advance(30)
        report = exchange.advance_exit("rcpt-8415-0001")
        self.assertTrue(report["complete"])
        self.assertTrue(report["burned"])

    def test_an_unknown_step_outcome_is_resolved_by_enquiry(self):
        exchange, _ = F.settled_at_b(voucher_outcomes={"voucher-issued:rdm-1": "unknown"})
        F.redeem_authorization(exchange)
        exchange.request_redemption("rcpt-8415-0001", F.B, "auth-redeem", "rdm-1", F.ALL_CHECKS)
        report = exchange.advance_exit("rcpt-8415-0001")
        self.assertEqual(report["state"], "blocked")
        exchange.voucher_desk.resolve_unknown("voucher-issued:rdm-1", "done")
        report = exchange.advance_exit("rcpt-8415-0001")
        self.assertTrue(report["complete"])

    def test_the_undefined_exit_order_is_reported(self):
        report = self.exchange.exit_report("rcpt-8415-0001")
        self.assertEqual(len(report["undefinedOrdering"]), 1)
        self.assertIn("D-07", report["undefinedOrdering"][0])

    def test_the_desk_is_marked_simulated(self):
        self.assertTrue(self.exchange.voucher_desk.simulated)
        self.assertIn("simulated", self.exchange.voucher_desk.label)


class NoRepeatedExit(unittest.TestCase):
    """T-33: repeated collection, voucher, burn and replay are refused."""

    def setUp(self):
        self.exchange, self.clock = F.settled_at_b()
        F.redeem_authorization(self.exchange)
        self.exchange.request_redemption("rcpt-8415-0001", F.B, "auth-redeem", "rdm-1",
                                         F.ALL_CHECKS)
        self.exchange.advance_exit("rcpt-8415-0001")

    def test_a_second_redemption_request_is_refused(self):
        eligibility = self.exchange.exit_eligibility("rcpt-8415-0001", F.B, "auth-redeem",
                                                     F.ALL_CHECKS)
        self.assertFalse(eligibility["eligible"])
        self.assertIn("EX_REDEMPTION_ALREADY_REQUESTED", eligibility["reasons"])
        with self.assertRaises(DomainError) as caught:
            self.exchange.request_redemption("rcpt-8415-0001", F.B, "auth-redeem", "rdm-2",
                                             F.ALL_CHECKS)
        self.assertEqual(caught.exception.code, "EX_REDEMPTION_REFUSED")

    def test_repeated_advance_calls_repeat_no_act(self):
        before = dict(self.exchange.voucher_desk._records)
        for _ in range(3):
            report = self.exchange.advance_exit("rcpt-8415-0001")
        self.assertTrue(report["complete"])
        self.assertEqual(self.exchange.voucher_desk._records.keys(), before.keys())

    def test_a_replayed_voucher_key_for_another_step_is_refused(self):
        with self.assertRaises(DomainError) as caught:
            self.exchange.voucher_desk.act("burn:rdm-1", "voucher-issued", "rcpt-8415-0001", F.B)
        self.assertEqual(caught.exception.code, "EX_VOUCHER_SUBSTITUTION_REFUSED")

    def test_a_replayed_voucher_key_for_another_account_is_refused(self):
        with self.assertRaises(DomainError) as caught:
            self.exchange.voucher_desk.act("burn:rdm-1", "burn", "rcpt-8415-0001", F.C)
        self.assertEqual(caught.exception.code, "EX_VOUCHER_SUBSTITUTION_REFUSED")

    def test_the_history_stays_readable_after_the_burn(self):
        timeline = self.exchange.receipt_timeline("rcpt-8415-0001")
        kinds = [entry["kind"] for entry in timeline]
        self.assertIn("receipt-minted", kinds)
        self.assertIn("transfer-executed", kinds)
        self.assertIn("registration-result", kinds)
        self.assertIn("segment-release-attempt", kinds)
        self.assertIn("receipt-burned", kinds)
        burned = next(e for e in timeline if e["kind"] == "receipt-burned")
        for retained in ("assetLink", "registrationOrder", "fundsRecord", "collectionRecord"):
            self.assertEqual(burned["detail"][retained], "retained")
        self.assertTrue(burned["detail"]["historyPreserved"])
        self.assertEqual(self.exchange.recorded_legs("rcpt-8415-0001"), 1)
        self.assertEqual(self.exchange.reconciliation("rcpt-8415-0001")["segments"][0]["released"],
                         True)

    def test_the_exit_report_still_answers_after_the_burn(self):
        report = self.exchange.exit_report("rcpt-8415-0001")
        self.assertTrue(report["burned"])
        self.assertTrue(report["historyPreserved"])
        self.assertTrue(report["complete"])


class ExitConsole(unittest.TestCase):
    """The pages report the deadline and the exit without claiming atomicity."""

    def setUp(self):
        from exchange import views
        self.views = views
        self.exchange, self.clock = F.settled_at_b()
        F.redeem_authorization(self.exchange)
        self.exchange.request_redemption("rcpt-8415-0001", F.B, "auth-redeem", "rdm-1",
                                         F.ALL_CHECKS)
        self.clock.advance(5)
        self.exchange.advance_exit("rcpt-8415-0001", through="voucher-handover-confirmed")
        self.clock.advance(60)
        self.exchange.advance_exit("rcpt-8415-0001")

    def _page(self, name):
        return self.views.page(self.exchange, "rcpt-8415-0001", name, run={"runId": "exit"})

    def test_the_receipt_page_denies_atomicity(self):
        html = self._page("receipt")
        self.assertIn("not one atomic act", html)
        self.assertIn("records its own completion instant", html)

    def test_the_receipt_page_lists_each_step_with_its_instant(self):
        html = self._page("receipt")
        for step in EXIT_STEPS:
            self.assertIn(step, html)
        self.assertIn("Verified checks on record", html)

    def test_the_receipt_page_says_the_records_are_retained_after_the_burn(self):
        self.assertIn("records are retained", self._page("receipt"))

    def test_the_receipt_page_reports_the_undefined_exit_ordering(self):
        self.assertIn("D-07", self._page("receipt"))

    def test_the_timeline_states_the_deadline_behaviour(self):
        exchange, clock = F.exit_exchange()
        F.funded_hop(exchange, F.A, F.B, 1, "transfer-ab", "session-a", "session-b",
                     price=F.PRICE_AB)
        exchange.submit_registration("rcpt-8415-0001", 0, "req-leg-0", 3_600)
        clock.now = exchange.receipt("rcpt-8415-0001").trade_stop_at
        html = self.views.page(exchange, "rcpt-8415-0001", "timeline")
        self.assertIn("New trades are refused from that instant", html)
        self.assertIn("continue under their own rules", html)
        self.assertIn("Undefined ordering", html)
        self.assertIn("D-03", html)

    def test_the_timeline_names_the_return_target_after_the_deadline(self):
        exchange, clock = F.rollback_chain_to_d()
        requests = F.submit_all(exchange)
        F.confirm(exchange, requests[0], "res-ab")
        clock.now = exchange.receipt("rcpt-8415-0001").trade_stop_at
        html = self.views.page(exchange, "rcpt-8415-0001", "timeline")
        self.assertIn("the last confirmed holder", html)
        self.assertIn(F.B, html)


if __name__ == "__main__":
    unittest.main()
