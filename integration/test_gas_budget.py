"""Authored gas contract fixtures; no real provider or wallet is called."""
import unittest
from dataclasses import replace
from fractions import Fraction
from exchange.gas_budget import (FeeSample, GasQuote, BuyerConfirmation, GasFreeze,
    GasConsumption, GasBudgetBook, GasBudgetRefused)


def quote(fees=(10, 30, 20)):
    samples = tuple(FeeSample('sample-' + str(i), 'transfer-1', 11155111,
        fee, 90 + i, 100 + i, 'fixture-provider', str(i) * 64)
        for i, fee in enumerate(fees))
    return GasQuote('quote-1', 1, 'budget-1', 'transfer-1', ('transfer', 'register'),
        11155111, 100, samples, 90, 99, 100, 200, 3000000000, 100,
        'fixture-fx', 'a' * 64)


def facts(q):
    confirmation = BuyerConfirmation(q.digest, 'buyer-1', 'action-digest-1',
        'grant-1', 101, 'buyer-proof-1')
    frozen = GasFreeze(q.budget_id, 'buyer-1', q.chain_id, q.cap_wei, q.digest,
        'wallet-freeze-1', 'FROZEN')
    return confirmation, frozen


def used(attempt='attempt-1', amount=40, outcome='SUCCESS', tx='1'):
    return GasConsumption(attempt, '0x' + tx * 64, amount, outcome, 'evm-proof-1')


class GasBudgetContracts(unittest.TestCase):
    def setUp(self):
        self.q = quote()
        self.confirmation, self.frozen = facts(self.q)
        self.book = GasBudgetBook(lambda kind, evidence: True)
        self.book.open(self.q, self.confirmation, self.frozen, 102)

    def test_real_sorted_median_and_odd_even_precision(self):
        self.assertEqual(self.q.median_wei, 20)
        even = quote((10, 11))
        self.assertEqual(even.median_wei, Fraction(21, 2))
        display = even.disclosure()
        self.assertEqual(display['median']['ETH'], '0.0000000000000000105')
        self.assertEqual(display['median']['USD'], '0.0000000000000315000000000')
        self.assertEqual(display['sampleCount'], 2)
        self.assertEqual(len(display['samples']), 2)
        self.assertEqual(display['cap']['ETH'], '0.0000000000000001000')

    def test_no_single_point_duplicates_or_inapplicable_samples(self):
        for samples in ((self.q.samples[0],), (self.q.samples[0], self.q.samples[0]),
                        (self.q.samples[0], replace(self.q.samples[1], chain_id=560048)),
                        (self.q.samples[0], replace(self.q.samples[1], scope='different'))):
            with self.subTest(samples=samples), self.assertRaises(GasBudgetRefused):
                replace(self.q, samples=samples)

    def test_exact_numbers_same_instant_fx_and_window(self):
        for changes in ({'cap_wei': True}, {'cap_wei': 1.5},
                        {'rate_observed_at': 99}, {'window_end': 101},
                        {'cap_wei': 1}, {'rate_sha256': 'missing'}):
            with self.subTest(changes=changes), self.assertRaises(GasBudgetRefused):
                replace(self.q, **changes)

    def test_confirmation_covers_the_entire_disclosure(self):
        changed = replace(self.q, version=2, cap_wei=110)
        with self.assertRaises(GasBudgetRefused):
            GasBudgetBook(lambda k, e: True).open(changed, self.confirmation, self.frozen, 102)
        with self.assertRaises(GasBudgetRefused):
            GasBudgetBook(lambda k, e: False).open(self.q, self.confirmation, self.frozen, 102)

    def test_freeze_is_separate_exact_and_known(self):
        for changes in ({'amount_wei': 99}, {'status': 'UNKNOWN'},
                        {'account_kind': 'PRICE_PRINCIPAL'}, {'buyer': 'other'},
                        {'chain_id': 560048}):
            with self.subTest(changes=changes), self.assertRaises(GasBudgetRefused):
                GasBudgetBook(lambda k, e: True).open(self.q, self.confirmation,
                    replace(self.frozen, **changes), 102)

    def test_retry_or_split_cannot_reset_aggregate_cap(self):
        self.book.reserve('budget-1', 'attempt-1', 'transfer', 60, 110)
        with self.assertRaises(GasBudgetRefused):
            self.book.reserve('budget-1', 'attempt-2', 'register', 41, 110)
        new = replace(self.q, quote_id='new-quote')
        c, f = facts(new)
        with self.assertRaises(GasBudgetRefused):
            self.book.open(new, c, f, 110)

    def test_actual_failed_gas_is_debited_and_unused_is_releasable(self):
        self.book.reserve('budget-1', 'attempt-1', 'transfer', 60, 110)
        evidence = used(outcome='FAILED')
        first = self.book.reconcile('budget-1', evidence)
        self.assertEqual(first['actualConsumedWei'], 40)
        self.assertEqual(self.book.reconcile('budget-1', evidence), first)
        closed = self.book.close('budget-1')
        self.assertEqual(closed['unfreezeProposalWei'], 60)
        self.assertEqual(closed['walletDebit'], 'NOT_RUN')
        self.assertEqual(closed['walletUnfreeze'], 'NOT_RUN')
        self.assertEqual(self.book.close('budget-1'), closed)

    def test_unknown_outcome_does_not_release_or_erase_reservation(self):
        self.book.reserve('budget-1', 'attempt-1', 'transfer', 60, 110)
        before = self.book.snapshot('budget-1')
        with self.assertRaises(GasBudgetRefused):
            self.book.reconcile('budget-1', used(outcome='UNKNOWN'))
        with self.assertRaises(GasBudgetRefused):
            self.book.close('budget-1')
        self.assertEqual(self.book.snapshot('budget-1'), before)

    def test_duplicate_transaction_under_new_attempt_cannot_charge_twice(self):
        self.book.reserve('budget-1', 'attempt-1', 'transfer', 60, 110)
        self.book.reconcile('budget-1', used())
        self.book.reserve('budget-1', 'attempt-2', 'register', 50, 111)
        with self.assertRaises(GasBudgetRefused):
            self.book.reconcile('budget-1', used('attempt-2', 10))
        self.assertEqual(self.book.snapshot('budget-1')['actualConsumedWei'], 40)

    def test_expired_uncovered_and_excess_bound_are_refused(self):
        for action, maximum, now in (('transfer', 20, 200), ('unknown', 20, 110),
                                     ('transfer', 101, 110)):
            with self.subTest(action=action, maximum=maximum, now=now):
                with self.assertRaises(GasBudgetRefused):
                    self.book.reserve('budget-1', 'attempt-1', action, maximum, now)
        self.assertEqual(self.book.snapshot('budget-1')['pendingBoundWei'], 0)

    def test_same_operation_cannot_reset_with_new_budget_id(self):
        replacement = replace(self.q, quote_id='quote-2', budget_id='budget-2')
        c, f = facts(replacement)
        with self.assertRaises(GasBudgetRefused):
            self.book.open(replacement, c, f, 110)

    def test_changed_consumption_or_over_reservation_preserves_state(self):
        self.book.reserve('budget-1', 'attempt-1', 'transfer', 60, 110)
        before = self.book.snapshot('budget-1')
        with self.assertRaises(GasBudgetRefused):
            self.book.reconcile('budget-1', used(amount=61))
        self.assertEqual(self.book.snapshot('budget-1'), before)
        self.book.reconcile('budget-1', used())
        with self.assertRaises(GasBudgetRefused):
            self.book.reconcile('budget-1', used(amount=39))
