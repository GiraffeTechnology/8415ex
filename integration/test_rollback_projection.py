"""Private synthetic projection definitions; no money, native return or chain calls."""
from copy import deepcopy
import unittest

from exchange.rollback_projection import RollbackProjectionRefused, rollback_projection


class RollbackDomain:
    def __init__(self):
        self.report = {'receiptId': 'receipt-1', 'observedAt': 100, 'open': True,
            'complete': False, 'state': 'in-progress', 'trigger': 'registrar refusal for that leg',
            'lastFinalizedPosition': 1, 'affectedLegs': (1,),
            'assetControl': {'returned': False, 'account': 'PRIVATE-WALLET'},
            'outstandingSteps': ({'stepId': 'PRIVATE-JOURNAL', 'legIndex': 1,
                                   'kind': 'refund', 'status': 'unknown',
                                   'detail': {'proof': 'PRIVATE-PROOF'}},),
            'funds': ({'legIndex': 1, 'principal': '1000', 'principalAsset': 'PYUSD',
                       'principalUnit': 'base-units', 'escrowStatus': 'locked',
                       'paymentStatus': 'unknown', 'refundedToOriginalBuyer': False,
                       'netToOriginalBuyer': '0', 'gasTotal': '17', 'gasAsset': 'ETH',
                       'gasUnit': 'wei', 'rollbackStatus': 'in-progress',
                       'originalBuyer': 'PRIVATE-BUYER', 'gasBorneBy': 'PRIVATE-BUYER'},)}

    def receipt_view(self, receipt_id, now):
        return {'receiptId': 'receipt-1', 'observedAt': 100, 'registeredPrefixLegs': 1,
                'outstandingLegs': 1, 'holder': {'position': 1}, 'owner': {'position': 2}}

    def rollback_report(self, receipt_id, observed):
        return deepcopy(self.report)


class RollbackProjectionTests(unittest.TestCase):
    def test_unknown_refund_preserves_separate_principal_and_consumed_eth_without_identity(self):
        result = rollback_projection(RollbackDomain(), 'receipt-1')
        row = result['funds'][0]
        self.assertEqual((row['principal'], row['principalAsset']), ('1000', 'PYUSD'))
        self.assertEqual((row['gasTotal'], row['gasAsset'], row['gasUnit']), ('17', 'ETH', 'wei'))
        self.assertEqual(row['netToOriginalBuyer'], '0')
        self.assertFalse(row['refundedToOriginalBuyer'])
        self.assertFalse(result['consumedGasRefunded'])
        self.assertFalse(result['nativeCompletionVerified'])
        self.assertEqual(result['outstandingSteps'][0]['status'], 'unknown')
        for private in ('PRIVATE-WALLET', 'PRIVATE-JOURNAL', 'PRIVATE-PROOF', 'PRIVATE-BUYER'):
            self.assertNotIn(private, str(result))

    def test_inconsistent_domain_completion_is_flagged_and_never_native_acceptance(self):
        domain = RollbackDomain()
        domain.report.update(complete=True, state='complete')
        result = rollback_projection(domain, 'receipt-1')
        self.assertTrue(result['domainReportedComplete'])
        self.assertFalse(result['domainReportConsistent'])
        domain.report['outstandingSteps'] = ()
        domain.report['assetControl']['returned'] = True
        domain.report['funds'][0].update(escrowStatus='refunded', refundedToOriginalBuyer=True,
                                        netToOriginalBuyer='1000')
        result = rollback_projection(domain, 'receipt-1')
        self.assertTrue(result['domainReportConsistent'])
        self.assertFalse(result['nativeCompletionVerified'])
        self.assertEqual(result['chainAcceptance'], 'NOT_RUN')

    def test_foreign_receipt_and_changed_observation_refuse(self):
        for field, value in (('receiptId', 'other-receipt'), ('observedAt', 101)):
            domain = RollbackDomain()
            domain.report[field] = value
            with self.subTest(field=field), self.assertRaises(RollbackProjectionRefused):
                rollback_projection(domain, 'receipt-1')

    def test_foreign_or_duplicate_financial_legs_refuse(self):
        domain = RollbackDomain()
        domain.report['funds'][0]['legIndex'] = 2
        with self.assertRaises(RollbackProjectionRefused):
            rollback_projection(domain, 'receipt-1')
        domain = RollbackDomain()
        domain.report['funds'] *= 2
        with self.assertRaises(RollbackProjectionRefused):
            rollback_projection(domain, 'receipt-1')

    def test_unknown_trigger_and_step_fields_are_not_echoed(self):
        domain = RollbackDomain()
        domain.report['trigger'] = 'PRIVATE-TRIGGER'
        domain.report['outstandingSteps'][0].update(kind='PRIVATE-KIND', status='PRIVATE-STATUS')
        result = rollback_projection(domain, 'receipt-1')
        self.assertEqual(result['trigger'], 'unknown')
        self.assertEqual(result['outstandingSteps'][0]['kind'], 'unknown')
        self.assertNotIn('PRIVATE-', str(result))
