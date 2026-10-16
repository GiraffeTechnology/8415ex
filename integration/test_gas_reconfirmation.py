"""Authored quote revision fixtures; wallet adjustment evidence is synthetic."""
import unittest
from dataclasses import replace
from exchange.gas_budget import GasBudgetRefused
from exchange.gas_reconfirmation import RevisableGasBudgetBook, GasAdjustment
from integration.test_gas_budget import quote, facts, used


class GasRevisionContracts(unittest.TestCase):
    def setUp(self):
        self.q = quote()
        self.c, self.f = facts(self.q)
        self.book = RevisableGasBudgetBook(lambda kind, evidence: True)
        self.book.open(self.q, self.c, self.f, 102)
        self.book.reserve('budget-1', 'attempt-1', 'transfer', 60, 110)
        self.book.reconcile('budget-1', used(amount=40, outcome='FAILED'))
        self.new = replace(self.q, quote_id='quote-2', version=2, cap_wei=160,
                           quoted_at=120, rate_observed_at=120, valid_until=220)
        self.nc, unused = facts(self.new)
        self.nc = replace(self.nc, confirmed_at=121)
        self.adjustment = GasAdjustment('adjust-1', 'budget-1', self.q.digest,
            self.new.digest, 'buyer-1', 11155111, 40, 120, 'wallet-freeze-1',
            'wallet-freeze-2', 'APPLIED')

    def revise(self, **changes):
        return self.book.revise('budget-1', self.new, self.nc,
                                replace(self.adjustment, **changes), 122)

    def test_increased_cap_preserves_actual_failed_consumption(self):
        revised = self.revise()
        self.assertEqual(revised['capWei'], 160)
        self.assertEqual(revised['actualConsumedWei'], 40)
        self.assertEqual(revised['unusedWei'], 120)
        self.book.reserve('budget-1', 'attempt-2', 'register', 120, 123)
        with self.assertRaises(GasBudgetRefused):
            self.book.reserve('budget-1', 'attempt-3', 'register', 1, 123)

    def test_duplicate_revision_is_idempotent(self):
        first = self.revise()
        self.assertEqual(self.revise(), first)
        self.book.reserve('budget-1', 'attempt-2', 'register', 100, 123)
        current = self.book.snapshot('budget-1')
        self.assertEqual(self.revise(), current)

    def test_pending_unknown_attempt_blocks_revision(self):
        self.book.reserve('budget-1', 'pending', 'register', 20, 111)
        before = self.book.snapshot('budget-1')
        with self.assertRaises(GasBudgetRefused):
            self.revise()
        self.assertEqual(self.book.snapshot('budget-1'), before)

    def test_missing_failed_or_insufficient_adjustment_keeps_old_quote(self):
        for changes in ({'status': 'UNKNOWN'}, {'status': 'FAILED'},
                        {'effective_frozen_wei': 119}, {'actual_consumed_wei': 0},
                        {'account_kind': 'PRICE_PRINCIPAL'}, {'buyer': 'other'}):
            with self.subTest(changes=changes), self.assertRaises(GasBudgetRefused):
                self.revise(**changes)
        self.assertEqual(self.book.snapshot('budget-1')['quoteDigest'], self.q.digest)

    def test_new_version_requires_new_confirmation(self):
        with self.assertRaises(GasBudgetRefused):
            self.book.revise('budget-1', self.new, self.c, self.adjustment, 122)
        bad = replace(self.nc, wallet_grant='broader-grant')
        with self.assertRaises(GasBudgetRefused):
            self.book.revise('budget-1', self.new, bad, self.adjustment, 122)

    def test_changed_operation_scope_and_old_proof_are_refused(self):
        for changes in ({'previous_quote_digest': 'wrong'},
                        {'previous_freeze_reference': 'other-freeze'}, {'chain_id': 560048}):
            with self.subTest(changes=changes), self.assertRaises(GasBudgetRefused):
                self.revise(**changes)
        changed = replace(self.new, actions=('different',))
        c, unused = facts(changed)
        c = replace(c, confirmed_at=121)
        with self.assertRaises(GasBudgetRefused):
            self.book.revise('budget-1', changed, c,
                replace(self.adjustment, new_quote_digest=changed.digest), 122)

    def test_new_transaction_charges_only_its_actual_cost_after_revision(self):
        self.revise()
        self.book.reserve('budget-1', 'attempt-2', 'register', 120, 123)
        self.book.reconcile('budget-1', used('attempt-2', amount=80, tx='2'))
        closed = self.book.close('budget-1')
        self.assertEqual(closed['actualConsumedWei'], 120)
        self.assertEqual(closed['unfreezeProposalWei'], 40)
        self.assertEqual(closed['walletUnfreeze'], 'NOT_RUN')

    def test_external_adjustment_must_be_verified(self):
        self.book.verify = lambda kind, evidence: kind != 'gas-budget-adjustment'
        before = self.book.snapshot('budget-1')
        with self.assertRaises(GasBudgetRefused):
            self.revise()
        self.assertEqual(self.book.snapshot('budget-1'), before)
