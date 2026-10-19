"""V1.4 retained physical evidence is queryable; no physical retry is executable."""
from copy import deepcopy
import unittest
from unittest.mock import Mock

from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.exit import (EXIT_STEPS, ExitStep, RedemptionRequest,
                           SimulatedVoucherDesk, exit_step_key)

R = "rcpt-8415-0001"


def historical_desk(step="burn", receipt=R, request="rdm"):
    """Load synthetic old evidence directly, never by executing a retired act."""
    clock = F.ManualClock()
    desk = SimulatedVoucherDesk(clock, "REG_DIRECT")
    key = exit_step_key(step, receipt, request)
    record = {"key": key, "step": step, "receiptId": receipt,
              "account": F.B, "status": "unknown", "effect": "unknown",
              "reference": "historical-observation", "attempt": 1}
    desk._records[key] = dict(record)
    desk._history[key] = [dict(record)]
    return desk, clock, key


class HistoricalVoucherEvidence(unittest.TestCase):
    def test_each_step_records_observed_failure_without_a_new_attempt(self):
        for step in EXIT_STEPS:
            with self.subTest(step=step):
                desk, clock, key = historical_desk(step)
                original = dict(desk.lookup(key))
                clock.advance(1)
                resolved = desk.resolve_unknown(key, "failed")
                for name in ("key", "step", "receiptId", "account", "reference", "attempt"):
                    self.assertEqual(resolved[name], original[name])
                self.assertEqual(resolved["effect"], "not-applied")
                self.assertIn("resolvedAt", resolved)
                self.assertEqual([row["status"] for row in desk.history(key)],
                                 ["unknown", "failed"])
                before = deepcopy((desk._records, desk._history))
                with self.assertRaises(DomainError) as caught:
                    desk.act(key, step, R, F.B)
                self.assertEqual(caught.exception.code, "EX_PHYSICAL_FULFILLMENT_RETIRED")
                self.assertEqual((desk._records, desk._history), before)

    def test_each_step_records_observed_success_without_reexecution(self):
        for step in EXIT_STEPS:
            with self.subTest(step=step):
                desk, _, key = historical_desk(step)
                original = dict(desk.lookup(key))
                resolved = desk.resolve_unknown(key, "done")
                self.assertEqual(resolved["effect"], "applied")
                self.assertEqual(resolved["attempt"], 1)
                self.assertEqual(resolved["reference"], original["reference"])
                self.assertEqual([row["status"] for row in desk.history(key)],
                                 ["unknown", "done"])
                before = deepcopy((desk._records, desk._history))
                for _ in range(2):
                    with self.assertRaises(DomainError) as caught:
                        desk.act(key, step, R, F.B)
                    self.assertEqual(caught.exception.code, "EX_PHYSICAL_FULFILLMENT_RETIRED")
                self.assertEqual((desk._records, desk._history), before)

    def test_all_outcomes_refuse_matching_or_substituted_action_bindings(self):
        for outcome in ("unknown", "done", "failed"):
            desk, _, key = historical_desk()
            if outcome != "unknown":
                desk.resolve_unknown(key, outcome)
            before = deepcopy((desk._records, desk._history))
            for args in ((key, "burn", R, F.B), (key, "burn", "other", F.B),
                         (key, "burn", R, F.C), (key, "voucher-issued", R, F.B),
                         ("other-key", "burn", R, F.B)):
                with self.subTest(outcome=outcome, args=args):
                    with self.assertRaises(DomainError) as caught:
                        desk.act(*args)
                    self.assertEqual(caught.exception.code, "EX_PHYSICAL_FULFILLMENT_RETIRED")
                    self.assertEqual((desk._records, desk._history), before)

    def test_resolution_refuses_missing_keys_invalid_status_and_terminal_rewrite(self):
        desk, _, key = historical_desk()
        before = deepcopy((desk._records, desk._history))
        for requested_key, status, expected in (
                ("missing-key", "done", "EX_VOUCHER_UNKNOWN_KEY"),
                (key, "retry", "EX_VOUCHER_REFUSED")):
            with self.subTest(key=requested_key, status=status):
                with self.assertRaises(DomainError) as caught:
                    desk.resolve_unknown(requested_key, status)
                self.assertEqual(caught.exception.code, expected)
                self.assertEqual((desk._records, desk._history), before)
        desk.resolve_unknown(key, "done")
        terminal = deepcopy((desk._records, desk._history))
        with self.assertRaises(DomainError) as caught:
            desk.resolve_unknown(key, "failed")
        self.assertEqual(caught.exception.code, "EX_VOUCHER_ALREADY_RESOLVED")
        self.assertEqual((desk._records, desk._history), terminal)

    def test_an_unobserved_failed_label_does_not_justify_a_physical_retry(self):
        desk, _, key = historical_desk()
        desk._records[key]["status"] = "failed"
        before = deepcopy((desk._records, desk._history))
        with self.assertRaises(DomainError) as caught:
            desk.act(key, "burn", R, F.B)
        self.assertEqual(caught.exception.code, "EX_PHYSICAL_FULFILLMENT_RETIRED")
        self.assertEqual((desk._records, desk._history), before)
        self.assertEqual(desk.history(key)[0]["status"], "unknown")

    def test_history_snapshots_and_repeated_reads_preserve_original_unknown(self):
        desk, _, key = historical_desk()
        before = deepcopy((desk._records, desk._history))
        copied = desk.history(key)
        copied[0]["status"] = "done"
        for _ in range(3):
            self.assertEqual(desk.lookup(key)["status"], "unknown")
            self.assertEqual(desk.history(key)[0]["status"], "unknown")
        self.assertEqual((desk._records, desk._history), before)

    def test_same_request_on_distinct_receipts_keeps_distinct_observations(self):
        desk, _, first = historical_desk()
        second = exit_step_key("burn", "rcpt-two", "rdm")
        desk._records[second] = dict(desk._records[first], key=second, receiptId="rcpt-two")
        desk._history[second] = [dict(desk._records[second])]
        other = deepcopy((desk._records[second], desk._history[second]))
        self.assertNotEqual(first, second)
        desk.resolve_unknown(first, "failed")
        self.assertEqual((desk._records[second], desk._history[second]), other)
        self.assertEqual(desk.lookup(second)["status"], "unknown")
        self.assertEqual(desk.lookup(first)["attempt"], 1)


class FrozenIntentViews(unittest.TestCase):
    def test_a_rejected_new_physical_request_does_not_freeze_an_existing_match(self):
        ex, _ = F.settled_at_b()
        match, _ = F.funded_hop(
            ex, F.B, F.C, 2, "transfer-bc", "session-b", "session-c", lock=False)
        F.redeem_authorization(ex)
        with self.assertRaises(DomainError) as caught:
            ex.request_redemption(R, F.B, "auth-redeem", "retired-request", F.ALL_CHECKS)
        self.assertEqual(caught.exception.code, "EX_PHYSICAL_FULFILLMENT_RETIRED")
        for intent in ("sell-bc", "buy-bc"):
            self.assertTrue(ex.validate_intent(intent)["executable"])
        self.assertEqual(ex.match_intents("sell-bc", "buy-bc"), match)
        escrow = ex.lock_escrow(match, "escrow-bc")
        ex.execute_transfer(match, "transfer-bc", escrow.escrow_id)
        self.assertEqual(ex.owner_of(R), F.C)
        self.assertEqual(ex.holder_of(R), F.B)

    def test_retained_unknown_legacy_evidence_still_blocks_new_mutations(self):
        ex, clock = F.settled_at_b()
        match, _ = F.funded_hop(
            ex, F.B, F.C, 2, "transfer-bc", "session-b", "session-c", lock=False)
        request = RedemptionRequest("historical-rdm", R, F.B, "old-auth", clock.now)
        ex._exits[R] = {
            "request": request, "state": "blocked", "verifiedChecks": (),
            "steps": (ExitStep("burn", exit_step_key("burn", R, request.request_id),
                               status="blocked", detail=(("outcome", "unknown"),)),)}
        before = deepcopy((ex._legs, ex._escrows, ex._used_nonces, ex._exits, ex._events))
        for intent in ("sell-bc", "buy-bc"):
            view = ex.validate_intent(intent)
            self.assertFalse(view["executable"])
            self.assertIn("EX_TRADE_EXIT_OPEN", view["reasons"])
        with self.assertRaises(DomainError) as caught:
            ex.match_intents("sell-bc", "buy-bc")
        self.assertEqual(caught.exception.code, "EX_MATCH_UNEXECUTABLE")
        for operation in (lambda: ex.lock_escrow(match, "escrow-bc"),
                          lambda: ex.execute_transfer(match, "transfer-bc")):
            with self.assertRaises(DomainError) as caught:
                operation()
            self.assertEqual(caught.exception.code, "EX_TRADE_EXIT_OPEN")
        self.assertEqual((ex._legs, ex._escrows, ex._used_nonces, ex._exits, ex._events), before)

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
