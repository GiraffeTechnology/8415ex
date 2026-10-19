"""Archived rollback source/time/privacy definitions; approved Linux only."""
from copy import deepcopy
import unittest

from exchange.rollback_projection import rollback_history_projection, RollbackProjectionRefused
from exchange.rollback_page import render_rollback, HISTORY
from integration import test_rollback_projection as fixtures


class HistoricalRollbackDomain(fixtures.RollbackDomain):
    def __init__(self):
        super().__init__()
        original = deepcopy(self.report)
        original.update(historical=True, complete=True, state='complete',
                        finalizedPrefixLegs=1, observedAt=70, outstandingSteps=())
        original['assetControl']['returned'] = True
        original['funds'][0].update(escrowStatus='refunded', refundedToOriginalBuyer=True,
                                    netToOriginalBuyer='1000')
        self.archive = [original]

    def historical_rollbacks(self, receipt_id):
        return deepcopy(self.archive)


class RollbackHistoryViewTests(unittest.TestCase):
    def test_archived_time_and_funds_never_inherit_current_positions(self):
        domain = HistoricalRollbackDomain()
        result = rollback_history_projection(domain, 'receipt-1')
        row = result['reports'][0]
        self.assertEqual(row['observedAt'], 70)
        self.assertEqual(row['registeredPrefixLegs'], 1)
        self.assertIsNone(row['holderPosition'])
        self.assertIsNone(row['ownerPosition'])
        self.assertIsNone(row['outstandingLegs'])
        self.assertEqual(row['funds'][0]['netToOriginalBuyer'], '1000')
        self.assertEqual(row['funds'][0]['gasTotal'], '17')
        self.assertFalse(row['nativeCompletionVerified'])
        for private in ('PRIVATE-WALLET', 'PRIVATE-JOURNAL', 'PRIVATE-PROOF', 'PRIVATE-BUYER'):
            self.assertNotIn(private, str(result))

    def test_foreign_unmarked_and_reordered_archives_refuse(self):
        for key, value in (('receiptId', 'other'), ('historical', False),
                           ('observedAt', True), ('observedAt', 101), ('complete', False)):
            domain = HistoricalRollbackDomain()
            domain.archive[0][key] = value
            with self.subTest(key=key), self.assertRaises(RollbackProjectionRefused):
                rollback_history_projection(domain, 'receipt-1')
        domain = HistoricalRollbackDomain()
        older = deepcopy(domain.archive[0])
        older['observedAt'] = 69
        domain.archive.append(older)
        with self.assertRaises(RollbackProjectionRefused):
            rollback_history_projection(domain, 'receipt-1')

    def test_empty_and_unavailable_history_are_distinct(self):
        domain = HistoricalRollbackDomain()
        domain.archive = []
        self.assertEqual(rollback_history_projection(domain, 'receipt-1'),
                         {'available': True, 'reports': []})
        self.assertEqual(rollback_history_projection(fixtures.RollbackDomain(), 'receipt-1'),
                         {'available': False, 'reports': []})

    def test_every_locale_keeps_archives_when_current_recovery_is_closed(self):
        domain = HistoricalRollbackDomain()
        domain.report = {'receiptId': 'receipt-1', 'observedAt': 100,
                         'open': False, 'complete': False, 'state': None}
        for locale, words in HISTORY.items():
            with self.subTest(locale=locale):
                html = render_rollback(domain, 'receipt-1', locale=locale)
                self.assertIn(words[0], html)
                self.assertIn('data-history-sequence="1"', html)
                self.assertIn('1000 PYUSD', html)
                self.assertIn('17 ETH wei', html)
                self.assertNotIn('PRIVATE-', html)
