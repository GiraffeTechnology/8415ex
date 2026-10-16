"""Known failed simulated exit acts recover without replaying unknown outcomes."""
import unittest
from unittest.mock import Mock

from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.exit import EXIT_STEPS, SimulatedVoucherDesk, exit_step_key

R = "rcpt-8415-0001"


class ResolvedVoucherFailure(unittest.TestCase):
    def test_each_step_recovers_after_unknown_is_confirmed_failed(self):
        for step in EXIT_STEPS:
            with self.subTest(step=step):
                key = exit_step_key(step, R, "rdm")
                ex, clock = F.settled_at_b(voucher_outcomes={key: "unknown"})
                F.redeem_authorization(ex)
                ex.request_redemption(R, F.B, "auth-redeem", "rdm", F.ALL_CHECKS)
                first = ex.advance_exit(R)
                self.assertEqual(first["state"], "blocked")
                reference = ex.voucher_desk.lookup(key)["reference"]
                act = Mock(wraps=ex.voucher_desk.act)
                ex.voucher_desk.act = act
                # Enquiry has not resolved the uncertainty: do not act again.
                self.assertEqual(ex.advance_exit(R)["state"], "blocked")
                act.assert_not_called()
                clock.advance(1)
                ex.voucher_desk.resolve_unknown(key, "failed")
                recovered = ex.advance_exit(R)
                self.assertTrue(recovered["complete"])
                calls = [call for call in act.call_args_list if call.args[0] == key]
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0].args, (key, step, R, F.B))
                self.assertEqual(ex.voucher_desk.lookup(key)["reference"], reference)
                history = ex.voucher_desk.history(key)
                self.assertEqual([entry["status"] for entry in history], ["unknown", "failed", "done"])
                self.assertEqual([entry["attempt"] for entry in history], [1, 1, 2])
                self.assertEqual(history[1]["effect"], "not-applied")
                self.assertTrue(history[1]["retryable"])
                self.assertIn("resolvedAt", history[1])
                count = act.call_count
                self.assertTrue(ex.advance_exit(R)["complete"])
                self.assertEqual(act.call_count, count)

    def test_each_step_resolved_done_is_reused_without_reexecution(self):
        for step in EXIT_STEPS:
            with self.subTest(step=step):
                key = exit_step_key(step, R, "rdm")
                ex, _ = F.settled_at_b(voucher_outcomes={key: "unknown"})
                F.redeem_authorization(ex)
                ex.request_redemption(R, F.B, "auth-redeem", "rdm", F.ALL_CHECKS)
                self.assertEqual(ex.advance_exit(R)["state"], "blocked")
                ex.voucher_desk.resolve_unknown(key, "done")
                act = Mock(wraps=ex.voucher_desk.act)
                ex.voucher_desk.act = act
                self.assertTrue(ex.advance_exit(R)["complete"])
                self.assertFalse(any(call.args[0] == key for call in act.call_args_list))
                self.assertEqual([entry["status"] for entry in ex.voucher_desk.history(key)],
                                 ["unknown", "done"])
                self.assertEqual(ex.voucher_desk.lookup(key)["attempt"], 1)

    def test_failed_resolution_rejects_binding_substitution_before_retry(self):
        for changed in (("burn", "other", F.B), ("burn", R, F.C),
                        ("voucher-issued", R, F.B)):
            with self.subTest(changed=changed):
                desk = SimulatedVoucherDesk(F.ManualClock(), "REG_DIRECT", {"key": "unknown"})
                desk.act("key", "burn", R, F.B)
                resolved = desk.resolve_unknown("key", "failed")
                with self.assertRaises(DomainError) as caught:
                    desk.act("key", *changed)
                self.assertEqual(caught.exception.code, "EX_VOUCHER_SUBSTITUTION_REFUSED")
                self.assertEqual(desk.lookup("key"), resolved)
                retry = desk.act("key", "burn", R, F.B)
                self.assertEqual(retry["status"], "done")
                self.assertFalse(retry["repeated"])

    def test_unknown_and_confirmed_done_are_never_reexecuted(self):
        desk = SimulatedVoucherDesk(F.ManualClock(), "REG_DIRECT", {"key": "unknown"})
        first = desk.act("key", "burn", R, F.B)
        again = desk.act("key", "burn", R, F.B)
        self.assertTrue(again["repeated"])
        self.assertEqual(again["status"], "unknown")
        desk.resolve_unknown("key", "done")
        complete = desk.act("key", "burn", R, F.B)
        self.assertTrue(complete["repeated"])
        self.assertEqual(complete["status"], "done")
        self.assertEqual(complete["reference"], first["reference"])

    def test_another_failed_attempt_retains_binding_and_can_retry(self):
        desk = SimulatedVoucherDesk(F.ManualClock(), "REG_DIRECT", {"key": "unknown"})
        desk.act("key", "burn", R, F.B)
        desk.resolve_unknown("key", "failed")
        desk._outcomes["key"] = "failed"
        failed = desk.act("key", "burn", R, F.B)
        self.assertEqual(failed["status"], "failed")
        self.assertFalse(failed["repeated"])
        with self.assertRaises(DomainError):
            desk.act("key", "burn", "other", F.B)
        self.assertEqual(desk.act("key", "burn", R, F.B)["status"], "done")
        self.assertEqual([entry["status"] for entry in desk.history("key")],
                         ["unknown", "failed", "failed", "done"])
        self.assertEqual([entry["attempt"] for entry in desk.history("key")], [1, 1, 2, 3])

    def test_failed_without_confirmed_no_effect_is_not_retryable(self):
        desk = SimulatedVoucherDesk(F.ManualClock(), "REG_DIRECT", {"key": "unknown"})
        desk.act("key", "burn", R, F.B)
        desk._records["key"]["status"] = "failed"
        with self.assertRaises(DomainError) as caught:
            desk.act("key", "burn", R, F.B)
        self.assertEqual(caught.exception.code, "EX_VOUCHER_OUTCOME_UNRESOLVED")
        self.assertEqual(len(desk.history("key")), 1)
        history = desk.history("key")
        history[0]["status"] = "done"
        self.assertEqual(desk.history("key")[0]["status"], "unknown")


class FrozenIntentViews(unittest.TestCase):
    def test_exit_freeze_is_visible_to_validation_and_matching(self):
        for through in (None, "stop-resale", "burn", "blocked"):
            with self.subTest(through=through):
                key = exit_step_key("voucher-issued", R, "rdm")
                ex, _ = F.settled_at_b(voucher_outcomes={key: "unknown"} if through == "blocked" else {})
                match, _ = F.funded_hop(ex, F.B, F.C, 2, "transfer-bc", "session-b", "session-c", lock=False)
                F.redeem_authorization(ex)
                ex.request_redemption(R, F.B, "auth-redeem", "rdm", F.ALL_CHECKS)
                if through:
                    ex.advance_exit(R, through="burn" if through == "blocked" else through)
                for intent in ("sell-bc", "buy-bc"):
                    view = ex.validate_intent(intent)
                    self.assertFalse(view["executable"])
                    self.assertIn("EX_TRADE_EXIT_OPEN", view["reasons"])
                with self.assertRaises(DomainError) as caught:
                    ex.match_intents("sell-bc", "buy-bc")
                self.assertEqual(caught.exception.code, "EX_MATCH_UNEXECUTABLE")
                with self.assertRaises(DomainError):
                    ex.lock_escrow(match, "escrow-bc")

    def test_rollback_and_return_freezes_are_visible_to_validation_and_matching(self):
        ex, _ = F.rollback_chain_to_d()
        F.funded_hop(ex, F.D, F.A, 4, "transfer-da", "session-d", "session-a", lock=False)
        requests = F.submit_all(ex)
        F.refuse(ex, requests[0], "refused-ab")
        ex.begin_rollback(R, 0, F.rollback_authority(ex, 0, "rb"))
        for complete in (False, True):
            with self.subTest(complete=complete):
                if complete:
                    ex.advance_rollback(R)
                view = ex.validate_intent("sell-da")
                self.assertFalse(view["executable"])
                self.assertIn("EX_TRADE_ROLLBACK_OPEN", view["reasons"])
                if complete:
                    self.assertIn("EX_TRADE_RETURNED_CHAIN_CLOSED", view["reasons"])
                with self.assertRaises(DomainError) as caught:
                    ex.match_intents("sell-da", "buy-da")
                self.assertEqual(caught.exception.code, "EX_MATCH_UNEXECUTABLE")
