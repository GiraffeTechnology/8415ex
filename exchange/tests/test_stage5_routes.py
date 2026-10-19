"""Cross-route local acceptance of recovery; no real provider or durable restart."""
import unittest
from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.stage5 import PATHS, RECEIPT, make_chain, release

class CrossRouteAcceptance(unittest.TestCase):
    def refused(self, path, **kwargs):
        ex, clock = make_chain(path, **kwargs)
        requests = F.submit_all(ex)
        F.refuse(ex, requests[0], "route-refusal")
        ex.begin_rollback(RECEIPT, 0, F.rollback_authority(ex, 0, "route-rollback"))
        return ex, requests

    def test_unknown_refund_reconciles_then_late_result_cannot_release(self):
        for path in PATHS:
            with self.subTest(path=path):
                ex, requests = self.refused(path, outcomes={"refund:escrow-ab": "unknown"})
                first = ex.advance_rollback(RECEIPT)
                self.assertFalse(first["complete"])
                before = ex.payments.movements
                ex.advance_rollback(RECEIPT)
                self.assertEqual(ex.payments.movements, before)
                ex.payments.resolve_unknown("refund:escrow-ab", "settled")
                ex.resume_payments(RECEIPT)
                self.assertTrue(ex.advance_rollback(RECEIPT)["complete"])
                before = ex.payments.movements
                _, late = F.confirm(ex, requests[1], "route-late")
                self.assertEqual(late["disposition"], "late-conflict")
                self.assertFalse(late["fundsReleasedAgain"])
                self.assertEqual(ex.payments.movements, before)
                self.assertEqual(ex.owner_of(RECEIPT), F.A)
                self.assertEqual(ex.escrow_for_leg(RECEIPT, 0).status, "refunded")

    def test_unknown_boundary_return_is_enquired_without_resending(self):
        for path in PATHS:
            with self.subTest(path=path):
                ex, _ = self.refused(path)
                key = "return:" + RECEIPT + ":" + ex.rollback_report(RECEIPT)["authorityId"]
                ex.asset_control._outcomes[key] = "unknown"
                self.assertFalse(ex.advance_rollback(RECEIPT)["complete"])
                ex.advance_rollback(RECEIPT)
                self.assertEqual(ex.asset_control.returns, 0)
                ex.asset_control.resolve_unknown(key, "returned")
                self.assertTrue(ex.advance_rollback(RECEIPT)["complete"])
                self.assertEqual(ex.asset_control.returns, 2)
                self.assertEqual(ex.asset_control.hops_walked, 2)
                self.assertEqual(len(ex.asset_control._records), 3)

    def test_partial_refund_failure_resumes_once_for_each_original_buyer(self):
        for path in PATHS:
            with self.subTest(path=path):
                ex, _ = self.refused(path, outcomes={"refund:escrow-bc": "failed"})
                self.assertFalse(ex.advance_rollback(RECEIPT)["complete"])
                self.assertTrue(ex.advance_rollback(RECEIPT)["complete"])
                self.assertEqual(ex.payments.movements, 3)
                for index, buyer in enumerate((F.B, F.C, F.D)):
                    segment = ex.reconciliation(RECEIPT)["segments"][index]
                    self.assertEqual(segment["buyer"], buyer)
                    self.assertTrue(segment["refunded"])
                    self.assertFalse(segment["released"])

    def test_nonzero_gas_stays_separate_from_refund_principal(self):
        for path in PATHS:
            with self.subTest(path=path):
                ex, _ = self.refused(path)
                for index, amount in enumerate((21, 23, 25)):
                    ex.record_gas(RECEIPT, index, "acceptance-trade", amount)
                self.assertTrue(ex.advance_rollback(RECEIPT)["complete"])
                for segment, amount in zip(ex.reconciliation(RECEIPT)["segments"], (21,23,25)):
                    self.assertEqual(segment["gasBorneBy"], segment["buyer"])
                    self.assertEqual(segment["gasTotal"], str(amount))
                    self.assertEqual(segment["netToPayer"], segment["principal"])

    def test_finalized_prefix_survives_shortfall_then_suffix_resume(self):
        for path in PATHS:
            with self.subTest(path=path):
                ex, _ = make_chain(path, gas_budgets={F.D: 0})
                requests = F.submit_all(ex)
                F.confirm(ex, requests[0], "route-ab")
                release(ex, 0)
                original = ex.reconciliation(RECEIPT)["segments"][0]
                F.refuse(ex, requests[1], "route-c-refusal")
                ex.begin_rollback(RECEIPT, 1, F.rollback_authority(ex, 1, "prefix-rollback"))
                self.assertFalse(ex.advance_rollback(RECEIPT)["complete"])
                ex._budgets[F.D] = 100000
                self.assertTrue(ex.advance_rollback(RECEIPT)["complete"])
                self.assertEqual(ex.reconciliation(RECEIPT)["segments"][0], original)
                self.assertEqual(ex.owner_of(RECEIPT), F.B)
                self.assertEqual(ex.payments.movements, 3)
