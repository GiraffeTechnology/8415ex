"""Reverse-chain rollback definitions; no real wallet or chain execution."""
from copy import deepcopy
import unittest

from exchange import fixtures as F
from exchange.errors import DomainError
from exchange.exchange_fact_snapshot import encode_exchange_snapshot, decode_exchange_snapshot
from exchange.tests.test_rollback import refused_at_ab, ab_settled_then_c_refused


RECEIPT = "rcpt-8415-0001"


class HopRollbackTests(unittest.TestCase):
    def opened(self, *, prefix=False, **options):
        exchange, clock, requests = (ab_settled_then_c_refused(**options)
                                     if prefix else refused_at_ab(**options))
        refused = 1 if prefix else 0
        state = exchange.begin_rollback(RECEIPT, refused,
                    F.rollback_authority(exchange, refused, "hop-sequence"))
        return exchange, state, clock, requests

    def test_original_reverse_path_and_unique_step_keys_are_explicit(self):
        exchange, state, _, _ = self.opened()
        self.assertEqual([(h["fromAccount"], h["toAccount"]) for h in state["assetHops"]],
                         [(F.D, F.C), (F.C, F.B), (F.B, F.A)])
        self.assertEqual([h["toPosition"] for h in state["assetHops"]], [2, 1, 0])
        self.assertEqual(len({h["key"] for h in state["assetHops"]}), 3)
        self.assertEqual(exchange.asset_control.returns, 0)

    def test_one_hop_per_call_exposes_partial_owner_without_complete(self):
        exchange, state, _, _ = self.opened()
        for cursor, account in enumerate((F.C, F.B, F.A), 1):
            report = exchange.advance_rollback(RECEIPT, max_asset_hops=1)
            self.assertEqual(exchange.owner_of(RECEIPT), account)
            self.assertEqual(report["hopCursor"], cursor)
            self.assertEqual(report["assetControl"]["returned"], cursor == 3)
            self.assertEqual(report["complete"], cursor == 3)
            self.assertEqual(sum(r["status"] == "done" for r in report["hopResults"]), cursor)
        self.assertEqual(exchange.asset_control.returns, 3)
        self.assertEqual(exchange.payments.movements, 3)

    def test_registered_settled_prefix_is_never_a_return_hop(self):
        exchange, state, _, _ = self.opened(prefix=True)
        self.assertEqual([(h["fromAccount"], h["toAccount"]) for h in state["assetHops"]],
                         [(F.D, F.C), (F.C, F.B)])
        report = exchange.advance_rollback(RECEIPT)
        self.assertTrue(report["complete"])
        self.assertEqual(exchange.holder_of(RECEIPT), F.B)
        self.assertEqual(exchange.owner_of(RECEIPT), F.B)
        self.assertEqual(exchange.escrow_for_leg(RECEIPT, 0).status, "released")
        self.assertEqual(exchange.leg(RECEIPT, 0).rollback_status, "detached")

    def test_unknown_hop_blocks_later_hops_and_reconciles_same_key(self):
        exchange, state, _, _ = self.opened()
        key = state["assetHops"][0]["key"]
        exchange.asset_control._outcomes[key] = "unknown"
        first = exchange.advance_rollback(RECEIPT)
        self.assertEqual(first["hopCursor"], 0)
        self.assertFalse(first["complete"])
        self.assertEqual(exchange.owner_of(RECEIPT), F.D)
        self.assertEqual(len(exchange.asset_control._records), 1)
        exchange.advance_rollback(RECEIPT)
        self.assertEqual(len(exchange.asset_control._records), 1)
        exchange.asset_control.resolve_unknown(key, "returned")
        report = exchange.advance_rollback(RECEIPT, max_asset_hops=1)
        self.assertEqual(report["hopCursor"], 1)
        self.assertEqual(exchange.owner_of(RECEIPT), F.C)
        self.assertEqual(len(exchange.asset_control._records), 1)

    def test_failure_after_first_hop_preserves_that_confirmed_cursor(self):
        exchange, state, _, _ = self.opened()
        exchange.asset_control._outcomes[state["assetHops"][1]["key"]] = "failed"
        report = exchange.advance_rollback(RECEIPT)
        self.assertEqual(report["hopCursor"], 1)
        self.assertEqual(exchange.owner_of(RECEIPT), F.C)
        self.assertEqual(report["hopResults"][0]["status"], "done")
        self.assertEqual(report["hopResults"][1]["status"], "blocked")
        self.assertEqual(report["hopResults"][2]["status"], "pending")
        self.assertTrue(exchange.advance_rollback(RECEIPT)["complete"])
        self.assertEqual(exchange.asset_control.returns, 3)
        self.assertEqual(exchange.payments.movements, 3)

    def test_repeated_completed_sequence_has_no_new_refund_or_hop(self):
        exchange, state, _, _ = self.opened()
        first = exchange.advance_rollback(RECEIPT)
        keys = set(exchange.asset_control._records)
        for _ in range(3):
            report = exchange.advance_rollback(RECEIPT)
            self.assertEqual(report["sequenceId"], first["sequenceId"])
            self.assertEqual(report["hopCursor"], 3)
        self.assertEqual(set(exchange.asset_control._records), keys)
        self.assertEqual(exchange.asset_control.returns, 3)
        self.assertEqual(exchange.payments.movements, 3)

    def test_snapshot_keeps_partial_cursor_results_and_unfinished_hops(self):
        exchange, state, _, _ = self.opened()
        exchange.advance_rollback(RECEIPT, max_asset_hops=1)
        facts = decode_exchange_snapshot(encode_exchange_snapshot(exchange))
        restored_facts = facts.domain["_rollbacks"][RECEIPT]
        self.assertEqual(restored_facts["sequenceId"], state["sequenceId"])
        self.assertEqual(restored_facts["hopCursor"], 1)
        self.assertEqual(restored_facts["assetHops"], state["assetHops"])
        self.assertEqual(facts.domain["_returned_to"][RECEIPT], (2, F.C))
        self.assertFalse(facts.complete_recovery)

    def test_wrong_hop_result_binding_does_not_advance_owner_or_cursor(self):
        exchange, state, _, _ = self.opened()
        original = exchange.asset_control.return_asset
        def substituted(*args):
            return dict(original(*args), toAccount=F.A)
        exchange.asset_control.return_asset = substituted
        with self.assertRaises(DomainError) as caught:
            exchange.advance_rollback(RECEIPT)
        self.assertEqual(caught.exception.code, "EX_ROLLBACK_HOP_RESULT_REFUSED")
        self.assertEqual(state["hopCursor"], 0)
        self.assertEqual(exchange.owner_of(RECEIPT), F.D)

    def test_single_return_legacy_state_is_not_resubmitted_as_new_semantics(self):
        exchange, state, _, _ = self.opened()
        del state["assetHops"]
        with self.assertRaises(DomainError) as caught:
            exchange.advance_rollback(RECEIPT)
        self.assertEqual(caught.exception.code, "EX_ROLLBACK_SEQUENCE_MIGRATION_REQUIRED")
        self.assertEqual(exchange.asset_control.returns, 0)

    def test_return_without_original_result_reference_is_not_complete(self):
        exchange, state, _, _ = self.opened()
        original = exchange.asset_control.return_asset
        def missing_reference(*args):
            return dict(original(*args), reference=None)
        exchange.asset_control.return_asset = missing_reference
        with self.assertRaises(DomainError) as caught:
            exchange.advance_rollback(RECEIPT)
        self.assertEqual(caught.exception.code, "EX_ROLLBACK_HOP_RESULT_REFUSED")
        self.assertEqual(state["hopCursor"], 0)

    def test_invalid_per_call_limit_does_not_execute_any_steps(self):
        exchange, state, _, _ = self.opened()
        before = deepcopy(state)
        for invalid in (0, -1, True, "1"):
            with self.subTest(limit=invalid), self.assertRaises(DomainError):
                exchange.advance_rollback(RECEIPT, max_asset_hops=invalid)
        self.assertEqual(state, before)
        self.assertEqual(exchange.payments.movements, 0)
        self.assertEqual(exchange.asset_control.returns, 0)
