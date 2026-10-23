"""Synthetic branch/identity definitions; no native execution or chain proof."""
from types import SimpleNamespace
import unittest

from exchange.timeline_projection import TimelineProjectionRefused, timeline_projection
from exchange.views import timeline_page


class TimelineDomain:
    def __init__(self):
        self.originals = [SimpleNamespace(receipt_id='receipt-1', transfer_id='private-' + str(i), leg_index=i,
                                         predecessor_transfer_id=predecessor)
                          for i, predecessor in enumerate((None, 'private-0', None, 'private-0'))]
        self.entries = [{'legIndex': i, 'transferId': 'private-' + str(i),
                         'price': '100', 'quoteAsset': 'PYUSD', 'registrationStatus': 'pending',
                         'fundingStatus': 'locked', 'rollbackStatus': 'available',
                         'executedAt': 100 + i, 'seller': 'PRIVATE-SELLER', 'buyer': 'PRIVATE-BUYER'}
                        for i in range(4)]

    def receipt_view(self, receipt_id, now):
        return {'legs': self.entries, 'activeLegIndices': (0, 3),
                'historicalWithdrawnLegIndices': (1, 2), 'owner': {'position': 4},
                'holder': {'position': 1}, 'observedAt': 110}

    def legs(self, receipt_id):
        return tuple(self.originals)


class TimelinePredecessorTests(unittest.TestCase):
    def test_resumed_branches_use_actual_predecessor_and_keep_withdrawn_history(self):
        result = timeline_projection(TimelineDomain(), 'receipt-1')
        self.assertEqual([row['fromPosition'] for row in result['legs']], [0, 1, 0, 1])
        self.assertEqual([row['toPosition'] for row in result['legs']], [1, 2, 3, 4])
        self.assertEqual([row['legIndex'] for row in result['legs'] if row['historicalWithdrawn']], [1, 2])
        self.assertEqual(result['ownerPosition'], 4)
        self.assertEqual(result['holderPosition'], 1)
        self.assertEqual(result['chainAcceptance'], 'NOT_RUN')
        self.assertFalse(result['protocolFinalityEstablished'])
        self.assertNotIn('PRIVATE-SELLER', str(result))
        self.assertNotIn('PRIVATE-BUYER', str(result))
        self.assertNotIn('private-0', str(result))

    def test_missing_predecessor_never_becomes_a_fabricated_root_or_adjacent_position(self):
        domain = TimelineDomain()
        domain.originals[3].predecessor_transfer_id = 'missing-original'
        row = timeline_projection(domain, 'receipt-1')['legs'][3]
        self.assertIsNone(row['fromPosition'])
        self.assertEqual(row['positionMapping'], 'unknown')
        del domain.originals[3].predecessor_transfer_id
        self.assertIsNone(timeline_projection(domain, 'receipt-1')['legs'][3]['fromPosition'])

    def test_duplicate_or_changed_original_identity_refuses(self):
        for change in ('duplicate-index', 'duplicate-id', 'changed-observation'):
            domain = TimelineDomain()
            if change == 'duplicate-index':
                domain.originals[3].leg_index = 0
            elif change == 'duplicate-id':
                domain.originals[3].transfer_id = 'private-0'
            else:
                domain.entries[3]['transferId'] = 'other-original'
            with self.subTest(change=change), self.assertRaises(TimelineProjectionRefused):
                timeline_projection(domain, 'receipt-1')

    def test_self_and_future_predecessors_refuse(self):
        for predecessor in ('private-1', 'private-3'):
            domain = TimelineDomain()
            domain.originals[1].predecessor_transfer_id = predecessor
            with self.subTest(predecessor=predecessor), self.assertRaises(TimelineProjectionRefused):
                timeline_projection(domain, 'receipt-1')

    def test_foreign_receipt_history_never_maps_local_positions(self):
        domain = TimelineDomain()
        domain.originals[0].receipt_id = 'another-receipt'
        with self.assertRaises(TimelineProjectionRefused):
            timeline_projection(domain, 'receipt-1')

    def test_partial_or_unknown_branch_partition_refuses(self):
        domain = TimelineDomain()
        original_read = domain.receipt_view
        domain.receipt_view = lambda *args: {**original_read(*args), 'activeLegIndices': (0,)}
        with self.assertRaises(TimelineProjectionRefused):
            timeline_projection(domain, 'receipt-1')

    def test_existing_native_timeline_uses_original_branch_source_positions(self):
        domain = TimelineDomain()
        for entry in domain.entries:
            entry.update(executionStatus='observed')
        original_read = domain.receipt_view
        domain.receipt_view = lambda *args: {**original_read(*args), 'tradingOpen': True,
                                            'tradeStopAt': 1000}
        domain.evaluate_deadline = lambda *args: {'pastDeadline': False, 'undefinedOrdering': []}
        page = timeline_page(domain, 'receipt-1', now=110)
        self.assertIn('<td>3</td><td>position 1</td><td>position 4</td>', page)
        self.assertIn('<td>2</td><td>position 0</td><td>position 3</td>', page)
        self.assertNotIn('<td>3</td><td>position 3</td><td>position 4</td>', page)
        self.assertNotIn('PRIVATE-BUYER', page)
