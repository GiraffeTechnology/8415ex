"""Internal acceptance regressions for audit evidence boundaries."""
import copy
import unittest
from exchange import audit, fixtures as F
from exchange.errors import DomainError
from exchange.tests.test_audit import CHAIN, _settled_chain
from exchange.tests.test_payment_binding import operation, R

class AuditBoundaries(unittest.TestCase):
    def test_conflicting_duplicate_refused_in_both_orders(self):
        ex, _ = _settled_chain()
        a = next(e for e in ex.receipt_timeline(R) if e['kind']=='segment-release-attempt')
        b = copy.deepcopy(a); b['detail']['escrowStatus']='failed'
        for stream in ([a,b],[b,a]):
            with self.assertRaises(DomainError) as caught: audit.replay(stream)
            self.assertEqual(caught.exception.code,'EX_EVENT_CONFLICT')

    def test_caller_chain_position_is_not_verified_evidence(self):
        c = audit.correlation(chain=CHAIN)
        self.assertFalse(c['observedOnChain'])
        self.assertTrue(c['chainPositionComplete'])
        self.assertEqual(c['chainEvidenceStatus'],'NOT_RUN')

    def test_zero_operation_return_not_counted(self):
        ex, _ = F.minted()
        e = copy.deepcopy(ex.receipt_timeline(R)[0])
        e.update(kind='asset-returned', detail={'operations':0,'boundaryIndex':0})
        self.assertEqual(audit.replay([e])['assetMovementCount'],0)

    def test_recovered_settlement_counted_once(self):
        for kind in ('release','refund'):
            ex, _, action = operation(kind, {kind+':escrow-ab':'unknown'})
            action(); before = audit.replay(ex.receipt_timeline(R))['fundMovementCount']
            ex.payments.resolve_unknown(kind+':escrow-ab','settled'); ex.resume_payments(R)
            stream = ex.receipt_timeline(R)
            self.assertEqual(audit.replay(stream)['fundMovementCount'],before+1)
            self.assertEqual(audit.replay(stream+stream)['fundMovementCount'],before+1)

    def test_timeline_is_detached_from_authoritative_events(self):
        ex, _ = F.minted(); stream=ex.receipt_timeline(R)
        stream[0]['detail']['origin']='tampered'
        self.assertNotEqual(ex.receipt_timeline(R)[0]['detail']['origin'],'tampered')

    def test_known_leg_correlation_retained(self):
        ex, _ = _settled_chain()
        for e in ex.receipt_timeline(R):
            if e['kind'] in ('registration-result','segment-release-attempt'):
                self.assertIsNotNone(e['correlation']['transferId'], e['kind'])

    def test_unknown_transfer_chain_correlation_refused(self):
        ex, _ = F.minted()
        with self.assertRaises(DomainError) as caught:
            ex.record_chain_observation(R,'transfer-observed',CHAIN,{'transferId':'invented'})
        self.assertEqual(caught.exception.code,'EX_CHAIN_TRANSFER_UNKNOWN')

    def test_mixed_stream_refused_and_gap_not_complete(self):
        ex, _ = _settled_chain(); stream=list(ex.receipt_timeline(R))
        self.assertFalse(audit.replay([stream[0],stream[2]])['completeFromMint'])
        second=copy.deepcopy(stream[1]); second['correlation']['runId']='other'
        with self.assertRaises(DomainError): audit.replay([stream[0],second])

    def test_minted_business_view_matches_live(self):
        ex, _ = F.minted(); result=ex.audit_replay(R)
        self.assertTrue(result['businessViewMatches'])
        self.assertEqual(result['businessView']['holder']['position'],0)

    def test_economic_payload_changes_replay_digest(self):
        ex, _ = _settled_chain(); stream=list(ex.receipt_timeline(R)); altered=copy.deepcopy(stream)
        next(e for e in altered if e['kind']=='escrow-locked')['detail']['principal']='999'
        self.assertNotEqual(audit.replay(stream)['digest'],audit.replay(altered)['digest'])

    def test_chain_transfer_leg_request_disagreement_refused(self):
        ex, _ = _settled_chain()
        for extra in ({'legIndex':1},{'requestId':'unknown-request'}):
            with self.assertRaises(DomainError) as caught:
                ex.record_chain_observation(R,'transfer-observed',CHAIN,dict(transferId='transfer-ab',**extra))
            self.assertEqual(caught.exception.code,'EX_CHAIN_CORRELATION_CONFLICT')

    def test_event_receipt_correlation_disagreement_refused(self):
        ex, _ = F.minted(); event=ex.receipt_timeline(R)[0]
        event['correlation']['receiptId']='different'
        with self.assertRaises(DomainError): audit.replay([event])
