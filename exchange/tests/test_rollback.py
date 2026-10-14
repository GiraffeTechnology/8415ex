"""T-17 to T-23, T-29, T-30: suffix rollback, the finalized prefix, and gas."""
import unittest

from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.model import Asset
from exchange.rollback import WITHDRAWN_MECHANISMS


def refused_at_ab(**kwargs):
    """owner = D, holder = A, and B's registration is refused."""
    exchange, clock = F.rollback_chain_to_d(**kwargs)
    requests = F.submit_all(exchange)
    F.refuse(exchange, requests[0], "res-ab-refused")
    return exchange, clock, requests


def ab_settled_then_c_refused(**kwargs):
    """owner = D, holder = B, AB released, and C's registration is refused."""
    exchange, clock = F.rollback_chain_to_d(**kwargs)
    requests = F.submit_all(exchange)
    F.confirm(exchange, requests[0], "res-ab")
    exchange.release_segment("rcpt-8415-0001", 0, F.release_authority(exchange, 0, "auth-0"))
    F.refuse(exchange, requests[1], "res-bc-refused")
    return exchange, clock, requests


class FullSuffixRollback(unittest.TestCase):
    """T-17: B refused while holder is still A unwinds everything back to A."""

    def setUp(self):
        self.exchange, _, _ = refused_at_ab()
        self.exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(self.exchange, 0, "rb-1"))
        self.report = self.exchange.advance_rollback("rcpt-8415-0001")

    def test_all_three_segments_are_refunded_to_their_own_buyers(self):
        paid = {entry["legIndex"]: (entry["originalBuyer"], entry["refundedToOriginalBuyer"])
                for entry in self.report["funds"]}
        self.assertEqual(paid, {0: (F.B, True), 1: (F.C, True), 2: (F.D, True)})
        self.assertEqual(self.exchange.payments.movements, 3)

    def test_the_receipt_returns_to_a(self):
        self.assertEqual(self.exchange.owner_of("rcpt-8415-0001"), F.A)
        self.assertEqual(self.exchange.owner_index("rcpt-8415-0001"), 0)
        self.assertEqual(self.report["returnBoundaryAccount"], F.A)
        self.assertTrue(self.report["assetControl"]["returned"])

    def test_the_rollback_only_reports_complete_with_every_step_evidenced(self):
        self.assertEqual(self.report["state"], "complete")
        self.assertTrue(self.report["complete"])
        self.assertEqual(self.report["outstandingSteps"], ())

    def test_history_is_preserved_rather_than_erased(self):
        self.assertEqual(self.exchange.recorded_legs("rcpt-8415-0001"), 3)
        self.assertTrue(self.report["assetControl"]["historyPreserved"])
        statuses = [leg.rollback_status for leg in self.exchange.legs("rcpt-8415-0001")]
        self.assertEqual(statuses, ["returned", "returned", "returned"])

    def test_the_report_names_the_trigger_and_the_interval(self):
        self.assertEqual(self.report["refusedLegIndex"], 0)
        self.assertEqual(self.report["affectedLegs"], (0, 1, 2))
        self.assertEqual(self.report["finalizedPrefixLegs"], 0)
        self.assertIn("refusal", self.report["trigger"])


class FinalizedPrefixSurvives(unittest.TestCase):
    """T-18: with AB settled, a refusal at C unwinds only BC and CD, back to B."""

    def setUp(self):
        self.exchange, _, _ = ab_settled_then_c_refused()
        self.exchange.begin_rollback("rcpt-8415-0001", 1, F.rollback_authority(self.exchange, 1, "rb-2"))
        self.report = self.exchange.advance_rollback("rcpt-8415-0001")

    def test_only_the_last_two_segments_are_unwound(self):
        self.assertEqual(self.report["affectedLegs"], (1, 2))
        refunded = {entry["legIndex"]: entry["refundedToOriginalBuyer"]
                    for entry in self.report["funds"]}
        self.assertEqual(refunded, {1: True, 2: True})

    def test_the_receipt_returns_to_b_and_not_to_a(self):
        self.assertEqual(self.exchange.owner_of("rcpt-8415-0001"), F.B)
        self.assertEqual(self.report["returnBoundaryAccount"], F.B)
        self.assertEqual(self.report["finalizedPrefixLegs"], 1)

    def test_the_settled_ab_payment_is_not_re_collected(self):
        escrow = self.exchange.escrow_for_leg("rcpt-8415-0001", 0)
        self.assertEqual(escrow.status, "released")
        self.assertIsNone(escrow.refunded_at)
        self.assertEqual(self.exchange.leg("rcpt-8415-0001", 0).rollback_status, "detached")
        self.assertNotIn(0, [entry["legIndex"] for entry in self.report["funds"]])

    def test_a_refusal_inside_the_finalized_prefix_is_refused(self):
        exchange, _, requests = ab_settled_then_c_refused()
        with self.assertRaises(DomainError) as caught:
            exchange.rollback_interval("rcpt-8415-0001", 0)
        self.assertEqual(caught.exception.code, "EX_ROLLBACK_PREFIX_IMMUTABLE")

    def test_a_cleared_rollback_capability_is_not_reopened(self):
        self.assertEqual(self.exchange.leg("rcpt-8415-0001", 0).rollback_status, "detached")
        self.assertEqual(self.exchange.payments.movements, 3,
                         "one release for AB and two refunds, nothing more")


class RefundsAndGas(unittest.TestCase):
    """T-19, T-21: each buyer's own principal back, with actual gas and net."""

    def setUp(self):
        self.exchange, _, _ = refused_at_ab()

    def test_each_segment_shows_principal_gas_and_net(self):
        for leg, spent in ((0, 21_000), (1, 23_000), (2, 25_000)):
            self.exchange.record_gas("rcpt-8415-0001", leg, "trade", spent)
        self.exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(self.exchange, 0, "rb-1"))
        report = self.exchange.advance_rollback("rcpt-8415-0001")
        expected = {0: (F.PRICE_AB, 21_000), 1: (F.PRICE_BC, 23_000), 2: (F.PRICE_CD, 25_000)}
        for entry in report["funds"]:
            principal, gas = expected[entry["legIndex"]]
            self.assertEqual(entry["principal"], str(principal))
            self.assertEqual(entry["gasTotal"], str(gas))
            self.assertEqual(entry["netToOriginalBuyer"], str(principal - gas))
            self.assertEqual(entry["gasBorneBy"], entry["originalBuyer"])

    def test_the_three_principals_do_not_merge_in_the_refund(self):
        self.exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(self.exchange, 0, "rb-1"))
        report = self.exchange.advance_rollback("rcpt-8415-0001")
        principals = sorted(entry["principal"] for entry in report["funds"])
        self.assertEqual(principals, sorted(str(p) for p in (F.PRICE_AB, F.PRICE_BC, F.PRICE_CD)))

    def test_a_shared_return_operation_is_not_charged_in_full_to_each_leg(self):
        self.exchange.record_gas("rcpt-8415-0001", 1, "shared-return", 48_000, shared_with=(2,))
        with self.assertRaises(DomainError) as caught:
            self.exchange.record_gas("rcpt-8415-0001", 2, "shared-return", 48_000, shared_with=(1,))
        self.assertEqual(caught.exception.code, "EX_GAS_DOUBLE_CHARGE_REFUSED")

    def test_the_refusal_does_not_move_gas_responsibility_between_legs(self):
        self.exchange.record_gas("rcpt-8415-0001", 2, "return-share", 30_000)
        report = self.exchange.reconciliation("rcpt-8415-0001")
        self.assertEqual(report["segments"][2]["gasBorneBy"], F.D)
        self.assertEqual(report["segments"][0]["gasTotal"], "0")


class ReturnDoesNotWalkIntermediates(unittest.TestCase):
    """T-20: a zero-balance intermediate wallet changes no obligation."""

    def test_the_return_is_one_operation_to_the_boundary(self):
        exchange, _, _ = refused_at_ab()
        exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(exchange, 0, "rb-1"))
        exchange.advance_rollback("rcpt-8415-0001")
        record = exchange.asset_control.lookup("return:rcpt-8415-0001:rb-1")
        self.assertEqual(record["operations"], 1)
        self.assertFalse(record["walkedIntermediateWallets"])
        self.assertFalse(record["requiredIntermediateGas"])
        self.assertEqual(exchange.asset_control.hops_walked, 0)

    def test_zero_balances_at_b_and_c_do_not_block_the_return(self):
        exchange, _, _ = refused_at_ab(gas_budgets={F.B: 0, F.C: 0})
        exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(exchange, 0, "rb-1"))
        report = exchange.advance_rollback("rcpt-8415-0001")
        self.assertTrue(report["complete"])
        self.assertEqual(exchange.owner_of("rcpt-8415-0001"), F.A)

    def test_the_obligation_list_is_unchanged_by_an_empty_intermediate_wallet(self):
        exchange, _, _ = refused_at_ab(gas_budgets={F.B: 0, F.C: 0})
        exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(exchange, 0, "rb-1"))
        report = exchange.advance_rollback("rcpt-8415-0001")
        self.assertEqual([entry["legIndex"] for entry in report["funds"]], [0, 1, 2])
        self.assertTrue(all(entry["refundedToOriginalBuyer"] for entry in report["funds"]))


class ShortfallStaysBlocked(unittest.TestCase):
    """T-22: a gas shortfall is blocked and resumable, never a disposal."""

    def setUp(self):
        self.exchange, _, _ = refused_at_ab(gas_budgets={F.D: 0})
        self.exchange.begin_rollback("rcpt-8415-0001", 0,
                                     F.rollback_authority(self.exchange, 0, "rb-1"))
        self.report = self.exchange.advance_rollback("rcpt-8415-0001")

    def test_the_return_step_is_blocked_with_a_named_reason(self):
        self.assertEqual(self.report["state"], "blocked")
        self.assertFalse(self.report["complete"])
        blocked = [step for step in self.report["outstandingSteps"] if step["status"] == "blocked"]
        self.assertEqual(len(blocked), 1)
        self.assertEqual(blocked[0]["kind"], "asset-return")
        self.assertEqual(blocked[0]["detail"]["reason"], "EX_GAS_BUDGET_EXHAUSTED")

    def test_no_custody_sale_or_liquidation_appears_anywhere(self):
        blocked = [entry for entry in self.exchange.receipt_timeline("rcpt-8415-0001")
                   if entry["kind"] == "rollback-step-blocked"]
        self.assertEqual(len(blocked), 1)
        self.assertFalse(blocked[0]["detail"]["custodyTaken"])
        self.assertFalse(blocked[0]["detail"]["forcedSale"])
        self.assertFalse(blocked[0]["detail"]["liquidation"])
        self.assertTrue(blocked[0]["detail"]["resumable"])
        self.assertEqual(self.report["withdrawnMechanismsNotUsed"], WITHDRAWN_MECHANISMS)

    def test_the_refunds_still_went_to_their_own_buyers(self):
        self.assertTrue(all(entry["refundedToOriginalBuyer"] for entry in self.report["funds"]))

    def test_it_resumes_once_the_budget_allows(self):
        self.exchange._budgets[F.D] = 100_000
        report = self.exchange.advance_rollback("rcpt-8415-0001")
        self.assertTrue(report["complete"])
        self.assertEqual(self.exchange.owner_of("rcpt-8415-0001"), F.A)
        self.assertEqual(self.exchange.payments.movements, 3, "no refund was repeated")
        self.assertEqual(self.exchange.asset_control.returns, 1)


class InterruptionAndLateResults(unittest.TestCase):
    """T-23: resume without repeating, and a late success revives nothing."""

    def test_an_interrupted_rollback_resumes_without_a_second_refund(self):
        exchange, _, _ = refused_at_ab(outcomes={"refund:escrow-bc": "failed"})
        exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(exchange, 0, "rb-1"))
        first = exchange.advance_rollback("rcpt-8415-0001")
        self.assertEqual(first["state"], "blocked")
        second = exchange.advance_rollback("rcpt-8415-0001")
        self.assertTrue(second["complete"])
        self.assertEqual(exchange.payments.movements, 3, "exactly one movement per segment")

    def test_an_unknown_refund_is_not_repaired_by_a_second_payment(self):
        exchange, _, _ = refused_at_ab(outcomes={"refund:escrow-ab": "unknown"})
        exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(exchange, 0, "rb-1"))
        exchange.advance_rollback("rcpt-8415-0001")
        before = exchange.payments.movements
        exchange.advance_rollback("rcpt-8415-0001")
        self.assertEqual(exchange.payments.movements, before)
        resumed = exchange.resume_payments("rcpt-8415-0001")
        self.assertIn("unknown", [entry["paymentStatus"] for entry in resumed])

    def test_an_unknown_asset_return_is_not_sent_twice(self):
        exchange, _, _ = refused_at_ab(return_outcomes={"return:rcpt-8415-0001:rb-1": "unknown"})
        exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(exchange, 0, "rb-1"))
        exchange.advance_rollback("rcpt-8415-0001")
        exchange.advance_rollback("rcpt-8415-0001")
        self.assertEqual(exchange.asset_control.returns, 0)
        exchange.asset_control.resolve_unknown("return:rcpt-8415-0001:rb-1", "returned")
        report = exchange.advance_rollback("rcpt-8415-0001")
        self.assertTrue(report["complete"])
        self.assertEqual(exchange.asset_control.returns, 0,
                         "the enquiry recorded the return; nothing was resent")

    def test_an_enquiry_about_a_refund_never_becomes_a_release(self):
        """Regression: a resumed enquiry must apply the outcome the payment was
        actually for. Reading a settled refund as a release would flip a
        refunded segment into a released one."""
        exchange, _, _ = refused_at_ab(outcomes={"refund:escrow-ab": "unknown"})
        exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(exchange, 0, "rb-1"))
        exchange.advance_rollback("rcpt-8415-0001")
        self.assertEqual(exchange.escrow_for_leg("rcpt-8415-0001", 0).payment_intent, "refund")
        exchange.payments.resolve_unknown("refund:escrow-ab", "settled")
        resumed = exchange.resume_payments("rcpt-8415-0001")
        escrow = exchange.escrow_for_leg("rcpt-8415-0001", 0)
        self.assertEqual(escrow.status, "refunded")
        self.assertIsNone(escrow.settled_at)
        self.assertIsNotNone(escrow.refunded_at)
        self.assertEqual(exchange.leg("rcpt-8415-0001", 0).funding_status, "refunded")
        self.assertEqual([entry["intent"] for entry in resumed if entry["legIndex"] == 0],
                         ["refund"])

    def test_a_late_success_cannot_revive_a_returned_leg(self):
        exchange, _, requests = refused_at_ab()
        exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(exchange, 0, "rb-1"))
        exchange.advance_rollback("rcpt-8415-0001")
        evidence, outcome = F.confirm(exchange, requests[1], "res-bc-late")
        self.assertEqual(outcome["disposition"], "late-conflict")
        self.assertFalse(outcome["legRevived"])
        self.assertFalse(outcome["fundsReleasedAgain"])
        self.assertEqual(exchange.holder_index("rcpt-8415-0001"), 0)
        self.assertEqual(exchange.escrow_for_leg("rcpt-8415-0001", 1).status, "refunded")
        self.assertEqual(exchange.payments.movements, 3)

    def test_the_conflict_is_retained_for_investigation(self):
        exchange, _, requests = refused_at_ab()
        exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(exchange, 0, "rb-1"))
        exchange.advance_rollback("rcpt-8415-0001")
        F.confirm(exchange, requests[2], "res-cd-late")
        report = exchange.rollback_report("rcpt-8415-0001")
        self.assertEqual(len(report["conflicts"]), 1)
        self.assertEqual(report["conflicts"][0]["resultId"], "res-cd-late")

    def test_a_returned_chain_is_not_re_traded_on_a_guess(self):
        exchange, _, _ = refused_at_ab()
        match, _ = F.funded_hop(exchange, F.A, F.B, 9, "transfer-prepared",
                               "session-a", "session-b", lock=False)
        exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(exchange, 0, "rb-1"))
        exchange.advance_rollback("rcpt-8415-0001")
        with self.assertRaises(DomainError) as caught:
            exchange.execute_transfer(match, "transfer-prepared")
        self.assertEqual(caught.exception.code, "EX_TRADE_RETURNED_CHAIN_CLOSED")
        with self.assertRaises(DomainError) as caught:
            F.funded_hop(exchange, F.A, F.B, 10, "transfer-again", "session-a", "session-b")
        self.assertEqual(caught.exception.code, "EX_MATCH_UNEXECUTABLE")
        self.assertIn("EX_TRADE_RETURNED_CHAIN_CLOSED", caught.exception.detail)


class RollbackPermission(unittest.TestCase):
    """T-29: no unverified authority, no confiscation, no prefix rewrite."""

    def setUp(self):
        self.exchange, _, _ = refused_at_ab()

    def _refused(self, code, **overrides):
        authority = F.rollback_authority(self.exchange, 0, "rb-bad", **overrides)
        with self.assertRaises(DomainError) as caught:
            self.exchange.begin_rollback("rcpt-8415-0001", 0, authority)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(self.exchange.payments.movements, 0)
        self.assertEqual(self.exchange.asset_control.returns, 0)

    def test_an_unverified_source_is_refused(self):
        self._refused("EX_ROLLBACK_SOURCE_REFUSED", source="self-declared-authority")

    def test_a_wrong_network_is_refused(self):
        self._refused("EX_ROLLBACK_BINDING_REFUSED", asset=Asset(1, F.CONTRACT, F.TOKEN_ID))

    def test_a_substituted_return_destination_is_refused(self):
        self._refused("EX_ROLLBACK_BINDING_REFUSED", boundary_account=F.C)

    def test_a_tampered_interval_binding_is_refused(self):
        self._refused("EX_ROLLBACK_BINDING_REFUSED", binding="0x" + "22" * 32)

    def test_something_that_is_not_authority_evidence_is_refused(self):
        for substitute in ("0xdeadbeef", "VALID", {"ok": True}, None):
            with self.subTest(substitute=substitute):
                with self.assertRaises(DomainError) as caught:
                    self.exchange.begin_rollback("rcpt-8415-0001", 0, substitute)
                self.assertEqual(caught.exception.code, "EX_ROLLBACK_AUTHORITY_REFUSED")

    def test_a_rollback_without_a_recorded_refusal_is_refused(self):
        exchange, _ = F.rollback_chain_to_d()
        F.submit_all(exchange)
        with self.assertRaises(DomainError) as caught:
            exchange.begin_rollback("rcpt-8415-0001", 1, F.rollback_authority(exchange, 1, "rb-x"))
        self.assertEqual(caught.exception.code, "EX_ROLLBACK_TRIGGER_REFUSED")

    def test_a_released_segment_cannot_be_refunded(self):
        exchange, _, _ = ab_settled_then_c_refused()
        exchange.begin_rollback("rcpt-8415-0001", 1, F.rollback_authority(exchange, 1, "rb-2"))
        exchange.advance_rollback("rcpt-8415-0001")
        escrow = exchange.escrow_for_leg("rcpt-8415-0001", 0)
        self.assertEqual(escrow.status, "released")
        self.assertIsNone(escrow.refunded_at)

    def test_two_rollbacks_cannot_be_open_at_once(self):
        self.exchange.begin_rollback("rcpt-8415-0001", 0,
                                     F.rollback_authority(self.exchange, 0, "rb-1"))
        with self.assertRaises(DomainError) as caught:
            self.exchange.begin_rollback("rcpt-8415-0001", 0,
                                         F.rollback_authority(self.exchange, 0, "rb-2"))
        self.assertEqual(caught.exception.code, "EX_ROLLBACK_ALREADY_OPEN")


class DuplicateAndReorderedEvents(unittest.TestCase):
    """T-30: duplicate or re-ordered observations move nothing twice."""

    def test_a_duplicate_refusal_result_is_idempotent(self):
        exchange, _, requests = refused_at_ab()
        evidence = exchange.registrars["REG_DIRECT"].result(requests[0], "rejected", "res-dup")
        first = exchange.apply_registration_result(evidence)
        second = exchange.apply_registration_result(evidence)
        self.assertEqual(first["disposition"], "rejected")
        self.assertEqual(second["disposition"], "idempotent")

    def test_repeated_advance_calls_do_not_repeat_any_movement(self):
        exchange, _, _ = refused_at_ab()
        exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(exchange, 0, "rb-1"))
        for _ in range(4):
            report = exchange.advance_rollback("rcpt-8415-0001")
        self.assertTrue(report["complete"])
        self.assertEqual(exchange.payments.movements, 3)
        self.assertEqual(exchange.asset_control.returns, 1)

    def test_a_replayed_release_after_a_refund_is_refused(self):
        exchange, _, _ = refused_at_ab()
        exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(exchange, 0, "rb-1"))
        exchange.advance_rollback("rcpt-8415-0001")
        state = exchange.segment_release_state("rcpt-8415-0001", 1)
        self.assertFalse(state["eligible"])
        self.assertIn("EX_SEGMENT_REFUNDED", state["reasons"])
        self.assertEqual(exchange.payments.movements, 3)

    def test_an_out_of_order_confirmation_before_the_refusal_still_defers(self):
        exchange, _ = F.rollback_chain_to_d()
        requests = F.submit_all(exchange)
        _, deferred = F.confirm(exchange, requests[2], "res-cd-early")
        self.assertEqual(deferred["disposition"], "deferred")
        F.refuse(exchange, requests[0], "res-ab-refused")
        self.assertEqual(exchange.holder_index("rcpt-8415-0001"), 0)
        self.assertEqual(exchange.deferred_legs("rcpt-8415-0001"), (2,))
        exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(exchange, 0, "rb-1"))
        report = exchange.advance_rollback("rcpt-8415-0001")
        self.assertTrue(report["complete"], "a buffered later result does not release anything")
        self.assertEqual(exchange.payments.movements, 3)

    def test_the_safe_retry_condition_is_stated(self):
        exchange, _, _ = refused_at_ab()
        exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(exchange, 0, "rb-1"))
        report = exchange.rollback_report("rcpt-8415-0001")
        self.assertIn("asks what already happened", report["safeRetryCondition"])
        self.assertFalse(report["complete"], "nothing is complete before its evidence")


class RollbackConsole(unittest.TestCase):
    """The rollback page shows the prefix, the boundary and what is still open."""

    def setUp(self):
        from exchange import views
        self.views = views
        self.exchange, _, _ = ab_settled_then_c_refused()
        self.exchange.begin_rollback("rcpt-8415-0001", 1,
                                     F.rollback_authority(self.exchange, 1, "rb-2"))
        self.exchange.advance_rollback("rcpt-8415-0001")

    def _page(self):
        return self.views.page(self.exchange, "rcpt-8415-0001", "rollback")

    def test_the_page_names_the_finalized_prefix_and_the_boundary(self):
        html = self._page()
        self.assertIn("Last finalized position", html)
        self.assertIn("is not reopened, reversed or re-collected", html)
        self.assertIn(F.B, html)

    def test_the_page_says_the_return_does_not_walk_the_intermediates(self):
        self.assertIn("without walking the intermediate", self._page())

    def test_the_page_lists_the_withdrawn_mechanisms_as_unused(self):
        html = self._page()
        for mechanism in WITHDRAWN_MECHANISMS:
            self.assertIn(mechanism, html)

    def test_an_incomplete_rollback_is_never_shown_as_complete(self):
        exchange, _, _ = refused_at_ab(gas_budgets={F.D: 0})
        exchange.begin_rollback("rcpt-8415-0001", 0, F.rollback_authority(exchange, 0, "rb-1"))
        exchange.advance_rollback("rcpt-8415-0001")
        html = self.views.page(exchange, "rcpt-8415-0001", "rollback")
        self.assertIn("blocked", html)
        self.assertIn("not complete until every step has its own evidence", html)


if __name__ == "__main__":
    unittest.main()
