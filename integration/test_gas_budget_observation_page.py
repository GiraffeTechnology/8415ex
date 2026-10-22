"""Budget observation contracts; synthetic original book, no Wallet/network."""
from copy import deepcopy
import unittest

from exchange.gas_budget import GasBudgetBook, GasBudgetRefused
from exchange.gas_confirmation_ui import GasConfirmationPage
from exchange.gas_budget_observation_page import WORDS
from integration.test_gas_budget import quote, facts, used


class GasBudgetObservationContracts(unittest.TestCase):
    def setUp(self):
        self.q = quote()
        self.confirmation, frozen = facts(self.q)
        self.book = GasBudgetBook(lambda kind, evidence: True)
        self.book.open(self.q, self.confirmation, frozen, 102)
        self.reads, self.confirms = [], []

    def read(self, budget_id):
        self.reads.append(budget_id)
        return self.book.snapshot(budget_id)

    def page(self, reader=None):
        def confirm(*args):
            self.confirms.append(args)
            return self.confirmation
        return GasConfirmationPage(lambda: self.q, confirm, 'buyer-1',
            'action-digest-1', 'grant-1', '/gas', lambda token: token == 'csrf',
            read_original_budget=reader)

    def fields(self):
        return {'csrf': 'csrf', 'quoteId': self.q.quote_id,
                'version': str(self.q.version), 'quoteDigest': self.q.digest,
                'accepted': 'yes'}

    def test_unknown_attempt_keeps_reservation_and_no_release_proposal(self):
        self.book.reserve(self.q.budget_id, 'pending', 'transfer', 60, 110)
        before = self.book.snapshot(self.q.budget_id)
        document = self.page(self.read).render(110, 'csrf')
        self.assertIn('<dt>' + WORDS['en']['pending'] + '</dt><dd>60 ETH wei</dd>', document)
        self.assertIn('<dt>' + WORDS['en']['unused'] + '</dt><dd>100 ETH wei</dd>', document)
        self.assertIn('<dd>Not proposed</dd>', document)
        with self.assertRaises(GasBudgetRefused):
            self.book.close(self.q.budget_id)
        self.assertEqual(self.book.snapshot(self.q.budget_id), before)
        self.assertEqual(self.confirms, [])

    def test_failed_receipt_cost_and_unused_proposal_are_separate(self):
        self.book.reserve(self.q.budget_id, 'attempt-1', 'transfer', 60, 110)
        self.book.reconcile(self.q.budget_id, used(outcome='FAILED'))
        closed = self.book.close(self.q.budget_id)
        document = self.page(self.read).render(110, 'csrf')
        for key, value in (('spent', 40), ('unused', 60), ('proposal', 60), ('pending', 0)):
            self.assertIn('<dt>' + WORDS['en'][key] + '</dt><dd>'
                          + str(value) + ' ETH wei</dd>', document)
        self.assertEqual(closed['walletDebit'], 'NOT_RUN')
        self.assertEqual(closed['walletUnfreeze'], 'NOT_RUN')
        self.assertEqual(self.book.snapshot(self.q.budget_id), closed)

    def test_duplicate_consumption_and_repeated_reads_never_double_charge(self):
        self.book.reserve(self.q.budget_id, 'attempt-1', 'transfer', 60, 110)
        self.book.reconcile(self.q.budget_id, used(outcome='FAILED'))
        before = self.book.reconcile(self.q.budget_id, used(outcome='FAILED'))
        page = self.page(self.read)
        self.assertEqual(page.render(110, 'csrf'), page.render(110, 'csrf'))
        self.assertEqual(self.book.snapshot(self.q.budget_id), before)
        self.assertEqual(self.reads, [self.q.budget_id] * 2)
        self.assertEqual(self.confirms, [])

    def test_all_locales_show_exact_zero_and_exclude_private_extra_fields(self):
        value = self.book.snapshot(self.q.budget_id)
        value.update(buyer='PRIVATE_BUYER', journal='PRIVATE_JOURNAL', error='<script>PRIVATE</script>')
        for locale, words in WORDS.items():
            document = self.page(lambda _: deepcopy(value)).render(110, 'csrf', locale)
            self.assertIn(words['heading'], document)
            self.assertIn('<dt>' + words['spent'] + '</dt><dd>0 ETH wei</dd>', document)
            self.assertNotIn('PRIVATE_', document)
            self.assertNotIn('<script>', document)
            self.assertNotIn(self.q.budget_id, document)

    def test_reader_failure_does_not_block_confirmation_or_leak_error(self):
        def unavailable(_):
            raise RuntimeError('PRIVATE_SOURCE_FAILURE')
        page = self.page(unavailable)
        document = page.render(110, 'csrf')
        self.assertIn(WORDS['en']['unavailable'], document)
        self.assertIn('<form method="post"', document)
        self.assertNotIn('PRIVATE_SOURCE_FAILURE', document)
        self.assertIs(page.submit(self.fields(), 110), self.confirmation)
        self.assertEqual(len(self.confirms), 1)

    def test_missing_conflicting_or_inconsistent_snapshot_is_unavailable(self):
        value = self.book.snapshot(self.q.budget_id)
        changes = ({'budgetId': 'other'}, {'quoteDigest': 'b' * 64},
                   {'capWei': 101}, {'actualConsumedWei': True},
                   {'pendingBoundWei': 101}, {'unusedWei': 99},
                   {'closed': True}, {'unfreezeProposalWei': 0},
                   {'closed': 1}, {'actualConsumedWei': '0'})
        for change in changes:
            with self.subTest(change=change):
                document = self.page(lambda _, c=change: dict(value, **c)).render(110, 'csrf')
                self.assertIn('data-gas-budget-observation="unavailable"', document)
                self.assertIn('<form method="post"', document)
        missing = dict(value)
        del missing['unfreezeProposalWei']
        document = self.page(lambda _: missing).render(110, 'csrf')
        self.assertIn('data-gas-budget-observation="unavailable"', document)

    def test_existing_default_and_post_fields_keep_original_contract(self):
        page = self.page()
        self.assertNotIn('data-gas-budget-observation', page.render(110, 'csrf'))
        page = self.page(self.read)
        page.render(110, 'csrf')
        reads = list(self.reads)
        with self.assertRaises(GasBudgetRefused):
            page.submit(dict(self.fields(), unfreezeProposalWei='100'), 110)
        self.assertEqual(self.confirms, [])
        self.assertIs(page.submit(self.fields(), 110), self.confirmation)
        self.assertEqual(self.reads, reads)

    def test_expired_quote_does_not_become_valid_through_budget_observation(self):
        with self.assertRaises(GasBudgetRefused):
            self.page(self.read).render(self.q.valid_until, 'csrf')
        self.assertEqual(self.reads, [])
        self.assertEqual(self.confirms, [])


if __name__ == '__main__':
    unittest.main()
