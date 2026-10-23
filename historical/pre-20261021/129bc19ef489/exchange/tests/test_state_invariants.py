"""Synthetic regressions for signed terms, protected prefixes and exit isolation."""
import copy
from dataclasses import replace
import unittest
from unittest.mock import Mock

from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.exit import EXIT_STEPS, ExitStep, RedemptionRequest, exit_step_key
from exchange.model import Asset

R = "rcpt-8415-0001"


def pending_match(exchange, seller=F.A, buyer=F.B, suffix="next", nonce=10):
    return F.funded_hop(exchange, seller, buyer, nonce, "transfer-" + suffix,
                        "session-" + ("b" if seller == F.B else "a"),
                        "session-" + ("b" if buyer == F.B else "c"), lock=False)[0]


class SignedMatchBinding(unittest.TestCase):
    def test_altered_results_refuse_before_any_business_mutation(self):
        changes = ({"seller": F.C}, {"buyer": F.C}, {"price": F.PRICE - 1},
                   {"price": F.PRICE + 1}, {"quote_asset": "OTHER"}, {"units": 2},
                   {"asset": Asset(F.CHAIN_ID, F.CONTRACT, F.TOKEN_ID + 1)})
        for change in changes:
            for operation in ("lock", "execute"):
                with self.subTest(change=change, operation=operation):
                    ex, _ = F.funded_exchange() if operation == "lock" else F.minted()
                    match = pending_match(ex)
                    before = copy.deepcopy((ex._legs, ex._used_nonces, ex._escrows, ex._events))
                    with self.assertRaises(DomainError) as caught:
                        altered = replace(match, **change)
                        if operation == "lock":
                            ex.lock_escrow(altered, "escrow-next")
                        else:
                            ex.execute_transfer(altered, "transfer-next")
                    if not ("seller" in change or "asset" in change):
                        self.assertEqual(caught.exception.code, "EX_MATCH_BINDING_REFUSED")
                    self.assertEqual((ex._legs, ex._used_nonces, ex._escrows, ex._events), before)

    def test_reversed_intent_digests_are_not_a_pair(self):
        ex, _ = F.funded_exchange()
        match = pending_match(ex)
        with self.assertRaises(DomainError):
            ex.lock_escrow(replace(match, sell_intent_digest=match.buy_intent_digest,
                                  buy_intent_digest=match.sell_intent_digest), "escrow-next")
        self.assertEqual(ex.owner_index(R), 0)
        self.assertEqual(ex._escrows, {})

    def test_valid_pair_still_locks_and_executes_at_signed_sell_limit(self):
        ex, _ = F.funded_exchange()
        match = pending_match(ex)
        escrow = ex.lock_escrow(match, "escrow-next")
        leg = ex.execute_transfer(match, "transfer-next", escrow.escrow_id)
        self.assertEqual((leg.price, ex.owner_of(R)), (F.PRICE, F.B))


class ProtectedRegistrationPrefix(unittest.TestCase):
    def test_confirmed_prefix_survives_suffix_rollback_with_every_payment_state(self):
        for outcome in (None, "failed", "unknown", "settled"):
            with self.subTest(outcome=outcome):
                key = "release:escrow-ab"
                ex, _ = F.rollback_chain_to_d(outcomes={key: outcome} if outcome else {})
                requests = F.submit_all(ex)
                F.confirm(ex, requests[0], "confirmed-ab")
                authority = F.release_authority(ex, 0, "release-ab")
                if outcome:
                    ex.release_segment(R, 0, authority)
                original = ex.escrow_for_leg(R, 0)
                F.refuse(ex, requests[1], "refused-bc")
                ex.begin_rollback(R, 1, F.rollback_authority(ex, 1, "rollback"))
                report = ex.advance_rollback(R)
                self.assertEqual(report["affectedLegs"], (1, 2))
                self.assertEqual((ex.owner_index(R), ex.owner_of(R)), (1, F.B))
                self.assertEqual(ex.escrow_for_leg(R, 0), original)
                self.assertIsNone(ex.payments.lookup("refund:escrow-ab"))
                if outcome == "unknown":
                    ex.payments.resolve_unknown(key, "settled")
                    calls = Mock(wraps=ex.payments.pay)
                    ex.payments.pay = calls
                    ex.resume_payments(R)
                    calls.assert_not_called()
                elif outcome != "settled":
                    ex.release_segment(R, 0, authority)
                self.assertEqual(ex.escrow_for_leg(R, 0).status, "released")
                self.assertIsNone(ex.escrow_for_leg(R, 0).refunded_at)
                with self.assertRaises(DomainError):
                    ex.release_segment(R, 0, authority)

    def test_later_rejection_cannot_rewrite_confirmed_registration(self):
        ex, _ = F.rollback_chain_to_d()
        requests = F.submit_all(ex)
        F.confirm(ex, requests[0], "confirmed-ab")
        with self.assertRaises(DomainError):
            F.refuse(ex, requests[0], "late-rejection-ab")
        self.assertEqual(ex.leg(R, 0).registration_status, "confirmed")
        self.assertEqual(ex.rollback_boundary(R)["boundaryIndex"], 1)

    def test_missing_lookup_does_not_resend_unknown_release(self):
        ex, _ = F.rollback_chain_to_d(outcomes={"release:escrow-ab": "unknown"})
        requests = F.submit_all(ex)
        F.confirm(ex, requests[0], "confirmed-ab")
        authority = F.release_authority(ex, 0, "release-ab")
        ex.release_segment(R, 0, authority)
        original = ex.escrow_for_leg(R, 0)
        ex.payments.lookup = Mock(return_value=None)
        ex.payments.pay = Mock(side_effect=AssertionError("must not resend unknown payment"))
        with self.assertRaises(DomainError):
            ex.release_segment(R, 0, authority)
        self.assertEqual(ex.escrow_for_leg(R, 0), original)
        ex.payments.pay.assert_not_called()


class RollbackIsolation(unittest.TestCase):
    def test_open_or_blocked_rollback_freezes_trade_and_late_results(self):
        for advance in (False, True):
            with self.subTest(advance=advance):
                ex, _ = F.rollback_chain_to_d(outcomes={"refund:escrow-ab": "unknown"},
                                               return_outcomes={"return:" + R + ":rb": "unknown"})
                match = pending_match(ex, F.D, F.A, "da", 4)
                requests = F.submit_all(ex)
                F.confirm(ex, requests[2], "early-cd")
                F.refuse(ex, requests[0], "refused-ab")
                ex.begin_rollback(R, 0, F.rollback_authority(ex, 0, "rb"))
                if advance:
                    ex.advance_rollback(R)
                before = copy.deepcopy((ex._legs, ex._escrows, ex._used_nonces))
                for operation in (lambda: ex.lock_escrow(match, "escrow-da"),
                                  lambda: ex.execute_transfer(match, "transfer-da")):
                    with self.assertRaises(DomainError):
                        operation()
                self.assertEqual((ex._legs, ex._escrows, ex._used_nonces), before)
                _, result = F.confirm(ex, requests[0], "late-ab")
                self.assertEqual(result["disposition"], "late-conflict")
                ex._drain_deferred(R)
                self.assertEqual(ex.holder_index(R), 0)
                self.assertEqual(ex.deferred_legs(R), (2,))
                self.assertEqual(len(ex.rollback_report(R)["conflicts"]), 1)

    def test_equal_return_address_restores_occurrence_without_asset_move(self):
        ex, _ = F.rollback_exchange()
        F.funded_hop(ex, F.A, F.B, 1, "transfer-ab", "session-a", "session-b")
        F.funded_hop(ex, F.B, F.A, 2, "transfer-ba", "session-b", "session-a")
        requests = F.submit_all(ex)
        F.refuse(ex, requests[0], "refused-ab")
        ex.begin_rollback(R, 0, F.rollback_authority(ex, 0, "rb"))
        ex.asset_control.return_asset = Mock(side_effect=AssertionError("no asset move needed"))
        report = ex.advance_rollback(R)
        self.assertTrue(report["complete"])
        self.assertEqual((ex.owner_index(R), ex.owner_of(R), ex.recorded_legs(R)), (0, F.A, 2))
        self.assertEqual([leg.rollback_status for leg in ex.legs(R)], ["returned", "returned"])
        ex.asset_control.return_asset.assert_not_called()
        with self.assertRaises(DomainError) as caught:
            pending_match(ex, suffix="again", nonce=3)
        self.assertEqual(caught.exception.code, "EX_MATCH_UNEXECUTABLE")
        self.assertIn("EX_TRADE_RETURNED_CHAIN_CLOSED",
                      ex.validate_intent("sell-again")["reasons"])

    def test_unfunded_suffix_marks_every_leg_returned(self):
        for circular in (False, True):
            with self.subTest(circular=circular):
                ex, _ = F.rollback_exchange()
                ex.funding_required = False
                F.hop(ex, F.A, F.B, 1, "transfer-ab", "session-a", "session-b")
                if circular:
                    F.hop(ex, F.B, F.A, 2, "transfer-ba", "session-b", "session-a")
                requests = F.submit_all(ex)
                F.refuse(ex, requests[0], "refused-ab")
                ex.begin_rollback(R, 0, F.rollback_authority(ex, 0, "rb"))
                self.assertTrue(all(leg.rollback_status == "in-progress" for leg in ex.legs(R)))
                self.assertTrue(ex.advance_rollback(R)["complete"])
                self.assertEqual(ex.owner_index(R), 0)
                self.assertTrue(all(leg.rollback_status == "returned" for leg in ex.legs(R)))
                self.assertEqual(ex.payments.movements, 0)


class ExitIsolation(unittest.TestCase):
    """Retained old physical states isolate mutations but are never replayed."""

    def retain(self, ex, clock, receipt=R, request_id="rdm", account=F.B,
               through=None):
        request = RedemptionRequest(request_id, receipt, account, "historical-auth", clock.now)
        completed = through in EXIT_STEPS
        index = EXIT_STEPS.index(through) if completed else -1
        steps = tuple(ExitStep(
            step, exit_step_key(step, receipt, request_id),
            status="done" if i <= index else "blocked" if through == "blocked" else "pending",
            completed_at=clock.now if i <= index else None,
            detail=(("outcome", "unknown"),) if through == "blocked" else ())
            for i, step in enumerate(EXIT_STEPS))
        ex._exits[receipt] = {
            "request": request, "steps": steps, "verifiedChecks": (),
            "state": "complete" if through == "burn" else "blocked" if through == "blocked" else "open"}
        key = exit_step_key("burn", receipt, request_id)
        record = {"key": key, "step": "burn", "receiptId": receipt, "account": account,
                  "status": "done" if through == "burn" else "unknown",
                  "effect": "applied" if through == "burn" else "unknown"}
        ex.voucher_desk._records[key] = dict(record)
        ex.voucher_desk._history[key] = [dict(record)]
        return key

    def snapshot(self, ex):
        return copy.deepcopy((ex._legs, ex._escrows, ex._used_nonces, ex._exits,
                              ex._events, ex.voucher_desk._records, ex.voucher_desk._history))

    def test_each_retained_phase_refuses_new_funding_and_transfer_without_mutation(self):
        for through in (None,) + EXIT_STEPS + ("blocked",):
            with self.subTest(through=through):
                ex, clock = F.settled_at_b()
                match = pending_match(ex, F.B, F.C, nonce=2)
                self.retain(ex, clock, through=through)
                before = self.snapshot(ex)
                for intent in ("sell-next", "buy-next"):
                    self.assertIn("EX_TRADE_EXIT_OPEN", ex.validate_intent(intent)["reasons"])
                for operation, code in (
                        (lambda: ex.lock_escrow(match, "escrow-next"), "EX_MATCH_UNEXECUTABLE"),
                        (lambda: ex.execute_transfer(match, "transfer-next"), "EX_TRADE_EXIT_OPEN"),
                        (lambda: ex.advance_exit(R), "EX_PHYSICAL_FULFILLMENT_RETIRED")):
                    with self.assertRaises(DomainError) as caught:
                        operation()
                    self.assertEqual(caught.exception.code, code)
                    self.assertEqual(self.snapshot(ex), before)
                self.assertEqual(ex.owner_of(R), F.B)

    def test_same_historical_request_on_two_receipts_keeps_distinct_evidence(self):
        ex, clock = F.minted()
        second = replace(F.receipt(), receipt_id="rcpt-two", receipt_number="WR-two",
                         asset=replace(F.asset(), token_id=F.TOKEN_ID + 1))
        ex.mint(second, specification=F.mint_specification(second))
        first_key = self.retain(ex, clock, request_id="shared", account=F.A)
        second_key = self.retain(ex, clock, receipt=second.receipt_id,
                                 request_id="shared", account=F.A)
        self.assertNotEqual(first_key, second_key)
        original_second = copy.deepcopy(ex._exits[second.receipt_id])
        ex.voucher_desk.resolve_unknown(first_key, "failed")
        self.assertEqual(ex.voucher_desk.lookup(second_key)["status"], "unknown")
        self.assertEqual(len(ex.voucher_desk.history(second_key)), 1)
        self.assertEqual(ex._exits[second.receipt_id], original_second)
        before = self.snapshot(ex)
        for receipt in (R, second.receipt_id):
            report = ex.exit_report(receipt)
            self.assertEqual(report["requestId"], "shared")
            self.assertFalse(report["executable"])
            with self.assertRaises(DomainError) as caught:
                ex.advance_exit(receipt)
            self.assertEqual(caught.exception.code, "EX_PHYSICAL_FULFILLMENT_RETIRED")
        self.assertEqual(self.snapshot(ex), before)

    def test_direct_desk_never_replays_retained_or_substituted_bindings(self):
        ex, clock = F.settled_at_b()
        key = self.retain(ex, clock)
        before = self.snapshot(ex)
        for candidate_key, step, receipt, account in (
                (key, "burn", R, F.B), (key, "burn", "other", F.B),
                (key, "burn", R, F.C), (key, "voucher-issued", R, F.B),
                ("unseen-key", "burn", R, F.B)):
            with self.subTest(key=candidate_key, step=step, receipt=receipt, account=account):
                with self.assertRaises(DomainError) as caught:
                    ex.voucher_desk.act(candidate_key, step, receipt, account)
                self.assertEqual(caught.exception.code, "EX_PHYSICAL_FULFILLMENT_RETIRED")
                self.assertEqual(self.snapshot(ex), before)

    def test_expiration_and_disconnect_do_not_erase_or_replay_completed_history(self):
        ex, clock = F.settled_at_b()
        key = self.retain(ex, clock, through="burn")
        before = self.snapshot(ex)
        clock.advance(1_000_000)
        ex.disconnect_wallet(F.B)
        report = ex.exit_report(R)
        self.assertTrue(report["complete"])
        self.assertTrue(report["historyPreserved"])
        self.assertFalse(report["executable"])
        self.assertEqual(ex.voucher_desk.lookup(key)["status"], "done")
        with self.assertRaises(DomainError) as caught:
            ex.advance_exit(R)
        self.assertEqual(caught.exception.code, "EX_PHYSICAL_FULFILLMENT_RETIRED")
        self.assertEqual(self.snapshot(ex), before)

    def test_exit_keys_are_unambiguous_and_bounded(self):
        self.assertNotEqual(exit_step_key("burn", "a:b", "c"),
                            exit_step_key("burn", "a", "b:c"))
        self.assertLessEqual(len(exit_step_key("voucher-handover-confirmed", "a" * 128,
                                               "b" * 128)), 128)
