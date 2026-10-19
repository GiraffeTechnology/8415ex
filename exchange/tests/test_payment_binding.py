"""Synthetic payment evidence, journal identity and confirmed-failure recovery."""
import copy
from dataclasses import replace
import unittest
from unittest.mock import Mock

from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.settlement import segment_binding

R = "rcpt-8415-0001"


def operation(kind, outcomes=None):
    ex, clock = F.rollback_chain_to_d(outcomes=outcomes)
    requests = F.submit_all(ex)
    if kind == "release":
        F.confirm(ex, requests[0], "confirmed-ab")
        authority = F.release_authority(ex, 0, "release-ab")
        action = lambda: ex.release_segment(R, 0, authority)
    else:
        F.refuse(ex, requests[0], "refused-ab")
        ex.begin_rollback(R, 0, F.rollback_authority(ex, 0, "rb"))
        action = lambda: ex.advance_rollback(R)
    return ex, clock, action


def payment_record(ex, kind, status):
    escrow = ex.escrow_for_leg(R, 0)
    return {"paymentKey": kind + ":escrow-ab",
            "payer": escrow.payer if kind == "release" else escrow.payee,
            "payee": escrow.payee if kind == "release" else escrow.payer,
            "quoteAsset": escrow.quote_asset, "principal": escrow.principal,
            "status": status, "reference": "sim-observed", "observedAt": ex._clock()}


class PaymentEvidenceBinding(unittest.TestCase):
    def test_lookup_terms_are_checked_for_release_refund_and_resume(self):
        changes = ({"paymentKey": "other-key"}, {"payer": F.D}, {"payee": F.C},
                   {"quoteAsset": "OTHER"}, {"principal": F.PRICE_AB + 1})
        for kind in ("release", "refund"):
            for resume in (False, True):
                for status in ("settled", "unknown", "failed"):
                    for change in changes:
                        with self.subTest(kind=kind, resume=resume, status=status, change=change):
                            key = kind + ":escrow-ab"
                            ex, _, action = operation(kind, {key: "unknown"})
                            if resume:
                                action()
                            record = dict(payment_record(ex, kind, status), **change)
                            ex.payments.lookup = Mock(return_value=record)
                            ex.payments.pay = Mock(side_effect=AssertionError("mismatched lookup must not send"))
                            before = copy.deepcopy((ex._escrows, ex._legs, ex._events, ex._rollbacks))
                            with self.assertRaises(DomainError) as caught:
                                ex.resume_payments(R) if resume else action()
                            self.assertEqual(caught.exception.code, "EX_PAYMENT_SUBSTITUTION_REFUSED")
                            self.assertEqual((ex._escrows, ex._legs, ex._events, ex._rollbacks), before)
                            ex.payments.pay.assert_not_called()

    def test_direct_pay_response_is_bound_before_bookkeeping(self):
        for kind in ("release", "refund"):
            with self.subTest(kind=kind):
                ex, _, action = operation(kind)
                bad = dict(payment_record(ex, kind, "settled"), payee=F.D)
                ex.payments.lookup = Mock(return_value=None)
                ex.payments.pay = Mock(return_value=bad)
                with self.assertRaises(DomainError) as caught:
                    action()
                self.assertEqual(caught.exception.code, "EX_PAYMENT_SUBSTITUTION_REFUSED")
                pending = ex.escrow_for_leg(R, 0)
                self.assertEqual((pending.status, pending.payment_status, pending.payment_intent),
                                 ("locked", "unknown", kind))
                self.assertEqual(pending.payment_key, kind + ":escrow-ab")
                self.assertIsNone(pending.settled_at)
                self.assertIsNone(pending.refunded_at)
                self.assertNotEqual(ex.leg(R, 0).rollback_status, "detached")
                self.assertEqual(ex.payments.pay.call_count, 1)
                ex.payments.pay.reset_mock()
                with self.assertRaises(DomainError) as caught:
                    action()
                self.assertEqual(caught.exception.code, "EX_PAYMENT_OUTCOME_UNRESOLVED")
                ex.payments.pay.assert_not_called()

    def test_pay_exception_keeps_attempt_pending_until_bound_enquiry(self):
        for kind in ("release", "refund"):
            with self.subTest(kind=kind):
                ex, _, action = operation(kind)
                ex.payments.pay = Mock(side_effect=TimeoutError("simulated interrupted response"))
                with self.assertRaises(TimeoutError):
                    action()
                escrow = ex.escrow_for_leg(R, 0)
                self.assertEqual((escrow.payment_key, escrow.payment_intent, escrow.payment_status),
                                 (kind + ":escrow-ab", kind, "unknown"))
                ex.payments.pay.reset_mock()
                with self.assertRaises(DomainError) as caught:
                    action()
                self.assertEqual(caught.exception.code, "EX_PAYMENT_OUTCOME_UNRESOLVED")
                ex.payments.pay.assert_not_called()
                ex.payments.lookup = Mock(return_value=payment_record(ex, kind, "settled"))
                ex.resume_payments(R)
                self.assertEqual(ex.escrow_for_leg(R, 0).status,
                                 "released" if kind == "release" else "refunded")
                ex.payments.pay.assert_not_called()

    def test_substituted_journal_does_not_release_or_send(self):
        ex, _, _ = operation("release")
        original = F.release_authority(ex, 0, "release-ab")
        changed = replace(original, journal_reference="journal-unrelated")
        ex.payments.pay = Mock(side_effect=AssertionError("unbound journal must not pay"))
        with self.assertRaises(DomainError) as caught:
            ex.release_segment(R, 0, changed)
        self.assertEqual(caught.exception.code, "EX_RELEASE_BINDING_REFUSED")
        ex.payments.pay.assert_not_called()
        self.assertEqual(ex.escrow_for_leg(R, 0).status, "locked")
        self.assertEqual(ex.leg(R, 0).rollback_status, "available")

    def test_journal_is_required_and_distinct_valid_journals_bind_distinctly(self):
        ex, _, _ = operation("release")
        authority = F.release_authority(ex, 0, "release-ab")
        escrow = ex.escrow_for_leg(R, 0)
        args = (authority.asset, R, 0, authority.transfer_id, escrow.payer, escrow.payee,
                escrow.principal, escrow.quote_asset)
        other = segment_binding(*args, "journal-other-verified")
        self.assertNotEqual(other, authority.binding)
        with self.assertRaises(DomainError):
            segment_binding(*args, "")
        with self.assertRaises(TypeError):
            segment_binding(*args)
        changed = replace(authority, journal_reference="journal-other-verified", binding=other)
        self.assertTrue(ex.release_segment(R, 0, changed)["released"])


class ConfirmedPaymentFailure(unittest.TestCase):
    def test_release_and_refund_retry_only_after_confirmed_failure(self):
        for kind in ("release", "refund"):
            with self.subTest(kind=kind):
                key = kind + ":escrow-ab"
                ex, _, action = operation(kind, {key: "unknown"})
                action()
                pay = Mock(wraps=ex.payments.pay)
                ex.payments.pay = pay
                action()
                pay.assert_not_called()
                ex.payments.resolve_unknown(key, "failed")
                action()
                self.assertEqual(ex.escrow_for_leg(R, 0).status,
                                 "released" if kind == "release" else "refunded")
                calls = [call for call in pay.call_args_list if call.args[0] == key]
                self.assertEqual(len(calls), 1)
                record = payment_record(ex, kind, "settled")
                self.assertEqual(calls[0].args, (key, record["payer"], record["payee"],
                                               record["quoteAsset"], record["principal"]))
                self.assertEqual(ex.payments.movements, 1 if kind == "release" else 3)
                history = ex.payments.history(key)
                self.assertEqual([record["status"] for record in history], ["unknown", "failed", "settled"])
                self.assertEqual([record["attempt"] for record in history], [1, 1, 2])
                self.assertEqual(history[1]["effect"], "not-applied")
                self.assertTrue(history[1]["retryable"])
                self.assertIn("resolvedAt", history[1])

    def test_known_failed_or_missing_result_without_no_effect_evidence_never_retries(self):
        for kind in ("release", "refund"):
            for state in ("failed", "unknown"):
                for missing in (False, True):
                    with self.subTest(kind=kind, state=state, missing=missing):
                        key = kind + ":escrow-ab"
                        ex, _, action = operation(kind, {key: state})
                        action()
                        record = payment_record(ex, kind, "failed")
                        ex.payments.lookup = Mock(return_value=None if missing else record)
                        ex.payments.pay = Mock(side_effect=AssertionError("no proven safe retry"))
                        with self.assertRaises(DomainError) as caught:
                            action()
                        self.assertEqual(caught.exception.code, "EX_PAYMENT_OUTCOME_UNRESOLVED")
                        ex.payments.pay.assert_not_called()

    def test_resolved_settled_is_recorded_by_resume_without_resending(self):
        for kind in ("release", "refund"):
            with self.subTest(kind=kind):
                key = kind + ":escrow-ab"
                ex, _, action = operation(kind, {key: "unknown"})
                action()
                ex.payments.resolve_unknown(key, "settled")
                ex.payments.pay = Mock(side_effect=AssertionError("settled must not resend"))
                ex.resume_payments(R)
                self.assertEqual(ex.escrow_for_leg(R, 0).status,
                                 "released" if kind == "release" else "refunded")
                self.assertEqual([entry["status"] for entry in ex.payments.history(key)],
                                 ["unknown", "settled"])
                self.assertEqual(ex.payments.lookup(key)["attempt"], 1)
                ex.resume_payments(R)
                ex.payments.pay.assert_not_called()

    def test_retry_failure_preserves_history_and_original_payment_terms(self):
        ex, _, action = operation("release", {"release:escrow-ab": "unknown"})
        key = "release:escrow-ab"
        action()
        ex.payments.resolve_unknown(key, "failed")
        before = ex.payments.history(key)
        with self.assertRaises(DomainError):
            ex.payments.pay(key, F.B, F.C, F.QUOTE_ASSET, F.PRICE_AB)
        self.assertEqual(ex.payments.history(key), before)
        ex.payments._outcomes[key] = "failed"
        self.assertFalse(action()["released"])
        self.assertTrue(action()["released"])
        self.assertEqual(ex.payments.movements, 1)
        self.assertEqual([entry["attempt"] for entry in ex.payments.history(key)], [1, 1, 2, 3])
        self.assertEqual([entry["status"] for entry in ex.payments.history(key)],
                         ["unknown", "failed", "failed", "settled"])
        history = ex.payments.history(key)
        history[0]["status"] = "settled"
        self.assertEqual(ex.payments.history(key)[0]["status"], "unknown")


class EscrowPreconditions(unittest.TestCase):
    def test_stale_match_never_reserves_the_next_slot(self):
        for reason in ("expired", "revoked", "head-moved"):
            with self.subTest(reason=reason):
                ex, clock = F.funded_exchange()
                stale, _ = F.funded_hop(ex, F.A, F.B, 1, "transfer-stale", "session-a", "session-b", lock=False,
                                       expires_at=clock() + 10 if reason == "expired" else 1_700_800_000)
                if reason == "expired":
                    clock.advance(11)
                elif reason == "revoked":
                    ex.revoke_authorization("auth-sell-stale")
                else:
                    ex.connect_wallet(F.C, "session-c")
                    ex.register_authorization(F.authorization(
                        F.C, "auth-buy-ac", "session-c", max_amount=F.PRICE + 1))
                    ex.submit_intent(F.intent("buy-ac", "buy", F.C, "auth-buy-ac", None, 2,
                                              limit_price=F.PRICE + 1))
                    current = ex.match_intents("sell-stale", "buy-ac")
                    escrow = ex.lock_escrow(current, "escrow-ac")
                    ex.execute_transfer(current, "transfer-ac", escrow_id=escrow.escrow_id)
                before = copy.deepcopy((ex._escrows, ex._escrow_by_leg))
                with self.assertRaises(DomainError):
                    ex.lock_escrow(stale, "escrow-stale")
                self.assertEqual((ex._escrows, ex._escrow_by_leg), before)
                # A resting bid remains eligible after the seller's grant is
                # revoked. Retire that original bid through its own grant,
                # rather than asking the matcher to skip its FIFO priority.
                ex.revoke_authorization("auth-buy-stale")
                seller = F.C if reason == "head-moved" else F.A
                fresh, _ = F.funded_hop(ex, seller, F.B, 3, "transfer-fresh", "session-c" if seller == F.C else "session-a",
                                       "session-b", lock=False)
                funded = ex.lock_escrow(fresh, "escrow-fresh")
                self.assertEqual(funded.leg_index, 1 if reason == "head-moved" else 0)
