"""Focused event-to-live business projection acceptance, independent of counters."""
import copy
import unittest
from exchange import fixtures as F
from exchange import audit_projection as P
from exchange.errors import DomainError

R = 'rcpt-8415-0001'


class BusinessProjection(unittest.TestCase):
    def check_projection(self, ex):
        timeline = ex.receipt_timeline(R)
        expected = P.live(ex, R)
        self.assertEqual(P.project(timeline), expected)
        self.assertEqual(P.project(list(timeline) * 2), expected)
        return expected

    def test_mint_and_unfunded_transfers(self):
        ex, _ = F.minted()
        self.assertEqual(self.check_projection(ex)['holder']['position'], 0)
        F.hop(ex, F.A, F.B, 1, 'transfer-ab', 'session-a', 'session-b')
        self.check_projection(ex)

    def test_deferred_prefix_and_release(self):
        ex, _ = F.funded_chain_to_d()
        self.check_projection(ex)
        requests = F.submit_all(ex)
        F.confirm(ex, requests[1], 'res-1')
        self.check_projection(ex)
        F.confirm(ex, requests[0], 'res-0')
        self.check_projection(ex)
        ex.release_segment(R, 0, F.release_authority(ex, 0, 'rel-0'))
        self.check_projection(ex)

    def test_unknown_release_resolved_by_enquiry(self):
        ex, _ = F.funded_chain_to_d(outcomes={'release:escrow-ab': 'unknown'})
        requests = F.submit_all(ex)
        F.confirm(ex, requests[0], 'res-0')
        ex.release_segment(R, 0, F.release_authority(ex, 0, 'rel-0'))
        self.check_projection(ex)
        ex.payments.resolve_unknown('release:escrow-ab', 'settled')
        ex.resume_payments(R)
        self.assertEqual(self.check_projection(ex)['escrows']['escrow-ab']['status'], 'released')

    def test_rollback_and_unknown_refund_recovery(self):
        ex, _ = F.rollback_chain_to_d(outcomes={'refund:escrow-ab': 'unknown'})
        requests = F.submit_all(ex)
        F.refuse(ex, requests[0], 'no-ab')
        ex.begin_rollback(R, 0, F.rollback_authority(ex, 0, 'rb'))
        self.check_projection(ex)
        ex.advance_rollback(R)
        self.check_projection(ex)
        ex.payments.resolve_unknown('refund:escrow-ab', 'settled')
        ex.resume_payments(R)
        self.check_projection(ex)
        ex.advance_rollback(R)
        self.check_projection(ex)

    def test_exit_steps_and_burn(self):
        ex, clock = F.settled_at_b()
        F.redeem_authorization(ex)
        ex.request_redemption(R, F.B, 'auth-redeem', 'exit-1', F.ALL_CHECKS)
        self.check_projection(ex)
        for step in ('stop-resale', 'voucher-issued', 'voucher-handover-confirmed', 'burn'):
            clock.advance(1)
            ex.advance_exit(R, through=step)
            self.check_projection(ex)

    def test_blocked_exit_remains_separate_from_burn(self):
        from exchange.exit import exit_step_key
        ex, _ = F.settled_at_b(voucher_outcomes={exit_step_key('burn', R, 'exit-1'): 'unknown'})
        F.redeem_authorization(ex)
        ex.request_redemption(R, F.B, 'auth-redeem', 'exit-1', F.ALL_CHECKS)
        ex.advance_exit(R)
        state = self.check_projection(ex)
        self.assertEqual(state['exit']['state'], 'blocked')
        self.assertFalse(state['exit']['burned'])

    def test_circular_return_updates_position_without_an_asset_operation(self):
        ex, _ = F.exit_exchange()
        F.funded_hop(ex, F.A, F.B, 1, 'transfer-ab', 'session-a', 'session-b')
        F.funded_hop(ex, F.B, F.A, 2, 'transfer-ba', 'session-b', 'session-a')
        requests = F.submit_all(ex)
        F.refuse(ex, requests[0], 'no-ab')
        ex.begin_rollback(R, 0, F.rollback_authority(ex, 0, 'rb'))
        ex.advance_rollback(R)
        state = self.check_projection(ex)
        self.assertEqual(state['owner'], {'account': F.A, 'position': 0})
        self.assertEqual(ex.asset_control.returns, 0)
        self.assertEqual(state['recordedLegs'], 2)

    def test_failed_release_and_nonterminal_enquiry(self):
        ex, _ = F.funded_chain_to_d(outcomes={'release:escrow-ab': 'failed'})
        requests = F.submit_all(ex)
        F.confirm(ex, requests[0], 'res-0')
        ex.release_segment(R, 0, F.release_authority(ex, 0, 'rel-0'))
        self.check_projection(ex)
        ex.resume_payments(R)
        self.check_projection(ex)

    def test_changed_business_payload_changes_projection(self):
        ex, _ = F.minted()
        timeline = copy.deepcopy(ex.receipt_timeline(R))
        timeline[0]['detail']['origin'] = F.B
        self.assertNotEqual(P.project(timeline), P.live(ex, R))

    def test_conflicting_duplicate_is_refused(self):
        ex, _ = F.minted()
        first = ex.receipt_timeline(R)[0]
        changed = copy.deepcopy(first)
        changed['detail']['origin'] = F.B
        with self.assertRaises(DomainError):
            P.project([first, changed])

    def test_changed_run_or_disagreeing_receipt_are_refused(self):
        ex, _ = F.funded_chain_to_d()
        for key, value in (('runId', 'another-run'), ('receiptId', 'another-receipt')):
            with self.subTest(key=key):
                timeline = copy.deepcopy(ex.receipt_timeline(R))
                timeline[1]['correlation'][key] = value
                with self.assertRaises(DomainError):
                    P.project(timeline)

    def test_undeclared_kind_is_refused(self):
        ex, _ = F.minted()
        timeline = copy.deepcopy(ex.receipt_timeline(R))
        timeline[0]['kind'] = 'receipt-minted-typo'
        with self.assertRaises(DomainError):
            P.project(timeline)

    def test_reordered_unique_events_are_refused(self):
        ex, _ = F.funded_chain_to_d()
        with self.assertRaises(DomainError):
            P.project(list(reversed(ex.receipt_timeline(R))))
