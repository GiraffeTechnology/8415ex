"""V1.4 T24/T25/T32: exact trading cutoff and retired physical-flow boundaries.

Positive physical collection/voucher/burn assertions belong to historical Git
versions. Holder remint is separate and retains its dedicated regression suite.
"""
from copy import deepcopy
import unittest
from unittest.mock import patch

from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.exit import EXIT_STEPS, ExitStep, RedemptionRequest, exit_step_key
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
        self.assertEqual(caught.exception.code, "EX_ORDER_NOT_ACCEPTED")
        self.assertEqual(state["tradeBlockingReasons"], ("EX_TRADE_WINDOW_CLOSED",))
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

    def test_timeout_and_deadline_use_confirmed_oracle_rules_without_a_policy_gate(self):
        F.funded_hop(self.exchange, F.A, F.B, 1, "transfer-ab", "session-a", "session-b",
                     price=F.PRICE_AB)
        self.exchange.submit_registration("rcpt-8415-0001", 0, "req-leg-0", 3_600)
        self.clock.now = self.stop
        state = self.exchange.evaluate_deadline("rcpt-8415-0001")
        self.assertEqual(state["overdueRequests"], (0,))
        self.assertTrue(state["pastDeadline"])
        self.assertEqual(state["undefinedOrdering"], ())
        self.assertTrue(state["requiresAuthoritativeReconciliation"])
        self.assertFalse(state["graceReceiptRequired"])
        self.assertFalse(state["recoveryExecutedByReport"])
        self.assertEqual(state["registrationTimeSource"],
                         "single authoritative Oracle record under mint conditions")


class RetiredPhysicalOperations(unittest.TestCase):
    """No grant, check list, replay or report may revive physical fulfillment."""

    def setUp(self):
        self.exchange, self.clock = F.settled_at_b()
        F.redeem_authorization(self.exchange)

    def snapshot(self):
        ex = self.exchange
        return deepcopy({
            "owner": ex.owner_of("rcpt-8415-0001"),
            "holder": ex.holder_of("rcpt-8415-0001"),
            "legs": ex.recorded_legs("rcpt-8415-0001"),
            "timeline": ex.receipt_timeline("rcpt-8415-0001"),
            "funds": ex.reconciliation("rcpt-8415-0001"),
            "exit": ex._exits["rcpt-8415-0001"],
            "deskRecords": ex.voucher_desk._records,
            "deskHistory": ex.voucher_desk._history,
        })

    def assert_retired(self, operation):
        before = self.snapshot()
        with patch.object(self.exchange.voucher_desk, "act",
                          side_effect=AssertionError("physical action must not run")):
            with self.assertRaises(DomainError) as caught:
                operation()
        self.assertEqual(caught.exception.code, "EX_PHYSICAL_FULFILLMENT_RETIRED")
        self.assertEqual(self.snapshot(), before)

    def test_agreement_and_complete_checks_cannot_make_physical_exit_eligible(self):
        before = self.snapshot()
        result = self.exchange.exit_eligibility(
            "rcpt-8415-0001", F.B, "auth-redeem", F.ALL_CHECKS)
        self.assertFalse(result["eligible"])
        self.assertEqual(result["reasons"], ("EX_PHYSICAL_FULFILLMENT_RETIRED",))
        self.assertEqual(result["physicalActions"], ())
        self.assertEqual(self.snapshot(), before)

    def test_missing_or_revoked_grants_do_not_create_a_new_physical_checklist(self):
        self.exchange.revoke_authorization("auth-redeem")
        before = self.snapshot()
        for account, grant in ((F.B, None), (F.B, "auth-redeem"), (F.C, "auth-redeem")):
            with self.subTest(account=account, grant=grant):
                result = self.exchange.exit_eligibility(
                    "rcpt-8415-0001", account, grant)
                self.assertFalse(result["eligible"])
                self.assertEqual(result["reasons"], ("EX_PHYSICAL_FULFILLMENT_RETIRED",))
                self.assertEqual(result["physicalActions"], ())
        self.assertEqual(self.snapshot(), before)

    def test_new_redemption_is_refused_even_with_the_old_full_grant_and_checks(self):
        self.assert_retired(lambda: self.exchange.request_redemption(
            "rcpt-8415-0001", F.B, "auth-redeem", "retired-request", F.ALL_CHECKS))

    def test_repeated_redemption_does_not_open_a_request_or_repeat_funds_actions(self):
        for _ in range(3):
            self.assert_retired(lambda: self.exchange.request_redemption(
                "rcpt-8415-0001", F.B, "auth-redeem", "same-retired-request", F.ALL_CHECKS))
        report = self.exchange.exit_report("rcpt-8415-0001")
        self.assertFalse(report["open"])
        self.assertFalse(report["complete"])
        self.assertTrue(report["retiredOperation"])
        self.assertFalse(report["executable"])

    def test_each_old_exit_step_and_default_resume_refuse_without_mutation(self):
        for step in (None,) + EXIT_STEPS:
            with self.subTest(step=step):
                self.assert_retired(lambda: self.exchange.advance_exit(
                    "rcpt-8415-0001", through=step))

    def test_the_old_simulator_cannot_create_or_replay_physical_actions(self):
        before = self.snapshot()
        for step in EXIT_STEPS:
            key = exit_step_key(step, "rcpt-8415-0001", "old-request")
            for account in (F.B, F.C):
                with self.subTest(step=step, account=account):
                    with self.assertRaises(DomainError) as caught:
                        self.exchange.voucher_desk.act(
                            key, step, "rcpt-8415-0001", account)
                    self.assertEqual(caught.exception.code, "EX_PHYSICAL_FULFILLMENT_RETIRED")
        self.assertEqual(self.snapshot(), before)

    def test_retired_readiness_is_read_only_and_never_a_new_acceptance_condition(self):
        before = self.snapshot()
        for _ in range(3):
            result = self.exchange.redemption_readiness("rcpt-8415-0001", F.B)
            self.assertFalse(result["eligible"])
            self.assertEqual(result["reasons"], ("EX_PHYSICAL_FULFILLMENT_RETIRED",))
        self.assertEqual(self.snapshot(), before)

    def test_a_refused_physical_request_does_not_block_an_authorized_new_trade(self):
        self.assert_retired(lambda: self.exchange.request_redemption(
            "rcpt-8415-0001", F.B, "auth-redeem", "never-opened", F.ALL_CHECKS))
        _, leg = F.funded_hop(
            self.exchange, F.B, F.C, 2, "transfer-bc",
            "session-b", "session-c", price=F.PRICE_BC)
        self.assertEqual(leg.buyer, F.C)
        self.assertEqual(self.exchange.owner_of("rcpt-8415-0001"), F.C)
        self.assertEqual(self.exchange.holder_of("rcpt-8415-0001"), F.B)

    def historical_unknown(self):
        """Synthetic retained evidence only; never a new physical attempt."""
        request = RedemptionRequest(
            "historical-request", "rcpt-8415-0001", F.B,
            "auth-redeem", self.clock.now)
        key = exit_step_key("burn", request.receipt_id, request.request_id)
        steps = tuple(ExitStep(
            step, exit_step_key(step, request.receipt_id, request.request_id),
            status="blocked" if step == "burn" else "pending",
            detail=(("outcome", "unknown"),) if step == "burn" else ())
            for step in EXIT_STEPS)
        self.exchange._exits[request.receipt_id] = {
            "request": request, "steps": steps, "state": "blocked",
            "verifiedChecks": F.ALL_CHECKS}
        self.exchange.voucher_desk._records[key] = {
            "key": key, "step": "burn", "receiptId": request.receipt_id,
            "account": F.B, "status": "unknown", "effect": "unknown"}
        self.exchange.voucher_desk._history[key] = [
            dict(self.exchange.voucher_desk._records[key])]
        return key

    def test_historical_unknown_stays_readable_and_cannot_be_resumed(self):
        self.historical_unknown()
        before = self.snapshot()
        report = self.exchange.exit_report("rcpt-8415-0001")
        self.assertTrue(report["open"])
        self.assertEqual(report["state"], "blocked")
        self.assertFalse(report["complete"])
        self.assertFalse(report["burned"])
        self.assertTrue(report["retiredOperation"])
        self.assertFalse(report["executable"])
        self.assertTrue(report["historyPreserved"])
        self.assertEqual(report["requestId"], "historical-request")
        burn = next(row for row in report["steps"] if row["step"] == "burn")
        self.assertEqual(burn["detail"]["outcome"], "unknown")
        self.assertIsNone(burn["completedAt"])
        self.assertEqual(self.snapshot(), before)
        self.assert_retired(lambda: self.exchange.advance_exit("rcpt-8415-0001"))

    def test_historical_lookup_and_report_do_not_erase_or_resolve_unknown(self):
        key = self.historical_unknown()
        before = self.snapshot()
        for _ in range(3):
            self.assertEqual(self.exchange.voucher_desk.lookup(key)["status"], "unknown")
            self.assertEqual(len(self.exchange.voucher_desk.history(key)), 1)
            self.exchange.exit_report("rcpt-8415-0001")
        self.assertEqual(self.snapshot(), before)

    def test_observed_unknown_resolution_retains_history_without_replaying_a_step(self):
        key = self.historical_unknown()
        before_timeline = self.exchange.receipt_timeline("rcpt-8415-0001")
        before_funds = deepcopy(self.exchange.reconciliation("rcpt-8415-0001"))
        with patch.object(self.exchange.voucher_desk, "act",
                          side_effect=AssertionError("resolution must not execute")):
            result = self.exchange.voucher_desk.resolve_unknown(key, "failed")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["effect"], "not-applied")
        self.assertEqual(len(self.exchange.voucher_desk.history(key)), 2)
        self.assertEqual(self.exchange.voucher_desk.history(key)[0]["status"], "unknown")
        self.assertEqual(self.exchange.receipt_timeline("rcpt-8415-0001"), before_timeline)
        self.assertEqual(self.exchange.reconciliation("rcpt-8415-0001"), before_funds)
        self.assert_retired(lambda: self.exchange.advance_exit("rcpt-8415-0001"))


if __name__ == "__main__":
    unittest.main()
