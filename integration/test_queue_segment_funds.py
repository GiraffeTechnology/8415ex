"""Authored segment-funds view contracts; no native writer or provider."""
from copy import deepcopy
import unittest

from exchange.funds_page import render_segment_funds, WORDS
from exchange.queue_status_page import render_queue_status


def segment(index, asset='PYUSD', principal='700', gas='11'):
    return {'legIndex': index, 'principal': principal, 'principalAsset': asset,
            'principalUnit': 'base-units', 'escrowStatus': 'locked',
            'paymentStatus': 'release-outcome-unknown', 'netToPayee': '0',
            'netToPayer': '0', 'gasTotal': gas, 'gasAsset': 'ETH', 'gasUnit': 'wei',
            'seller': 'fixture-private-seller', 'buyer': '0x' + 'ab' * 20,
            'journalKey': 'fixture-private-journal'}


class OriginalReader:
    def __init__(self):
        self.calls = []
        self.report = {'receiptId': 'receipt-fixture', 'observedAt': 100,
                       'segments': [segment(3), segment(7, 'ETH', '900', '13')]}

    def reconciliation(self, receipt_id, now=None):
        self.calls.append((receipt_id, now))
        return deepcopy(self.report)

    def receipt_view(self, receipt_id, now=None):
        return {'receiptId': receipt_id, 'observedAt': 100,
                'legs': [{'legIndex': index, 'registrationStatus': 'pending'} for index in (3, 7)],
                'deferredLegs': [], 'rejectedLegs': []}

    def overdue_requests(self, receipt_id, now=None):
        return []


class SegmentFundsContracts(unittest.TestCase):
    def setUp(self):
        self.source = OriginalReader()

    def render(self, locale='en'):
        return render_segment_funds(self.source, 'receipt-fixture', 100, [3, 7], locale=locale)

    def test_exact_original_currencies_and_gas_remain_separate_in_all_locales(self):
        before = deepcopy(self.source.report)
        for locale, words in WORDS.items():
            with self.subTest(locale=locale):
                html = self.render(locale)
                self.assertIn(words['heading'], html)
                self.assertIn('700 PYUSD (' + words['units'] + ')', html)
                self.assertIn('900 ETH (' + words['units'] + ')', html)
                self.assertIn('11 ETH wei', html)
                self.assertIn('13 ETH wei', html)
                self.assertNotIn('689 PYUSD', html)
                self.assertNotIn('887 ETH', html)
                self.assertIn(words['releaseUnknown'], html)
                self.assertNotIn('<form', html)
        self.assertEqual(self.source.report, before)
        self.assertEqual(self.source.calls, [('receipt-fixture', 100)] * len(WORDS))

    def test_private_parties_journals_errors_and_extra_fields_are_not_rendered(self):
        self.source.report['segments'][0]['arbitrary'] = '<script>private-error</script>'
        self.source.report['error'] = 'fixture-private-error'
        html = self.render()
        for value in ('fixture-private-seller', '0x' + 'ab' * 20,
                      'fixture-private-journal', 'private-error', '<script>', 'sellerPosition'):
            self.assertNotIn(value, html)
        self.source.reconciliation = lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError('fixture-private-error'))
        html = self.render()
        self.assertIn(WORDS['en']['unavailable'], html)
        self.assertNotIn('fixture-private-error', html)

    def test_receipt_time_leg_order_duplicates_and_omissions_refuse_only_component(self):
        valid = deepcopy(self.source.report)
        changed = [
            dict(valid, receiptId='other-receipt'), dict(valid, observedAt=101),
            dict(valid, observedAt=True), dict(valid, segments=list(reversed(valid['segments']))),
            dict(valid, segments=valid['segments'][:1]),
            dict(valid, segments=[valid['segments'][0], valid['segments'][0]]),
        ]
        for value in changed:
            with self.subTest(report=value):
                self.source.report = value
                html = self.render()
                self.assertIn(WORDS['en']['unavailable'], html)
                self.assertNotIn('700 PYUSD', html)

    def test_missing_invalid_or_mismatched_units_never_become_zero(self):
        for key, value in (('principal', None), ('principal', '00700'),
                           ('principal', str(2**256)), ('principalUnit', 'wei'),
                           ('principalAsset', 'PYUSD<script>')):
            with self.subTest(key=key):
                self.source.report['segments'] = [segment(3)]
                self.source.report['segments'][0][key] = value
                html = render_segment_funds(self.source, 'receipt-fixture', 100, [3])
                self.assertIn('<td>' + WORDS['en']['unknown'] + '</td>', html)
                self.assertNotIn('700 PYUSD', html)
                self.assertNotIn('<script>', html)

    def test_absent_or_non_eth_gas_is_unknown_and_not_replaced_by_principal(self):
        for key, value in (('gasTotal', None), ('gasAsset', 'WETH'),
                           ('gasUnit', 'base-units'), ('gasTotal', '-1')):
            with self.subTest(key=key):
                self.source.report['segments'] = [segment(3)]
                self.source.report['segments'][0][key] = value
                html = render_segment_funds(self.source, 'receipt-fixture', 100, [3])
                self.assertIn('700 PYUSD', html)
                self.assertNotIn('11 ETH wei', html)
                self.assertIn('<td>Unknown</td>', html)

    def test_explicit_zero_is_preserved_and_status_cannot_invent_a_net(self):
        row = segment(3, 'ETH', '0', '0')
        row['escrowStatus'] = 'released'
        row['netToPayee'] = None
        self.source.report['segments'] = [row]
        html = render_segment_funds(self.source, 'receipt-fixture', 100, [3])
        self.assertIn('0 ETH (base units)', html)
        self.assertIn('0 ETH wei', html)
        self.assertIn('<td>Released</td>', html)
        self.assertIn('<td>Unknown</td>', html)

    def test_queue_hook_uses_same_observation_time_and_keeps_noncontiguous_leg_identity(self):
        html = render_queue_status(self.source, 'receipt-fixture')
        self.assertIn('Operations queue', html)
        self.assertIn('data-segment-funds="1"', html)
        self.assertIn('<td>3</td>', html)
        self.assertIn('<td>7</td>', html)
        self.assertEqual(self.source.calls, [('receipt-fixture', 100)])
        self.source.report['receiptId'] = 'wrong'
        html = render_queue_status(self.source, 'receipt-fixture')
        self.assertIn('Operations queue', html)
        self.assertIn(WORDS['en']['unavailable'], html)

    def test_empty_bound_report_and_unknown_status_remain_honest(self):
        self.source.report['segments'] = []
        html = render_segment_funds(self.source, 'receipt-fixture', 100, [])
        self.assertIn(WORDS['en']['empty'], html)
        self.assertIn('colspan="7"', html)
        self.source.report['segments'] = [segment(3)]
        self.source.report['segments'][0]['paymentStatus'] = '<script>success</script>'
        html = render_segment_funds(self.source, 'receipt-fixture', 100, [3])
        self.assertIn('<td>Unknown</td>', html)
        self.assertNotIn('<script>', html)
