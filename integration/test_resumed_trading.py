"""Recovered paths use fresh global IDs; local model evidence only."""
import copy
import unittest
from exchange import fixtures as F
from exchange.errors import DomainError

R = "rcpt-8415-0001"


class RecoveredTrading(unittest.TestCase):
    def recovery(self, prefix=True, outcomes=None):
        exchange, clock = F.rollback_chain_to_d(outcomes=outcomes)
        requests = F.submit_all(exchange)
        if prefix:
            F.confirm(exchange, requests[0], "prefix-ab")
            refused = 1
        else:
            refused = 0
        F.refuse(exchange, requests[refused], "refused")
        authority = F.rollback_authority(exchange, refused, "recover-1")
        exchange.begin_rollback(R, refused, authority)
        exchange.advance_rollback(R)
        return exchange, clock, requests

    def allow_current_validity(self, exchange):
        original = exchange._mint_book.verify
        def verifier(kind, payload):
            return True if kind == "current-asset-validity" else original(kind, payload)
        exchange._mint_book.verify = verifier

    def test_registered_prefix_and_refunded_history_survive_new_global_leg(self):
        exchange, clock, requests = self.recovery()
        self.allow_current_validity(exchange)
        old = exchange.legs(R)
        escrow_ids = dict(exchange._escrow_by_leg[R])
        result = exchange.resume_trading(R)
        self.assertEqual(result["activeLegs"], (0,))
        self.assertEqual(result["nextGlobalLegIndex"], 3)
        escrow, leg = F.funded_hop(exchange, F.B, F.C, 4, "transfer-new-bc",
            "session-b", "session-c", price=F.PRICE_BC)
        self.assertEqual(leg.leg_index, 3)
        self.assertEqual(leg.predecessor_transfer_id, old[0].transfer_id)
        self.assertNotIn(escrow.escrow_id, tuple(escrow_ids.values()))
        request, _ = exchange.submit_registration(R, 3, "request-new-bc", 100)
        F.confirm(exchange, request, "new-bc-confirmed")
        self.assertEqual(exchange.holder_of(R), F.C)
        self.assertTrue(exchange.segment_release_state(R, 3)["eligible"])
        self.assertFalse(exchange.segment_release_state(R, 1)["eligible"])
        self.assertEqual(exchange.legs(R)[:3], old)
        self.assertEqual(exchange.active_leg_indices(R), (0, 3))
        self.assertEqual(exchange.recorded_legs(R), 4)
        self.assertEqual(exchange.receipt_view(R)["registeredPrefixLegs"], 2)
        self.assertEqual(len(exchange.historical_rollbacks(R)), 1)

    def test_full_suffix_return_starts_at_original_holder_without_reusing_legs(self):
        exchange, clock, requests = self.recovery(prefix=False)
        self.allow_current_validity(exchange)
        exchange.resume_trading(R)
        self.assertEqual(exchange.owner_of(R), F.A)
        self.assertEqual(exchange.holder_of(R), F.A)
        escrow, leg = F.funded_hop(exchange, F.A, F.B, 4, "transfer-new-ab",
            "session-a", "session-b", price=F.PRICE_AB)
        self.assertEqual(leg.leg_index, 3)
        self.assertIsNone(leg.predecessor_transfer_id)
        self.assertEqual(exchange.active_leg_indices(R), (3,))

    def test_unknown_refund_remains_incomplete_even_if_asset_has_returned(self):
        exchange, clock, requests = self.recovery(
            outcomes={"refund:escrow-bc": "unknown"})
        self.allow_current_validity(exchange)
        self.assertEqual(exchange.owner_of(R), exchange.holder_of(R))
        with self.assertRaises(DomainError) as caught:
            exchange.resume_trading(R)
        self.assertEqual(caught.exception.code, "EX_RECOVERY_INCOMPLETE")
        self.assertEqual(exchange.historical_rollbacks(R), ())

    def test_current_validity_is_not_inherited_from_old_mint(self):
        exchange, clock, requests = self.recovery()
        before = copy.deepcopy(exchange.rollback_report(R))
        with self.assertRaises(DomainError) as caught:
            exchange.resume_trading(R)
        self.assertEqual(caught.exception.code, "EX_ASSET_VALIDITY_NOT_VERIFIED")
        self.assertEqual(exchange.rollback_report(R), before)
        self.assertEqual(exchange.historical_rollbacks(R), ())

    def test_expired_asset_does_not_reopen_after_completed_recovery(self):
        exchange, clock, requests = self.recovery()
        self.allow_current_validity(exchange)
        clock.now = exchange.receipt(R).trade_stop_at
        with self.assertRaises(DomainError) as caught:
            exchange.resume_trading(R)
        self.assertEqual(caught.exception.code, "EX_TRADE_WINDOW_CLOSED")
        self.assertEqual(exchange.historical_rollbacks(R), ())

    def test_old_result_cannot_revive_withdrawn_leg_after_resume(self):
        exchange, clock, requests = self.recovery()
        self.allow_current_validity(exchange)
        exchange.resume_trading(R)
        evidence = exchange.registrars["REG_DIRECT"].result(
            requests[1], "confirmed", "late-old-bc")
        result = exchange.apply_registration_result(evidence)
        self.assertEqual(result["disposition"], "late-conflict")
        self.assertEqual(exchange.holder_of(R), F.B)
        self.assertEqual(exchange.active_leg_indices(R), (0,))
        self.assertEqual(exchange.leg(R, 1).rollback_status, "returned")
        self.assertFalse(exchange.segment_release_state(R, 1)["eligible"])
        self.assertEqual(len(exchange.historical_rollbacks(R)[0]["conflicts"]), 1)
        with self.assertRaises(DomainError):
            exchange.submit_registration(R, 1, "old-request-retry", 100)

    def test_second_recovery_uses_only_new_suffix_and_keeps_global_identity(self):
        exchange, clock, requests = self.recovery()
        self.allow_current_validity(exchange)
        exchange.resume_trading(R)
        F.funded_hop(exchange, F.B, F.C, 4, "transfer-new-bc",
            "session-b", "session-c", price=F.PRICE_BC)
        request, _ = exchange.submit_registration(R, 3, "request-new-bc", 100)
        F.refuse(exchange, request, "new-refusal")
        authority = F.rollback_authority(exchange, 3, "recover-2")
        state = exchange.begin_rollback(R, 3, authority)
        self.assertEqual(state["affectedLegs"], (3,))
        exchange.advance_rollback(R)
        exchange.resume_trading(R)
        self.assertEqual(len(exchange.historical_rollbacks(R)), 2)
        escrow, leg = F.funded_hop(exchange, F.B, F.D, 5, "transfer-new-bd",
            "session-b", "session-d", price=F.PRICE_CD)
        self.assertEqual(leg.leg_index, 4)
        self.assertEqual(exchange.active_leg_indices(R), (0, 4))
        self.assertEqual(exchange.owner_of(R), F.D)

    def test_ordinary_resale_need_not_wait_for_holder_after_resume(self):
        exchange, clock, requests = self.recovery()
        self.allow_current_validity(exchange)
        exchange.resume_trading(R)
        F.funded_hop(exchange, F.B, F.C, 4, "transfer-new-bc",
            "session-b", "session-c", price=F.PRICE_BC)
        F.funded_hop(exchange, F.C, F.D, 5, "transfer-new-cd",
            "session-c", "session-d", price=F.PRICE_CD)
        self.assertEqual(exchange.owner_of(R), F.D)
        self.assertEqual(exchange.holder_of(R), F.B)
        self.assertEqual(exchange.active_leg_indices(R), (0, 3, 4))

    def test_cutoff_report_keeps_fixed_rule_and_requires_original_authority(self):
        exchange, clock = F.rollback_chain_to_d()
        F.submit_all(exchange)
        before = copy.deepcopy(exchange.receipt_timeline(R))
        clock.now = exchange.receipt(R).trade_stop_at
        report = exchange.evaluate_deadline(R)
        self.assertFalse(report["newTradesAccepted"])
        self.assertEqual(report["undefinedOrdering"], ())
        self.assertTrue(report["requiresAuthoritativeReconciliation"])
        self.assertFalse(report["graceReceiptRequired"])
        self.assertFalse(report["recoveryExecutedByReport"])
        self.assertEqual(exchange.receipt_timeline(R), before)
        self.assertEqual(exchange.owner_of(R), F.D)
        self.assertEqual(exchange.holder_of(R), F.A)

    def test_completed_return_is_not_reported_open_before_resume(self):
        exchange, clock, requests = self.recovery()
        self.assertFalse(exchange.evaluate_deadline(R)["newTradesAccepted"])
        self.allow_current_validity(exchange)
        exchange.resume_trading(R)
        self.assertTrue(exchange.evaluate_deadline(R)["newTradesAccepted"])
